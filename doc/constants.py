# encoding:utf-8

import time
import json

from data import data

from qfcommon.base import logger, dbpool
from qfcommon.base.dbpool import get_connection_exception
log = logger.install('stdout')

SRC = 'mchnt_api'

# 线上环境
#import dbenc
#dbconf = dbenc.DBConf()
#dbpool.install({
    #'qf_core': dbconf.get_dbpool(
            #'apollo_core_read',
            #engine='pymysql', conn=20
    #),
#})
# APOLLO_SERVERS = [{'addr': ('192.30.2.188', 6702), 'timeout': 2000}, ]
# 渠道服务
# QUDAO_SERVERS = [{'addr': ('192.30.2.173', 8001), 'timeout': 2000},]

# 线下环境
dbpool.install({
    'qf_mchnt': {
        'engine':'mysql',
        'db': 'qf_mchnt',
        #'host': '172.100.101.156',
        'host': '172.100.101.107',
        #'host': '172.100.101.155',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    }
})

def eq(str1, str2):
    if str1 == str2:
        return True

    else:
        try:
            if json.loads(str1) == json.loads(str2):
                return True
        except:
            return False

    return False

unicode_to_utf8 = lambda v: v.encode('utf-8') if isinstance(v, unicode) else str(v)
decode_from_utf8 = lambda v: v if isinstance(v, unicode) else v.decode('utf-8')

def batch_update():
    now = int(time.time())
    with get_connection_exception('qf_mchnt') as db:
        keys = data.keys()
        constants = db.select(
            table = 'language_constant',
            where = {
                'code': ('in', keys),
                'src': SRC
            },
            fields = 'code, value'
        )
        constants = {i['code']:i['value'] for i in constants}

    # 批量插入
    insert_data = []
    for k, v in data.iteritems():
        k = decode_from_utf8(k)
        if k not in constants:
            insert_data.append({
                'code': k, 'value': v,
                'ctime': now, 'utime': now,
                'src': SRC
            })
    if insert_data:
        with get_connection_exception('qf_mchnt') as db:
            db.insert_list('language_constant', insert_data)

    # 批量更新
    with get_connection_exception('qf_mchnt') as db:
        for k, v in data.iteritems():
            k = decode_from_utf8(k)
            if k in constants and not eq(v, constants[k]):
                db.update(
                    table = 'language_constant',
                    values = {'value': v, 'utime': now},
                    where = {'code': k, 'src':SRC}
                )


if __name__ == '__main__':
    batch_update()

