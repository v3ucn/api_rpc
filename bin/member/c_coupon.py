# coding:utf-8

'''
会员中心 - 红包相关接口
'''

import json
import config
import time
import datetime
import logging
import traceback

from base import MemBase
from constants import DT_FMT

from utils.decorator import check
from utils.valid import is_valid_int
from utils.tools import userid_cache, apcli_ex
from utils.date_api import future, str_diffdays

from qfcommon.base.qfresponse import success
from qfcommon.base.dbpool import get_connection, get_connection_exception

log = logging.getLogger()

def get_use_amt(use_rule):
    '''获取使用门槛金额'''
    try:
        rule = json.loads(use_rule)['rule']
        return dict((i[0], i[2]) for i in rule)['amt']
    except:
        log.warn(traceback.format_exc())

    return 0

def get_coupon_type(actv_type):
    # 只有关注送送商品兑换券是商品劵
    if actv_type == 6:
        return 2
    else:
        return 1

class List(MemBase):
    '''红包列表'''

    _base_err = '获取红包列表失败'

    def get_query_userids(self, params):
        if is_valid_int(params.get('userid')):
            return [int(params['userid']), ]

        groupid = self.get_query_groupid(params)
        if groupid:
            return userid_cache[groupid] or []

        return None

    def get_where(self):
        params = self.req.input()

        customer_id = self.get_cid()

        where = {'cb.customer_id' : str(customer_id)}

        now = int(time.time())
        userids = self.get_query_userids(params)
        if userids is not None:
            where['cb.mchnt_id'] = ('in', map(str, userids))

        # 红包是否过期 1未过期 2过期
        is_expire= params.get('is_expire', '1')
        if is_expire == '1':
            where['cb.expire_time'] = ('>', now)
        elif is_expire == '2':
            where['cb.expire_time'] = ('<', now)

        # 查询模式
        mode = params.get('mode', 'exclude_expire')
        # 查询将要过期红包
        if mode == 'expire':
            limit_days = getattr(config, 'COUPON_LIMIT_DAY', 7)
            expire_time = future(
                datetime.date.today(), days=limit_days, fmt_type='timestamp'
            )
            where['`cb.expire_time`'] = ('<', expire_time)

        # 排除将要过期红包
        elif mode == 'exclude_expire':
            limit_days = getattr(config, 'COUPON_LIMIT_DAY', 7)
            expire_time = future(
                datetime.date.today(), days=limit_days, fmt_type='timestamp'
            )
            where['`cb.expire_time`'] = ('>=', expire_time)

        # 状态  0:全部 1:未使用 2:已使用 3:作废
        state = params.get('state', '1')
        if state == '1':
            where['cb.status'] = ('in', (1, 2))
        elif state == '2':
            where['cb.status'] = 3
        elif state == '3':
            where['cb.status'] = 4

        return where

    def gen_ret(self, coupons):
        '''整理输出'''
        if not coupons: return []

        cr_ids = [i['coupon_rule_id'] for i in coupons if not i['use_mchnt_id']]
        use_mchnt_dict = {}
        if cr_ids:
            with get_connection('qf_marketing') as db:
                use_mchnts = db.select(
                    'coupon_rule_mchnt',
                    where = {'coupon_rule_id' : ('in', cr_ids)},
                    fields = 'coupon_rule_id,  mchnt_id_list'
                )
                for i in use_mchnts:
                    try:
                        t = json.loads(i['mchnt_id_list'])
                        if t:
                            use_mchnt_dict[i['coupon_rule_id']] = (len(t), t[0])
                    except:
                        log.warn(traceback.format_exc())

        # 需要查询店铺信息
        mchnt_ids = [
            coupon['use_mchnt_id']
            for coupon in coupons if coupon['use_mchnt_id']
        ]
        for mode, userid in use_mchnt_dict.values():
            if mode == 1:
                mchnt_ids.append(userid)

        users = {}
        if mchnt_ids:
            users = apcli_ex(
                'findUserBriefsByIds', list({int(i) for i in mchnt_ids})
            )
            users = {user.uid:user.__dict__ for user in users or []}

        today = time.strftime(DT_FMT)
        for coupon in coupons:
            use_rule = coupon.pop('use_rule', '')
            coupon_rule_id = coupon.pop('coupon_rule_id', '')
            create_mchnt_id = coupon.pop('create_mchnt_id', '')

            coupon['id'] = str(coupon['id'])
            coupon['use_amt'] =  get_use_amt(use_rule)

            if create_mchnt_id:
                coupon['platform'] = 0
            else:
                coupon['platform'] = 1

            userid = None
            if coupon['use_mchnt_id']:
                userid = int(coupon['use_mchnt_id'])

            elif coupon_rule_id in use_mchnt_dict:
                multi, u_userid = use_mchnt_dict[coupon_rule_id]
                if multi == 1:
                    userid = int(u_userid)
                else:
                    coupon['multi'] = multi

            else:
                coupon['multi'] = 1

            if userid:
                coupon['multi'] = 0
                user = users.get(int(userid), {})
                coupon['addr'] = user.get('address', '')
                coupon['shopname'] = user.get('shopname', '')
            coupon['coupon_type'] = get_coupon_type(coupon['type'])
            try:
                coupon['expire_day'] = str_diffdays(
                    today, str(coupon['expire_time'])[:10]
                ) + 1
            except:
                coupon['expire_day'] = 0

        return coupons

    @check()
    def GET(self):
        other = self.get_other(
            fields=['create_time', 'expire_time'], default_field='cb.create_time',
            default_type='desc'
        )
        where = self.get_where()

        with get_connection_exception('qf_marketing') as db:
            coupons = db.select_join(
                'activity a', 'coupon_bind cb',
                on = {'a.id' : 'cb.activity_id'},
                fields = (
                    'a.title, a.type, a.create_mchnt_id, cb.coupon_rule_id, '
                    'cb.id, cb.amt, cb.start_time, cb.expire_time'
                ),
                where = where,
                other = other,
            )
            # 补充红包规则
            if coupons:
                cr_ids = {i['coupon_rule_id'] for i in coupons}
                coupon_rules = db.select(
                    'coupon_rule',
                    where = {'id': ('in', cr_ids)},
                    fields = 'id, use_rule, mchnt_id use_mchnt_id'
                )
                cr_dict = {i['id']:i for i in coupon_rules}

                cr_fields = ['use_rule', 'use_mchnt_id']
                for i in coupons:
                    i['use_rule'] = ''
                    i['use_mchnt_id'] = ''
                    if i['coupon_rule_id'] not in cr_dict:
                        continue
                    for field in cr_fields:
                        i[field] = cr_dict[i['coupon_rule_id']][field]

            total = db.select_one(
                'coupon_bind cb', where = where,
                fields = 'count(1) as num'
            )['num']

        return success({
            'coupons' : self.gen_ret(coupons),
            'total' : total
        })
