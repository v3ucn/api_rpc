# coding: utf-8

import xlrd
import time

from qfcommon.base import logger, dbpool
from qfcommon.base.dbpool import get_connection_exception
log = logger.install('stdout')

# 线下环境
dbpool.install({
    'qf_mis': {
        'engine':'mysql',
        'db': 'qf_mis',
        'host': '172.100.101.107',
        # 'host': '172.100.101.156',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    }
})

wb = xlrd.open_workbook('area_code.xls')
sh = wb.sheet_by_name(u'2017-11-07')
nrows = sh.nrows
all_data = []
now = time.strftime('%Y-%m-%d %H:%M:%S')
for i in xrange(nrows):
    if i == 0:
        continue
    row = sh.row_values(i)
    if row[6]:  # 街道的id
        tmp = dict()
        tmp['name'] = 'street'
        tmp['parent_id'] = row[4] if row[4] else (row[2] if row[2] else row[0])
        tmp['area_id'] = row[6]
        tmp['status'] = 1
        tmp['full_name'] = row[7]
        tmp['create_time'] = now
        tmp['update_time'] = now
        all_data.append(tmp)

with get_connection_exception('qf_mis') as conn:
    conn.insert_list('lst_area', all_data)
    log.info('街道数据插入完成')

all_data = []
area_ids = set()
for i in xrange(nrows):
    if i == 0:
        continue
    row = sh.row_values(i)
    if row[4]:  # 县的id
        tmp = dict()
        tmp['name'] = 'area'
        tmp['parent_id'] = row[2] if row[2] else row[0]
        tmp['area_id'] = row[4]
        tmp['status'] = 1
        tmp['full_name'] = row[5]
        tmp['create_time'] = now
        tmp['update_time'] = now
        if row[4] not in area_ids:
            all_data.append(tmp)
            area_ids.add(row[4])

with get_connection_exception('qf_mis') as conn:
    conn.insert_list('lst_area', all_data)
    log.info('县数据插入完成')

all_data = []
area_ids = set()
for i in xrange(nrows):
    if i == 0:
        continue
    row = sh.row_values(i)
    if row[2]:  # 市的id
        tmp = dict()
        tmp['name'] = 'city'
        tmp['parent_id'] = row[0]
        tmp['area_id'] = row[2]
        tmp['status'] = 1
        tmp['full_name'] = row[3]
        tmp['create_time'] = now
        tmp['update_time'] = now
        if row[2] not in area_ids:
            all_data.append(tmp)
            area_ids.add(row[2])

with get_connection_exception('qf_mis') as conn:
    conn.insert_list('lst_area', all_data)
    log.info('市数据插入完成')

all_data = []
area_ids = set()
for i in xrange(nrows):
    if i == 0:
        continue
    row = sh.row_values(i)
    if row[0]:  # 省的id
        tmp = dict()
        tmp['name'] = 'province'
        tmp['parent_id'] = 0
        tmp['area_id'] = row[0]
        tmp['status'] = 1
        tmp['full_name'] = row[1]
        tmp['create_time'] = now
        tmp['update_time'] = now
        if row[0] not in area_ids:
            all_data.append(tmp)
            area_ids.add(row[0])
with get_connection_exception('qf_mis') as conn:
    conn.insert_list('lst_area', all_data)
    log.info('省数据插入完成')
