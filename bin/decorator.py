# encoding: utf-8

import time
import types
import json
import uuid
import redis
import traceback
import config
import logging
log = logging.getLogger()

from constants import OPERATE_TYPE
from excepts import MchntException, ParamError
from util import openid2userid,getid,slsm_is_enable

from qfcommon.web.validator import Validator
from qfcommon.qfpay.qfresponse import error,QFRET
from qfcommon.qfpay.apollouser import ApolloUser
from qfcommon.qfpay.apollouser import user_from_session
from qfcommon.base.http_client import RequestsClient
from qfcommon.base.dbpool import get_connection

def with_validator():
    '''
    参数合法验证
    params:
        _validator_fields: class里, 需要验证的参数
        _validator_errfunc: class里, 出现错误的处理函数,
                            默认直接返回ParamError
    returns:
        当参数验证错误时, 会直接返回ParamError
    '''
    def _(func):
        def __(self, *args, **kwargs):
            fields = getattr(self, '_validator_fields')
            errfunc = getattr(self, '_validator_errfunc', None)
            vdt = Validator(fields)
            self.validator = vdt
            ret = vdt.verify(self.req.input())
            if ret:
                if not errfunc:
                    return self.write(
                        error(
                            errcode = QFRET.PARAMERR,
                            respmsg = '参数错误:%s' % ', '.join(ret)
                        )
                    )
                else:
                    return errfunc(self, ret)
            return func(self, *args, **kwargs)
        return __
    return _

def keep_operate(_type=None):
    def _(func):
        def __(self, *args, **kwargs):
            operate_type = _type or getattr(self, 'operate_type', None)
            if operate_type not in OPERATE_TYPE:
                raise ParamError('操作类型错误')

            d = {k:v.strip() for k, v in self.req.input().iteritems()}
            # 操作userid
            op_userid = d.get('op_userid')
            if not op_userid:
                raise ParamError('操作userid不能为空')
            op_userid = int(op_userid)

            # 执行函数
            ret = func(self, *args, **kwargs)

            # 所有的参数
            content = json.dumps(d)
            now = int(time.time())
            # 操作记录表
            with get_connection('qf_mchnt') as db:
                indata = {'id': getid(), 'userid': d['op_userid'],
                        'type': operate_type, 'content': content, 'ctime': now}
                db.insert('operate', indata)

            return ret
        return __
    return _

def raise_excp(info='参数错误'):
    def _(func):
        def __(self, *args, **kwargs):
            try:
                # 错误信息
                module_name = getattr(self, '__module__', '')
                class_name  = getattr(getattr(self, '__class__', ''), '__name__', '')
                func_name   = getattr(func, '__name__', '')
                errinfo = '%s %s %s' % (module_name, class_name, func_name)

                return func(self, *args, **kwargs)
            except MchntException, e:
                log.warn('[%s] error: %s' % (errinfo, e))
                return self.write(error(e.errcode, respmsg=e.errmsg))
            except:
                log.warn('[%s] error:%s' % (errinfo, traceback.format_exc()))
                return self.write(error(QFRET.PARAMERR, respmsg=info))
        return __
    return _

def login_or_ip(func):
    def _(self, *args, **kwargs):
        def ck_sid():
            try:
                sessionid = self.get_cookie('sessionid')
                self.user = ApolloUser(sessionid=sessionid)
                if not self.user.is_login():
                    return False
                self._ck_mode = 'sid'
                return True
            except:
                return False

        def ck_ip():
            try:
                ips = ['192.30.*.*', '192.10.*.*', '127.0.0.1','172.100.*.*']
                remote_ip = self.req.clientip()
                self._ck_mode = 'ip'
                for ip in ips:
                    index = ip.find('*')
                    if index == -1:
                        if remote_ip == ip:
                            return True
                    elif remote_ip[:index - 1] == ip[:index - 1]:
                        return True
            except:
                return False

        try:
            if ck_sid() or ck_ip():
                ret = func(self, *args, **kwargs)

                if self._ck_mode == 'sid':
                    if self.user.ses.data:
                        self.user.ses.save()
                return ret
        except:
            log.warn('check_login error: %s' % traceback.format_exc())
        return self.write(error(QFRET.SESSIONERR))
    return _

def check_ip(p=None):
    p = (p or getattr(config, 'IP_LIMIT', None) or
         ('192.30.*.*', '192.10.*.*', '127.0.0.1','172.100.*.*'))
    def _deco(func):
        def __deco(self, *args, **kwargs):
            ips = p if isinstance(p, (types.TupleType, types.ListType)) else [p]

            if not ips:
                return func(self, *args, **kwargs)

            remote_ip = self.req.clientip()
            for ip in ips:
                index = ip.find('*')
                if index == -1:
                    if remote_ip == ip:
                        return func(self, *args, **kwargs)
                elif remote_ip[:index - 1] == ip[:index - 1]:
                    return func(self, *args, **kwargs)

            self.set_headers({'Content-Type': 'application/json; charset=UTF-8'})
            return self.write(error(QFRET.IPERR, data={'ip': remote_ip}, escape=False))
        return __deco
    return _deco

def with_user(func):
    def _(self, *args, **kwargs):
        sessionid = self.get_cookie('sessionid')
        self.user = user_from_session(sessionid, load_now = False)
        ret = func(self, *args, **kwargs)
        if self.user.ses.data:
            self.user.ses.save()
        return ret
    return _

def check_login(func):
    def _(self, *args, **kwargs):
        try:
            sessionid = self.get_cookie('sessionid')
            self.user = ApolloUser(sessionid=sessionid)
            if not self.user.is_login():
                return self.write(error(QFRET.SESSIONERR))

            ret = func(self, *args, **kwargs)
            if self.user.ses.data:
                self.user.ses.save()
            return ret
        except:
            log.warn('check_login error: %s' % traceback.format_exc())
            return self.write(error(QFRET.SESSIONERR))
    return _

def check_login_ex(prefunc=None, postfunc=None):
    '''验证登录'''
    def _(func):
        def __(self, *args, **kwargs):
            try:
                sessionid = self.get_cookie('sessionid')
                self.user = ApolloUser(sessionid=sessionid)
                if not self.user.is_login():
                    return self.write(error(QFRET.SESSIONERR))
                if prefunc:
                    prefuncs = prefunc if isinstance(prefunc, (types.ListType, types.TupleType)) else [prefunc]
                    for f in prefuncs:
                        f(self, *args, **kwargs)

                ret = func(self, *args, **kwargs)
                if self.user.ses.data:
                    self.user.ses.save()
                return ret
            except MchntException, e:
                log.warn('check_login_ex error:%s' % e)
                return self.write(error(e.errcode, respmsg=e.errmsg))
            except:
                log.warn('check_login error: %s' % traceback.format_exc())
                return self.write(error(QFRET.SESSIONERR))
            finally:
                if postfunc:
                    postfuncs = postfunc if isinstance(postfunc, (types.ListType, types.TupleType)) else [postfunc]
                    for f in postfuncs:
                        f(self, *args, **kwargs)
        return __
    return _

def check_validator(fields=None, data=None, errfunc=None):
    def _(func):
        def __(self, *args, **kwargs):
            v   = Validator(fields or self.fields)
            ret = v.verify(data or {k:v.strip() for k, v in self.req.input().iteritems()})
            if ret:
                log.info('check_validator error: %s' % ret)
                if not errfunc:
                    return self.write(error(QFRET.PARAMERR, respmsg='参数错误:%s' % ', '.join(ret)))
                else:
                    return errfunc(ret)
            return func(self, *args, **kwargs)
        return  __
    return _

def get_session_wx(swx):
    if not swx: return {}
    try:
        r = redis.Redis(host=config.REDIS_CONF['host'], port=config.REDIS_CONF['port'], password=config.REDIS_CONF['password'])
        d = json.loads(r.get('mchnt_'+swx))
        return d or {}
    except:
        return {}

def update_session_wx(swx, **k):
    try:
        log.debug('update session wx swx:%s, k:%s' % (swx, k))
        r = redis.Redis(host=config.REDIS_CONF['host'], port=config.REDIS_CONF['port'],
            password=config.REDIS_CONF['password'])
        d = r.get('mchnt_'+swx)
        if d:
            k.update(json.loads(d))
        r.set('mchnt_'+swx, json.dumps(k))
        r.expire(swx, config.REDIS_CONF['default_expire'])
    except:
        log.warn('update session wx error:%s' % traceback.format_exc())

def openid_required(func):
    def _(self, *args, **kwargs):
        try:
            if 'MicroMessenger' not in self.req.environ.get('HTTP_USER_AGENT',''):
                return self.write('请用微信打开该页面')

            d = {k:v.strip() for k, v in self.req.input().iteritems()}

            # 带有跳转码,将取出更新input
            if '_skip_code' in d:
                ud = get_session_wx(d['_skip_code']).get('skip_data', {})
                for i in ud:
                    d[i] = ud[i] or d[i]

            # 取出sessionid_wx
            swx = self.get_cookie('sessionid_wx')
            log.debug('swx:%s' % swx)
            openid = get_session_wx(swx).get('openid', '')

            # 如果没有微信openid
            if not openid:
                swx = str(uuid.uuid1())

                # 获取code
                if 'code' not in d:
                    update_session_wx(swx, **{'skip_data':d})

                    state = config.OP_SKIP_URL+'?_skip_code='+swx
                    return self.redirect(config.WX_REDIRECT % state)

                # 获取openid
                wxconf = {
                    'appid': config.WX_CONF['wx_appid'],
                    'secret': config.WX_CONF['wx_appsecret'],
                    'grant_type': 'authorization_code',
                    'code' : d['code']
                }
                r = json.loads(RequestsClient().get(config.WX_CONF['wx_ak_url'], wxconf))
                openid = r.get('openid', '')

            if not openid:
                raise ParamError('无法获取openid')

            self.openid, self.swx, self._d  = openid, swx, d

            # 设置cookie
            log.debug('swx:%s' % swx)
            self.set_cookie('sessionid_wx', swx, **config.COOKIE_CONFIG)
            if openid:
                update_session_wx(swx, **{'openid':openid})

            return func(self, *args, **kwargs)
        except:
            log.warn('openid required error: %s' % traceback.format_exc())
            return self.write(error(QFRET.SESSIONERR))
    return _

def openid_or_login(func):
    def _(self, *args, **kwargs):
        # 检验cookie sessionid
        def ck_sid():
            try:
                sessionid = self.get_cookie('sessionid')
                self.user = ApolloUser(sessionid=sessionid)
                if not self.user.is_login():
                    return False
                self._userid = self.user.ses.get('userid', '')
                self._ck_mode = 'sid'
                return True
            except:
                return False

        # 检验参数
        def ck_swx(d):
            swx = self.get_cookie('sessionid_wx') or d.get('_swx', '')
            log.debug('swx:%s' % swx)
            if not swx:
                return False

            openid = get_session_wx(swx).get('openid', '')
            if not openid:
                return False

            userid = openid2userid(openid)
            if not userid:
                return False
            self.swx, self.openid, self._userid, self._ck_mode = swx, openid, userid, 'swx'
            return  True

        def ret_before():
            if self._ck_mode == 'sid':
                if self.user.ses.data:
                    self.user.ses.save()
            elif self._ck_mode == 'swx':
                # 设置cookie
                self.set_cookie('sessionid_wx', self.swx, **config.COOKIE_CONFIG)
                if self.openid:
                    update_session_wx(self.swx, **{'openid':self.openid})

        try:
            d = {k:v.strip() for k, v in self.req.input().iteritems()}
            if ck_sid() or ck_swx(d):
                ret = func(self, *args, **kwargs)

                ret_before()
                return ret

        except:
            log.warn('check_login error: %s' % traceback.format_exc())
        return self.write(error(QFRET.SESSIONERR))
    return _

def required_slsm_enable(func):
    def _wrapper(self, *args, **kwargs):
        try:
            if not slsm_is_enable(self.user.userid):
                log.warn('slsm(%s) is disable', self.user.userid)
                return self.write(error('0211', respmsg='该业务员已经注销'))
        except:
            log.warn('check_login error: %s' % traceback.format_exc())
            return self.write(error(QFRET.SESSIONERR))

        ret = func(self, *args, **kwargs)

        return ret

    return _wrapper
