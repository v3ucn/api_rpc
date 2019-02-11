# encoding:utf-8

import uuid
import time
import fire
import json

from hashids import Hashids
from requests import post
from functools import wraps
import redis
redis_pool = redis.Redis()
hids = Hashids('qfpay')

from color import UseStyle

env = 'debug'
# env = 'qa'
SKEY = 'test_sid'
CUSTOMER_ID = 1

if env == 'product':
    HOST = 'https://o.qfpay.com'

    USERNAME = 18513504945 # 12
    PASSWORD = '504945'

elif env == 'qa':
    HOST = 'http://172.100.101.107:6310'

    USERNAME = 14700000291
    PASSWORD = '000291'
else:
    HOST = 'http://127.0.0.1:6200'

    #USERNAME = 14000000007 # 20
    USERNAME = 17000000000 # 12
    #USERNAME = 18513504945 # 13
    PASSWORD = '123456'

    #USERNAME = '12#0006'
    #PASSWORD = '12133X'

def del_func(func):
    @wraps(func)
    def _(self, *arg, **kw):
        timeit = kw.pop('timeit', False)
        if not timeit:
            ret = func(self, *arg, **kw)
            if hasattr(ret, 'text'):
                data = json.loads(ret.text)
            else:
                data = ret
            if data is not None:
                print UseStyle(json.dumps(data, indent = 2,
                                      ensure_ascii = False))
        else:
            st = time.time()
            for i in xrange(10000):
                func()
            print time.time() - st
    return _

class Log(type):

    def __new__(cls, cls_nm, cls_parents, cls_attrs):
        for attr_nm in cls_attrs:
            if (not attr_nm.startswith('_')  and callable(cls_attrs[attr_nm])
                and attr_nm not in ('print_env', )):
                cls_attrs[attr_nm] = del_func(cls_attrs[attr_nm])
        return super(Log, cls).__new__(cls, cls_nm, cls_parents, cls_attrs)

class Base(object):

    __metaclass__ = Log

    def print_env(self):
        self.username = redis_pool.get(SKEY+'_username') or USERNAME
        self.password = redis_pool.get(SKEY+'_pwd') or PASSWORD
        self.host = redis_pool.get(SKEY+'_host') or HOST
        print '-' * 40
        print UseStyle('username: %s' % self.username)
        print UseStyle('password: %s' % self.password)
        print UseStyle('host:     %s' % self.host)
        print '-' * 40

    def __init__(self):
        self.print_env()
        self.hids = Hashids('qfpay')

    def _change_env(self, **kw):
        '''修改环境变量'''

        fields = ['username', 'password', 'class', 'host']
        for field in fields:
            if field in kw:
                redis_pool.set(SKEY+'_'+field, kw[field])
        self.del_sid()
        self.print_env()

    def _clear_env(self):
        fields = ['username', 'password', 'class', 'host']
        for field in fields:
            redis_pool.delete(SKEY+'_'+field)
        self.del_sid()
        self.print_env()

    def del_sid(self):
        redis_pool.delete(SKEY)

    def _login(self):
        data = {
            'username' : self.username,
            'password' : self.password,
            'udid' : '123',
            #'opuid' : '1',
        }
        return post(self.host+'/mchnt/user/login', data=data)

    login = _login

    def _get_sid(self):
        try:
            sid = redis_pool.get(SKEY)
            if not sid:
                ret = self._login()
                sid = json.loads(ret.text)['data']['sessionid']
            return sid
        finally:
            if sid:
                try:
                    redis_pool.set(SKEY, sid, 2 * 24 * 3600)
                except:
                    pass

    def _get_csid(self):
        svalue = {
            '__ses__': {
                'expire': 3600
            },
            'customer_id': CUSTOMER_ID,
            'openids': {}
        }

        csid = str(uuid.uuid1())
        r = redis.Redis('172.100.101.156')
        r.set(csid, json.dumps(svalue))
        r.expire(csid, 3600*10)

        return csid

    get_csid = _get_csid

if __name__ == '__main__':
    fire.Fire(Base)
