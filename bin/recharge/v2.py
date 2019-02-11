# encoding:utf-8
'''
商户付费
'''

import json
import time
import config
import copy
import datetime
import logging
log = logging.getLogger()

from constants import DATETIME_FMT
from excepts import ParamError
from base import RechargeUtil, ORDER_STATUS
from runtime import redis_pool
from util import (
    getid, prelogin_lock, postlogin_lock
)
from decorator import (
    check_login, check_login_ex, raise_excp, with_validator
)
from utils.base import BaseHandler
from utils.date_api import future

from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.base.qfresponse import success
from qfcommon.web.validator import Field, T_STR

class Goods(BaseHandler):
    '''
    商户所有服务的信息
    '''

    @check_login
    @raise_excp('获取商户服务信息失败')
    def GET(self):
        userid = int(self.user.userid)
        allgoods = copy.deepcopy(config.GOODS)

        payinfos = []
        vip_goods = {}
        gratis_goods = config.GOODS[0]
        for goods in allgoods:
            if goods.get('is_gratis'):
                gratis_goods = goods
            else:
                vip_goods[goods['code']] = goods

        with get_connection('qf_mchnt') as db:
            payinfos = db.select(
                    table= 'recharge',
                    where= {
                        'userid': userid,
                        'goods_code': ('in', vip_goods.keys())
                    },
                    fields= 'expire_time, status, goods_code') or []
        payinfos = {payinfo['goods_code']:payinfo for payinfo in payinfos}

        # 当前服务
        now = datetime.datetime.now()
        expire_code = vip_code = None
        for code, payinfo in payinfos.iteritems():
            if not vip_code or vip_goods[code]['vip'] > vip_goods[vip_code]['vip']:
                vip_code = code

            if ((payinfo['expire_time'] > now) and
                (not expire_code  or
                vip_goods[code]['vip'] > vip_goods[expire_code]['vip'])):
                expire_code = code
        curgoods = vip_goods.get(expire_code or vip_code, gratis_goods)

        # 当前服务信息
        cur_payinfo = {
            'name': curgoods['name'],
            'logo_url': curgoods['logo_url'],
            'code': curgoods['code']
        }
        if curgoods.get('is_gratis'):
            cur_payinfo['expire_time'] = ''
        else:
            cur_payinfo['expire_time'] = payinfos[curgoods['code']]['expire_time']

        # 更高级服务信息
        up_goods, up_opt = [], []
        fields = ['services', 'color', 'pg_name', 'desc']
        for goods in allgoods:
            if goods['vip'] < curgoods['vip']:
                continue
            elif goods['code'] == curgoods['code']:
                goods['pg_name'] = '我的权益'
            else:
                goods['pg_name'] = '{}权益'.format(goods['name'])
                up_opt.append({
                    'name': '升级到{}'.format(goods['name']),
                    'code': goods['code']
                })

            goods['services'] = [{i:service.get(i, '') for i in ['title', 'icon_url', 'info_url']}
                                  for service in goods['services']]
            t = {field:goods[field] for field in fields}
            try:
                redis_key = '__mchnt_api_goods_info_{}_{}__'.format(userid, goods['code'])
                update_data = json.loads(redis_pool.get(redis_key))
                t.update(update_data)
            except:
                pass

            up_goods.append(t)

        return self.write(success({'payinfo': cur_payinfo,
                'up_goods': up_goods, 'up_opt': up_opt}))

class Preview(BaseHandler):
    '''
    支付预览页面
    '''

    _validator_fields = [
        Field('goods_code', T_STR),
        Field('promo_code', T_STR),
        Field('price_code', T_STR, default='12month'),
    ]

    @check_login
    @with_validator()
    @raise_excp('获取付费预览失败')
    def GET(self):
        userid = int(self.user.userid)

        # 验证信息
        info = RechargeUtil.check_recharge_info(userid, **self.validator.data)
        upgoods = info['goods']

        # 获取当前支付信息
        code = self.validator.data['goods_code']
        cur_amt, cur_expire = RechargeUtil.get_cur_payinfo(userid, code)
        add_conf = {upgoods['price']['alidity']['unit']: upgoods['price']['alidity']['key']}
        expire_time = future(cur_expire, **add_conf)

        # 付费服务信息
        goods_info = copy.deepcopy(upgoods)
        goods_info['price'] = {i:goods_info['price'][i]
                                   for i in ['code', 'goods_name', 'amt']}
        goods_info['services'] = [{i: service.get(i, '') for i in ['title', 'icon_url', 'info_url']}
                                   for service in goods_info['services']]
        goods_info['pg_name'] = '{}权益'.format(goods_info['name'])

        fields = ['services', 'color', 'pg_name', 'code', 'logo_url', 'price', 'desc']
        goods_info = {field:goods_info[field] for field in fields}
        goods_amt = goods_info['price']['amt']


        promo_amt = info.get('promo_amt', 0)
        promo_amt = min(promo_amt, goods_amt - 1)
        ret = {}
        ret['goods_info'] = goods_info
        ret['promo_amt'] = promo_amt
        ret['cur_amt'] = (cur_amt if (promo_amt + cur_amt) < goods_amt
                          else (goods_amt - promo_amt - 1))
        ret['txamt'] = max(goods_amt - promo_amt - cur_amt, 1)
        ret['expire_time'] = expire_time

        return self.write(success(ret))


class PromoCode(BaseHandler):
    '''
    查询优惠码是否可用
    '''

    @check_login
    @raise_excp('获取优惠信息失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        userid = int(self.user.userid)

        if not d.get('promo_code'):
            raise ParamError('优惠码不存在')

        RechargeUtil.check_recharge_info(userid, **d)

        return self.write(success({}))

class OrderCreate(BaseHandler):
    '''
    创建订单
    '''

    @check_login_ex(prelogin_lock, postlogin_lock)
    @raise_excp('下单失败')
    def POST(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        order = {field:d.get(field, '') for field in ('goods_code', 'price_code', 'promo_code')}
        order['userid'] = int(self.user.userid)
        ext = {}
        ext['promo_code'] = order['promo_code']

        # 获取信息
        info = RechargeUtil.check_recharge_info(**order)
        goods = info['goods']
        promo_amt = info.get('promo_amt', 0)
        ext['promo_amt'] = promo_amt

        # 折算金额
        cur_amt, _ = RechargeUtil.get_cur_payinfo(order['userid'], order['goods_code'])
        ext['cur_amt'] = cur_amt

        order['total_amt'] = goods['price']['amt']
        order['goods_name'] = goods['price']['goods_name']
        order['txamt'] = max(order['total_amt'] - cur_amt - promo_amt, 1)

        # 订单其他信息
        order['id'] = getid()
        order['out_sn'] = 0
        order['ext'] = json.dumps(ext)
        order['promo_code'] = order['promo_code'][2:]
        order['status'] = ORDER_STATUS['undo']
        order['ctime'] = order['utime'] = int(time.time())
        # 插入paying_order
        with get_connection_exception('qf_mchnt') as db:
            db.insert('paying_order', order)

        # 返回值
        r = {}
        r['goods_name'] = order['goods_name']
        r['txamt'] = order['txamt']
        r['txcurrcd'] = 'CNY'
        r['txdtm'] = time.strftime(DATETIME_FMT)
        r['out_trade_no'] = order['id']
        r['udid'] = 'mchnt_api'
        r['appcode'] = config.QT2_APP_CODE
        r['sign'] = RechargeUtil.make_sign(r)

        return self.write(success(r))
