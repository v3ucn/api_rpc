# coding:utf-8

import config
import logging
log = logging.getLogger()

from user.base import APPLY_STATE

from util import get_bigmchntid
from utils.base import BaseHandler
from utils.decorator import check
from runtime import apcli
from constants import (
    CHNLBIND_TYPE_WX, SETTLE_TYPE_T1,
    SETTLE_TYPE_D1, SETTLE_TYPE_D0
)

from qfcommon.base.dbpool import get_connection
from qfcommon.base.qfresponse import success

class AuditStat(BaseHandler):
    '''
    统计商户审核信息
    '''

    _base_err = '获取审核统计信息失败'
    @check('check_ip')
    def POST(self):
        userids = set()
        in_userids = self.req.input().get('userids', '')
        for userid in in_userids.split(','):
            filter_userid = filter(str.isdigit, userid)
            if filter_userid:
                userids.add(int(filter_userid))

        ret = {}
        ret['nodata'] = 0
        ret['pass'] = ret['wait'] = 0
        ret['refuse'] = ret['fail'] = 0
        if userids:
            audits = None
            with get_connection('qf_mis') as db:
                audits = db.select(
                        table= 'apply',
                        where= {
                            'user': ('in', userids)
                        },
                        fields= 'user, state')
            for audit in audits or []:
                if audit['state'] == APPLY_STATE['pass']:
                    ret['pass'] += 1
                elif audit['state'] == APPLY_STATE['refuse']:
                    ret['refuse'] += 1
                elif audit['state'] == APPLY_STATE['fail']:
                    ret['fail'] += 1
                else:
                    ret['wait'] += 1
            ret['nodata'] = len(userids) - sum([ret[i] for i in
                        ['pass', 'wait', 'refuse', 'fail'] ])

        return self.write(success(ret))

class SettleType(BaseHandler):
    '''
    商户到账类型
    '''
    _base_err = '获取商户到账类型失败'

    def check_exist(self, users):
        '''检查用户是否存在'''
        ret = []
        userids = []
        if not users:
            return ret
        with get_connection('qf_core') as db:
            userids = db.select(
                    table = 'auth_user',
                    where = {'id': ('in', users)},
                    fields = 'id')
        ret = [userid['id'] for userid in userids]
        return ret

    def get_dzero_users(self, userids):
        '''通过user_service的code来判断d0'''
        ret = []
        if not userids:
            return ret
        users_service = apcli('getAllUserServices', userids)
        for k,v in users_service.iteritems():
            codes = [service.code for service in v if service.status == 1]
            if 'balance' in codes:
                log.debug('userid={},codes={}'.format(k, codes))
                ret.append(k)
        return ret

    def get_settle_type(self, chnlbind, dzero_ids, bigmchntids):
        '''获取结算类型的逻辑'''

        if not chnlbind or not bigmchntids:
            return SETTLE_TYPE_T1

        mchntid_termid = '{}_{}'.format(chnlbind.get('mchntid'), chnlbind.get('termid'))

        if not (chnlbind.get('chnlid') in config.D1_CHNLIDS and \
              mchntid_termid not in bigmchntids):
            return SETTLE_TYPE_T1
        if chnlbind['userid'] not in dzero_ids:
            return SETTLE_TYPE_D1

        return SETTLE_TYPE_D0

    @check('check_ip')
    def GET(self):

        # 获取userids
        in_userids = self.req.input().get('userids', '')
        in_userids = filter(str.isdigit, in_userids.split(','))
        in_userids = map(int, in_userids)
        userids = self.check_exist(set(in_userids))
        userids.append(0)
        d0_ids = self.get_dzero_users(userids)
        bigmchntids = set(get_bigmchntid() or [])

        # 查询通道
        ret = {}
        chnlbinds = []
        with get_connection('qf_core') as db:
            chnlbinds = db.select(
                    table = 'chnlbind',
                    where = {
                        'userid' : ('in', userids),
                        'available' : 1,
                        'tradetype' : CHNLBIND_TYPE_WX
                    },
                    other = 'order by priority',
                    fields = 'key3, mchntid, chnlid, termid, userid, priority')
        if not chnlbinds:
            return self.write(success(ret))

        # 优先级
        default_pri_chnlbind = {} # 默认使用的通道
        chnlbind_userids = set() # 绑定了通道的userid
        high_pri_chnlbinds = [] # 优先级高于默认通道userid
        for cb in chnlbinds:
            cb_userid = cb['userid']
            if cb_userid == 0 and not default_pri_chnlbind:
                default_pri_chnlbind = cb
            if not default_pri_chnlbind:
                high_pri_chnlbinds.append(cb_userid)
            chnlbind_userids.add(cb_userid)

        # 暂时无效
        notbind_userids = set(userids) - chnlbind_userids
        default_pri_settle = self.get_settle_type(default_pri_chnlbind,
                d0_ids, bigmchntids)

        for chnlbind in chnlbinds:
            userid = chnlbind['userid']

            # 商户绑定多个通道，默认取优先级最高的
            # 用户绑定的通道优先级低，则会取默认通道
            if userid == 0 or userid in ret:
                continue
            if userid not in high_pri_chnlbinds:
                chnlbind = default_pri_chnlbind
            ret[userid] = self.get_settle_type(chnlbind, d0_ids, bigmchntids)

        # 无效代码，防止以后再有默认结算类型
        # 未绑定通道的就没有结算类型
        # for notbind_user in notbind_userids:
            # ret[notbind_user] = default_pri_settle
        return self.write(success(ret))

