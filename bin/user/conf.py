# encoding:utf-8
'''
商户付费
'''

import copy
import json
import types
import traceback
import config
import logging

from util import get_app_info
from utils.tools import get_value, rate_cache, get_qudaoinfo
from utils.qdconf_api import get_qd_conf_value
from utils.decorator import check
from utils.language_api import get_constant

from constants import MulType
from base import UserBase

from qfcommon.base.dbpool import get_connection
from qfcommon.base.qfresponse import success
from qfcommon.server.client import HttpClient
from qfcommon.web.cache import CacheDict

log = logging.getLogger()

# 需要开刷卡的ua列表
UA_CARDS = (
    config.UA_CARD if isinstance(config.UA_CARD, MulType) else
    [config.UA_CARD, ]
)

## 获取所有生效的custom
def get_all_custom(app_id, data=None):
    customs = None
    with get_connection('app_conf') as db:
        customs = db.select(
            table = 'app_custom',
            where = {
                'status' : 1,
                'app_id' : app_id,
            },
            other = 'order by app_version',
            fields = (
                'custom_key, custom_value, user_list_type, user_list'
            )
        ) or []
    if not customs:
        return []

    # 将所有custom进行排序
    # 1. 按照商户id配置 2. 按照渠道id配置 0.所有通用配置
    weight = {0: 1, 2:2, 1:3}
    customs.sort(key=lambda d: weight.get(d['user_list_type']), reverse=True)

    for custom in customs:
        if custom['user_list_type'] in (1, 2):
            custom['user_list'] =  set(custom['user_list'].split(','))

    return customs

custom_cache = CacheDict(
    get_all_custom,
    getattr(config, 'CUSTOM_CACHE', 10 * 60)
)


def get_custom_value(userid, groupid, app_id, custom_key):
    '''获取对应的custom_value'''
    custom_value = None

    customs = custom_cache[app_id] or []
    for custom in customs:
        if custom['custom_key'] != custom_key:
            continue

        if (
            custom['user_list_type'] == 0 or
            (
                custom['user_list_type'] == 1 and
                str(userid) in custom['user_list']
            ) or
            (
                custom['user_list_type'] == 2 and
                str(groupid) in custom['user_list']
            )
           ):
            return custom['custom_value']

    return custom_value


class Conf(UserBase):
    '''
    用户初始化接口
    返回值:
        zip_conf: 离线包
        activity_conf: 红包活动配置
        pay_sequence: 支付序列
    '''

    def get_appid(self):
        '''获取app对应的appid'''

        default_appid = config.APPID_MAP.get(self._platform)

        return get_qd_conf_value(
                mode= (self._platform or '') + '_appid',
                key= 'ext', groupid= self.get_groupid(),
                default_val= default_appid)


    def mchnt_conf(self, qdmode, qdkey='service', **kw):
        '''获取配置'''
        default = getattr(config, qdmode, None)
        groupid = self.get_groupid()

        return get_qd_conf_value(
                mode= qdmode,
                key= qdkey, groupid= groupid,
                default_key= int(groupid not in config.QF_GROUPIDS),
                default_val= default)

    def service_conf(self, pos='head', addon=None, **kw):
        '''功能配置'''
        return self.get_user_services(pos= pos, addon= addon)

    def app_conf(self, qdmode, qdkey='service', user_jugge=False,  **kw):
        '''从app_conf数据库查询数据'''
        # qdconf配置权重最高
        groupid = self.get_groupid()
        qdcustom = get_qd_conf_value(
            mode=qdmode, key=qdkey, groupid=groupid,
            default_key=int(groupid not in config.QF_GROUPIDS),
            default_val=None
        )
        if qdcustom is not None:
            return qdcustom

        userid = int(self.user.userid)
        custom = get_custom_value(userid, groupid, self.appid, qdmode)
        try:
            custom = json.loads(custom)
        except:
            pass

        return custom

    def rate_conf(self, **kw):
        '''
        获取金额的兑换人民币的比率
        '''
        if get_qd_conf_value(
                groupid = self.get_groupid(), mode = 'rate_control',
                key = 'ext', default = 0
            ):
            qdinfo = get_qudaoinfo(self.get_groupid())

            return rate_cache[qdinfo['currency_sign']]

    def del_pay_sequence(self, value):
        conf = copy.deepcopy(value)
        try:
            actvs = json.loads(HttpClient(config.PREPAID_SERVERS).get(
                path = '/prepaid/v1/api/b/activity_history?pos=0&count=1',
                headers = {'COOKIE': 'sessionid={}'.format(
                    self.get_cookie('sessionid'))}))['data']
            if not actvs and 'prepaid' in conf:
                conf.remove('prepaid')
        except:
            log.warn(traceback.format_exc())

        # 支持刷卡的ua
        user_agent = self._ua.upper()
        for i in UA_CARDS:
            if i in user_agent:
                conf.append('card')
                break

        return conf

    def del_trade_config(self, value):
        '''处理交易流水筛选多语言'''
        if not value:
            return value

        confs = copy.deepcopy(value)

        for conf in confs:
            for k, v in conf.iteritems():
                if k in ('choose_name', 'user_type'):
                    conf[k] = get_constant(v, self._language)
                elif k in ('ptype_name'):
                    conf[k] = [get_constant(i, self._language) for i in v]

        return confs

    _base_err = '系统繁忙'

    @check('login')
    def GET(self):
        self._ua = self.req.environ.get('HTTP_USER_AGENT','')
        log.debug('user_agent:%s userid:%s' % (self._ua, self.user.userid))
        ret = {}

        # app版本号 手机platform
        version, platform = get_app_info(self._ua)
        self._platform = (platform or
                self.req.inputjson().get('platform'))
        self._version = version

        # 获取appid
        self.appid = self.get_appid()

        # 获取语言
        self._language = self.get_language()

        #香港渠道是否可退款
        ret['is_refund'] = 1
        groupid = self.get_groupid()
        if groupid in config.HK_GROUPID:
            opuid = self.user.ses.get("opuid", '')
            cate = self.get_cate()
            if cate == 'submerchant' or opuid:
                ret['is_refund'] = 0

        # 获取配置
        app_conf = config.USER_CONF
        for k,v in app_conf.iteritems():
            if isinstance(v, types.DictType):
                try:
                    mode = v.get('mode', 'mchnt')
                    func = getattr(self, mode+'_conf')
                    value = func(**v)
                    # 版本控制
                    if v.get('app_control'):
                        value = get_value(value, self._platform, self._version)

                    # 如果是pay_sequence, 单独处理
                    if k == 'pay_sequence':
                        value = self.del_pay_sequence(value)

                    # 语言控制
                    if k == 'trade_config':
                        value = self.del_trade_config(value)

                    if value is not None:
                        ret[k] = value
                except:
                    log.debug(traceback.format_exc())

            elif hasattr(config, v):
                ret[k] = getattr(config, v)

        return self.write(success(ret))
