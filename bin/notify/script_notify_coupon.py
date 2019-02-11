# coding: utf-8
"""
11 0 * * * cd $project/0/bin/; python notify/script_notify_coupon.py --runmode production
"""

import json
import os
import sys
import time
import argparse

import datetime

working_dir = os.path.dirname(os.path.abspath(__file__))
bin_dir = os.path.join(working_dir, '../')
conf_dir = os.path.join(working_dir, '../../conf')

sys.path.insert(0, conf_dir)
sys.path.insert(0, bin_dir)

from qfcommon.base.tools import thrift_callex
from qfcommon.base.dbpool import get_connection, install
from qfcommon.base import logger
from qfcommon.thriftclient.qf_marketing import QFMarketing
from qfcommon.thriftclient.qf_marketing.ttypes import CouponDispatchArgs

push_activity_id_list = []

# parse argument
parser = argparse.ArgumentParser()
parser.add_argument('--runmode', required=True, choices=['debug', 'production'])
parser.add_argument('--activity-id', type=int, help="sale activity id", nargs="*")
parser.add_argument('--log-stdout', help="log to stdout", action="store_true")
parser.add_argument('--enable-weixin-push', action="store_true", help="enable weixin push, default not push")
parser.add_argument('--date', nargs="?", default=datetime.date.today().strftime('%Y-%m-%d'),
                    type=lambda today_str: datetime.datetime.strptime(today_str, "%Y-%m-%d"))

args = parser.parse_args(sys.argv[1:])

if args.runmode == 'debug':
    import config_debug as config
elif args.runmode == 'production':
    import config
else:
    raise RuntimeError('invalid runmode')

if args.log_stdout:
    log = logger.install('stdout')
else:
    log = logger.install(config.LOGFILE)

if args.activity_id:
    push_activity_id_list = args.activity_id

install(config.DATABASE)

def get_actvs():
    '''获取活动列表'''
    actvs = None
    date = args.date
    with get_connection('qf_marketing') as db:
        where = {'type': 3, 'status' : ('in', [1,2])}
        if push_activity_id_list:
            where['id'] = ('in', push_activity_id_list)
        else:
            timestamp = int(time.mktime(date.timetuple()))
            where['start_time'] = 'between', (timestamp, timestamp+24*3600-1)
        actvs = db.select('activity', where=where)

    return actvs

def get_members(actv):
    '''根据活动获取会员列表'''
    userids = []
    if actv['mchnt_id']:
        userids.append(actv['mchnt_id'])

    mchntids = []
    with get_connection('qf_marketing') as db:
        activity_mchnt = db.select_one('activity_mchnt',
                where={'activity_id': actv['id']}, fields='mchnt_id_list') or {}
        if activity_mchnt:
            mchntids = json.loads(activity_mchnt['mchnt_id_list'])
    userids.extend(mchntids)
    if not userids:
        return None

    members = []
    with get_connection('qf_mchnt') as db:
        members = db.select('member',
                where={'userid': ('in', userids)}, fields='distinct customer_id') or []
        members = [str(member['customer_id']) for member in members]

    return members

def main():
    actvs = get_actvs()
    if not actvs:
        return

    for actv in actvs:
        members = get_members(actv)
        if not members:
            continue

        dispatch_args = CouponDispatchArgs()
        dispatch_args.src = 'qpos'
        dispatch_args.customer_list = members
        dispatch_args.activity_id = actv['id']
        dispatch_args.mchnt_id = actv['mchnt_id']

        try:
            ret = thrift_callex(config.COUPON_QF_MARKETING_SERVERS,
                    QFMarketing, 'coupon_dispatch', dispatch_args)
            log.info('coupon_dispatch success: args: %s', dispatch_args)
        except Exception as e:
            log.exception('coupon_dispatch failure: %s, args: %s', e, dispatch_args)
            continue

        if ret:
            log.warn('dispatch failure: %s', ret)
        else:
            log.info('coupon_dispatch success: activity: %d', actv['id'])


if __name__ == "__main__":
    log.info('执行脚本')
    log.info(args)
    main()
