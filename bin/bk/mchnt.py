# coding=utf-8

import time
import config
import json
import logging
log = logging.getLogger()
import traceback

from runtime import apcli, redis_pool
from util import getid
from decorator import with_validator, raise_excp, check_login

from utils.base import BaseHandler

from qfcommon.base.dbpool import get_connection
from qfcommon.base.qfresponse import success
from qfcommon.web.validator import Field, T_STR, T_REG
from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.data_activiquer import activiquer

class Stat(BaseHandler):
    '''
    商户信息
    '''

    def get_avg_stat(self):
        ret = {}
        try:
            ret = json.loads(redis_pool.get('_mchnt_api_bk_avg_stat_'))
        except:
            log.debug(traceback.format_exc())
        return ret

    @check_login
    @raise_excp('获取诊断数据失败')
    def GET(self):
        ret = {}
        userid = int(self.user.userid)
        avg_stat = stat = None
        try:
            stat = json.loads(thrift_callex(config.DATAS_SERVERS, activiquer,
                              'activiq', 'zhenduan', str(userid)))[0]
        except:
            log.debug(traceback.format_exc())
            avg_stat = self.get_avg_stat()
            stat = {}

        # 同行业
        ret['avg'] = {}
        for field in ('cat_avg_amt', 'cat_rcg_rate', 'cat_retention_rate'):
            if field in stat:
                ret['avg'][field] = stat[field]
            elif field in avg_stat:
                ret['avg'][field] = avg_stat[field]

        # 店铺信息
        ret['stat'] = {}
        if stat:
            ret['stat'] = {k:v for k, v in stat.iteritems()}

        # 店铺名
        if 'nickname' in ret['stat']:
            ret['shopname'] = ret['stat']['nickname']
        else:
            user = apcli.user_by_id(userid) or {}
            log.debug(user)
            ret['shopname'] = user.get('shopname') or ''

        return self.write(success(ret))

class Apply(BaseHandler):
    '''
    生意王上传
    '''

    STATE_PATTERN = r'^(1|2|3|4)$'

    _validator_fields = [
        Field('wx_pub', T_STR, default=''),
        Field('mobile', T_STR, default=''),
        Field('license_state', T_REG, match=STATE_PATTERN, default=1),
    ]

    @with_validator()
    @check_login
    @raise_excp('上传信息失败')
    def POST(self):
        data = self.validator.data
        data['ctime'] = data['utime'] = int(time.time())
        data['id'] = getid()
        data['userid'] = self.user.userid
        data['state'] = 1
        if not data['mobile']:
            user = apcli.user_by_id(data['userid']) or {}
            data['mobile'] = user.get('mobile') or ''

        with get_connection('qf_mchnt') as db:
            db.insert('bk_apply', data)

        return self.write(success({}))
