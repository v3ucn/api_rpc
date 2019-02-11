# encoding:utf-8
'''
用户的活动相关的
'''

import json
import time
import config
import copy
import traceback
import logging
log = logging.getLogger()

from coupon.base import CouponDefine
from notify.base import SpecialApi
from base import UserDefine
from constants import MulType, DATETIME_FMT
from decorator import check_login, raise_excp, with_validator
from util import unicode_to_utf8_ex
from excepts import ParamError

from utils.base import BaseHandler
from utils.date_api import str_to_tstamp, tstamp_to_str

from qfcommon.base.dbpool import get_connection
from qfcommon.qfpay.qfresponse import success
from qfcommon.web.validator import Field, T_INT

class AllowActv(BaseHandler):
    '''
    允许创建的活动
    '''

    def allow_create_sale(self, userid):
        '''是否允许创建特卖'''
        if SpecialApi.check_allow_create(userid):
            return 'sale'

    def allow_create_coupon(self, userid):
        '''是否允许创建红包'''
        ret = []
        with get_connection('qf_marketing') as db:
            actvs = db.select('activity',
                    where = {
                        'src' : CouponDefine.SRC,
                        'mchnt_id' : userid,
                        'status' : CouponDefine.ACTV_STATUS_ENABLE,
                        'expire_time' : ('>=', int(time.time())),
                        'type' : ('in', CouponDefine.HJ_ACTVS),
                    },
                    fields = 'type, obtain_xx_id, used_amt, total_amt') or []
            actvs = [actv  for actv in actvs if not(actv['type'] == CouponDefine.ACTV_TYPE_PAYMENT
                                                    and actv['used_amt'] >= actv['total_amt'])]
            actv_types = set([])
            for actv in actvs:
                if  actv['type'] == CouponDefine.ACTV_TYPE_PAYMENT:
                    if actv['obtain_xx_id']:
                        actv_types.add(CouponDefine.ACTV_TYPE_SHARE)
                    else:
                        actv_types.add(CouponDefine.ACTV_TYPE_PAYMENT)
                else:
                    actv_types.add(CouponDefine.ACTV_TYPE_COMMON)

            # 满减红包
            if CouponDefine.ACTV_TYPE_PAYMENT not in actv_types:
                ret.append('payment_coupon')
            # 消费分享红包
            if CouponDefine.ACTV_TYPE_SHARE not in actv_types:
                ret.append('share_coupon')
            # 店铺红包
            if CouponDefine.ACTV_TYPE_COMMON not in actv_types:
                ret.append('notify_coupon')
        return ret

    def allow_create_card(self, userid):
        '''是否允许创建集点活动'''
        with get_connection('qf_mchnt') as db:
            where = {
                'expire_time': ('>', int(time.time())),
                'userid': userid
            }
            if db.select_one('card_actv', where=where,
                             fields='count(1) as num')['num']:
                return None

        return 'card'

    @check_login
    def GET(self):
        userid = int(self.user.userid)
        allow_funcs = getattr(config, 'ALLOW_FUNCS', ['sale', 'coupon', 'sale', 'card'])
        actv_types  = getattr(config, 'ACTV_TYPES', ['share_coupon', 'payment_coupon',
                                                    'notify_coupon', 'sale', 'card'])
        ret = []
        for i in allow_funcs:
            func = getattr(self, 'allow_create_'+i, None)

            if func:
                actvs = func(userid)
                if actvs:
                    ret.extend(actvs if isinstance(actvs, MulType) else [actvs])

        return self.write(success({'actvs' : [i for i in actv_types if i in ret]}))

class ActvEffect(BaseHandler):
    '''
    获取活动结案报告
    '''

    @check_login
    @raise_excp('获取活动结案报告失败')
    def GET(self):
        if 'id' not in self.req.input():
            raise ParamError('活动不存在')
        actv_id = self.req.input()['id'].strip()
        userid = int(self.user.userid)

        actv = {}
        with get_connection('qf_mchnt') as db:
            actv = db.select_one('actv_effect',
                            where = {
                                'id' : actv_id,
                                'userid' : userid
                            }) or {}
        if not actv:
            raise ParamError('活动不存在')

        if actv['type'] not in UserDefine.ACTV_EFFECTS:
            raise ParamError('活动类型错误')

        # 活动结案报告
        params = json.loads(actv['content'])
        effect = copy.deepcopy(config.ACTV_EFFECT[actv['type']])

        # 整理输出
        result = {}
        for key, val in effect.iteritems():
            if key in ('datas', 'effect'):
                param = params.get(key) or {}
                param = {k:(v/100.0 if k.endswith('amt') else v) for k,v in param.iteritems()}
                result[key] = []
                for item in val:
                    try:
                        item['desc'] = item['desc'].format(**param)
                        result[key].append(item)
                    except:
                        #log.debug(traceback.format_exc())
                        pass
            elif key == 'rank':
                try:
                    result['rank'] = val.format(**params['rank'])
                except:
                    result['rank'] = ''
            elif not key.startswith('_'):
                result[key] = val

        # 活动信息
        datas = params.get('datas') or {}
        if datas:
            if actv['type'] == UserDefine.ACTV_EFFECT_SALE:
                datas['start_time'] = datas['create_time']
                datas['expire_time'] =datas['redeem_end_date'] + ' 00:00:00'

            try:
                result['actv_info'] = {
                    'expire_time' : str_to_tstamp(datas['expire_time'], DATETIME_FMT),
                    'start_time' : str_to_tstamp(datas['start_time'], DATETIME_FMT),
                    'actv_name' : datas.get('title', '')
                }
                if actv['type'] == UserDefine.ACTV_EFFECT_CARD:
                    result['actv_info']['actv_name'] = u'兑换{}活动'.format(params['datas']['goods_name'])
            except:
                log.debug(traceback.format_exc())

        return self.write(success(result))

class DataList(BaseHandler):
    '''
    数据报告列表报告
    '''

    _validator_fields = [
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=20),
    ]

    @check_login
    @with_validator()
    @raise_excp('获取数据失败')
    def GET(self):
        d = self.validator.data
        datas = None
        with get_connection('qf_mchnt') as db:
            datas = db.select(
                     table= 'actv_effect',
                     where= {
                         'userid' : self.user.userid,
                     },
                     other= ('order by ctime desc limit {limit} offset {offset}'.format(
                        offset = d['page'] * d['pagesize'], limit = d['pagesize'])),
                     fields= 'id, ctime, type, content'
                    ) or []

        actv_effect = config.ACTV_EFFECT
        default_img_url = getattr(config, 'DATA_DEFAULT_IMG_URL', '')
        default_desc_fmt = getattr(config, 'DATA_DEFAULT_DESC_FMT', '')
        default_info_url = getattr(config, 'DATA_DEFAULT_INFO_URL', '')
        ret = []
        for data in datas:
            if data['type'] not in actv_effect:
                continue

            desc_fmt = actv_effect[data['type']].get('_desc_fmt', default_desc_fmt)
            info_url = actv_effect[data['type']].get('_info_fmt', default_info_url)
            param = data['content']
            try:
                actv = json.loads(param)['datas']
                actv = {k: unicode_to_utf8_ex(v) for k, v in actv.iteritems()}
                ret.append({
                    'ctime': tstamp_to_str(data['ctime']),
                    'img_url': actv_effect[data['type']].get('_img_url',
                                                             default_img_url),
                    'type': data['type'],
                    'id': data['id'],
                    'desc': desc_fmt.format(**actv),
                    'info_url': info_url.format(data['id'])
                })
            except:
                log.debug(traceback.format_exc())

        return self.write(success({'datas': ret}))
