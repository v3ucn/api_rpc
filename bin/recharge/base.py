# encoding:utf-8

import time
import datetime
import hashids
import hashlib
import logging
import traceback
log = logging.getLogger()

import config
paying_goods = config.PAYING_GOODS
from excepts import ParamError
from runtime import redis_pool
from qfcommon.base.dbpool import get_connection

# 渠道状态 1:关闭 2:开启
PROMO_STATUS = {'normal': 1, 'close': 2}

# 渠道推广码状态 1:关闭 2:开启
PROMO_CODE_STATUS = {'normal': 1, 'close': 2}

# 渠道推广码类型 1:余额 2:余次
PROMO_CODE_TYPE = {'balance': 1, 'num': 2}

# 订单状态 1:未支付 2:完成(已支付)
ORDER_STATUS = {'all': 0, 'undo': 1, 'done': 2, 'fail': 3}

unicode2str = lambda s: s.encode('utf-8') if isinstance(s, unicode) else str(s)
class RechargeUtil():

    @staticmethod
    def unzip_promo_code(promo_code, goods_code, type_len=4):
        promo_code = promo_code[2:]
        # 优惠码是否在黑名单里
        if redis_pool.sismember('mchnt_api_forbid_code', promo_code):
            raise ParamError('该优惠码已禁止使用')

        # 优惠码是否存在
        # code: 1,2,3,4 无限制使用的优惠码
        # code: 5,6,7,8 同一商户只能使用一次
        try:
            hids = hashids.Hashids(
                config.PROMO_KEYS[goods_code][0],
                alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789'
            )
            code, userid, amt = hids.decode(promo_code)
            code_type, code = (code-1) / type_len,  (code % type_len) or type_len
        except:
            log.debug(traceback.format_exc())
            raise ParamError('优惠码不存在')
        log.info('code:%s userid:%s amt:%s' % (code, userid, amt))

        return code_type, code, amt

    @staticmethod
    def check_promo_code(goods_code, price_code, promo_code, **kw):
        '''
        验证优惠码接口
        v1版本:
        '''
        code_type, code, amt = RechargeUtil.unzip_promo_code(promo_code, goods_code)
        # 商品价格
        price = RechargeUtil.get_price(goods_code, price_code)
        if price['promo_code'] != code:
            raise ParamError('该商品不能使用该优惠码')

        # 验证code_type
        if code_type >= 1:
            with get_connection('qf_mchnt') as db:
                where = {'userid': kw['userid'],
                    'promo_code':promo_code, 'status': ORDER_STATUS['done']}
                r = db.select_one('paying_order', where)
            if r:
                raise ParamError('该优惠码只能使用一次哦')

        # 是否满足条件
        return (price['amt']-1) if amt*100 > price['amt'] else amt * 100

    @staticmethod
    def check_recharge_info(userid, goods_code='v1', price_code='12month', promo_code=None, **kw):
        '''验证提交的信息

        支付预览和优惠码是验证

        Args:
            goods_code: 服务code
            price_code: 价格code
            promo_code: 当promo_code为空时, 不验证优惠码信息

        Raise:
            当服务，价格，优惠码不存在时会抛出ParamError

        Returns:
            cur_goods, promo_amt

        '''
        # 获取当前服务
        cur_goods = None
        for goods in config.GOODS:
            if goods['code'] == goods_code:
                if goods.get('is_gratis'):
                    raise ParamError('该服务免费')
                cur_goods = goods
                break
        else:
            raise ParamError('未找到服务')
        if cur_goods['price']['code'] != price_code:
            raise ParamError('服务没有该价格')

        # 若无优惠码
        if not promo_code:
            return {'goods':cur_goods}

        # 验证优惠码
        code_type, code, amt = RechargeUtil.unzip_promo_code(promo_code, goods['code'], 1)
        if goods['price']['promo_code'] != code:
            raise ParamError('该商品不能使用该优惠码')
        if code_type >= 1:
            with get_connection('qf_mchnt') as db:
                r = db.select_one('paying_order',
                            where= {
                                'userid': userid,
                                'promo_code': promo_code[2:],
                                'status': 2
                            })
            if r:
                raise ParamError('该优惠码只能使用一次哦')

        return {'goods': cur_goods, 'promo_amt': amt*100}

    @staticmethod
    def get_goods(goods_code='card'):
        goods = next((i for i in paying_goods['goods'] if i['code'] == goods_code), None)
        if not goods:
            raise ParamError('未找到该商品')

        return goods

    @staticmethod
    def get_price(goods_code, price_code):
        goods = RechargeUtil().get_goods(goods_code)
        price = next((i for i in goods['price'] if i['code'] == price_code), None)
        if not price:
            raise ParamError('该商品没有这个价位')

        return price

    @staticmethod
    def make_sign(data):
        unsign_str = ''
        keys = data.keys()
        keys.sort()

        for i in keys:
            k = unicode2str(i)
            v = unicode2str(data[i])
            if v:
                if unsign_str:
                    unsign_str += '&%s=%s'%(k,v)
                else:
                    unsign_str += '%s=%s'%(k,v)

        unsign_str += unicode2str(config.QT2_APP_KEY)
        s = hashlib.md5(unsign_str).hexdigest()
        return s.upper()

    @staticmethod
    def check_sign(data, sign, not_include = ['sign']):
        '''检查发送上来请求的签名'''

        unsign_str = ''
        keys = data.keys()
        keys.sort()

        for i in keys:
            k = unicode2str(i)
            v = unicode2str(data[i])
            if k not in not_include and v:
                if unsign_str:
                    unsign_str += '&%s=%s'%(k,v)
                else:
                    unsign_str += '%s=%s'%(k,v)

        unsign_str += unicode2str(config.QT2_APP_KEY)
        s = hashlib.md5(unsign_str).hexdigest()

        return sign.upper() == s.upper()

    @staticmethod
    def get_cur_payinfo(userid, goods_code):
        '''获取商户当前会员信息

        Args:
            userid: 商户userid
            goods_code: 要付费的goods_code

        Returns:
            cur_amt: 低级服务折算价
            cur_expire: 当前等级服务价格

        '''
        all_goods = {goods['code']:goods for goods in config.GOODS}
        cur_goods = all_goods[goods_code]
        now = int(time.time())
        # 所有付费信息
        payinfos = []
        with get_connection('qf_mchnt') as db:
            payinfos = db.select('recharge',
                    where= {
                        'expire_time': ('>', now),
                        'userid': userid,
                    },
                    fields= 'goods_code, expire_time') or []

        # 当前信息
        cur_amt= 0
        cur_expire = datetime.datetime.now()
        get_diffdays = lambda dt: (int(time.mktime(dt.timetuple()))-now) / (24 * 3600)
        for payinfo in payinfos:
            if payinfo['goods_code'] not in all_goods:
                continue

            goods = all_goods[payinfo['goods_code']]
            if payinfo['goods_code'] == goods_code:
                cur_expire = (payinfo['expire_time']
                              if payinfo['expire_time'] > cur_expire
                              else cur_expire)

            elif (goods['vip'] < cur_goods['vip'] and
                  goods.get('per_price', 0)):
                diff_days = get_diffdays(payinfo['expire_time'])
                cur_amt += goods['per_price'] * diff_days

        return int(cur_amt), cur_expire
