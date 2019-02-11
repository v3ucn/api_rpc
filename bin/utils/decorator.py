# encoding: utf-8

import config
import types
import traceback
import logging
log = logging.getLogger()

from .language_api import get_constant
from runtime import redis_pool
from constants import MulType

from excepts import MchntException, SessionError, ReqError

from qfcommon.web.validator import Validator
from qfcommon.qfpay.qfresponse import error,QFRET
from qfcommon.qfpay.apollouser import ApolloUser
from qfcommon.qfpay.qfuser import customer_from_session

# 数据函数dict
data_funcs = {}

def func_register(mode='valid'):
    '''注册接口'''
    def _(func):
        if mode == 'valid':
            data_funcs[func.__name__] = func
        return func
    return _


def with_customer(func):
    def _(self, *args, **kwargs):
        csid = self.get_cookie('csid')
        self.customer = customer_from_session(csid)
        ret = func(self, *args, **kwargs)
        if self.customer.ses.data:
            self.customer.ses.save()
            self.set_cookie(
                'csid', self.customer.ses._sesid,
                **config.COOKIE_CONFIG
            )
        return ret
    return _


@func_register()
def validator(func):
    '''
    参数合法验证
    params:
        _validator_fields: class里, 需要验证的参数
        _validator_errfunc: class里, 出现错误的处理函数,
                            默认直接返回ParamError
    returns:
        当参数验证错误时, 会直接返回ParamError
    '''
    def _(self, *args, **kw):
        fields = getattr(self, '_validator_fields')
        errfunc = getattr(self, '_validator_errfunc', None)
        vdt = Validator(fields)
        self.validator = vdt
        ret = vdt.verify(self.req.inputjson())
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
        return func(self, *args, **kw)
    return _


@func_register()
def user_lock(func):
    def get_lock(key, src=None, expire=115):
        '''获取锁'''
        if not key: return
        rkey = 'mchnt_api_lock_%s_%s_' % (key, src or '')
        if redis_pool.get(rkey):
            return False
        else:
            redis_pool.set(rkey, 1, expire)
            return True

    def release_lock(key, src=None):
        '''释放锁'''
        if not key: return
        rkey = 'mchnt_api_lock_%s_%s_' % (key, src or '')
        redis_pool.delete(rkey)

    def _(self, *args, **kw):
        try:
            src = '.'.join([self.__module__, self.__class__.__name__])
            key = self.user.userid
            if not get_lock(key, src):
                raise ReqError('操作过于频繁')

            return func(self, *args, **kw)

        finally:
            release_lock(key, src)

    return _

@func_register()
def check_ip(func):
    p = (getattr(config, 'IP_LIMIT', None) or
        ('192.30.*.*', '192.10.*.*', '127.0.0.1','172.100.*.*'))
    def _(self, *args, **kwargs):
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
    return _

@func_register()
def login(func):
    def _(self, *args, **kw):
        sessionid = self.get_cookie('sessionid')
        self.user = ApolloUser(sessionid=sessionid)
        if not self.user.is_login():
            raise SessionError('商户未登录')

        ret = func(self, *args, **kw)

        if self.user.ses.data:
            self.user.ses.save()
        return ret
    return _


@func_register()
def ip_or_login(func):
    ips = (getattr(config, 'IP_LIMIT', None) or
        ('192.30.*.*', '192.10.*.*', '127.0.0.1','172.100.*.*'))
    def _(self, *args, **kw):
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

        if not ck_sid() and not ck_ip():
            raise SessionError('商户未登录')

        if self._ck_mode == 'ip' and 'userid' in self.req.inputjson():
            self.user = ApolloUser(self.req.inputjson()['userid'])

        ret = func(self, *args, **kw)

        if self._ck_mode == 'sid' and self.user.ses.data:
            self.user.ses.save()

        return ret
    return _


@func_register()
def check_perm(func):
    def _(self, *args, **kwargs):
        if 'opuid' in self.user.ses and int(self.user.ses.data.get('opuid')):
            return self.write(error(QFRET.ROLEERR, respmsg='抱歉，您当前没有权限完成此操作，请联系老板协助完成～'))
        return func(self, *args, **kwargs)
    return _

def check(funcs=None):
    def _(func):
        def __(self, *args, **kwargs):
            def get_language():
                try:
                    language = self.get_language()
                except:
                    language = 'zh-cn'

                return language

            resperr = ''

            try:
                del_func = func
                deco_funcs = []
                if funcs:
                    deco_funcs = (funcs if isinstance(funcs, MulType)
                                  else [funcs])
                for f in deco_funcs[::-1]:
                    if callable(f):
                        del_func = del_func(f)
                    elif f in data_funcs:
                        del_func = data_funcs[f](del_func)
                return del_func(self, *args, **kwargs)
            except MchntException, e:
                log.warn(traceback.format_exc())
                errcode, errinfo = e.errcode, e.errmsg
                resperr = e.resperr
            except:
                log.warn(traceback.format_exc())
                errinfo = getattr(self, '_base_err', 'param error')
                errcode = QFRET.PARAMERR

            # 获取错误翻译
            language = get_language()
            respmsg = errinfo
            try:
                if errinfo:
                    respmsg = get_constant(errinfo, language)
            except:
                pass

            return error(errcode, respmsg=respmsg, resperr = resperr)

        return __
    return _
