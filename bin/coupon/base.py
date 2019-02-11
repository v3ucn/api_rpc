# encoding:utf-8

import redis
import json
import config
import types
import time
import traceback
import logging
log = logging.getLogger()

from collections import defaultdict
from constants import DATETIME_FMT
from excepts import ThirdError

from qfcommon.thriftclient.open_user import OpenUser
from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.base.tools import thrift_callex

# 活动来源
ACTIVITY_SRC = 'QPOS'

# 活动类型 1: 满减  2: 消费返券/分享券 3: 通用 11:消费返积分
ACTIVITY_TYPE = (ACTIVITY_TYPE_FULLCUT, ACTIVITY_TYPE_PAYMENT, ACTIVITY_TYPE_COMMON, ACTIVITY_TYPE_POINT) = (1, 2, 3, 11)

# 活动分享类型 1:红包 2:积分
ACTIVITY_SHARE_TYPE = (ACTIVITY_SHARE_TYPE_COUPON, ACTIVITY_SHARE_TYPE_INTEGRAL) = (1, 2,)

# 红包状态 1: 领取  2: 绑定  3: 使用  4:  作废
COUPON_STATUS = (COUPON_STATUS_OBTAIN, COUPON_STATUS_BIND, COUPON_STATUS_USE, COUPON_STATUS_DESTROY) = (1, 2, 3, 4)

# 红包使用规则状态 1: 创建  2: 启用  3: 修改
COUPON_RULE_STATUS = (COUPON_RULE_STATUS_CREATE, COUPON_RULE_STATUS_ENABLE, COUPON_RULE_STATUS_CLOSE) = (1, 2, 3)

# 记录状态 0: 领取  1: 使用  2: 还原  3:  作废
RECORD_STATUS = (RECORD_STATUS_OBTAIN, RECORD_STATUS_USE, RECORD_STATUS_UNDO, RECORD_STATUS_DESTROY) = (0, 1, 2, 3)

class CouponDefine(object):
    '''红包定义'''

    SRC = 'QPOS'

    # 活动分类
    ACTV_TYPE_FULLCUT = 1 # 满减
    ACTV_TYPE_PAYMENT = 2 # 消费反卷
    ACTV_TYPE_SHARE = 21 # 消费分享
    ACTV_TYPE_COMMON  = 3 # 通用
    ACTV_TYPE_POINT = 4 # 消费返积分

    # 好近创建的红包活动
    HJ_ACTVS = ACTV_TYPE_PAYMENT, ACTV_TYPE_COMMON

    # 活动状态
    ACTV_STATUS_CREATE = 1 # 创建
    ACTV_STATUS_ENABLE = 2 # 启用
    ACTV_STATUS_CLOSED = 3 # 关闭

    # 红包状态
    CP_STATUS_OBTAIN = 1 # 领取
    CP_STATUS_BIND = 2 # 绑定
    CP_STATUS_USE = 3 # 已使用
    CP_STATUS_CLOSED = 4 # 作废

    # 记录状态
    RD_STATUS_OBTAIN = 0 # 领取
    RD_STATUS_USE = 1 # 使用
    RD_STATUS_UNDO = 2 # 还原
    RD_STATUS_DESTROY = 3 # 作废

class CouponUtil(object):

    @staticmethod
    def get_actv_state(actv):
        '''
        根据活动信息获取活动的状态
        '''
        now = time.strftime(DATETIME_FMT)
        return 1 if now <= str(actv['expire_time']) \
            and actv['status'] == COUPON_RULE_STATUS_ENABLE \
            and actv['used_amt'] < actv['total_amt'] else 2

    @staticmethod
    def get_actv_stats(actids):
        '''获取活动的统计信息'''
        if not actids: return {}
        mode = 'ids'
        if not isinstance(actids, (types.ListType, types.TupleType)):
            actids, mode = [int(actids)], 'id'

        def award_stat():
            '''奖励活动奖励消费者的红包数与金额'''
	    r = {}
            where = {
                'src'        : ACTIVITY_SRC,
                'activity_id': ('in', actids),
                'share_id'   : 0,  # 在红包与消费者绑定表中，分享不存在，则为奖励
                'status': ('!=', COUPON_STATUS_DESTROY),
            }
            fields = 'activity_id, count(1) as num, sum(amt) as amt'
            other = ' ' if len(actids) == 1 else 'group by activity_id'
            with get_connection('qf_marketing') as db:
                r = db.select('coupon_bind', where=where, fields=fields, other=other)
                r = {i['activity_id']:(i['num'] or 0, i['amt'] or 0) for i in r if i['activity_id']}
            return r

        def obtain_stat():
            '''奖励消费者领取活动的红包数与金额'''
            r = {}
            where = {
                'src'        : ACTIVITY_SRC,
                'activity_id': ('in', actids),
                'share_id'   : ('!=', 0),  # 在红包与消费者绑定表中，分享存在，则为领取
                'status': ('!=', COUPON_STATUS_DESTROY),
            }
            fields = 'activity_id, count(1) as num, sum(amt) as amt'
            other = ' ' if len(actids) == 1 else 'group by activity_id'
            with get_connection('qf_marketing') as db:
                r = db.select('coupon_bind', where=where, fields=fields, other=other)
                r = {i['activity_id']:(i['num'] or 0, i['amt'] or 0) for i in r if i['activity_id']}
            return r

        def use_stat():
            '''活动发放的红包使用统计'''
            r = {}
            where = {
                'activity_id': ('in', actids),
                'status'     : COUPON_STATUS_USE,
            }
            fields = 'activity_id, count(1) as num, sum(amt) as amt'
            other = '' if len(actids) == 1 else 'group by activity_id'
            with get_connection('qf_marketing') as db:
                r = db.select('coupon_bind', where=where, fields=fields, other=other)
                r = {i['activity_id']:(i['num'] or 0, i['amt'] or 0) for i in r if i['activity_id']}
            return r

        def order_total_amt():
            '''统计核销的红包金额'''
            r = {}
            where = {
                'activity_id': ('in', actids),
                'type'       : ('in', (RECORD_STATUS_USE, RECORD_STATUS_UNDO, RECORD_STATUS_DESTROY))
            }
            fields = 'activity_id, type, sum(total_amt) as amt'
            other = 'group by type' if len(actids) == 1 else 'group by activity_id,type'
            with get_connection('qf_marketing') as db:
                sr = db.select('record', where=where, fields=fields, other=other)
                dr = defaultdict(dict)
                for i in sr:
                    dr[i['activity_id']]['use' if i['type'] == RECORD_STATUS_USE else 'destroy'] = i['amt']
                r = {k:(v.get('use', 0)-v.get('destroy', 0)) for k, v in dr.iteritems()}
            return r

        def share_num():
            '''统计分享的次数'''
            r = {}
            where = {'activity_id': ('in', actids)}
            fields = 'activity_id, count(1) as num'
            other = '' if len(actids) == 1 else 'group by activity_id'
            with get_connection('qf_marketing') as db:
                r = db.select('activity_share', where=where, fields=fields, other=other)
                r = {i['activity_id']:i['num'] or 0 for i in r if i['activity_id']}
            return r

        astat = award_stat()
        ostat = obtain_stat()
        ustat = use_stat()
        otamt = order_total_amt()
        sstat = share_num()

        r = {}
        for i in actids:
            t = {}
            t['award_num'], t['award_amt'] = astat.get(i, (0, 0))
            t['obtain_num'], t['obtain_amt'] = ostat.get(i, (0, 0))
            t['use_num'], t['use_amt'] = ustat.get(i, (0, 0))
            t['order_total_amt'] = otamt.get(i, 0)
            t['share_num'] = sstat.get(i, 0)
            r[i] = t
        return r if mode == 'ids' else r[actids[0]]

    @staticmethod
    def get_actv_pv(actid):
        '''获取活动的pv'''
        try:
            r = redis.Redis(host=config.REDIS_CONF['host'], port=config.REDIS_CONF['port'],
                password=config.REDIS_CONF['password'])
            return r.get('__yyk_coupon_obtain_%s_pv__' % actid) or 0
        except:
            log.warn('get pv error:%s' % traceback.format_exc())
            return 0

    @staticmethod
    def get_customer(actid, **cf):
        '''获取消费者信息'''
        customer_num, info = 0, []
        try:
            # 查询消费者
            where  = {'activity_id':actid, 'status':COUPON_STATUS_USE}
            limit, offset =  cf.get('limit', 5) , cf.get('offset', 0)
            with get_connection_exception('qf_marketing') as db:
                cps = db.select('coupon_bind', fields = 'distinct customer_id', where= where,
                    other = 'order by create_time desc limit %s, %s' % (offset, limit))
            cids, info = [i['customer_id'] for i in cps], []

            # 查询总共有多少消费者
            customer_num = db.select_one('coupon_bind', where = where, fields = 'count(distinct customer_id) as num')['num']

            # 查询消费者信息
            if cids:
                spec = json.dumps({"user_id":cids})
                r = thrift_callex(config.OPENUSER_SERVER, OpenUser, 'get_profiles', config.OPENUSER_APPID, spec)
                r = {str(i.user_id):i for i in r}
                # 处理返回值
                for i in cids:
                    if i in r:
                        info.append({'id':i, 'avatar':r[i].avatar or config.HJ_AVATAR, 'nickname':r[i].nickname})
                    else:
                        info.append({'id':i, 'avatar':config.HJ_AVATAR, 'nickname':i})
        except:
            log.warn('get openuser_info error:%s' % traceback.format_exc())
            if cf.get('raise_ex', ''):
                raise ThirdError('获取消费者信息失败')

        return customer_num, info
