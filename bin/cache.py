# encoding:utf-8

'''
简单缓存系统
单例缓存
'''

try:
    import simplejson as json
except:
    import json

import time
import datetime
import hashlib
import types
import logging
log = logging.getLogger()

from functools import wraps
from runtime import redis_pool
from config import CACHE_CONF

def json_default_trans(obj):
    '''json对处理不了的格式的处理方法'''
    if isinstance(obj, datetime.datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(obj, datetime.date):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, datetime.timedelta):
        return str(obj)
    raise TypeError('%r is not JSON serializable' % obj)

class SingleCache(dict):
    '''
    单例缓存类
    '''

    def __init__(self):
        self._prefix = CACHE_CONF['redis_cache_name']

    def __contains__(self, k):
        '''是否过期'''
        return redis_pool.exists(k)

    is_absolete = __contains__

    def _md5(self, s):
        return hashlib.md5(s.encode('utf-8') if isinstance(s, types.UnicodeType) else s).hexdigest()

    def _compute_key(self, func, args, kw):
        '''序列化并求其哈希值'''
        def is_valid_json(k):
            try:
                json.dumps(k)
                return True
            except:
                return False

        try:
            return self._md5(self._prefix+json.dumps((func.__module__,func.__class__.__name__,
                                                      func.__name__,args,kw)))
        except:
            return self._md5(self._prefix+json.dumps((func.__module__,func.__class__.__name__,func.__name__,
                                                      [i for i in args if is_valid_json(i)],kw)))

    def __setitem__(self, k, v):
        value = json.dumps(v, default=json_default_trans)
        expire = min(v.get('expire') or 0, 10*60)
        try:
            redis_pool.set(k, value, expire)
        except:
            redis_pool.set(k, value)
            redis_pool.expire(k, expire)

    def __getitem__(self, k, default=None):
        return json.loads(redis_pool.get(k))

    def mget(self, keys):
        return [(json.loads(i)['value'] if i else None)
                for i in redis_pool.mget(keys)]

Cache = SingleCache()

def is_cached(key):
    '''是否已经缓存'''
    return key in Cache

def push_cache(data, expire=5*60):
    '''放入缓存'''
    for k, v in data.iteritems():
        Cache[k] = {'value' : v, 'expire' : expire}

def get_cache(key):
    return Cache[key]['value']

def mget(keys):
    '''
    Method return caches
    :params keys: array of keys to look up in Redis
    :return dict of found key/values
    '''
    if keys:
        values = Cache.mget(keys)
        return {k: v for (k, v) in zip(keys, values) if v is not None}

def cache(ex=True, is_save_None=False, redis_key=None):
    '''自动缓存'''
    def _(func):
        @wraps(func)
        def __(*args, **kw):
            key = redis_key or Cache._compute_key(func, args, kw)
            log.debug('cache key:%s' % key)
            if key in Cache:
                return  Cache[key]['value']
            try:
                r = func(*args, **kw)
            except:
                if ex:
                    raise
                else:
                    return None

            if is_save_None or r:
                cache_conf_key = redis_key or func.__name__+'_conf'
                conf = CACHE_CONF.get(cache_conf_key if cache_conf_key in CACHE_CONF else 'default')
                times = conf.get('times', 10*60)
                Cache[key] = {'value' : r, 'expire' : times}

            return r
        return __
    return _

def test():
    sc = SingleCache()
    @cache()
    def A(a='yyk', b='c'):
        time.sleep(1)
        return 123

    ra = A(a='yyk', b='a')
    print 'result (yyk, a): ', ra

    print sc._data
    rc = A(a='yyk', b='c')
    print 'result (yyk, c): ', rc

    rra = A(a='yyk', b='a')
    print 'result (yyk, a): ', rra
    print sc._data

def test1():
    sc = SingleCache(1)
    @cache()
    def A(a='yyk', b='c'):
        time.sleep(2)
        return 123

    ra = A(a='yyk', b='a')
    print 'result (yyk, a): ', ra

    print sc._data
    rc = A(a='yyk', b='c')
    print 'result (yyk, c): ', rc

    print sc._data
    rra = A(a='yyk', b='a')
    print 'result (yyk, a): ', rra
    print sc._data

if __name__ == '__main__':
    #test()
    test1()
