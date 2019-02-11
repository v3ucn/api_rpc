# coding: utf-8

import config
import logging
import re

from util import unicode_to_utf8_ex

from utils.valid import is_valid_int
from utils.tools import check_smscode

from config import PRESMS_FMT
from constants import MOBILE_PATTERN, EMAIL_PATTERN
from excepts import ParamError, ThirdError
from runtime import apcli, smscli, redis_pool, hids

from utils.decorator import check as dec_check, login
from utils.base import BaseHandler
from utils.qdconf_api import get_qd_conf_value
from utils.tools import apcli_ex
from utils.valid import is_valid_mobile

from qfcommon.base.qfresponse import success
from qfcommon.thriftclient.captcha import CaptchaServer
from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.captcha.ttypes import CaptchaException
from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.library.mail import MailSender, MailMessage

log = logging.getLogger()


class Send(BaseHandler):
    '''
    获取验证码, 发验证码
    '''

    _base_err = '获取验证码失败'

    def check_signup(self, mobile):
        '''
        登录验证码验证
        '''
        # 验证手机号是否注册
        user = apcli.user_by_mobile(mobile)
        if user:
            raise ParamError('该手机已经注册')

        # 验证登录信息
        if self.check_login():
            self._groupid = self.get_groupid()

        # saleman_mobile
        d = self.req.input()
        if (not getattr(self, '_groupid', None) and
            'saleman_mobile' in d and  d['saleman_mobile']):
            user = apcli.user_by_mobile(d['saleman_mobile'])
            if user:
                self._groupid = user['groupid']

    def check_reset_pwd(self, mobile):
        user = apcli.user_by_mobile(mobile)
        if not user:
            raise ParamError('该手机号还未注册')

        self._groupid = user['groupid']

    def check_customer(self, mobile):
        '''
        消费者补充会员休息
        '''
        enuserid = self.req.input().get('enuserid')
        if enuserid:
            try:
                userid = hids.decode(enuserid)[0]
            except:
                if not is_valid_int(enuserid):
                    return
                userid = int(enuserid)

            user = apcli('findUserBriefById', userid)
            if user:
                self._groupid = user.groupid

    @login
    def check_modify_username_grant(self, mobile):
        userid = int(self.user.userid)

        user = apcli_ex('findUserBriefById', userid)
        if not user:
            raise ParamError('商户不存在')

        if mobile != user.mobile:
            raise ParamError('账号信息错误, 联系客服更改')

        self._groupid = user.groupid

    @login
    def check_modify_username_verify(self, mobile):
        with get_connection_exception('qf_core') as db:
            new_user = db.select_one('auth_user', where = {'mobile' : mobile})
        if new_user:
            raise ParamError('该手机已经注册')

        userid = int(self.user.userid)
        user = apcli_ex('findUserBriefById', userid)
        if not user:
            raise ParamError('商户不存在')

        self._groupid = user.groupid


    def check(self, mobile, mode):
        if not is_valid_mobile(mobile):
            raise ParamError('手机号码不合法')
        if mode not in PRESMS_FMT:
            raise ParamError('发送验证码模式错误')

        # 验证ip是否受限
        ip = self.req.clientip()
        log.debug('ip:%s' % ip)
        if redis_pool.sismember('_mchnt_api_sms_code_ip_', ip):
            raise ParamError('ip受限')

        # 手机号码是不是频繁获取验证码
        key = '_mchnt_api_sms_code_get_{}_'.format(mobile)
        if int(redis_pool.get(key) or 0) >= config.SMS_CODE_RULE['count_limit']:
            raise ParamError('该手机号频繁获取验证码')
        self._rkey = key

        self._groupid = None
        if mode.startswith('signup'):
            self.check_signup(mobile)
        elif callable(getattr(self, 'check_'+mode, None)):
            getattr(self, 'check_'+mode)(mobile)

    @dec_check()
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        mobile = d.get('mobile')
        mode = d.get('mode', 'signup')

        # 验证信息
        self.check(mobile, mode)

        # 获取验证码
        try:
            smsexpires = config.SMS_CODE_RULE.get('expires', 6*50)
            smslength = config.SMS_CODE_RULE.get('length', 6)
            smsmode = config.SMS_CODE_RULE.get('mode', 1)
            limit_time = config.SMS_CODE_RULE.get('limit_time', 60)
            code = thrift_callex(
                config.CAPTCHA_SERVERS, CaptchaServer,
                'captcha_get_ex', ucode=mobile, src=config.CAPTCHA_SRC,
                expires=smsexpires, length=smslength, mode=smsmode,
                limit_time=limit_time
            )
            log.debug('获取验证码:%s' % code)
        except CaptchaException, e:
            raise ParamError(str(e.respmsg))

        # 短信内容
        groupid = getattr(self, '_groupid', None)
        if 'group' in d and d['group']:
            group = d['group']
        else:
            group = redis_pool.get('_mchnt_api_group_{}_'.format(groupid)) or 'hjsh'
        log.debug('groupid:{} group:{}'.format(groupid, group))

        fmt = PRESMS_FMT.get(mode+'_'+group, PRESMS_FMT[mode])
        csinfo = get_qd_conf_value(
            userid=None, mode=None, key='csinfo', groupid=groupid
        ) or {}
        csinfo = {k: unicode_to_utf8_ex(v) for k,v in csinfo.iteritems()}
        content = fmt.format(code=code, **csinfo)
        log.debug('content:%s' % content)

        # 短信tag
        tags = config.PRESMS_TAG
        tag = tags.get(groupid or group, tags['hjsh'])

        r, respmsg = smscli.sendSms(
            mobile=mobile, content=str(content), tag=tag,
            source='merchant', target=mode
        )
        if not r:
            log.debug('调起发送短信服务失败:%s' % respmsg)
            raise ThirdError('发送验证码失败')

        # 设置获取验证码限制
        if not redis_pool.exists(self._rkey):
            redis_pool.set(self._rkey, 0, config.SMS_CODE_RULE['expire_limit'])
        redis_pool.incr(self._rkey)

        return self.write(success({}))


class Check(BaseHandler):
    '''
    验证码错误
    '''

    _base_err = '验证验证码失败'

    @dec_check()
    def POST(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}

        if d.get('mobile'):
            checkcode = d.get('mobile', '')
            if not re.match(MOBILE_PATTERN, checkcode):
                raise ParamError('手机号码不合法')

        elif d.get('email'):
            checkcode = d.get('email', '')
            if not re.match(EMAIL_PATTERN, checkcode):
                raise ParamError('邮箱不合法')

        else:
            raise ParamError('参数错误')

        code = d.get('code', '')
        if not code:
            raise ParamError('验证码为空')

        # 验证验证码
        if check_smscode(code, checkcode):
            return self.write(success({}))

        raise ParamError('验证码错误')


class EmailCodeSend(BaseHandler):
    '''
    邮政验证码获取
    '''

    _base_err = '获取验证码失败'

    @dec_check()
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        email = d.get('email', '')

        if not re.match(EMAIL_PATTERN, email):
            raise ParamError('邮箱不合法')

        user = None
        with get_connection('qf_core') as db:
            user = db.select_join_one(
                'auth_user', 'profile',
                on = {'auth_user.id' : 'profile.userid'},
                where = {'auth_user.email' : email},
                fields = 'profile.groupid, profile.nickname, profile.userid'
            )
        if not user:
            raise ParamError('邮箱不存在')

        # 邮箱相关配置
        email_conf = get_qd_conf_value(
            mode='email_conf', key='ext',
            groupid=user['groupid'], default = config.EMAIL_CODE_CONF
        )

        # 获取验证码
        try:
            smsexpires = email_conf.get('expires', 6*50)
            smslength = email_conf.get('length', 6)
            smsmode = email_conf.get('mode', 1)
            limit_time = email_conf.get('limit_time', 60)
            code = thrift_callex(config.CAPTCHA_SERVERS, CaptchaServer,
                    'captcha_get_ex', ucode=email, src=config.CAPTCHA_SRC,
                    expires=smsexpires, length=smslength, mode=smsmode,
                    limit_time=limit_time)
            log.debug('获取验证码:%s' % code)
        except CaptchaException, e:
            raise ParamError(str(e.respmsg))

        # 发送验证码
        sender = MailSender(
            email_conf['server'], email_conf['frommail'],
            email_conf['password']
        )

        for k, v in user.iteritems():
            user[k] = unicode_to_utf8_ex(v)

        message = MailMessage(
            email_conf['subject'].format(code=code),
            email_conf['frommail'],
            email, email_conf['content'].format(code = code, **user)
        )

        sender.send(message)

        return success({})
