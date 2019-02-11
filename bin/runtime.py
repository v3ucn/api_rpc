# encoding:utf-8

import config
import redis
import hashids

from qfcommon.qfpay.apolloclient import Apollo
from qfcommon.qfpay.presmsclient import PreSms
from qfcommon.web import cache as qf_cache
qfcache = qf_cache.install()

# hids
hids = hashids.Hashids(config.QRCODE_SALT)

# redis连接池
redis_conf = config.CACHE_CONF['redis_conf']
redis_pool = redis.Redis(host=redis_conf['host'],
    port=redis_conf['port'], password=redis_conf['password'])

# mmwd redis cli
ms_redis_pool = redis.Redis(**config.MMWD_SOCIAL_REDIS)

# apollo cli
apcli = Apollo(config.APOLLO_SERVERS)

# 短信服务 cli
smscli = PreSms(config.PRESMS_SERVERS)

# geo redis cli
geo_redis_pool = redis.Redis(**config.GEO_REDIS_CONF)
