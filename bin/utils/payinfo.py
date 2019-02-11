# encoding:utf-8
'''
商户付费信息Api
'''

import config
import traceback
import datetime, time
import logging
log = logging.getLogger()

from constants import DATE_FMT, MulType
from excepts import ParamError, DBError
from util import (
    getid, str_timestamp, future, get_mchnt_paying,
    get_mchnt_info, get_qd_conf_value
)
from util import add_free as ori_add_free

from qfcommon.base.dbpool import (
    get_connection, get_connection_exception
)

def get_price(price_code, goods_code=None, service_code=None):
    goods = get_goods(goods_code, service_code)
    price = next((i for i in goods['price'] if i['code'] == price_code), None)
    if not price:
        raise ParamError('该商品没有这个价位')

    return price

def get_goods(goods_code=None, service_code=None, mode='one'):
    ret = []
    if goods_code:
        goods = next((item for item in config.GOODS
                      if item['code'] == goods_code), {})
        if goods:
            ret.append(goods)

    elif service_code:
        condition = lambda code: (
                (service_code in code) if isinstance(code, MulType)
                else (service_code == code))
        for item in config.GOODS:
            if next((True for service in item['services']
                     if condition(service['code'])), False):
                ret.append(item)
                if mode == 'one':
                    break

    if not ret:
        raise ParamError('未找到该服务')

    return ret[0] if mode == 'one' else ret

def get_pay_info(userid, goods_code=None, service_code='coupon'):
    '''获取商户付费信息

    通过goods_code或者service_code定位某项服务,
    通过recharge表获取商户信息

    Args:
        userid: 商户id
        goods_code: 商品code, 若传入了goods_code, service_code将无效
                    card:会员服务, diancan:点餐服务, prepaid:储值服务
        service_code: 服务code, 针对不同的goods_code拥有不同的service_code

    Returns:
        返回商户服务信息的字典,若商户未曾开通或者体验过返回{},
        否则返回expire_time, status, goods_code的一个字典.

    Raises:
        ParamError: 商户参数错误
    '''
    goods = get_goods(goods_code, service_code, 'all')

    # 若服务是免费的话
    # 返回有效期是10年以后
    for i in goods:
        if i.get('is_gratis', False):
            return {
                'expire_time':  future(years=10),
                'status': 2,
                'goods_code' : i['code']
            }

    recharge_info = {}
    with get_connection('qf_mchnt') as db:
        recharge_info = db.select_one(
                table= 'recharge',
                where= {
                    'userid': int(userid),
                    'goods_code': ('in', [i['code'] for i in goods]),
                },
                fields= 'expire_time, status, goods_code',
                other= 'order by expire_time desc')

    return recharge_info

def adjust_pay_info(userid, goods_code=None, service_code='coupon'):
    '''
    整理商户付费信息
    '''
    if not goods_code and not service_code:
        raise ParamError('商品code和服务code不能同时为空')

    r = get_pay_info(userid, goods_code, service_code) or {}

    # 商户状态 0:新 1:免费体验商户 2:付费商户
    r['status'] =  r.get('status', 0)
    r['overdue'] = 1

    free = left_day =  left_warn = 0
    if r.get('expire_time'):
        now = datetime.datetime.now()
        r['overdue'] = int(bool(now > r['expire_time']))
        left_day = max((r['expire_time'] - now).days, 0)
        # 剩余天数小于5天会提醒
        left_warn = int(bool(left_day <= 5))
        goods = next((item for item in config.GOODS
                           if item['code'] ==  r['goods_code']), {})
        r['goods_name'] = goods.get('name', '')
        free = goods.get('free', 0)

    r['left_day'] =  left_day
    r['left_warn'] = left_warn
    r['free'] = free

    return r

def add_free(userid, goods_code=None, service_code='card_actv'):
    '''
    给userid开通免费体验
    '''
    goods = get_goods(goods_code, service_code)
    if not goods.get('free'):
        raise ParamError('该服务暂不支持免费体验')
    free = goods['free']

    try:
        now = int(time.time())
        expire_time = str_timestamp(time.strftime(DATE_FMT), DATE_FMT)+(free+1)*24*3600-1
        recharge_id = getid()
        with get_connection_exception('qf_mchnt') as db:
            db.insert('recharge', {
                'id': recharge_id,
                'userid': userid,
                'ctime': now, 'utime': now,
                'goods_code': goods['code'],
                'status': 1,
                'expire_time': expire_time
                })
        return recharge_id
    except:
        log.warn('create activity error: %s' % traceback.format_exc())
        raise DBError('开通免费体验失败')

# 低版本goods_code和service_code
_goods_codes = {goods['code'] for goods in config.PAYING_GOODS['goods']}
_service_codes = []
for goods in config.PAYING_GOODS['goods']:
    for service in goods['services']:
        if isinstance(service['code'], MulType):
            _service_codes.extend(service['code'])
        else:
            _service_codes.append(service['code'])

## v1版本的goods_code和service_code
_v1_goods_codes = {goods['code'] for goods in config.PAYING_GOODS['goods']}
_v1_service_codes = []
for goods in config.GOODS:
    for service in goods['services']:
        if isinstance(service['code'], MulType):
            _v1_service_codes.extend(service['code'])
        else:
            _v1_service_codes.append(service['code'])

def get_goods_version(goods_code=None, service_code=None):
    '''
    根据goods_code和service_code
    '''
    if goods_code:
        if goods_code in _goods_codes:
            return 'v'
        elif goods_code in _v1_goods_codes:
            return 'v1'
    elif service_code:
        if service_code in _service_codes:
            return 'v'
        elif service_code in _v1_service_codes:
            return 'v1'
    else:
        raise ParamError('商品不存在')

def get_payinfo_ex(userid, goods_code=None, service_code='coupon', groupid=None):
    '''
    根据groupid来决定调用
    '''
    # 非直营渠道且是第一版的服务
    if int(groupid or 0) not in config.QF_GROUPIDS:
        version = get_goods_version(goods_code, service_code)
        if version == 'v':
            return get_mchnt_paying(userid, service_code)

    return get_pay_info(userid, goods_code, service_code)

def adjust_payinfo_ex(userid, goods_code=None, service_code='coupon', groupid=None):
    '''
    根据groupid来决定调用
    '''

    # 若是点餐服务, 全走老逻辑
    if goods_code == 'diancan' or service_code == 'diancan':
        return get_mchnt_info(userid, 'diancan')

    # 非直营渠道且是第一版的服务
    if int(groupid or 0) not in config.QF_GROUPIDS:
        # 若该渠道将会员服务免费
        free_card = get_qd_conf_value(userid, mode='free_card',
                                      key='service', groupid=groupid,
                                      default=False)
        if not free_card:
            version = get_goods_version(goods_code, service_code)
            if version == 'v':
                return get_mchnt_info(userid, service_code)
        else:
            return {
                'status': 2,
                'goods_name': '会员服务',
                'goods_code': goods_code,
                'free': 0,
                'left_day': 10 * 365,
                'left_warn': 0,
                'expire_time': future(years=10),
                'overdue': 0
            }

    return adjust_pay_info(userid, goods_code, service_code)

def add_free_ex(userid, goods_code=None, service_code=None, groupid=None):
    # 非直营渠道且是第一版的服务
    if int(groupid or 0) not in config.QF_GROUPIDS:
        version = get_goods_version(goods_code, service_code)
        if version == 'v':
            return ori_add_free(userid, service_code)

    return add_free(userid, goods_code, service_code)
