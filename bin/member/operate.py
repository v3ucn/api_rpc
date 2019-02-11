# coding=utf-8

import traceback
import time
import config
import logging

from runtime import hids
from decorator import raise_excp
from util import get_member_info
from base import MemberUtil, MemDefine
from excepts import ParamError

from utils.date_api import str_to_tstamp
from utils.base import BaseHandler
from utils.valid import is_valid_int
from utils.tools import userid_cache
from utils.decorator import with_customer

from qfcommon.qfpay.apolloclient import Apollo
from qfcommon.base.dbpool import get_connection_exception, with_database
from qfcommon.base.qfresponse import success
from qfcommon.thriftclient.apollo import ApolloServer
from qfcommon.thriftclient.apollo.ttypes import UserQuery
from qfcommon.thriftclient.apollo.ttypes import User
from qfcommon.base.tools import thrift_callex

log = logging.getLogger()

class Promotion(BaseHandler):
    '''
    获取会员的促销信息
    mode: info, marketing_http调用，用于支付完成页面的显示
    mode: list, 促销信息列表展示所用
    userid: 商户id
    customer_id: 消费者信息
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        log.info('d:%s' % d)
        r = {}
        try:
            r['customer_id'] = hids.decode(d.get('customer_id'))[0]
        except:
            if self.customer.customer_id:
                r['customer_id'] = self.customer.customer_id
            else:
                r['customer_id'] = -1

        r['mode'] = d.get('mode', '')
        r['userid'] = d.get('userid', '')
        if is_valid_int(d.get('groupid')):
            r['groupid'] = d.get('groupid')

        if r['mode'] not in ('info', 'list'):
            raise ParamError('请求参数错误')
        elif r['mode'] == 'info':
            r['userid'] = int(r['userid'])
        elif r['mode'] == 'list':
            r['mchnt_id'] = int(d.get('mchnt_id') or 0)
            if r['customer_id'] == -1:
                raise ParamError('消费者id不正确')
            page, pagesize = d.get('page', 0), d.get('pagesize', 10)
            if not all(map(is_valid_int, (pagesize, page))):
                raise ParamError('分页信息错误')
            r['offset'], r['limit'] = int(page)*int(pagesize), int(pagesize)
        return r

    def _get_users(self, uids):
        if not uids: return {}
        users = {}
        try:
            r = thrift_callex(config.APOLLO_SERVERS, ApolloServer, 'findUsers', UserQuery(uids=uids))
            for i in r or []:
                users[i.uid] = {
                    'shopname': i.shopname,
                    'addr': i.address
                }
        except:
            log.warn('get userinfo error:%s' % traceback.format_exc())

        return users

    @with_database('qf_mchnt')
    def _get_promotion(self, d):
        now = int(time.time())
        fields = 'cast(id as char) as id, title, bg_url, userid, start_time, expire_time, status, audit_info, content'
        where = {'expire_time': ('>', now), 'status': 1, 'type': MemDefine.ACTV_TYPE_PROMO}
        def _get_userids():
            # 过去消费过的店铺
            userids = self.db.select('member',
                where={'customer_id': d['customer_id']}, fields='userid')
            userids = [i['userid'] for i in userids or []]
            if is_valid_int(d['userid']):
                userids.append(int(d['userid']))
            return set(userids)

        def _info():
            where = {'expire_time': ('>', now), 'status': 1, 'userid': d['userid']}
            # 获取详细信息
            where['userid'] = d['userid']
            r = self.db.select_one('member_actv', where=where, fields=fields, other='order by ctime desc')
            if r:
                r['title'] = r['title'] or r['content']
                r['content'] = '' if r['title'] == r['content'] else r['content']
                r['bg_url'] =  r['bg_url'] or config.MCHNT_AVATAR
                r['start_time'] = str_to_tstamp(str(r['start_time']))
                r['expire_time'] = str_to_tstamp(str(r['expire_time']))
                MemberUtil.add_actv_pv(r['id'])
            # 获取过去消费过的店铺
            where['userid'] = ('in', _get_userids())
            # 获取总量
            num = self.db.select_one('member_actv', where=where, fields='count(1) as num')['num']
            return self.write(success({'info': r or {}, 'num': num}))

        def _list():
            if d['mchnt_id']:
                where['userid'] = d['mchnt_id']
            else:
                userids = _get_userids()
                if d.get('groupid'):
                    userid_cache_list = userid_cache[d['groupid']]
                    userids = userids & set(userid_cache_list)
                if not userids:
                    return self.write(success({'list': [], 'num':0}))
                where['userid'] = ('in', userids)
            prts = self.db.select('member_actv', fields=fields, where=where,
                other='order by ctime desc limit %s offset %s' % (d['limit'], d['offset'])) or []
            userids = set([i['userid'] for i in prts])
            users = self._get_users(userids)
            ids = []
            for prt in prts:
                user = users.get(prt['userid'], {})
                prt['shopname'] = user.get('shopname') or ''
                prt['addr'] = user.get('addr') or ''
                prt['bg_url'] =  prt['bg_url'] or config.MCHNT_AVATAR
                prt['start_time'] = str_to_tstamp(str(prt['start_time']))
                prt['expire_time'] = str_to_tstamp(str(prt['expire_time']))
                ids.append(prt['id'])
            MemberUtil.add_actv_pv(ids)

            # 获取总量
            num = self.db.select_one('member_actv', where=where, fields='count(1) as num')['num']
            return self.write(success({'list': prts, 'num': num}))

        if d['mode'] == 'info':
            return _info()
        else:
            return _list()

    @with_customer
    @raise_excp('获取会员活动列表失败')
    def GET(self):
        d = self._trans_input()

        # get promotion
        return self._get_promotion(d)

class PromotionInfo(BaseHandler):
    '''
    促销活动详细信息
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        # 活动id
        r = {'id' : d.get('id', '')}
        if not is_valid_int(r['id']):
            raise ParamError('活动id不合法')

        try:
            r['customer_id'] = hids.decode(d.get('customer_id'))[0]
        except:
            if self.customer.customer_id:
                r['customer_id'] = self.customer.customer_id
            else:
                raise ParamError('消费者id不正确')

        return r

    def _get_user(self, userid):
        try:
            r = Apollo(config.APOLLO_SERVERS).user_by_id(userid)
            if r:
                return {k:v or '' for k, v in r.iteritems()}
        except:
            log.warn('get userinfo error:%s' % traceback.format_exc())
        return {k:v or '' for k, v in User().__dict__.iteritems()}

    @with_customer
    @raise_excp('查询活动信息失败')
    def GET(self):
        d = self._trans_input()

        # fields
        fields = ('cast(id as char) as id, status,  title, bg_url,'
            'content, start_time, expire_time, audit_info, userid')
        # where
        where = {'id': d['id']}
        # 获取活动报名详细信息
        with get_connection_exception('qf_mchnt') as db:
            r = db.select_one('member_actv', where = where, fields = fields)
            if not r:
                raise ParamError('该活动不存在')

        MemberUtil.add_actv_pv(r['id'])

        r['state'] = MemberUtil.get_actv_state(r)
        r['start_time']  = str_to_tstamp(str(r['start_time']))
        r['expire_time'] = str_to_tstamp(str(r['expire_time']))

        # 店铺信息
        shop_info = self._get_user(r['userid'])
        r['shop_info'] = {
            'addr': shop_info['address'],
            'mobile': shop_info['mobile'],
            'shopname': shop_info['shopname'],
        }

        # 消费者信息
        member_info = get_member_info(d['customer_id']) or {}
        r['customer_info'] = {
            'nickname': member_info.get('nickname') or '顾客',
            'gender': member_info.get('gender') or 3,
            'avatar': member_info.get('avatar') or config.HJ_AVATAR
        }

        return self.write(success(r))
