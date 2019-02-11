# encoding:utf-8

import redis
import datetime
import types
import time
import traceback
import logging
log = logging.getLogger()
from math import (
    radians, atan, tan, sin, cos, acos
)

from config import MMWD_REDIS
from cache import cache
from constants import DATE_FMT, DATETIME_FMT
from util import redis_pool, is_valid_num

from qfcommon.base.dbpool import get_connection, get_connection_exception

# mmwd redis cli
mmwd_redis_cli = redis.Redis(**MMWD_REDIS)
# 距离fmt
dist_fmt = lambda dist: '{}m'.format(int(dist*1000)) if dist < 1 else '{:.1f}km'.format(dist)

class SpecialDefine(object):
    '''
    特卖常量
    '''

    # market_activity 类型
    ATYPE_SALE = 1   # 特卖
    ATYPE_TAKEOUT = 2   # 外卖
    ATYPE_ORDINARY = 3   # 普通电商

    STATUS_PLACED = 0 # 未开始
    STATUS_NORMAL = 1 #  上线
    STATUS_DOWN = 2 # 下线
    STATUS_TEST = 3 # 测试
    STATUS_DELETED = 4 # 删除

    AUDIT_STATUS_PLACED = 0 # 提交审核
    AUDIT_STATUS_SUCCESS = 1 # 审核成功
    AUDIT_STATUS_FAILED = 2 # 审核失败

    # 通知状态
    NOTIFY_INIT = 0        # 未开始
    NOTIFY_IN_PROGRESS = 1 # 进行中
    NOTIFY_DONE = 2        # 结束
    NOTIFY_REJECT = 3      # 审核失败
    NOTIFY_DELETED = 4     # 删除

    # 活动状态
    STATE_ON = 1 # 抢购中
    STATE_DONE = 2 # 已结束
    STATE_REJECT = 3 # 审核失败
    STATE_STOP = 4 # 已终止

    # 查看from
    FROM_DICT = {
        'payTMSale' : '支付完成页',
        'menuTMSale' : '公众号菜单',
        'tuwenTMSale' : '图文消息推送',
        'appTMSale' : '好近客户端',
        'wordTMSale' : '公众号文字通知',
        'singlemessage' : '分享消息',
    }
    # 查看list
    FROM = ['payTMSale', 'menuTMSale', 'tuwenTMSale', 'appTMSale', 'wordTMSale', 'singlemessage']

    # 特卖活动购买数量 redis key
    SALES_RKEY = 'MarketActivity_sales'

    # 查看特看pv redis prefix
    RKEY_PREFIX = '__special_sale_%s_pv__'

class SpecialApi(object):
    '''
    特卖api
    '''

    @staticmethod
    def get_head_sales():
        '''获取置顶电商特卖'''
        try:
            saleids = [int(i) for i in redis_pool.zrange('mchnt_api_head_sales', 0, -1)]
        except:
            return []

        if not saleids: return []

        sales, today = [], time.strftime(DATE_FMT)
        where = {
            'id' : ('in', saleids),
            'audit_status' : ('in', (SpecialDefine.AUDIT_STATUS_PLACED,
                                     SpecialDefine.AUDIT_STATUS_SUCCESS)),
            'status' : ('in', (SpecialDefine.STATUS_PLACED,
                               SpecialDefine.STATUS_NORMAL,
                               SpecialDefine.STATUS_TEST)),
            'buyable_start_date' : ('<=', today),
            'buyable_end_date' : ('>=', today),
            'title' : ('not like', '测试%'),
            'quantity' : ('>', 0),
        }
        with get_connection('qmm_wx') as db:
            sales = db.select('market_activity', where=where)
        if not sales: return []

        return SpecialApi.tidy_sales(sales, 'head_sales', default_region='全国')

    @staticmethod
    def get_actv_pv(ids):
        '''获取活动的pv'''
        if not isinstance(ids, (types.ListType, types.TupleType)):
            ids = [ids]
        r = {}
        try:
            for i in ids:
                query_info = []
                pvs = redis_pool.hgetall(SpecialDefine.RKEY_PREFIX % i)
                for code in SpecialDefine.FROM_DICT:
                    if code in pvs:
                        query_info.append({'desc' : SpecialDefine.FROM_DICT[code],
                                           'count' : int(pvs[code])})
                r[i] = query_info
        except:
            log.warn('get pv error:%s' % traceback.format_exc())
        return r

    @staticmethod
    def add_actv_pv(ids, query_from=None):
        '''增加活动的pv'''
        if not isinstance(ids, (types.ListType, types.TupleType)):
            ids = [ids]
        r = {}
        try:
            query_from = query_from if query_from in SpecialDefine.FROM_DICT else 'singlemessage'
            for i in ids:
                redis_pool.hincrby(SpecialDefine.RKEY_PREFIX  % i, query_from, 1)
        except:
            log.warn('incr pv error:%s' % traceback.format_exc())
        return r

    @staticmethod
    def get_actv_sales(ids):
        if not isinstance(ids, (types.ListType, types.TupleType)):
            ids = [ids]
        r = {}
        try:
            sales = mmwd_redis_cli.hmget(SpecialDefine.SALES_RKEY, *ids)
            for idx, key in enumerate(ids):
                r[key] = int(sales[idx] or 0)
        except:
            log.warn('get sales error:%s' % traceback.format_exc())
        return r

    @staticmethod
    def get_actv_status(actv):
        '''活动通知状态'''
        td = datetime.date.today()
        now = str(datetime.datetime.now())
        notify_datetime = str(actv['redeem_start_date']) + ' 11:00:00'
        if actv['audit_status'] == SpecialDefine.AUDIT_STATUS_FAILED:
            status = SpecialDefine.NOTIFY_REJECT
        elif actv['status'] not in (SpecialDefine.STATUS_PLACED, SpecialDefine.STATUS_NORMAL, SpecialDefine.STATUS_TEST):
            status = SpecialDefine.NOTIFY_DELETED
        elif now < notify_datetime:
            status = SpecialDefine.NOTIFY_INIT
        elif td <= actv['redeem_end_date']:
            status = SpecialDefine.NOTIFY_IN_PROGRESS
        else:
            status = SpecialDefine.NOTIFY_DONE

        return status

    @staticmethod
    def get_actv_state(actv):
        '''活动状态'''
        redeem_datetime = (datetime.datetime.strptime(str(actv['redeem_end_date']), DATE_FMT)+
                           actv['redeem_end_time'])
        if actv['audit_status'] == SpecialDefine.AUDIT_STATUS_FAILED:
            state = SpecialDefine.STATE_REJECT
        elif (actv['status'] in (SpecialDefine.STATUS_PLACED, SpecialDefine.STATUS_NORMAL,
                                 SpecialDefine.STATUS_TEST)
              and
              str(redeem_datetime) >  time.strftime(DATETIME_FMT) and actv['quantity']):
            state = SpecialDefine.STATE_ON
        elif actv['status'] == SpecialDefine.STATUS_DOWN:
            state = SpecialDefine.STATE_STOP
        else:
            state = SpecialDefine.STATE_DONE

        return state

    @staticmethod
    def check_allow_create(userid):
        # 若在黑名单
        if redis_pool.sismember('_mchnt_api_sale_limit_userids_', userid):
            return False

        try:
            max_actvs = int(redis_pool.get('mchnt_api_max_sale_actv'))
        except:
            max_actvs = 2
        with get_connection_exception('qmm_wx') as db:
            where = {
                'qf_uid' : int(userid),
                'audit_status' : ('in', (SpecialDefine.AUDIT_STATUS_PLACED,
                                         SpecialDefine.AUDIT_STATUS_SUCCESS)),
                'status' : ('in', (SpecialDefine.STATUS_PLACED,
                                   SpecialDefine.STATUS_NORMAL,
                                   SpecialDefine.STATUS_TEST)),
                'redeem_end_date' : ('>=', time.strftime(DATE_FMT)),
                'quantity' : ('!=', 0),
            }
            fields = 'redeem_end_date, redeem_end_time, id, quantity, daily_quantity, img'
            actvs = db.select('market_activity', where=where, fields=fields)

        if not actvs: return True

        # 判断同时进行的是否超过两个
        count, now = 0, time.strftime(DATETIME_FMT)
        for i in actvs:
            redeem_datetime = (datetime.datetime.strptime(str(i['redeem_end_date']), DATE_FMT)+
                            i['redeem_end_time'])
            if str(redeem_datetime) < now: continue
            count += 1
            if count >= max_actvs:
                return False

        return True

    @staticmethod
    def tidy_sales(sales, mode='near', **kw):
        '''
        Method tidy sales.
        :param sales: 特卖列表
        :param mode: consumed: 曾经消费过
                     near: 附近
                     head_sales: 置顶特卖
        :param default_region:当未取到商圈名, 默认的商圈名
        :param lng/lat: mode为near时的经纬度
        :param dist_max: mode为near时的最大范围
        '''
        if not sales: return []

        lng, lat = kw.get('lng'), kw.get('lat')
        default_region = kw.get('default_region', '')
        dist_max = kw.get('dist_max', 50)

        ret = []
        can_caldist = is_valid_num(lng) and is_valid_num(lat) and lng and lat
        for sale in sales:
            dist = None
            if mode == 'near':
                if not can_caldist and sale.get('lng') and sale.get('lat'):
                    continue
                dist = calcDistance(lng, lat, sale['lng'], sale['lat'])
                if dist > dist_max:
                    continue

            elif mode == 'consumed':
                dist = (calcDistance(lng, lat, sale['lng'], sale['lat'])
                        if (sale.get('lng') and sale.get('lat') and can_caldist)
                        else None)

            ret.append({
                'region' : sale.get('region') or default_region,
                'shop_name' : sale.get('shop_name', sale['business_title']),
                'distance' : dist_fmt(dist) if dist is not None else '',
                'activity_id' :sale['id'],
                'img' : sale['img'],
                'goods_name' : sale['title'],
                'price' : sale['price'],
                'origin_price' : sale['origin_price'],
                'dist' : dist,
            })
        return ret

    @staticmethod
    @cache(redis_key = '_mchnt_api_all_sales_')
    def get_all_sales():
        '''
        Method return all online sales with shopinfo.
        '''
        return

def get_notify_datetime(dt, days=1):
    notify_datetime = datetime.datetime(dt.year, dt.month, dt.day)
    notify_datetime = notify_datetime + datetime.timedelta(days=days, hours=11)
    return notify_datetime

def get_coupon_rule(rule_id):
    with get_connection_exception('qf_marketing') as conn:
        rule = conn.select_one('coupon_rule', where=dict(id=rule_id))
        if not rule:
            log.warn('not found coupon_rule for rule: %s', rule_id)
            return None
        else:
            #log.info('found rule for rule: %d, rule: %s', rule_id, rule)
            return rule
        pass

    return

def calcDistance(lng_a, lat_a, lng_b, lat_b):
    '''
    TODO: 由两点计算距离
    Input:
        lng_A 经度A
        lat_A 纬度A
        lng_B 经度B
        lat_B 纬度B
    output
        dist 距离
    '''
    if (lng_a, lat_a) == (lng_b, lat_b):
        return 0
    try:
        ra = 6378.140  # 赤道半径 (km)
        rb = 6356.755  # 极半径 (km)
        flatten = (ra - rb) / ra  # 地球扁率
        rad_lat_A = radians(lat_a)
        rad_lng_A = radians(lng_a)
        rad_lat_B = radians(lat_b)
        rad_lng_B = radians(lng_b)
        pA = atan(rb / ra * tan(rad_lat_A))
        pB = atan(rb / ra * tan(rad_lat_B))
        xx = acos(sin(pA) * sin(pB) + cos(pA) * cos(pB) * cos(rad_lng_A - rad_lng_B))
        c1 = (sin(xx) - xx) * (sin(pA) + sin(pB)) ** 2 / cos(xx / 2) ** 2
        c2 = (sin(xx) + xx) * (sin(pA) - sin(pB)) ** 2 / sin(xx / 2) ** 2
        dr = flatten / 8 * (c1 - c2)
        dist = ra * (xx + dr)
    except ZeroDivisionError:
        log.debug(traceback.format_exc())
        return 0
    else:
        return dist
