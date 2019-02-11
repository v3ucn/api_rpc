# encoding:utf-8

import config
import time
import json
import datetime
import logging
log = logging.getLogger()

from constants import DTM_FMT
from excepts import ParamError
from runtime import redis_pool, apcli, hids
from utils.tools import apcli_ex
from utils.base import BaseHandler
from utils.decorator import with_customer

from qfcommon.thriftclient.open_user import OpenUser
from qfcommon.base.tools import thrift_callex
from qfcommon.base.dbpool import (
    get_connection_exception, get_connection, DBFunc
)

# 卡卷活动状态
ACTV_STATUS = (ACTV_STATUS_ALL, ACTV_STATUS_NORMAL, ACTV_STAUS_STOPED) = (0, 1, 2)

# 卡卷活动状态
ACTV_STATE = (ACTV_STATE_ALL, ACTV_STATE_ON, ACTV_STATE_OFF) = (0, 1, 2)

# 会员集点记录类型 记录类型 1: 领取  2:撤销
PT_RECORD_TYPE = (PT_RECORD_GET, PT_RECORD_CANCEL) = (1, 2)

# 会员兑换码状态 1: 已兑换 2:创建优惠码 3:已撤销
CODE_STATUS = (CODE_STATUS_EXCHANGED, CODE_STATUS_CREATE, CODE_STATUS_CANCEL) = (1, 2, 3)
PT_RECORD_TYPE = (PT_RECORD_GET, PT_RECORD_CANCEL) = (1, 2)

class CardBase(BaseHandler):
    '''
    集点基础类
    '''

    pre_code = 'haojin_card:'

    @with_customer
    def get_customer_id(self):
        '''获取customer_id'''
        try:
            customer_id = hids.decode(self.req.input().get('customer_id'))[0]
        except:
            if self.customer.customer_id:
                customer_id = self.customer.customer_id
            else:
                raise ParamError('消费者不存在')

        return customer_id

    @staticmethod
    def get_state(expire_time):
        return (ACTV_STATE_ON
                if time.strftime(DTM_FMT) <= expire_time
                else ACTV_STATE_OFF)

    @staticmethod
    def is_new_card(userid, customer_id, src):
        '''将用户设置为新用户'''
        is_new = 0

        TIME_LIMIT = 24 * 3600
        with get_connection('qf_mchnt') as db:
            member = db.select_one('member',
                    where = {
                        'customer_id': customer_id,
                        'userid': userid,
                    }, fields = 'id, ctime') or []

            key = '_mchnt_api_is_new_{}_{}_{}__'.format(
                    userid, customer_id, src)
            now = int(time.time())
            if (not member or
                (now-member['ctime'] < TIME_LIMIT and
                 not redis_pool.get(key))):
                is_new = 1
                redis_pool.set(key, 1, TIME_LIMIT)

        return is_new

    def get_mchnt_id_list(self, mchnt_id_list, aid = None):
        ''' 获取mchnt_id_list'''
        userid = int(self.user.userid)
        if self.get_cate() != 'bigmerchant':
            return json.dumps([str(userid)])

        mchnt_id_list = [i for i in mchnt_id_list if i]

        # 获取适用门店列表
        link_ids = apcli.userids_by_linkid(userid, 'merchant')
        link_ids = {i.userid for i in link_ids}
        if not mchnt_id_list:
            mchnt_ids = link_ids
        else:
            mchnt_ids = set()
            for i in mchnt_id_list:
                try:
                    mchnt_ids.add(hids.decode(i)[0])
                except:
                    pass

        if mchnt_ids - link_ids:
            raise ParamError('包含了非自己的子商户')

        with get_connection_exception('qf_mchnt') as db:
            userids = list(mchnt_ids) + [userid]
            actvs = db.select('card_actv',
                    where={
                        'expire_time': ('>', int(time.time())),
                        'userid': ('in', userids)
                    },
                    fields = 'userid, mchnt_id_list, id')
            for actv in actvs:
                if aid == actv['id']:
                    continue
                try:
                    uids = json.loads(actv['mchnt_id_list'])
                    uids = {int(i) for i in uids}
                except:
                    uids = set()

                onuids = uids & mchnt_ids
                if onuids:
                    mchnt = apcli_ex('findUserBriefsByIds',
                            [list(onuids)[0]]) or []
                    shopname = mchnt[0].shopname if mchnt else  ''
                    raise ParamError('{}等子商户有正在进行的集点活动'.format(shopname))

        return json.dumps([str(i) for i in mchnt_ids])

    def get_userid_condition(self, userid=None):
        ''' 获取查询条件

        查询大商户和自己创建的并参与的集点活动
        '''
        req_userid = userid
        userid = userid or int(self.user.userid)

        big_uid = self.get_big_uid(req_userid)
        userid_condition = userid
        if big_uid:
            userid_condition =  (' in ',
                DBFunc('({uid}, {big_uid}) and locate(\'"{uid}"\', '
                'mchnt_id_list)'.format(uid=userid, big_uid=big_uid)))

        return userid_condition

    def check_allow_change(self, aid):
        '''验证能否修改集点活动

        Params:
            aid: 集点活动id
        Returns:
            返回活动信息
        '''
        userid = self.user.userid
        cate = self.get_cate()

        actv = None
        with get_connection_exception('qf_mchnt') as db:
            actv = db.select_one('card_actv', where={'id': aid})
        if not actv:
            raise ParamError('活动不存在')

        if actv['userid'] != int(userid):
            # 判断登录角色
            cate = self.get_cate()
            if cate in ('merchant', 'submerchant'):
                raise ParamError('子商户不能修改大商户创建的活动')

            # 活动的大商户是否是登录商户
            re_relates = apcli_ex('getUserReverseRelation',
                    actv['userid'], 'merchant') or []
            userids = [i.userid for i in re_relates]
            if int(userid) not in userids:
                raise ParamError('活动不存在')

        now = datetime.datetime.now()
        if actv['expire_time'] < now:
            raise ParamError('活动已停止')

        return actv

    def check_allow_query(self, aid):
        '''验证能否查看集点活动

        能查看的情况
        1. 自己创建的活动
        2. 自己参与的活动
        3. 自己子商户的活动

        '''
        userid = self.user.userid

        # 子商户可以查看大商户活动
        with get_connection_exception('qf_mchnt') as db:
            actv = db.select_one(
                'card_actv', where={'id': aid})
            if not actv:
                raise ParamError('活动不存在')

        if actv['userid'] != int(userid):
            # 参与活动能查看
            try:
                mchnt_id_list = json.loads(actv['mchnt_id_list'])
            except:
                mchnt_id_list = []
            if str(userid) in mchnt_id_list:
                return actv

            # 活动创建商户的大商户能查看
            re_relates = apcli_ex('getUserReverseRelation',
                    actv['userid'], 'merchant') or []
            userids = [i.userid for i in re_relates]
            if int(userid) not in userids:
                raise ParamError('活动不存在')

        return actv

    def get_customers(self, actv):
        ret = {'customers': [], 'customer_num': 0}

        members = []
        with get_connection('qf_mchnt') as db:
            where= {
                'activity_id': int(actv['id'])
            }
            members = db.select('member_pt',
                fields= 'customer_id',
                where= where,
                other= 'order by utime limit 5 offset 0') or []

            ret['customer_num'] = db.select_one('member_pt',
                    fields='count(*) as num', where=where)['num']

        cids = [i['customer_id'] for i in members]
        if cids:
            spec = json.dumps({'user_id': cids})
            p = thrift_callex(config.OPENUSER_SERVER, OpenUser,
                    'get_profiles', config.OPENUSER_APPID, spec)
            p = {i.user_id:i for i in p}
            for i in cids:
                t = (p[i].avatar if i in p else '') or config.HJ_AVATAR
                ret['customers'].append({'avatar': t})

        return ret
