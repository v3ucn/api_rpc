# encoding:utf-8

import os
import sys
import json
import traceback
import time

HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(HOME)
sys.path.append(os.path.join(os.path.dirname(HOME), 'conf'))

from qfcommon.base import loader
loader.loadconf_argv(HOME)

import config
from qfcommon.base import dbpool
dbpool.install(config.DATABASE)
from qfcommon.base import logger
log = logger.install(config.LOGFILE)


from util import redis_pool, hids, str_timestamp
from constants import DATE_FMT
from qfcommon.base.dbpool import get_connection
from qfcommon.base.tools import thrift_callex
from qfcommon.server.client import HttpClient
from qfcommon.thriftclient.open_user import OpenUser

# 是否制定特定的商户推送
try:
    LIMIT_USER = int(redis_pool.get('_mchnt_api_limit_user_flag_') or 0)
except:
    LIMIT_USER = True

# 推送次数redis key
SEND_KEY = '_mchnt_api_promote_%s_' % time.strftime('%Y%m')
try:
    if not redis_pool.exists(SEND_KEY):
        redis_pool.hset(SEND_KEY, 0, 0)
        redis_pool.expire(SEND_KEY, 31 * 24 * 3600)
except:
    pass

def get_userids():
    now = int(time.time())

    yestoday_st = str_timestamp(time.strftime(DATE_FMT), DATE_FMT) - 24 * 3600
    yestoday_ed = str_timestamp(time.strftime(DATE_FMT), DATE_FMT)
    where = {'ctime': ('between', (yestoday_st, yestoday_ed)),
            'status': 1, 'expire_time': ('>', now)}

    userids = []
    with get_connection('qf_mchnt') as db:
        userids = db.select('member_actv',
            where= where, fields='distinct(userid)') or []

    userids = [i['userid'] for i in userids]

    # 是否只针对特定的商户发
    if LIMIT_USER:
        limit_userids = redis_pool.smembers('_mchnt_api_limit_user_')
        limit_userids = {int(i) for i in limit_userids}
        userids = list(set(userids) & limit_userids)

    # 验证本月发送次数
    if not userids: return
    send_num = redis_pool.hmget(SEND_KEY, userids)
    userids = [ v  for idx, v in enumerate(userids)
            if int(send_num[idx] or 0) < config.NOTIFY_MAX_COUNT_MONTH]

    return userids

def get_customer_info(cid):
    # 获取openid
    openid = thrift_callex(config.OPENUSER_SERVER, OpenUser,
            'get_openids_by_user_ids', config.OPENUSER_APPID, [cid, ])[0]

    # 获取profile
    spec = json.dumps({'id': cid})
    profile = thrift_callex(config.OPENUSER_SERVER, OpenUser,
            'get_profiles', config.OPENUSER_APPID, spec)[0]

    return {'openid': openid, 'nickname': profile.nickname}

def push(cid):
    try:
        customer_info = get_customer_info(cid)
        p = {
            'customer_id': hids.encode(int(cid)),
            'busicd': 'promote_note',
        }
        p.update(customer_info)
        HttpClient(config.TRADE_PUSH_SERVER).post('/push/v2/msg', params=p)
    except:
        log.warn('push error :%s' % traceback.format_exc())
        redis_pool.sadd('_mchnt_api_pusherror_', cid)

def send_over(userids):
    with get_connection('qf_mchnt') as db:
        users = db.select('member', where = {'userid': ('in', userids)},
            fields='userid, count(1) as num', other='group by userid') or []
        users = [(i['userid'],i['num']) for i in users]

    for userid,num in users:
        try:
            redis_pool.hincrby(SEND_KEY, userid)
            p = {
                'userid': userid,
                'num': num,
                'busicd': 'app_promote_send_over',
            }
            HttpClient(config.TRADE_PUSH_SERVER).post('/push/v2/msg', params=p)
        except:
            log.warn('push app error :%s' % traceback.format_exc())
            redis_pool.sadd('_mchnt_api_pushapperror_', userid)

def send():
    log.debug('开始执行send_promotion脚本')
    userids = get_userids()
    if not userids: return

    customer_ids = []
    with get_connection('qf_mchnt') as db:
        members = db.select('member',
            where={'userid': ('in', userids)}, fields='distinct(customer_id)')
    if not members: return

    redis_pool.delete('_mchnt_api_pusherror_', '_mchnt_api_pushapperror_')
    customer_ids = [i['customer_id'] for i in members]
    for customer_id in customer_ids:
        push(customer_id)

    send_over(userids)

if __name__ == '__main__':
    send()
