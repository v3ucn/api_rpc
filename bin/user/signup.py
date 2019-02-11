# coding:utf-8
'''
注册相关接口
注册, 大商户注册, 商户签约信息等
'''

import re
import time
import config
import json
import logging
import traceback

from decimal import Decimal
from excepts import ParamError, ThirdError, SessionError, DBError
from runtime import apcli, redis_pool
from util import (
    check_user, remove_emoji, check_password,
    unicode_to_utf8_ex, covert, get_app_info
)
from constants import DATE_FMT, DATETIME_FMT
from base import UserBase, UserDefine, UserUtil

from utils.tools import check_smscode, re_mobile, apcli_ex, get_qd_mchnt
from utils.decorator import check
from utils.valid import is_valid_int, is_valid_num, is_valid_date

from qfcommon.qfpay.apollouser import ApolloUser
from qfcommon.thriftclient.data_engine import DataEngine
from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.base.qfresponse import success
from qfcommon.server.client import ThriftClient
from qfcommon.thriftclient.qudao import QudaoServer
from qfcommon.thriftclient.qudao.ttypes import MchntRegisteredArg
from qfcommon.base.tools import thrift_callex, thrift_call
from qfcommon.thriftclient.finance import Finance
from qfcommon.thriftclient.finance.ttypes import TradeFeeStruct
from qfcommon.thriftclient.qudao.ttypes import SlsmRegisteredArg
from qfcommon.thriftclient.apollo.ttypes import (
    BankInfo, UserRelation, User, UserCate, UserProfile, UserExt
)
from qfcommon.qfpay.msgpassclient import publish
from qfcommon.thriftclient.audit import AuditServer
from qfcommon.thriftclient.audit.ttypes import Audit as audit_api

log = logging.getLogger()


class ToBigMchnt(UserBase):
    '''
    大商户注册
    '''

    def get_userprofile(self):
        params = self.req.input()
        sls_user = None
        if not re_mobile.match(params.get('username', '')):
            raise ParamError('请用手机号注册')
        user = check_user(params['username'])
        if user['is_signup']:
            raise ParamError('该用户已经注册，请更换手机号')

        if not 6 <= len(params.get('password', '')) <= 20:
            raise ParamError('密码需在6-20位')

        shopname = remove_emoji(params.get('shopname', ''))
        if not shopname:
            raise ParamError('店名不能为空')

        if 'saleman_mobile' in params:
            saleman_mobile = params.get('saleman_mobile', '')
            if not saleman_mobile:
                raise ParamError('推荐人手机号不能为空')
            else:
                sls_user = apcli.user_by_mobile(saleman_mobile)

        else:
            # 签约宝登录信息
            if self.check_login():
                sls_user = apcli.user_by_id(self.user.userid)
                usercates = {i['code'] for i in sls_user.get('userCates', [])}
                if 'saleman' in usercates:
                    saleman_mobile = sls_user.get('mobile', '')
                    if not saleman_mobile:
                        raise ParamError('推荐人手机号不能为空')

        if not sls_user:
            raise ParamError('推荐人身份错误')
        sls_usercates = {i['code'] for i in sls_user.get('userCates', [])}
        if 'saleman' not in sls_usercates:
            raise ParamError('推荐人手机号码错误')
        groupid = sls_user['groupid']
        self._sls_user = sls_user

        # 调解接口商户不验证验证码
        if (not ('code' not in params and self.check_ip()) and
            not check_smscode(
                params.get('code', ''), params['username'], 1
            )):
            raise ParamError('验证码错误')

        p = {}
        p['mobile'] = params['username']
        p['password'] = params['password']
        p['shopname'] = shopname
        p['groupid'] = groupid
        p['userCates'] = [UserCate(code='bigmerchant', name='大商户')]

        return UserProfile(user=User(**p))

    # 设置用户费率
    def _set_user_fee(self, userid):
        try:
            p = config.QPOS_TRADE_FEE
            p['userid'] = int(userid)
            ratios = self.get_ratio()
            if not ratios:return
            p.update(ratios)
            trade_fee = TradeFeeStruct(**p)
            ret = thrift_callex(config.FINANCE_SERVERS, Finance, 'set_trade_fee', trade_fee)
            if ret != 1:
                raise Exception('operate error')
        except:
            log.warn('userid:%s 设置用户费率失败, error:%s' % (userid, traceback.format_exc()))

    def relate_mchnt(self, userid):
        sls_user = getattr(self, '_sls_user', None)
        if not sls_user:return

        try:
            client = ThriftClient(config.QUDAO_SERVERS, QudaoServer, framed=True)
            mchnt_arg = MchntRegisteredArg(
                mchnt_uid=userid, slsm_uid=sls_user['uid'])
            client.mchnt_on_registered(mchnt_arg, -1)
        except:
            log.warn(traceback.format_exc())

    def get_ratio(self):
        '''获取商户上传费率'''
        sls_user = getattr(self, '_sls_user', None)
        if not sls_user:return
        else:
            usercates = {i['code'] for i in sls_user.get('userCates', [])}
            if 'saleman' in usercates:

                # 输入的费率
                fields = ['jdpay_ratio', 'tenpay_ratio', 'feeratio', 'qqpay_ratio',
                          'alipay_ratio', 'creditratio']
                d = {k: v.strip() for k, v in
                        self.req.input().iteritems()}
                input_ratios = {field: float(Decimal(d[field])/100) for field in fields
                                if is_valid_num(d.get(field))}
                log.debug('输入费率:%s' % input_ratios)

            else:
                input_ratios = ''
        return input_ratios

    _base_err = '注册大商户失败'

    @check()
    def POST(self):
        userprofile = self.get_userprofile()

        # 当商户已经注册时，提示错误
        userid, respmsg = apcli.signup(userprofile, allow_exist=False)

        # 如果调apollo失败
        if respmsg:
            raise ThirdError(respmsg)

        # 如果注册成功
        elif userid:
            #签约宝入网设置费率
            if self.check_login():
                self._set_user_fee(userid)

            # 绑定渠道商户关系
            self.relate_mchnt(userid)

            # 添加注册标志
            self.add_sign_tag(userprofile.user.groupid, userid)

        return success({'userid': userid})


class Ratio(UserBase):
    '''
    获取用户费率
    '''

    _base_err = '获取签约信息失败'

    @check('login')
    def GET(self):
        # userid = self.get_input_userid()
        params = self.req.input()
        if params.has_key('enuserid'):
            userid = params.get('enuserid')
            try:
                userid = int(userid)
            except:
                raise ParamError('enuserid参数错误')
        else:
            userid = int(self.user.userid)
        log.info('userid:%s' % userid)
        try:
            ret = thrift_call(
                Finance, 'get_trade_fee',
                config.FINANCE_SERVERS, userid=int(userid), src=''
            )
            log.debug('ret:%s' % ret)
        except:
            log.warn('finance error:%s' %  traceback.format_exc())
            raise ParamError('获取签约信息失败')

        ratios = []
        for i in config.RATIOS:
            ratio = getattr(ret, i['key'], '')
            extra_ratios = config.RATIO_CONF.get(i['key']+'_extra', [])

            if ratio in extra_ratios:
                ratio = config.RATIO_CONF.get(
                    i['key']+'_extra_name', '特殊费率')
            else:
                ratio = str(ratio*100)+'%' if ratio else ''

            ratios.append({
                'url': i['url'],
                'name': i['name'],
                'ratio': ratio
            })

 	return success({'ratios': ratios})


class Audit(UserBase):
    '''
    获取审核信息
    '''

    _base_err = '获取审核信息失'

    @check('login')
    def GET(self):
        # userid = self.get_input_userid()
        params = self.req.input()
        if params.has_key('enuserid'):
            userid = params.get('enuserid')
            try:
                userid = int(userid)
            except:
                raise ParamError('enuserid参数错误')
        else:
            userid = int(self.user.userid)

        amt_per_wxpay = -1
        # 获取每笔限额
        try:
            is_display = int(redis_pool.get('mchnt_api_audit_display') or 0)
            if is_display:
                ret = thrift_call(DataEngine, 'get_risk_param',
                    config.DATAENGINE_SERVERS, int(userid), '', 0x02)
                amt_per_wxpay = ret.user_param.param_list.param.get('amt_per_wxpay', 0)
        except:
            log.debug(traceback.format_exc())

        # 获取审核信息
        state = self.get_audit_state(userid)
        audit_info = {'info':'', 'title':'', 'memo':'', 'state':state}
        audit_info.update(UserDefine.AUDIT_STATE_DICT.get(state, {}))
        if state == UserDefine.AUDIT_FAIL:
            r = {}
            with get_connection('qf_mis') as db:
                other = 'order by create_date desc'
                where = {'user_id' : int(userid)}
                r = db.select_one('mis_auditlog', where= where, other=other) or {}
            audit_info['memo'] = r.get('memo', '')
        # 更新审核状态
        self.set_cache_audit(userid, state)

        return success({
            'amt_per_wxpay' : amt_per_wxpay,
            'audit_info' : audit_info
        })


class SignBase(UserBase):
    '''
    注册相关辅助类
    '''

    def get_src(self):
        if hasattr(self, '_src'):
            return self._src

        useragent = self.req.environ.get('HTTP_USER_AGENT','')
        log.debug('useragent:%s' % useragent)

        # 通过useragent判断
        version, platform = get_app_info(useragent)
        if platform:
            self._src = 'mchnt'
            return 'mchnt'

        # 通过上传值判断
        input_src = self.req.input().get('src')
        if not input_src:
            if 'QYB' in useragent:
                self._src = 'salesman'
            else:
                self._src = 'mchnt'
        else:
            self._src = input_src
        return self._src

    def get_big_uid(self):
        params = self.req.input()
        src = self.get_src()
        log.debug('src:%s' % src)

        # 验证登录
        if not self.check_login():
            raise SessionError('用户未登录')

        if src == 'salesman':
            if not is_valid_int(params.get('big_uid')):
                raise ParamError('参数错误')
            sm_uid = self.user.userid
            cates = apcli(
                'getUserCategory', int(sm_uid), ''
            ) or []
            cates = [i.code for i in cates]
            if 'saleman' not in cates and 'qudao' not in cates:
                raise ParamError('该用户非业务员')

            big_cates = apcli(
                'getUserCategory', int(params['big_uid']), ''
            ) or []
            big_cates = [i.code for i in big_cates]
            if 'bigmerchant' not in big_cates:
                raise ParamError('非大商户')

            return int(params['big_uid'])

        else:
            if self.get_cate() != 'bigmerchant':
                raise ParamError('非大商户')
            return int(self.user.userid)


class PreSignup(SignBase):
    '''
    注册时预注册
    '''

    _base_err = '预注册失败'

    def username_mchnt(self):
        '''商户预注册'''
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        self.req.inputjson()['password'] = '*****'
        # 验证用户名
        username = d.get('username', '')
        if not username:
            raise ParamError('用户名为空')

        # 验证验证码
        code = d.get('code', '')
        if not check_smscode(code, username):
            raise ParamError('验证码错误')

        # 验证是否注册
        if UserUtil.check_profile(**{'auth_user.username' : username}):
            raise ParamError('商户已经注册')

        # 获取userid
        user = None
        with get_connection('qf_core') as db:
            user = db.select_one('auth_user',
                    where={'mobile':username},
                    fields='id, password')
            log.debug(user)
        if user:
            if (user['password'] and
                not check_password(d.get('password', ''), user['password'])):
                raise SessionError('该账号已经设置密码')
            return d['username'], user['id']
        return d['username'], None


    def username_bigmchnt(self):
        '''大商户预注册子商户'''
        userid = self.get_big_uid()

        prefix = '9' + '0'*max(0, 8-len(str(userid))) + str(userid)

        with get_connection_exception('qf_core') as db:
            auser = db.select_one('auth_user',
                    where= {
                        'username': ('like', '{}%%'.format(prefix)),
                    },
                    fields= 'username',
                    other=  'order by username desc') or {}
        username = auser.get('username', '{}0000'.format(prefix))
        next_username = '{prefix}{no:04d}'.format(
            prefix= prefix, no= int(username[-4:] or 0) + 1)

        return next_username

    @check()
    def POST(self):
        mode = self.req.inputjson().get('mode', 'mchnt')

        userid = None
        # 普通商户预注册
        # 验证验证码
        if mode == 'mchnt':
            username, userid = self.username_mchnt()

        # 大商户预注册子商户
        # 验证登录状态
        elif mode == 'bigmchnt':
            username = self.username_bigmchnt()

        else:
            raise ParamError('该摸式不支持预注册')

        if not userid:
            userid = apcli_ex('preRegister', username, '', '')
            if not userid:
                raise DBError('预注册失败')

        enuserid = UserUtil.o2_syssn_encode(
            int(userid) +
            UserDefine.o2_BASE_MAGIC_NUMBER
        )

        return success({'userid' : enuserid, 'username': username})


class Signup(SignBase):
    '''
    用户注册
    '''

    def check_mchnt(self, data):
        ''' 注册成为商户

        来源分为: 商户平台(bigmchnt), 签约宝(salesman), 商户app(mchnt)

        1. 都需要验证验证码

        2. 只允许指定来源的的商户成为业务员

        '''
        # 验证验证码
        code = data.get('code')
        if not code:
            raise ParamError('验证码不能为空')
        if not check_smscode(code, data['username'], 1):
            raise ParamError('验证码错误')

        # 注册来源
        src = self.get_src()

        # 业务员手机号
        check_sls_user = False
        saleman_mobile = data.get('saleman_mobile')
        if saleman_mobile:
            sls_user = apcli.user_by_mobile(saleman_mobile) or {}
            check_sls_user = True

        # 签约宝登录信息
        elif self.check_login():
            sls_user = apcli.user_by_id(self.user.userid)
            check_sls_user = True
            self._qd_login = True

        if src == 'salesman':
            self._data['src'] = '签约宝'

        if not check_sls_user: return

        # 推荐人信息
        sls_usercates = {i['code'] for i in sls_user.get('userCates', [])}
        if not ({'saleman', 'qudao'} & sls_usercates):
            raise ValueError('推荐人手机号码错误')
        self._data['groupid'] = sls_user['groupid']
        if 'qudao' in sls_usercates:
            allow_sm_signup_src = getattr(
                config, 'ALLOW_SM_SIGNUP_SRC', ['mchnt', 'salesman']
            )
            if src in allow_sm_signup_src:
                self._data['cate'] = 'saleman'
                self._data['src'] = self._data['src'] + '-业务员注册'
                self._data['saleman_uid'] = sls_user['uid']

        elif 'saleman' in sls_usercates:
            self._data['saleman_uid'] = sls_user['uid']
            self._data['cate'] = 'mchnt'

    def check_bigmchnt(self, data):
        '''大商户注册子商户
        来源分为: 商户平台(bigmchnt), 签约宝(salesman), 商户app(mchnt)

        如果是签约宝, 需要传入big_uid
        '''
        self._big_uid = userid = self.get_big_uid()
        prefix = '9' + '0'*max(0, 8-len(str(userid))) + str(userid)
        if not re.match('%s\d{4}' % prefix, data['username']):
            raise ParamError('子商户账号命名不合规')

        # 注册来源
        src = self.get_src()
        # 签约宝
        if src == 'salesman':
            self._data['src'] = '签约宝-大商户入网子商户'
            sm_uid = int(self.user.userid)

        # 商户平台
        else:
            self._data['src'] = '商户平台-大商户入网子商户'
            qdmchnt = get_qd_mchnt(userid)
            log.debug(qdmchnt)
            sm_uid = qdmchnt and qdmchnt.slsm_uid

        # 注册商户的业务员信息
        # 若业务员存在
        if sm_uid:
            sls_user = apcli.user_by_id(sm_uid)
            self._data['saleman_uid'] = sls_user['uid']
            self._data['groupid'] = sls_user['groupid']

        # 否则保持和大商户一样
        else:
            big_user = apcli.user_by_id(userid)
            self._data['groupid'] = big_user['groupid']

    def check_entry(self):
        data = {k:v.strip() for k, v in
            self.req.input().iteritems()}

        # 默认数据
        self._data = {
            'groupid': config.SIGNUP_GROUPID,
            'saleman_uid': 0,
            'src': '好近自主注册',
            'cate': 'mchnt',
            'password': '',
        }

        # 凭证字段
        voucher_fields = [
            'shopphoto', 'goodsphoto'
        ]

        # 地址字段
        addr_fields = [
            'province', 'city', 'address', 'location',
            'shopname', 'shoptype_id'
        ]

        # 必传字段
        for i in ('username', 'idnumber', 'headbankname',
                  'bankuser', 'bankaccount', 'bankprovince',
                  'bankcity', 'bankname', 'bankcode'):
            if i not in data:
                raise ParamError('请将账户信息填充完整')
            else:
                self._data[i] = data[i]

        # 非必传字段
        for i in ['name', 'landline', 'longitude',
                  'latitude', 'banktype', 'bankmobile',
                  'idstatdate', 'idenddate', 'provinceid',
                  'location', 'regionid', 'address',
                  'udid', 'head_img', 'logo_url',
                  'legalperson', 'password', 'licensenumber',
                  'subshopdesc', 'authedcardfront', 'authedcardback',
                  'idcardfront', 'idcardback', 'idcardinhand'
                  ] + addr_fields + voucher_fields:
            self._data[i] = data.get(i, '')

        # 处理密码
        if not data.get('password'):
            self._data['password'] = re.sub(
                    '\D', 'X', data['idnumber'][-6:], 6)
        if not 6 <= len(self._data['password']) <= 20:
            raise ParamError('密码应在6到20位!')

        # 验证是否注册
        if UserUtil.check_profile(
                **{'auth_user.username' : data['username']}):
            raise ParamError('该用户已经注册')

        # 商户shoptype_id
        if not is_valid_int(self._data['shoptype_id']):
            self._data['shoptype_id'] = UserDefine.DEFAULT_SHOPTYPE_ID
        else:
            self._data['shoptype_id'] = int(self._data['shoptype_id'])

        # 商户类型
        usertype = data.get('usertype', UserDefine.SIGNUP_USERTYPE_TINY)
        if int(usertype) not in UserDefine.SIGNUP_USERTYPES:
            raise ParamError('商户注册类型错误')
        self._data['usertype'] = int(usertype)

        self._mode = data.get('mode', 'mchnt')
        func = getattr(self, 'check_'+self._mode)
        if not func:
            raise ParamError('注册模式不支持')
        func(data)

        name = (self._data['name'] or self._data['legalperson'] or
                self._data['bankuser'] or self._data['shopname'])
        # 如果是注册成为商户
        # voucher_fields 和 addr_fields 是必填字段
        if self._data['cate'] == 'mchnt':
            for i in voucher_fields:
                if not data.get(i):
                    raise ParamError('凭证请上传完整')

            for i in addr_fields:
                if i not in data:
                    raise ParamError('请将店铺地址相关信息上传完整')
            self._data['name'] = name

        # 注册成为业务员
        else:
            self._data['name'] = name
            self._data['shopname'] = '业务员' + (data.get('shopname') or name)

        # 省名,城市名
        self._data['province'] = (data.get('province') or
                self._get_province(data.get('provinceid')))
        self._data['city'] = (data.get('city') or
                self._get_city(data.get('provinceid')))
        self._data['bankprovince'] = (
                data.get('bankprovince') or self._data['province'])

    def _get_province(self, provinceid):
        '''由provinceid获取省份'''
        if not provinceid or not is_valid_int(provinceid[:2]):
            return ''

        area = None
        with get_connection('qf_mis') as db:
            area = db.select_one(
                    'tools_area',
                    where= {
                        'area_no': int(provinceid[:2]),
                        'area_display': 1,
                    },
                    fields= 'area_name')
        area = (area or {}).get('area_name', '')
        return unicode_to_utf8_ex(area)

    def _get_city(self, provinceid):
        '''由provinceid获取市'''
        if not provinceid or not is_valid_int(provinceid):
            return ''

        city = None
        with get_connection('qf_mis') as db:
            city = db.select_join_one(
                    'tools_areacity tac', 'tools_area ta',
                    on= {'tac.area_id': 'ta.id'},
                    where= {
                        'area_display': 1,
                        'city_display': 1,
                        'ta.area_no': int(provinceid[:2]),
                        'tac.city_no': ('in', (provinceid[:2], provinceid[:4], provinceid))
                    },
                    fields= 'city_name')
        city = (city or {}).get('city_name', '')
        return unicode_to_utf8_ex(city)

    # 用户信息
    def get_UserProfile(self):
        d = self._data

        # 用户基本信息
        user = User(
            idnumber = d['idnumber'], # 身份证'
            name = d['name'], # 用户名
            mobile = d['username'], # 用户名
            password = d['password'], # 密码
            province  = d['province'], # 省份
            city = d['city'], # 市
            shopname = d['shopname'], # 店铺名
            telephone = d['landline'], # 座机号码
            address = ''.join([d['city'], d['location'], d['address']]),  # 地址
            longitude = covert(d['longitude'] or '0.0', float),  # 经度
            latitude = covert(d['latitude'] or '0.0', float),   # 纬度
            risklevel = config.RISKLEVEL
        )

        # 清算银行信息
        bankInfo = BankInfo(
            headbankname = d['headbankname'], # 总行名称
            bankuser = d['bankuser'], # 开户名
            bankaccount = d['bankaccount'].replace(' ', ''), # 开户银行号
            bankProvince = d['bankprovince'], # 支行所属省份
            bankCity = d['bankcity'], # 支行所属城市
            bankname = d['bankname'], # 支行名称
            bankcode = d['bankcode'], # 开户联行号
            banktype = (2 if d['banktype'] == '2' else 1), # 账户类型
            bankmobile = d['bankmobile'] # 预留手机号码
        )

        return UserProfile(user=user, bankInfo=bankInfo)

    # 添加店铺额外信息
    def add_user_ext(self, userid):
        data = self._data
        user_ext = UserExt(
            uid = int(userid),
            shoptype_id = data['shoptype_id'],
            contact = data.get('landline', ''),
            head_img = data.get('head_img'),
            logo_url = data.get('logo_url'),
        )
        if is_valid_int(data.get('regionid')):
            user_ext.regionid = int(data['regionid'])

        apcli_ex('bindUserExt', user_ext)


    def get_ratio(self):
        '''获取商户上传费率'''
        def get_input_ratios():
            # 输入的费率
            data = self.req.input()
            return {
                field: float(Decimal(data[field])/100)
                for field in ratio_fields if is_valid_num(data.get(field))
            }

        def get_bigmchnt_ratios():
            userid = int(self._big_uid)
            fee = thrift_call(Finance, 'get_trade_fee',
                    config.FINANCE_SERVERS, userid=int(userid), src='')
            log.debug(fee)
            if not fee: return ''

            return {
                field: getattr(fee, field)
                for field in ratio_fields if hasattr(fee, field)
            }

        ratio_fields = [
            'jdpay_ratio', 'tenpay_ratio', 'debit_ratio',
            'qqpay_ratio', 'alipay_ratio', 'credit_ratio'
        ]
        ratios = ''
        try:
            if getattr(self, '_qd_login', False):
                ratios = get_input_ratios()

            # 未设置费率, 取大商户费率
            if not ratios and getattr(self, '_big_uid', None):
                ratios = get_bigmchnt_ratios()

            # 未设置费率, 取渠道默认费率
            if not ratios and self._data['cate'] == 'saleman':
                ratios = getattr(
                    config, 'SALESMAN_RATIOS',
                    {'alipay_ratio' : '0.0038', 'tenpay_ratio' : '0.0038'}
                )

            log.info('设置费率:%s' % ratios)
        except:
            log.warn(traceback.format_exc())

        return json.dumps(ratios) if ratios else ''



    def auto_apply(self, userid):
        data = self._data
        td, now = time.strftime(DATE_FMT), time.strftime(DATETIME_FMT)
        #新审核系统预设参数
        info = {}
        #凭证参数
        piclist = []

        # 字典转码
        def byteify(input):
            if isinstance(input, dict):
                return {byteify(key): byteify(value) for key, value in input.iteritems()}
            elif isinstance(input, list):
                return [byteify(element) for element in input]
            elif isinstance(input, unicode):
                return input.encode('utf-8')
            else:
                return input

        # 写入凭证
        with get_connection('qf_mis') as db:
            d = {k:v.strip() for k, v in
                self.req.input().iteritems()}
            cert_types = UserDefine.CERT_TYPE
            for code in UserDefine.CERT_TYPE_LIST:
                if (code not in d or not d[code] or
                    code not in cert_types):
                    continue
                insert_data = {
                    'user_id': userid, 'upgrade_id': 0, 'apply_level': 0,
                    'cert_type': cert_types[code], 'name': code, 'submit_time': now,
                    'state': 1, 'input_state': 1, 'typist_user' : 0,
                    'typist_time': now, 'imgname': d[code]
                }

                try:
                    piclist.append({"name":str(code),"src":str(d[code]),"cert_type":str(cert_types[code])})
                    db.insert('mis_upgrade_voucher', insert_data)
                except:
                    log.debug(traceback.format_exc())

        info["piclist"] = piclist

        # 写入审核
        version, platform = get_app_info(self.req.environ.get('HTTP_USER_AGENT',''))
        src = ''.join([data['src'], platform, version])
        idstatdate = (data['idstatdate']
                      if is_valid_date(data.get('idstatdate'))
                      else td)
        idenddate = (data['idenddate']
                     if is_valid_date(data.get('idenddate'))
                     else td)

        # mcc
        if data['cate'] == 'saleman' and not data['shoptype_id']:
            mcc = UserDefine.DEFAULT_SALEMAN_MCC
        else:
            mcc = UserUtil.get_mcc(data['shoptype_id'])

        apply_values = {
            'user' : int(userid), 'usertype' : data['usertype'],
            'legalperson' : data['legalperson'] or data['bankuser'],
            'name' : data['name'], 'idnumber' : data['idnumber'],
            'idstatdate' : idstatdate, 'idenddate' : idenddate,
            'telephone': data['landline'], 'idphoto1' : data['idcardfront'],
            'idphoto2' : data['idcardback'], 'licenseend_date' : td,
            'licensephoto':'', 'taxenddate' : td,
            'longitude' : covert(data['longitude'], float),
            'latitude' : covert(data['latitude'], float),
            'address' : ''.join([data['city'],
                    data['location'], data['address']]),
            'city' : data['city'], 'province' : data['province'],
            'mobile' : data['username'], 'headbankname' : data['headbankname'],
            'banktype' : (2 if data['banktype'] == '2' else 1),
            'bankname' : data['bankname'], 'bankuser' : data['bankuser'],
            'bankProvince' : data['bankprovince'], 'bankCity' : data['bankcity'],
            'bankaccount' : data['bankaccount'].replace(' ', ''), 'state' : 4,
            'brchbank_code' :  data['bankcode'], 'mcc' : mcc,
            'nickname' : data['shopname'],
            'src' : src, 'groupid' : data['groupid'],
            'srctype': UserDefine.SIGNUP_SRCTYPE_TINY, # 先固定为小微商户
            'edu': 1, 'monthincome': 0, 'monthexpense': 0, 'tid':'',
            'terminalcount': 1, 'last_admin': 0, 'allowarea': 0,
            'needauth': 2, 'passcheck': 2, 'last_modify' : now,
            'post' : '', 'provision' : '',
            'bankmobile' : data['bankmobile'],
            'monthtradeamount': 1,  'founddate' : td, 'area': 100,
            'payment_type': 1, 'rent_count': 0, 'pertradeamount': 1,
            'rent_total_amt': -1, 'utime' : now, 'uploadtime' : now,
            "licensenumber": data.get("licensenumber", "")
        }

        # 获取上传费率
        apply_values['ratio'] = self.get_ratio() or ''

        #收集后台需要的字段,摒弃废弃字段，后期只用下面的字段
        userid = int(userid)
        groupid = int(data['groupid'])

        info["usertype"] = data['usertype']
        info["mobile"] = data['username']
        info["name"] = data['name']
        info["cardstart"] = data['idstatdate']
        info["cardend"] = data['idenddate']
        info["legalperson"] = data['legalperson'] or data['bankuser']
        info["src"] = data['src']
        info["licensenumber"] = data['licensenumber']
        info["mcc"] = mcc
        info["risk_level"] = "54"
        info["telephone"] = data['landline']
        info["nickname"] = data['shopname']
        info["bankaccount"] = data['bankaccount'].replace(' ','')
        info["shop_province"] = data['province']
        info["shop_city"] = data['city']
        info["shop_address"] = data['address']
        info["banktype"] = (2 if data['banktype'] == '2' else 1)
        info["bankname"] = data['bankname']
        info["bankuser"] = data['bankuser']
        info["headbankname"] = data['headbankname']
        info["bankcode"] = data['bankcode']

        fee = self.get_ratio() or ''
        if fee != '':
            fee = json.loads(fee)
            for (k, v) in fee.items():
                info[k] = v

        info = byteify(info)
        info = json.dumps(info, ensure_ascii=False)

        #指定的灰度渠道下商户进入新审核逻辑
        if groupid in config.NEW_AUDIT_GROUP:
            client = ThriftClient(config.AUDIT_SERVERS,AuditServer,framed=False)
            client.raise_except = True
            re = client.call('add_audit',audit_api(audit_type='signup', userid=userid, groupid=groupid,info=info))

        #其他渠道的商户继续老的审核系统
        else:
            with get_connection('qf_mis') as db:
                db.insert('apply', apply_values)

        self.set_cache_audit(userid, 2)

    # 调整注册成功返回值
    def adjust_ret(self, userid):
        data = self._data
        ret = {}
        try:
            # 存储session
            user = ApolloUser(userid, expire=86400*7)
            user.ses['chnlid'] = 0
            user.ses['groupid'] = data['groupid']
            user.ses['udid'] = data.get('udid', '')
            user.login(userid)
            user.ses.save()
            sessionid = user.ses._sesid

            # 用户信息
            userinfo = {i:data.get(i, '') for i in
                ('shopname', 'province', 'city', 'address', 'username')}
            userinfo['groupid'] = data['groupid']
            userinfo['mobile'] = userinfo['username']
            userinfo['uid'] = userid
            userinfo['jointime'] = time.strftime('%Y-%m-%d %H:%M:%S')
            userinfo['telephone'] = data.get('landline') or ''

            # 返回登录的信息
            ret = UserUtil.ret_userinfo(
                userinfo, sessionid=sessionid, is_creat_shop=0)
            ret['shop_info']['head_img'] = (
                    data.get('head_img', '') or config.APP_DEFAULT_AVATR)
            ret['shop_info']['logo_url'] = data.get('logo_url') or ''
        except:
            log.debug(traceback.format_exc())
            ret = {}

        return ret

    def relate_mchnt(self, userid):
        '''绑定渠道或者业务员'''
        if not self._data['saleman_uid']:
            return

        try:
            client = ThriftClient(config.QUDAO_SERVERS, QudaoServer, framed=True)
            if self._data['cate'] == 'saleman':
                slsm_arg = SlsmRegisteredArg(
                    slsm_uid=userid, qd_uid=self._data['saleman_uid'])
                client.slsm_on_registered(slsm_arg, -1)

            elif self._data['cate'] == 'mchnt':
                mchnt_arg = MchntRegisteredArg(
                    mchnt_uid=userid, slsm_uid=self._data['saleman_uid'])
                client.mchnt_on_registered(mchnt_arg, -1)
        except:
            log.warn(traceback.format_exc())

    _base_err = '用户注册失败'

    @check()
    def POST(self):
        # 验证并获取用户和业务员信息
        self.check_entry()

        # apollo signup
        userprofile = self.get_UserProfile()
        userid, respmsg = apcli.signup(
            userprofile, self._data['saleman_uid'])

        # 如果调apollo失败
        if respmsg:
            raise ThirdError(respmsg)

        # 如果注册成功
        elif userid:
            # 如果是大商户
            # 需要自动绑定子商户
            if self._mode == 'bigmchnt':
                apcli_ex('setUserRelation',
                    int(self._big_uid),
                    [UserRelation(int(userid), 'merchant')]
                )

            # 添加补充信息
            self.add_user_ext(userid)

            # 自动过审
            self.auto_apply(userid)

            # 绑定渠道商户关系
            self.relate_mchnt(userid)

            # 添加注册标志
            self.add_sign_tag(self._data['groupid'], userid)

            # 分发注册成功信息
            publish(
                config.SIGNUP_MSGPASS_KEY, json.dumps({'userid': userid}),
            )

            return success(self.adjust_ret(userid))
        else:
            raise ParamError('用户注册失败')
