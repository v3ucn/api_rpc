# encoding:utf-8

import time
import logging
log = logging.getLogger()

import config
import json
import traceback
from util import prelogin_lock, postlogin_lock
from recharge.base import RechargeUtil, ORDER_STATUS
from utils.date_api import get_day_begin_ts
from constants import (
    DATE_FMT, DATETIME_FMT, MCHNT_STATUS_FREE, MCHNT_STATUS_NORMAL,
    DT_FMT, DTM_FMT
)
from card.base import (
    ACTV_STATUS, ACTV_STATUS_ALL, ACTV_STATUS_NORMAL, ACTV_STAUS_STOPED,
    ACTV_STATE, ACTV_STATE_ALL, ACTV_STATE_ON, ACTV_STATE_OFF,
)
from coupon.base import (
    CouponUtil, ACTIVITY_SRC, ACTIVITY_TYPE_PAYMENT,
    COUPON_RULE_STATUS_CLOSE, ACTIVITY_SHARE_TYPE_COUPON
)

from utils.valid import is_valid_int, is_valid_date
from utils.tools import getid
from decorator import check_login, check_login_ex, raise_excp, check_ip

from qfcommon.server.client import HttpClient
from excepts import (
    MchntException, ParamError, ThirdError
)

from excepts import ParamError

from qfcommon.base.dbpool import (
    get_connection_exception, get_connection, DBFunc
)

paying_goods = config.PAYING_GOODS
from utils.base import BaseHandler
from utils.tools import apcli_ex
from utils.date_api import (
    str_to_tstamp, tstamp_to_str, future
)
from qfcommon.qfpay.presmsclient import PreSms
from qfcommon.base.qfresponse import QFRET, error, success
from utils.qdconf_api import get_qd_conf_value
from utils.tools import unicode_to_utf8



class InfoMessages(BaseHandler):
    '''
    创建短信详细信息
    '''

    _base_err = '获取短信营销内容失败'

    def get_userid_condition(self, userid=None):
        ''' 获取查询条件
        查询大商户和自己创建的并参与的集点活动
        '''
        req_userid = userid
        userid = userid or int(self.user.userid)

        big_uid = self.get_big_uid(req_userid)
        userid_condition = userid
        if big_uid:
            userid_condition =  (' in ',
                DBFunc('({uid}, {big_uid}) and locate(\'"{uid}"\', '
                'mchnt_id_list)'.format(uid=userid, big_uid=big_uid)))

        return userid_condition

    def get_big_actvids(self):
        '''
        获取大商户自己创建的红包活动id
        '''
        big_uid = self.get_big_uid()
        if not big_uid:
            return []
        actvids = actvs = None
        userid = self.user.userid
        with get_connection('qf_marketing') as db:
            actvs = db.select_join(
                    table1='activity a', table2='activity_mchnt am',
                    on={'a.id': 'am.activity_id'},
                    where={
                        'a.create_mchnt_id': str(big_uid),
                        'a.type':  ACTIVITY_TYPE_PAYMENT,
                        'a.status': 2,
                        'a.mchnt_id': DBFunc('0 and locate(\'"{}"\', '
                                'am.mchnt_id_list)'.format(userid))
                    },
                    fields='a.id')
            actvids = [actv['id'] for actv in actvs]

        self._bigids = actvids or []
        return actvids

    def coupon_actvs(self, userid):
        '''
        获取活动列表
        '''
        def get_where():
            now = int(time.time())

            big_actvids = self.get_big_actvids()
            where = '(create_mchnt_id={userid} {bigids}) '.format(
                    userid=userid,
                    bigids=('' if not big_actvids else
                        ' or id in ({})'.format(
                            ','.join(str(int(i))for i in big_actvids))
                    ))
            where += ('and src="{src}" and type={type} '.format(
                    src=ACTIVITY_SRC, type=ACTIVITY_TYPE_PAYMENT))
            # 启用的
            where += ('and expire_time>{now} and start_time<={now} and status=2 and '
                          'used_amt<total_amt'.format(now=now))
            return where

        actvs = None
        with get_connection('qf_marketing') as db:
            sql = ('select {fields} from activity where {where} '
                   'order by create_time desc '.format(
                    fields=(
                            'id, mchnt_id, type, title, total_amt, '
                            'obtain_xx_id, obtain_num, sponsor_award_num, '
                            'sponsor_xx_id, rule, start_time, expire_time, '
                            'create_time, create_mchnt_id'
                        ),
                        where=get_where(),
                    ))
            actvs = db.query(sql)

        if not actvs:
            return []

        cids = {i['sponsor_xx_id'] or i['obtain_xx_id'] for i in actvs}
        coupons = []
        if cids:
            if cids:
                cps = None
                with get_connection('qf_marketing') as db:
                    cps = db.select(
                            table='coupon_rule',
                            fields='id, amt_max, amt_min',
                            where={'id': ('in', cids)})
                for cp in cps:
                    coupons.append(cp['amt_max'])
        return coupons

    def card_actv(self):
        '''
        获取大商户和自己创建的集点活动
        '''
        def _get_where():
            now = int(time.time())
            r = {'userid': self.get_userid_condition(), 'status': ACTV_STATUS_NORMAL}
            r["expire_time"] = (">", now)
            r['start_time'] = ('<=', now)

            return r

        where = _get_where()
        with get_connection_exception('qf_mchnt') as db:
            actvs = db.select_one(
                    table='card_actv',
                    fields=(
                        'id, start_time, expire_time, exchange_num, '
                        'total_pt, status, goods_amt, goods_name, '
                        'obtain_amt, obtain_limit, exchange_pt'
                    ),
                    where = where,
                    other = 'order by ctime desc')

        return actvs

    def prepaid_actv(self):
        '''
        获取储值活动
        '''
        params = {}
        params['status'] = '1'
        params['pos'] = 0
        params['count'] = 10
        params['activity_status'] = '1'
        merchant_path = '/prepaid/v1/api/b/activity_detail'
        try:
            client = HttpClient(config.PREPAID_SERVERS)
            ret = json.loads(getattr(client, 'get')(
                merchant_path,
                headers={
                    'COOKIE': 'sessionid={}'.format(
                            self.get_cookie('sessionid'))
                }
            ))
            if ret['respcd'] == "0000":
                rules = ret.get('data', {}).get('rules', [])
                if rules:
                    mchnts_sorted = sorted(rules, key=lambda x: (x['present_amt']), reverse=True)
                    result = mchnts_sorted[0].get('present_amt', 0)
                    return result
        except:
            log.warn(traceback.format_exc())
            return 0
            # raise ThirdError('服务繁忙')

    @check_login
    def GET(self):
        userid = int(self.user.userid)
        price = get_qd_conf_value(mode='msg_price', key='ext',
                                       groupid=self.get_groupid())
        template = config.MESSAGE_TEMPLATE
        user = apcli_ex('findUserBriefById', userid)
        log.info(user)
        shopname = user.shopname if user else ''
        log.info(shopname)
        coupon = self.coupon_actvs(userid)
        card = self.card_actv()
        prepaid = self.prepaid_actv()
        vip_template = []
        common_temp = []
        if coupon:
            coupon_content = template['coupon'].format(max(coupon)/100.0, shopname)
            vip_template.append({'title': '红包模板', 'content': coupon_content, 'type': 1})
        if card:
            exchange_pt = unicode_to_utf8(card.get('exchange_pt', ''))
            goods_name = unicode_to_utf8(card.get('goods_name', ''))
            card_content = template['card'].format(exchange_pt, goods_name, shopname)
            vip_template.append({'content': card_content, 'title': '集点模板', 'type': 2})
        if prepaid:
            card_content = template['prepaid'].format(prepaid/100.0, shopname)
            vip_template.append({'content': card_content, 'title': '储值模板', 'type': 3})
        for i in template['common_template']:
            content = i['content'].format(shopname)
            title = i['title']
            common_temp.append({'title': title, 'content': content, 'type': i['type']})

        with get_connection('qf_mchnt') as db:
            total = db.select_one(
                        'member_tag',
                        where= {
                            'userid': userid,
                            'submit': ('>=', 1)
                        },
                        fields='count(1) as num')['num']

        return self.write(success({
            'now': time.strftime(DATETIME_FMT),
            'vip_temp': vip_template,
            'common_temp': common_temp,
            'price': price if price else config.DEFAULT_PRICE,
            'total_auth': total,
            'send_total': total,
            'items': config.ITEM_1 if total else config.ITEM_0

        }))


class Create(BaseHandler):
    '''
    创建订单
    返回qt2需要的支付参数
    '''

    def _trans_input(self):
        d = {k: v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        price = d.get('price', 10)
        num = d.get('num', 0)
        type = d.get('type', 1)
        content = d.get('content', '')
        title = d.get('title', '')
        if not all(map(is_valid_int, (price, num, type))):
            raise ParamError('参数不正确')
        r['price_code'] = ''
        r['promo_code'] = ''
        r['goods_code'] = 'message'
        r['userid'] = int(self.user.ses.get('userid', ''))

        # 商品价格和名称
        total = int(price) * int(num)
        r['total_amt'] = r['txamt'] = total
        r['goods_name'] = '短信营销'
        r['price'] = price
        r['num'] = num
        r['type'] = type
        r['content'] = content
        r['id'] = getid()
        r['title'] = title

        return r

    def _create_order(self, d):
        # 订单信息
        fields = ('id', 'userid', 'goods_code', 'txamt', 'total_amt', 'price_code', 'promo_code', 'goods_name')
        order = {i: d[i] for i in fields}
        order['out_sn'] = 0
        order['ext'] = order['promo_code'][:2]
        order['promo_code'] = order['promo_code'][2:]
        order['status'] = ORDER_STATUS['undo']
        order['ctime'] = order['utime'] = int(time.time())
        # 插入paying_order
        with get_connection('qf_mchnt') as db:
            db.insert('paying_order', order)

        # 返回值
        r = {}
        r['goods_name'] = d['goods_name']
        r['txamt'] = d['txamt']
        r['txcurrcd'] = 'CNY'
        r['txdtm'] = time.strftime(DATETIME_FMT)
        r['out_trade_no'] = order['id']
        r['udid'] = 'mchnt_api'
        r['appcode'] = config.QT2_APP_CODE
        r['sign'] = RechargeUtil.make_sign(r)
        return r

    def _create_message(self, d):
        # 订单信息
        fields = ('id', 'userid', 'type', 'content', 'price', 'num', 'title')
        message = {i: d[i] for i in fields}
        message['out_sn'] = 0
        message['ext'] = ''
        message['status'] = 0
        message['ctime'] = message['utime'] = int(time.time())
        # 插入messages
        with get_connection('qf_mchnt') as db:
            db.insert('messages', message)

    @check_login_ex(prelogin_lock, postlogin_lock)
    @raise_excp('下单失败')
    def POST(self):
        # 转化input参数
        userid = int(self.user.userid)
        d = self._trans_input()
        td_start = get_day_begin_ts()
        now = int(time.time())
        where = {
            'userid': userid,
            'status': 1,
            'type': int(d['type'])
        }
        where['ctime'] = 'between', (td_start, now)
        with get_connection_exception('qf_mchnt') as db:
            messages = db.select(table='messages', where=where)
        if messages:
            raise ParamError('同一活动模板一天只能发送一次哦，避免过度打扰会员明天再试吧~')
        # 创建订单
        self._create_message(d)
        r = self._create_order(d)

        return self.write(success(r))


class List(BaseHandler):
    '''
    短信列表查询
    '''

    def _trans_input(self):
        d = {k: v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        # 分页信息
        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息不正确')
        r['offset'], r['limit'] = int(page) * int(pagesize), int(pagesize)

        return r

    @check_login
    @raise_excp('查询短信列表失败')
    def GET(self):
        # 转化input参数
        d = self._trans_input()
        userid = int(self.user.userid)
        where = {
            'userid': userid,
            'status': 1,
        }
        other = 'order by ctime desc limit %s offset %s' % (d['limit'], d['offset'])
        results = []
        with get_connection_exception('qf_mchnt') as db:
            messages = db.select(table='messages', where=where, other=other)
        for message in messages:
            tmp = {'time': tstamp_to_str(message['utime'], DATETIME_FMT)}
            tmp['content'] = message['content']
            tmp['num'] = message['num']
            tmp['txamt'] = message['price'] * message['num']
            tmp['status'] = message['status']
            tmp['type'] = message['type']
            tmp['title'] = message['title']
            results.append(tmp)

        return self.write(success(results))


class MessageQuestionHandler(BaseHandler):
    '''
    短信营销说明
    '''

    @check_login
    def GET(self):
        return self.write(success(config.MESSAGE_QUESTIONS))


class VOICEBROADHandler(BaseHandler):
    '''
    语音播报锦囊
    '''

    def GET(self):
        return self.write(success({'android': config.VOICE_BROADCAST_ANDROID, 'ios': config.VOICE_BROADCAST_IOS}))