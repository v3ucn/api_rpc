# encoding:utf-8

import json
import time
from copy import deepcopy
import logging
log = logging.getLogger()
import config
paying_goods = config.PAYING_GOODS

from base import RechargeUtil
from decorator import check_login_ex, raise_excp, login_or_ip
from util import (
    prelogin_lock, postlogin_lock, get_app_info
)
from runtime import redis_pool

from utils.base import BaseHandler
from utils.payinfo import get_payinfo_ex, add_free_ex


from excepts import ParamError
from qfcommon.base.qfresponse import success

class Info(BaseHandler):
    '''
    获取开通服务列表
    '''

    @login_or_ip
    @raise_excp('获取商品列表失败')
    def GET(self):
        r = deepcopy(paying_goods)
        r['now'] = int(time.time())
        _, platform = get_app_info(self.req.environ.get('HTTP_USER_AGENT',''))
        if self._ck_mode == 'sid':
            userid = self.user.userid
        for i in r['goods']:
            # 根据平台配置
            t = getattr(config, '_'.join([i['code'],platform,'SERVICE']).upper(), None)
            if t:
                i['services'] = t
            # 个人配置
            if self._ck_mode == 'sid':
                try:
                    redis_key = '__mchnt_api_goods_info_{}__'.format(i['code'])
                    tservices = json.loads(redis_pool.hget(redis_key, userid))
                except:
                    pass
                else:
                    i['services'] = tservices
            if not i.get('show_price'):
                i['price'] = []
        return self.write(success(r))

class Free(BaseHandler):
    '''
    领取免费体验日期
    '''

    @check_login_ex(prelogin_lock, postlogin_lock)
    @raise_excp('免费体验失败')
    def POST(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        userid = int(self.user.userid)
        code = d.get('service_code') or 'card_actv'
        groupid = self.get_groupid()

        mchnt = get_payinfo_ex(userid, service_code=code,
                               groupid=groupid)
        if mchnt:
            raise ParamError('已经免费体验过，充值才能变得更强哦')

        # 获取免费体验
        _id = add_free_ex(userid, service_code=code, groupid=groupid)
        return self.write(success({'id': _id}))

class PromoCode(BaseHandler):
    '''
    查询优惠码
    返回优惠的价格
    '''

    @check_login_ex(prelogin_lock, postlogin_lock)
    @raise_excp('获取优惠信息失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        p = {i:d.get(i) or '' for i in ('goods_code', 'price_code', 'promo_code')}
        p['userid'] = int(self.user.ses.get('userid'))
        return self.write(success({'amt': RechargeUtil.check_promo_code(**p)}))
