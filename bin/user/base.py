# coding:utf-8

import types
import time
import traceback
import config
import logging
import copy

from constants import DATETIME_FMT
from util import (
    redis_pool, get_app_info, get_services, get_mchnt_paying
)
from runtime import apcli, hids
from excepts import ThirdError, ParamError

from utils.base import BaseHandler
from utils.payinfo import adjust_payinfo_ex
from utils.qdconf_api import get_qd_conf, get_qd_conf_value
from utils.tools import get_qudaoinfo
from utils.language_api import get_constant

from qfcommon.base.tools import thrift_call
from qfcommon.base.dbpool import get_connection
from qfcommon.thriftclient.finance import Finance

log = logging.getLogger()

redis_new_sign = '_mchnt_api_new_sign_'

APPLY_STATE = {
    'wait_base' : 0, # 等待基本信息
    'wait_voucher' : 1, # 等待上传凭证
    'ing' : 3, # 审核中
    'wait_audit' : 4, # 等待审核
    'pass' : 5, # 审核通过
    'script_fail' : 6, # 自动审核失败，待人工审核
    'refuse' : 7, # 审核拒绝
    'fail' : 8, # 审核失败
    'wait_reaudit' : 9, # 等待复审
    'script_pass' : 10, # 自动审核成功
}


class UserDefine(object):

    # openapi加密
    o2_BASE_MAGIC_NUMBER = 20141314654321L

    # 审核状态
    AUDIT_PREPASS = 1 # 审核通过，但额度偏低
    AUDIT_PASS = 11 # 审核通过
    AUDIT_ING = 2 # 审核中
    AUDIT_FAIL = 3 # 审核驳回

    # 审核title
    AUDIT_STATE_DICT = {
        AUDIT_PREPASS : {
            'title' : '审核通过',
            'info' : ('目前您的交易额度偏低，如需要提高交易额度，请联系'
                    '微信客服，提交你的店铺”营业执照“照片即可。')
        },
        AUDIT_PASS : {'title' : '审核通过'},
        AUDIT_ING  : {
            'title' : '审核中',
            'info' : '正在审核您的信息，审核结果会以推送,短信等方式通知，请你耐心等待。',
        },
        AUDIT_FAIL  : {
            'title' : '审核驳回',
            'info' : '修改审核信息，请与客服联系沟通。',
        }
    }

    # 银行卡审核状态
    BANK_APPLY_WAIT = 1 # 等待处理
    BANK_APPLY_ING = 2 # 审核中
    BANK_APPLY_SUCC = 3 # 审核通过
    BANK_APPLY_CLOSED = 4 # 审核关闭

    # 银行卡同步状态
    BANK_SYNC_NO = 0 # 未同步
    BANK_SYNC_SUCC = 1 # 同步成功
    BANK_SYNC_FAIL = 2 # 同步失败

    # 银行卡审核状态 (返回)
    BANK_APPLY_STATE_ING = 1 # 审核中
    BANK_APPLY_STATE_SUCC = 2 # 审核成功
    BANK_APPLY_STATE_FAIL = 3 # 审核失败

    # 账期列表缓存
    ACCOUNT_PERIOD_CACHE = {}

    # chnlbind tradetype
    CHNLBIND_TYPE = 8 # 微信支付

    # 清算类型
    SETTLE_TYPE_T1 = 1 # t1清算
    SETTLE_TYPE_D1 = 2 # d1清算

    # 划款状态
    SETTLE_STATUS_HAVE = 1 # 已划款
    SETTLE_STATUS_PART_FAIL = 2 # 部分划款 (包含划款失败)
    SETTLE_STATUS_PART = 20 # 部分划款 (不包含划款失败)
    SETTLE_STATUS_NO = 3 # 未划款
    SETTLE_STATUS_FAIL = 4 # 划款失败

    # 商户注册类型
    SIGNUP_USERTYPE_TINY = 1 # 小微商户
    SIGNUP_USERTYPE_PERSON = 2 # 个体工商户
    SIGNUP_USERTYPE_COMPANY = 3 # 企业级商户
    SIGNUP_USERTYPES = SIGNUP_USERTYPE_TINY, SIGNUP_USERTYPE_PERSON, SIGNUP_USERTYPE_COMPANY


    # apply src_type
    SIGNUP_SRCTYPE_TINY = 1 # 小微商户

    # 默认店铺id
    DEFAULT_SHOPTYPE_ID = 324

    # 默认业务员mcc (钱方业务推广)
    DEFAULT_SALEMAN_MCC = 21005

    # 默认商户mcc (其他生活服务)
    DEFAULT_MCC = 8099


    # 凭照对照表
    CERT_TYPE = {
        'idcardfront': 1,  # 身份证正面/法人身份证正面
        'idcardback': 1,  # 身份证背面/法人身份证背面
        'licensephoto': 3,  # 营业执照
        'livingphoto': 6,  # 近期生活照
        'groupphoto': 6,  # 业务员与申请人合影
        'goodsphoto': 7,  # 所售商品/经营场所内景照片
        'shopphoto': 7,  # 经营场所/经营场所外景照片
        'authcertphoto': 9,  # 授权书照片
        'idcardinhand': 10,  # 手持身份证合照
        'signphoto': 10,  # 手写签名照
        'otherphoto': 10,  # 其他凭证照片
        'authidcardfront': 11,  # 被授权法人身份证正面
        'authidcardback': 11,  # 被授权法人身份证背面
        'invoicephoto': 11,  # 发票
        'purchaselist': 11,  # 进货单
        'taxproof': 11,  # 完税证明
        'taxphoto': 18,  # 税务登记证
        'paypoint': 32,  # 收银台照
        'lobbyphoto': 22,  # 财务室或者大堂照
        'authbankcardfront': 33,  # 授权法人银行卡正面
        'authbankcardback': 34,  # 授权法人银行卡背面
        'rentalagreement': 23,  # 租赁协议，产权证明，市场管理方证明/店铺租赁合同
        'orgphoto': 4,  # 组织机构代码证
        'openlicense': 19,  # 开户许可证
        'delegateagreement': 35,  # 业务代理合同或者协议
        'iatacert': 36,  # 航协证
        'insurancecert': 37,  # 经营保险代理业务许可证，保险兼业
        'bankcardfront': 38, #收款银行卡正面照片
        'creditcardfront': 39, #信用卡正面
        'subshopdesc': 40,  # 分店说明
        'authedcardfront': 41,  # 被授权人身份证正面
        'authedcardback': 42,  # 被授权人身份证反面
        'checkstand_weixin': 43,  # 活动收银台照片(微信绿洲)
        'checkstand_alipay': 43,  # 活动收银台照片(支付宝蓝海)
        'checkin_weixin' : 43, # 活动餐饮平台入驻照(微信绿洲)
        'checkin_alipay' : 43, # 活动餐饮平台入驻照(支付宝蓝海)
    }
    # 凭证列表
    CERT_TYPE_LIST = ['idcardfront', 'idcardback', 'licensephoto', 'livingphoto', 'groupphoto',
                      'shopphoto', 'goodsphoto', 'authcertphoto', 'idcardinhand', 'signphoto',
                      'otherphoto', 'authidcardfront', 'authidcardback', 'invoicephoto',
                      'purchaselist', 'taxproof', 'taxphoto', 'paypoint', 'lobbyphoto',
                      'authbankcardfront', 'authbankcardback', 'rentalagreement', 'orgphoto',
                      'openlicense', 'delegateagreement', 'iatacert', 'insurancecert',
                      'bankcardfront', 'creditcardfront', 'subshopdesc', 'authedcardfront', 'authedcardback']

    ACTV_EFFECT_CARD = 1 # 集点活动
    ACTV_EFFECT_SALE = 2 # 特卖活动
    ACTV_EFFECT_BACK_CP = 3 # 消费返红包
    ACTV_EFFECT_SHARE_CP = 30 # 消费分享红包
    ACTV_EFFECT_PUSH_CP = 31 # 分发红包

    ACTV_EFFECTS = [ACTV_EFFECT_CARD, ACTV_EFFECT_SALE, ACTV_EFFECT_BACK_CP,
                    ACTV_EFFECT_SHARE_CP, ACTV_EFFECT_PUSH_CP]

class UserUtil(object):

    @staticmethod
    def get_periods(dates):
        '''缓存账期'''
        if not dates: return

        if not isinstance(dates, (types.ListType, types.TupleType)):
            mode = 'single'
            dates = [dates]

        searchdate = list(set(dates) - set(UserDefine.ACCOUNT_PERIOD_CACHE))

        if searchdate:
            try:
                periods = thrift_call(Finance, 'get_account_period',
                                      config.FINANCE_SERVERS, dates)
                for period in periods:
                    UserDefine.ACCOUNT_PERIOD_CACHE[period.search_date] = period.__dict__
            except:
                log.warn(traceback.format_exc())

        if mode == 'single':
            return UserDefine.ACCOUNT_PERIOD_CACHE.get(dates[0])
        else:
            return {i:UserDefine.ACCOUNT_PERIOD_CACHE[i] for i in dates
                            if i in UserDefine.ACCOUNT_PERIOD_CACHE}

    @staticmethod
    def o2_syssn_encode(syssn):
        char_lib = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        char_list = list(char_lib)
        lenth =  len(char_lib)
        index = 0
        result = []
        rs = syssn

        while(rs > lenth):
            result.append(rs % lenth)
            rs = rs / lenth
            index = index + 1

        result.append(rs)
        ret = ''
        for t in result:
            ret = ret + char_list[t]
        return ret

    @staticmethod
    def get_recharge_info(userid, groupid=None):
        '''获取商户付费信息'''
        # 商户付费情况
        mchnt_info = adjust_payinfo_ex(userid,
                service_code= 'card_actv', groupid=groupid)

        # 付费过期
        if mchnt_info['status'] and mchnt_info['overdue']:
            num = 0
            with get_connection('qf_mchnt') as db:
                num = db.select_one('member', where={'userid': userid},
                                    fields='count(*) as num')['num']
            # 过期提示
            mchnt_info['note'] = (
                '抱歉，您的会员服务已到期，会员功能将无法继续使用，正常收款不受影响。'
                '为保证{num}已有会员的体验，建议尽快续费哦~'.format(
                    num = '%d位'%num if num else '')
            )
            mchnt_info['num'] = num

        return mchnt_info

    @staticmethod
    def get_mcc(mcc_id):
        key = 'mchnt_api_mcc_list'
        return redis_pool.hget(key, mcc_id) or UserDefine.DEFAULT_MCC

    @staticmethod
    def check_profile(**kw):
        r = None
        with get_connection('qf_core') as db:
            r = db.select_join_one('auth_user', 'profile',
                    on = {'auth_user.id' : 'profile.userid'},
                    where=kw, fields='auth_user.id')
        return int(bool(r))

    @staticmethod
    def ret_userinfo(userinfo, user_ext=None, qdinfo=None, **cf):
        r = {
            'mobile' : userinfo['mobile'],
            'userid': userinfo['uid'],
            'profile' : {},
            'shop_info' : {},
            'is_creat_shop': 0,
        }
        # 是否是白牌渠道下的商户
        if 'groupid' in userinfo:
            groupid = userinfo['groupid']
            r['is_bpgroup'] = int(groupid in config.BAIPAI_GROUPIDS)
            r['is_qfgroup'] = int(groupid in config.QF_GROUPIDS)

            r['channel_info'] = get_qd_conf_value(
                    mode=None, key='csinfo', groupid=groupid)
            if qdinfo:
                r['channel_info'].update(qdinfo)
            else:
                r['channel_info'].update(get_qudaoinfo(groupid))

        # 店铺信息
        r['shop_info']['shopname'] = userinfo['shopname']
        r['shop_info']['province'] = userinfo['province']
        r['shop_info']['city'] = userinfo['city']
        r['shop_info']['address'] = userinfo['address']
        r['shop_info']['telephone'] = userinfo['telephone']

        # 用户信息
        r['profile']['uid'] = userinfo['uid']
        r['profile']['mobile'] = userinfo['mobile']
        r['profile']['jointime'] = userinfo['jointime']
        r['profile']['cate'] = cf.get('cate') or 'merchant'
        r['profile']['bind_id'] = userinfo['uid']
        r['profile']['need_change_pwd'] = 0
        if get_qd_conf_value(
                groupid = groupid, key= 'ext', mode = 'change_pwd_control',
                default = 0
            ):
             r['profile']['need_change_pwd'] = int(redis_pool.sismember(
                    redis_new_sign, userinfo['uid']))

        # 如果有线下店铺信息
        if user_ext:
            if (getattr(config, 'NEED_CREATE_USER_EXT', True) and
                not user_ext.shoptype_id):
                r['is_creat_shop'] = 1

            default_head_img = (
                getattr(config, 'BP_DEFAULT_AVATR', '')
                if r.get('is_bpgroup') else config.APP_DEFAULT_AVATR
            )
            r['shop_info']['head_img'] = user_ext.head_img or default_head_img
            r['shop_info']['logo_url'] = user_ext.logo_url or ''

        # 若果有操作员信息
        if 'opinfo' in cf and cf['opinfo']:
            r['opinfo'] = cf['opinfo']

            if getattr(config, 'BIND_OPUSER', True):
                r['profile']['bind_id'] = (
                    int(userinfo['uid'])*10000 +
                    int(cf['opinfo']['opuid'])
                )

        r.update(cf)

        return r

    @staticmethod
    def get_max_opuid(userid):
        '''
        获取商户下目前最大的opuid
        return: 返回一个int型opuid
        '''
        opuid = None
        with get_connection('qf_core') as db:
            opuid = db.select_one(
                    table = 'opuser',
                    fields = 'opuid',
                    where = {'userid': userid},
                    other='order by opuid desc')
        if not opuid:
            return opuid
        return opuid['opuid']


class UserBase(BaseHandler):

    def get_user_cate(self):
        # 获取用户的登录角色
        # bigmerchant大商户 submerchant/merchant商户 opuser操作员
        if self.user.ses.get('opuid'):
            return 'opuser'
        else:
            return self.get_cate()


    #### 九宫格配置相关 ####

    def get_user_services(self, pos='all', addon=None, limit=None):
        '''
        获取用户功能列表
        参数:
            pos all:全部功能 home_page:首页 head: 头部
            addon 功能多加载的数据
            limit 限制数量
        '''
        userid = int(self.user.userid)
        language = self.get_language()

        # 获取用户的信息
        user = apcli('findUserBriefById', userid)
        if not user:
            raise ThirdError('商户不存在')
        user = user.__dict__
        self._user = user

        # 获取用户的登录角色
        user_cate = self.get_user_cate()

        # 获取渠道配置
        qd_conf = get_qd_conf()

        # 用户服务列表
        groupid = user['groupid']
        default_services= get_qd_conf_value(
            userid, 'default', 'service', groupid=groupid,
            default=config.DEFAULT_SERVICES, qd_confs=qd_conf
        )
        user_service = apcli.user_service(userid)
        self._user_service = {i['code'] for i in user_service} | set(default_services)

        # 根据版本号和平台获取服务列表
        version, platform = get_app_info(self.req.environ.get('HTTP_USER_AGENT',''))
        log.info('user_agent:%s version:%s  platform:%s userid:%s' %
            (self.req.environ.get('HTTP_USER_AGENT',''), version, platform, userid))
        sys_services = get_qd_conf_value(
            userid,  'services', 'service',
            groupid=groupid, default=config.SYSTEM_SERVICES,
            qd_confs=qd_conf
        )
        must_addon = [
            'recharge_link', 'group_link', 'condition',
            'dis_groupids', 'nodis_groupids', 'dis_service',
            'dis_condition', 'show_cate'
        ]
        addon = (addon or []) + must_addon
        services = get_services(
            version, platform, addon=addon,
            sys_services=sys_services
        )

        # 调整返回值
        ret = []
        payinfo = None
        user_open_service = {i['code'] for i in user_service}
        for service in services:
            # 若不满足条件, 直接跳过
            if service['code'] not in self._user_service:
                continue

            # 指定角色才展示
            show_cates = service.pop('show_cate') or ['merchant', 'submerchant']
            if user_cate not in show_cates:
                continue

            # 显示位置判断
            tpos = service.pop('pos') or ['all']
            if pos not in tpos:
                continue

            dis_condition = service.pop('dis_condition', None)
            if dis_condition:
                try:
                    if not eval(
                        dis_condition,
                        {'user':user, 'user_open': service['code'] in user_open_service}
                       ):
                        continue
                except:
                    log.warn(traceback.format_exc())
                    continue

            # 条件
            condition = service.pop('condition', None)

            # 渠道link
            group_link = service.pop('group_link', None) # 渠道link

            # 根据grouid配置是否展示
            dis_groupids = service.pop('dis_groupids') or config.QF_GROUPIDS
            nodis_groupids = service.pop('nodis_groupids') or config.QF_GROUPIDS

            # 付费后的链接
            recharge_link = service.pop('recharge_link', None)

            # 余额提现链接
            dis_service = service.pop('dis_service', '')

            # 根据条件判断
            if condition:
                # 如果指定服务存在将不展示
                if ('dis_service' in condition and
                    dis_service in self._user_service):
                    continue

                # 根据渠道判断
                # 白牌渠道不展示
                if 'group_dis' in condition:
                    if groupid in qd_conf:
                        continue

                # 根据渠道id来控制展示
                if 'group_control' in condition:
                    if groupid not in dis_groupids:
                        continue

                # 根据渠道id来控制展示
                if 'nogroup_control' in condition:
                    if groupid in nodis_groupids:
                        continue

                # 白牌渠道link
                if 'group_link' in condition:
                    if groupid in  qd_conf:
                        service['link'] = group_link

                # 开通点餐服务
                if 'diancan_service' in condition:
                    if payinfo is None:
                        payinfo = get_mchnt_paying(userid, code='diancan')
                    if payinfo and str(payinfo['expire_time']) > time.strftime(DATETIME_FMT):
                        service['link'] = recharge_link

            # 链接带上参数
            service['link'] = service['link'].format(**user)

            # name根据语言可控制
            if 'name' in service:
                service['name'] = get_constant(
                    service['name'], language)

            ret.append(service)

        return ret[:limit]

    def get_user_modules(self, pos='all', addon=None, modules=None, **kw):
        '''
        获取用户功能模块
        参数:
            pos all:全部功能 home_page:首页
            addon 功能多加载的数据
            modules 模块(默认config.MODULES)
        '''
        language = self.get_language()
        # 用户所有功能
        services = self.get_user_services(pos, addon)
        services.sort(key=lambda x: x.get('weight', 0), reverse=True)

        # 用户模块定义
        gmodules = get_qd_conf_value(
            None, 'modules', 'service',
            groupid=self.get_groupid(),
            default=config.MODULES,
        )
        modules = copy.deepcopy(modules or gmodules)
        for i in modules:
            i['services'] = []
            if 'name' in i:
                i['name'] = get_constant(
                    i['name'], language)
        module_dict = {module['module']:idx for idx, module in enumerate(modules)}

        # 分组
        for i in services:
            idx = module_dict[i.pop('module', None) or 'default']
            if 'fields' in kw:
                modules[idx]['services'].append({field:i.get(field, '')
                    for field in  kw['fields'] if field != 'tip' or i.get(field)})
            else:
                modules[idx]['services'].append(i)

        return [i for i in modules if i['services']]


    #### 审核相关 ####

    def audit2state(self, audit_state, userid):
        # 审核通过
        if audit_state == APPLY_STATE['pass']:
            # 非自主注册将自动变为审核通过
            groupid = self.get_groupid()
            if groupid != config.SIGNUP_GROUPID:
                return UserDefine.AUDIT_PASS

            # 获取是否有营业执照
            no_licence = None
            with get_connection('qf_core') as db:
                where = {'taggit_tag.name' : '无执照',
                        'taggit_taggeditem.object_id' : userid}
                on = {'taggit_tag.id' : 'taggit_taggeditem.tag_id'}
                no_licence = db.select_join_one('taggit_taggeditem', 'taggit_tag',
                    where=where, fields='count(1) as num', on=on)['num']
            return UserDefine.AUDIT_PREPASS if no_licence else UserDefine.AUDIT_PASS

        # 审核失败
        elif audit_state in (APPLY_STATE['refuse'], APPLY_STATE['fail'],
                APPLY_STATE['wait_reaudit'], APPLY_STATE['script_fail']):
            return UserDefine.AUDIT_FAIL

        # 审核中
        else:
            return UserDefine.AUDIT_ING

    def get_audit_state(self, userid):
        # 获取审核信息
        with get_connection('qf_mis') as db:
            audit = db.select_one(
                'apply',
                where={'user':int(userid)},
                fields='state'
            ) or {}

        audit_state = audit.get('state', APPLY_STATE['pass'])

        return self.audit2state(audit_state, userid)

    def get_cache_audit(self, userid):
        key = 'mchnt_api_audit_state_{}'.format(userid)
        return redis_pool.get(key) or -1

    def set_cache_audit(self, userid, audit_state=None, state=None):
        key = 'mchnt_api_audit_state_{}'.format(userid)
        val = audit_state or self.audit2state(int(state))
        redis_pool.set(key, val, 30*24*3600)

    def get_audit_info(self):
        '''获取审核信息'''
        userid = int(self.user.userid)
        language = self.get_language()
        ret = {}

        # 获取用户审核信息
        ret['audit_state'] = self.get_audit_state(userid)
        title = UserDefine.AUDIT_STATE_DICT[ret['audit_state']]['title']
        ret['audit_title'] = get_constant(title, language)

        # 更新上次缓存的审核信息
        cache_state = self.get_cache_audit(userid)
        audit_update = 0
        if cache_state != -1:
            audit_update = 0 if ret['audit_state'] == int(cache_state) else 1
            self.set_cache_audit(userid, ret['audit_state'])
        ret['audit_update'] = audit_update

        return ret


    #### 辅助类函数 ####

    def get_input_userid(self):
        cate = self.get_cate()
        if cate == 'bigmerchant':
            params = self.req.input()
            if params.get('userid'):
                userid = int(params['userid'])

            elif params.get('enuserid'):
                userid = hids.decode(params['enuserid'])
                if not userid:
                    raise ParamError('商户不存在')

                else:
                    userid = userid[0]

            else:
                return int(self.user.userid)

            link_ids = self.get_link_ids()
            if userid not in link_ids:
                raise ParamError('商户不存在')

            return userid
        else:
            return int(self.user.userid)


    #### 注册辅助类函数 ####

    def add_sign_tag(self, groupid, userid):
        '''
        针对特殊渠道需要将注册商户加入名单内
        '''
        if get_qd_conf_value(
                groupid = groupid, key = 'ext', mode = 'change_pwd_control',
                default = 0
            ):
            redis_pool.sadd(redis_new_sign, userid)

    def kick_sign_tag(self, userid):
        '''
        剔除userid
        '''
        redis_pool.srem(redis_new_sign, userid)
