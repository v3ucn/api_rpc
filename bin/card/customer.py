# encoding:utf-8

import time
import json
import traceback
import logging
log = logging.getLogger()

from collections import defaultdict

import config
from util import unicode_to_utf8
from constants import DATE_FMT, DATETIME_FMT
from excepts import  ParamError
from base import CODE_STATUS_EXCHANGED, CODE_STATUS_CREATE

from runtime import hids
from utils.valid import is_valid_int
from utils.date_api import str_to_tstamp, tstamp_to_str
from utils.decorator import check
from utils.tools import apcli_ex
from base import CardBase

from qfcommon.base.dbpool import (
    get_connection, get_connection_exception, DBFunc
)
from qfcommon.base.qfresponse import success
from qfcommon.thriftclient.open_user import OpenUser
from qfcommon.base.tools import thrift_callex, thrift_call
from qfcommon.server.client import HttpClient
from qfcommon.web.validator import Field, T_INT, T_STR
from qfcommon.thriftclient.qf_wxmp import QFMP


class List(CardBase):
    '''
    会员活动消费者集点列表
    '''

    _validator_fields = [
        Field('id', T_STR, isnull=False),
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
        Field('order_field', T_STR, default='utime'),
        Field('order_type', T_STR, default='desc'),
    ]

    _base_err = '获取列表失败'

    @check(['login', 'validator'])
    def GET(self):
        data = self.validator.data
        data['order_field'] = data['order_field'] or 'utime'
        data['order_type'] = data['order_type'] or 'desc'

        if data['order_field'] not in ('total_pt', 'cur_pt', 'utime', 'last_exdtm'):
            raise ParamError('参数错误')
        if data['order_type'] not in ('desc', 'asc'):
            raise ParamError('参数错误')

        # 检查活动
        self.check_allow_query(data['id'])

        # 排序, 分页
        data['limit'] = data['pagesize']
        data['offset'] = data['pagesize']*data['page']
        other = (
            'order by {order_field} {order_type} '
            'limit {limit} offset {offset}'.format(**data)
        )

        customers = None
        with get_connection('qf_mchnt') as db:
            customers = db.select('member_pt',
                    where= {'activity_id': data['id']}, other= other)
        if not  customers:
            return self.write(success({'customers': []}))

        # 获取消费信息
        cids = {i['customer_id'] for i in customers}
        try:
            spec = json.dumps({'user_id': list(cids)})
            p = thrift_callex(config.OPENUSER_SERVER, OpenUser,
                    'get_profiles', config.OPENUSER_APPID, spec)
            infos  = {i.user_id:i.__dict__ for i in p}
        except:
            log.warn(traceback.format_exc())
            infos = {}

        # 补全消费者信息
        for i in customers:
            t = infos.get(i['customer_id']) or {}
            i['gender'] = t.get('gender') or 0
            i['avatar'] = t.get('avatar') or config.HJ_AVATAR
            i['nickname'] = t.get('nickname') or '微信支付顾客'

        return self.write(success({'customers': customers}))


class ExchangeList(CardBase):
    '''
    会员活动集点兑换记录
    '''

    _validator_fields = [
        Field('id', T_STR, isnull=False),
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
    ]

    _base_err = '获取集点兑换记录列表失败'

    @check(['login', 'validator'])
    def GET(self):
        data = self.validator.data

        # 检查活动
        self.check_allow_query(data['id'])

        # 排序 分页
        data['limit'] = data['pagesize']
        data['offset'] = data['pagesize']*data['page']
        other = ('order by utime desc limit {limit} '
                 'offset {offset}'.format(**data))

        records = None
        with get_connection('qf_mchnt') as db:
            records = db.select(
                    table= 'exchange_record',
                    where= {
                        'activity_id': data['id'],
                        'status': CODE_STATUS_EXCHANGED
                    },
                    fields='customer_id, utime, code',
                    other= other)
        if not records:
            return self.write(success({'records': []}))

        cids = {i['customer_id'] for i in records}
        spec = json.dumps({'user_id': list(cids)})
        try:
            p = thrift_callex(config.OPENUSER_SERVER,
                    OpenUser, 'get_profiles', config.OPENUSER_APPID, spec)
            infos  = {i.user_id:i.__dict__ for i in p}
        except:
            log.warn(traceback.format_exc())
            infos = {}

        # 处理返回值
        for i in records:
            info = infos.get(i['customer_id']) or {}
            i['avatar'] = info.get('avatar') or config.HJ_AVATAR
            i['gender'] = info.get('gender') or 0
            i['nickname'] = info.get('nickname') or '微信支付顾客'
            i['exchange_time'] = tstamp_to_str(i['utime'], DATETIME_FMT)
            i['code'] = '{:0>4d}'.format(i['code'])

        # 按日期整理结果
        tidy_records = defaultdict(list)
        for i in records:
            t = tstamp_to_str(i['utime'], DATE_FMT)
            tidy_records[t].append(i)

        # 获取头部信息
        last_day = str_to_tstamp(tstamp_to_str(
                records[-1]['utime'], DATE_FMT), DATE_FMT)
        sql = (
            'select FROM_UNIXTIME(utime, "%%Y-%%m-%%d") as date, '
            'count(id) as num from exchange_record '
            'where activity_id=%d and utime>=%s and status=%d '
            'group by FROM_UNIXTIME(utime, "%%Y%%m%%d") order by utime desc'
            % (int(data['id']), last_day, CODE_STATUS_EXCHANGED)
        )
        with get_connection_exception('qf_mchnt') as db:
            diff_days = db.query(sql) or []

        ret = []
        for i in diff_days:
            t = {}
            t['date'] = i['date']
            t['total_num'] = i['num']
            t['records'] = tidy_records.get(i['date']) or []
            ret.append(t)

        return self.write(success({'records': ret}))


class Exchange(CardBase):
    '''
    会员活动集点兑换
    '''

    _base_err = '兑换失败'

    def get_appid(self):
        userid = int(self.user.userid)
        req_userids = [userid]

        groupid = self.get_groupid()
        if groupid:
            req_userids.append(int(groupid))

        big_uid = int(self.get_big_uid())
        if big_uid:
            req_userids.append(int(big_uid))

        # 获取mp_confs
        try:
            mp_confs = thrift_call(
                QFMP, 'batch_mp_query', config.QFMP_SERVERS,
                list(set(req_userids))
            )
        except:
            log.warn(traceback.format_exc())
            mp_confs = {}

        for uid in req_userids:
            if uid in mp_confs and mp_confs[uid]:
                mp_conf = mp_confs[uid][0]
                return mp_conf.appid, mp_conf.hj_appid
        else:
            return config.DEFAULT_APPID, config.OPENUSER_APPID


    def trade_push(self, actv, member, code_info):
        '''推送'''
        customer_id = member['customer_id']
        appid, hj_appid = self.get_appid()
        try:
            p = {}
            p['appid'] = appid
            # 获取openid
            p['openid']= thrift_callex(
                config.OPENUSER_SERVER, OpenUser,
                'get_openids_by_user_ids', hj_appid,
                [customer_id, ]
            )[0]

            # 店铺名
            user = apcli_ex('findUserBriefById', int(self.user.userid))
            p['shopname'] = user.shopname if user else ''
            p['exchange_num'] = member['exchange_num'] + 1
            p['exchange_pt'] = actv['exchange_pt']
            p['obtain_amt'] = actv['obtain_amt']
            p['busicd'] = 'card_actv_exchange'
            p['goods_amt'] = actv['goods_amt']
            p['goods_name'] = actv['goods_name']
            p['code'] = code_info['code']
            p['customer_id'] = hids.encode(customer_id)
            p['activity_id'] = actv['id']
            p['card_id'] = member['id']
            p = {unicode_to_utf8(k):unicode_to_utf8(v) for k, v in p.iteritems()}

            HttpClient(config.TRADE_PUSH_SERVER).post('/push/v2/push', params=p)
        except:
            log.warn('error:%s' % traceback.format_exc())

    def exchange(self, actv, member, code_info):
        now = int(time.time())
        with get_connection_exception('qf_mchnt') as db:
            # 更新会员集点
            db.update('member_pt',
                    values=  {
                        'cur_pt': DBFunc('cur_pt-%d'%actv['exchange_pt']),
                        'exchange_num': DBFunc('exchange_num+1'),
                        'last_exdtm': now, 'utime':now
                    },
                    where= {'id': member['id']})

            # 更新exchange_record
            db.update('exchange_record',
                    values= {
                        'status': CODE_STATUS_EXCHANGED,
                        'utime': now,
                        'userid': self.user.userid
                    },
                    where= {'id': code_info['id']})

            # 更新card_actv表
            db.update('card_actv',
                    values= {
                        'exchange_num': DBFunc('exchange_num+1'),
                        'utime': now
                    },
                    where= {'id': actv['id']})

    @check('ip_or_login')
    def POST(self):
        params = self.req.inputjson()
        code = params.get('code')
        if code.startswith(self.pre_code):
            encode = code[len(self.pre_code):]
            code, actv_id, code_id = hids.decode(encode)
            code = '{:0>4d}'.format(code)
        else:
            actv_id = params.get('id')
            if not is_valid_int(actv_id):
                raise ParamError('活动不存在')
            actv_id = int(actv_id)

        # 检查活动
        actv = self.check_allow_query(actv_id)

        # 检查兑换码
        if (not is_valid_int(code) or
            len(code) != 4 or not int(code)):
            raise ParamError('兑换码错误,请确认')

        with get_connection_exception('qf_mchnt') as db:
            # 获取兑换码信息
            records = db.select('exchange_record',
                    where = {'activity_id': actv_id, 'code': int(code)})
            if not records:
                raise ParamError('兑换码错误，请确认')

            # 查看兑换码的状态
            codes = {}
            for i in records:
                codes[i['status']] = i
            if codes.get(CODE_STATUS_CREATE):
                code_info = codes[CODE_STATUS_CREATE]
                cid = code_info['customer_id']
            elif codes.get(CODE_STATUS_EXCHANGED):
                raise ParamError('兑换失败，此码不可重复使用')
            else:
                raise ParamError('兑换码错误，请确认')

            # 查询消费者信息
            member = db.select_one('member_pt',
                    where= {'activity_id': actv_id, 'customer_id':cid})
            if not member:
                raise ParamError('消费者不存在')

            if actv['exchange_pt'] > member['cur_pt']:
                raise ParamError('兑换码信息错误')

        # 更新兑换信息
        self.exchange(actv, member, code_info)

        # 推送
        self.trade_push(actv, member, code_info)

        return self.write(success({}))
