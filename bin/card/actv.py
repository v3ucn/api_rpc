# encoding:utf-8

import time
import logging
log = logging.getLogger()

import config
from constants import (
    DATE_FMT, DATETIME_FMT, MCHNT_STATUS_FREE, MCHNT_STATUS_NORMAL,
    DT_FMT, DTM_FMT
)
from .base import (
    ACTV_STATUS, ACTV_STATUS_ALL, ACTV_STATUS_NORMAL, ACTV_STAUS_STOPED,
    ACTV_STATE, ACTV_STATE_ALL, ACTV_STATE_ON, ACTV_STATE_OFF,
)

from utils.date_api import str_to_tstamp, str_diffdays
from utils.valid import is_valid_int, is_valid_date
from utils.payinfo import get_payinfo_ex, add_free_ex
from utils.qdconf_api import get_qd_conf_value
from utils.tools import getid, remove_emoji, str_len
from utils.decorator import check
from base import CardBase

from excepts import ParamError

from qfcommon.base.dbpool import (
    get_connection, get_connection_exception
)
from qfcommon.base.qfresponse import success
from qfcommon.web.validator import Field, T_INT, T_STR

paying_goods = config.PAYING_GOODS

class Create(CardBase):
    '''
    创建会员集点活动
    '''

    _validator_fields = [
        Field('goods_name', T_STR, isnull=False),
        Field('goods_amt', T_INT, default=0),
        Field('start_time', T_STR),
        Field('expire_time', T_STR),
        Field('exchange_pt', T_INT, default=0),
        Field('obtain_amt', T_INT, default=0),
        Field('obtain_limit', T_INT, default=1),
    ]

    _base_err = '创建集点活动失败'

    def allow_create(self, userid):
        cate = self.get_cate()
        # 大商户允许创建多个集点活动
        if cate == 'bigmerchant':
            return True

        with get_connection_exception('qf_mchnt') as db:
            num = db.select_one('card_actv',
                    where= {
                        'expire_time': ('>', int(time.time())),
                        'userid': self.get_userid_condition(),
                    },
                    fields='count(1) as num')['num']
            if num:
                raise ParamError('已经有进行中的活动')

    @check(['ip_or_login', 'check_perm', 'user_lock', 'validator'])
    def POST(self):
        userid = int(self.user.userid)

        # 商户付费状态
        groupid = self.get_groupid()
        mchnt = get_payinfo_ex(userid,
                service_code='card_actv', groupid=groupid)
        if not mchnt:
            add_free_ex(userid, service_code='card_actv', groupid=groupid)
        elif str(mchnt['expire_time']) <= time.strftime(DATETIME_FMT):
            if mchnt['status'] == MCHNT_STATUS_FREE:
                raise ParamError('免费体验已经到期了哦')
            if mchnt['status'] == MCHNT_STATUS_NORMAL:
                raise ParamError('付费已经到期了哦')

        # 能否创建集点活动
        self.allow_create(userid)

        actv = self.validator.data

        # 适用门店
        d = self.req.input()
        actv['mchnt_id_list'] = self.get_mchnt_id_list(
                d.get('mchnt_id_list', '').strip().split(','))
        actv['userid'] = userid
        actv['goods_name'] = remove_emoji(actv.get('goods_name'))
        if not 1 <= str_len(actv['goods_name']) <= 8:
            raise ParamError('商品名长度是1至8位')

        if actv['goods_amt'] <= 0:
            raise ParamError('商品价格应大于0')

        actv['start_time'] = actv.get('start_time') or time.strftime(DT_FMT)
        if not(is_valid_date(actv['start_time']) and
               is_valid_date(actv['expire_time'])):
            raise ParamError('活动时间格式不合法')
        if actv['start_time'] > actv['expire_time']:
            raise ParamError('开始时间应该小于结束时间')
        actv['start_time'] = str_to_tstamp(actv['start_time'], DT_FMT)
        actv['expire_time'] = str_to_tstamp(actv['expire_time'], DT_FMT) + 86399

        if actv['exchange_pt'] not in range(1, 11):
            raise ParamError('暂不只支持该兑换集点的活动')

        if actv['obtain_amt'] <= 0:
            raise ParamError('集点条件大于0')

        if actv['obtain_limit'] < 0:
            raise ParamError('一次交易获取的最多集点应该大于0')

        actv['id'] = getid()
        actv['ctime'] = actv['utime'] = int(time.time())
        actv['status'] = ACTV_STATUS_NORMAL

        with get_connection_exception('qf_mchnt') as db:
            db.insert('card_actv', actv)

        return self.write(success({'id': actv['id']}))


class Change(CardBase):
    '''
    修改会员集点活动
    '''

    _base_err = '修改活动失败'

    @check(['ip_or_login', 'check_perm', 'user_lock'])
    def POST(self):
        d = self.req.inputjson()
        userid = self.user.userid

        # 付费过期不能修改活动
        mchnt = get_payinfo_ex(
            userid, service_code='card_actv',
            groupid=self.get_groupid())
        if str(mchnt.get('expire_time')) < time.strftime(DATETIME_FMT):
            raise ParamError('付费已经到期了哦')

        # 获取活动信息
        self.check_allow_change(d.get('id'))

        update_value = {}
        # 活动开始截止时间
        for field in ('start_time', 'expire_time'):
            if d.get(field):
                if not is_valid_date(d[field]):
                    raise ParamError('时间格式错误')
                if field == 'start_time':
                    update_value[field] = str_to_tstamp(d[field], DT_FMT)
                else:
                    update_value[field] = str_to_tstamp(d[field], DT_FMT)+86399

        for field in ('obtain_amt', 'obtain_limit', 'goods_amt'):
            if d.get(field) and not is_valid_int(d[field]):
                raise ParamError('数据格式错误')

        # 修改活动状态
        if is_valid_int(d.get('status')):
            if int(d['status']) in (ACTV_STATUS_NORMAL, ACTV_STAUS_STOPED):
                update_value['status'] = int(d['status'])

            # 结束申明
            if int(d['status']) == ACTV_STAUS_STOPED and d.get('statement'):
                if d.get('statement'):
                    statement = remove_emoji(d['statement'])
                    if not 1 <= str_len(statement) <= 150:
                        raise ParamError('停止活动声明应该是1至150位')
                    update_value['statement'] = statement

        # 集点条件
        if d.get('obtain_amt'):
            if d['obtain_amt'] < 0:
                raise ParamError('集点条件大于0元')
            update_value['obtain_amt'] = d['obtain_amt']

        # 集点限制
        if d.get('obtain_limit'):
            if d['obtain_limit'] < 0:
                raise ParamError('集点条件大于0元')
            update_value['obtain_limit'] = d['obtain_limit']

        # 奖品名称
        if d.get('goods_name'):
            d['goods_name'] = remove_emoji(d['goods_name'])
            if not 1 <= str_len(d['goods_name']) <= 8:
                raise ParamError('商品名长度是1至8位')
            update_value['goods_name'] = d['goods_name']

        # 奖品金额
        if d.get('goods_amt'):
            if d['goods_amt'] <= 0:
                raise ParamError('商品价格应大于0')
            update_value['goods_amt'] = d['goods_amt']

        # 参与商户
        if 'mchnt_id_list' in d:
            update_value['mchnt_id_list'] = self.get_mchnt_id_list(
                    d['mchnt_id_list'].strip().split(','), int(d['id']))

        if update_value:
            update_value['utime'] = int(time.time())
            with get_connection_exception('qf_mchnt') as db:
                db.update('card_actv', update_value, {'id': d['id']})

        return self.write(success({'id': d['id']}))


class Close(CardBase):
    '''
    关闭会员集点活动
    '''

    _base_err = '修改活动失败'

    @check(['login', 'check_perm', 'user_lock'])
    def POST(self):
        d = self.req.inputjson()

        actv = self.check_allow_change(d.get('id'))

        update_value = {
            'utime': int(time.time()),
            'status': ACTV_STAUS_STOPED,
        }

        # 结束申明
        if d.get('statement'):
            statement = remove_emoji(d['statement'])
            if not 1 <= str_len(statement) <= 150:
                raise ParamError('停止活动声明应该是1至150位')
            update_value['statement'] = statement

        # 结束时间
        if d.get('expire_time'):
            expire_time = d.get('expire_time')
            if not is_valid_date(expire_time):
                raise ParamError('截止日期时间格式不对')
            if expire_time > str(actv['expire_time']):
                raise ParamError('只能缩短活动截止日期')

            # 活动结束时间小于当前时间
            if expire_time < time.strftime(DT_FMT):
                update_value['expire_time'] = int(time.time() - 600)
            else:
                update_value['expire_time'] = str_to_tstamp(
                        expire_time, DT_FMT) + 86399
        else:
            update_value['expire_time'] = int(time.time() - 600)

        with get_connection_exception('qf_mchnt') as db:
            db.update('card_actv', update_value, {'id': d['id']})

        return success({})


class Index(CardBase):
    '''
    会员集点活动首页
    返回商户创建的会员活动的列表以及商户的付费情况
    '''

    _base_err = '获取会员活动首页数据失败'

    def mchnt_info(self, userid):
        '''商户付费情况'''
        r = get_payinfo_ex(
            userid, service_code='card_actv',
            groupid= self.get_groupid()
        ) or {'status': 0, 'expire_time': ''}

        left_day, free_warn = (0, 1)
        if r['expire_time']:
            left_day = max(str_diffdays(time.strftime(DATE_FMT),
                                        str(r['expire_time'])[:10]), 0)
            free_warn = 0 if left_day > 5 else 1
        r['free_left_day'] = left_day
        r['free_left_warn'] = free_warn
        r['free'] = paying_goods['free']
        return r

    @check('login')
    def GET(self):
        userid = int(self.user.userid)

        r = {}
        r['mchnt_info'] = self.mchnt_info(userid)
        r['now'] = time.strftime(DTM_FMT)

        # 活动信息
        actv = total_num = None
        with get_connection('qf_mchnt') as db:
            where = {'userid': self.get_userid_condition()}
            actv = db.select_one('card_actv',
                    fields= (
                        'id, start_time, expire_time, exchange_num, '
                        'total_pt, status, goods_amt, goods_name, '
                        'obtain_amt, exchange_pt, obtain_limit'
                    ),
                    where= where,
                    other= 'order by expire_time desc')
            if actv:
                total_num = db.select_one('card_actv',
                        where= where,
                        fields= 'count(1) as num',
                        )['num']

                # 更新customers 和 customer_num
                actv.update(self.get_customers(actv))

                actv['id'] = str(actv['id'])
                actv['state'] = self.get_state(str(actv['expire_time']))
                actv['left_day'] = max(str_diffdays(
                    time.strftime(DATE_FMT), str(actv['expire_time'])[:10]), 0)
                actv['left_warn'] = 0 if actv['left_day'] > 5 else 1
                actv['promotion_url'] =  get_qd_conf_value(userid, 'card')
                actv['lost_customer_num'] = 0
                if str(r['mchnt_info']['expire_time']) < time.strftime(DTM_FMT):
                    actv['lost_customer_num'] = db.select_one('member',
                            where= {'userid': userid},
                            fields= 'count(1) as num')['num']

        r['actv_info'] = actv or {}
        r['total_num'] = total_num or 0
        r['max_expire_day'] = config.CARD_ACTV_MAX_EXPIRE
        r['max_start_day'] = config.CARD_ACTV_MAX_START

        return self.write(success(r))


class List(CardBase):
    '''
    会员集点活动列表
    '''

    _base_err = '获取活动列表失败'

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.inputjson().iteritems()}
        r = {}
        # 活动状态
        r['state'] = int(d.get('state') or ACTV_STATE_ALL)
        r['status'] = int(d.get('status') or ACTV_STATUS_ALL)
        if r['state'] not in ACTV_STATE:
            raise ParamError('查询状态不存在')
        if r['status'] not in ACTV_STATUS:
            raise ParamError('查询状态不存在')

        # 分页信息
        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息不正确')
        r['offset'], r['limit'] = int(page) * int(pagesize), int(pagesize)

        return r

    def _actv_list(self, d):
        def _get_where():
            now = int(time.time())

            r = {'userid': self.get_userid_condition()}

            if d['status'] in (ACTV_STATUS_NORMAL, ACTV_STAUS_STOPED):
                r['status'] = d['status']

            if d['state'] == ACTV_STATE_ON:
                r['expire_time'] = ('>=', now)
            elif d['state'] == ACTV_STATE_OFF:
                r['expire_time'] = ('<', now)

            return r

        def _get_customer_num(ids):
            if not ids:
                return {}
            with get_connection_exception('qf_mchnt') as db:
                r = db.select('member_pt',
                        fields= 'activity_id, count(*) as num',
                        where= {
                            'activity_id': ('in', ids)
                        },
                        other='group by activity_id') or []
            return {i['activity_id']:i['num'] for i in r or []}

        where = _get_where()
        with get_connection_exception('qf_mchnt') as db:
            actvs = db.select(
                    table = 'card_actv',
                    fields = (
                        'id, start_time, expire_time, exchange_num, '
                        'total_pt, status, goods_amt, goods_name, '
                        'obtain_amt, obtain_limit, exchange_pt'
                    ),
                    where = where,
                    other = 'order by ctime desc limit {} offset {}'.format(
                                    d['limit'], d['offset']))
            total_num = db.select_one('card_actv',
                    where=where, fields='count(1) as num')['num']

        ids = [i['id'] for i in actvs or []]
        customer_num = _get_customer_num(ids)
        userid = self.user.userid
        promotion_url = get_qd_conf_value(userid,
                'card', groupid=self.get_groupid())
        for i in actvs:
            i['customer_num'] = customer_num.get(i['id']) or 0
            i['id'] = str(i['id'])
            i['state'] = self.get_state(str(i['expire_time']))
            i['promotion_url'] = promotion_url

        return (actvs, total_num)

    @check('ip_or_login')
    def GET(self):
        d = self._trans_input()
        r, total_num = self._actv_list(d)

        return self.write(success({
            'now': time.strftime(DATETIME_FMT),
            'total_num': total_num,
            'activities': r
        }))


class Info(CardBase):
    '''
    会员集点活动详细信息
    '''

    _validator_fields = [
        Field('id', T_INT, isnull=False),
    ]

    _base_err = '获取活动信息失败'

    @check(['ip_or_login', 'validator'])
    def GET(self):
        actv = self.check_allow_query(self.validator.data['id'])

        fields = [
            'id', 'start_time', 'expire_time', 'exchange_num', 'total_pt',
            'status', 'goods_amt', 'goods_name', 'obtain_amt', 'obtain_limit',
            'exchange_pt', 'statement', 'mchnt_id_list'
        ]
        actv_info = {field:actv[field] for field in fields}
        actv_info['id'] = str(actv_info['id'])
        actv_info['state'] = self.get_state(str(actv_info['expire_time']))
        actv_info['big_create'] = int(actv['userid'] != int(self.user.userid))
        actv['promotion_url'] = get_qd_conf_value(
            self.user.userid, 'card', groupid=self.get_groupid()
        )
        actv_info.update(self.get_customers(actv))

        return success(actv_info)
