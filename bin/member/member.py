# coding=utf-8

import logging
import traceback
import time
import json

import config
from decorator import check_login, raise_excp
from constants import DATE_FMT, DATETIME_FMT
from util import get_member_info
from excepts import ParamError, ThirdError
from base import MemBase

from utils.base import BaseHandler
from utils.payinfo import adjust_payinfo_ex
from utils.valid import is_valid_int
from utils.date_api import tstamp_to_str, str_to_tstamp
from utils.decorator import check

from runtime import hids

from qfcommon.base.dbpool import (
    get_connection_exception, get_connection
)
from qfcommon.base.qfresponse import success

from qfcommon.thriftclient.open_user import OpenUser
from qfcommon.base.tools import thrift_callex, thrift_call
log = logging.getLogger()

class Info(MemBase):
    '''
    消费者信息 - (b端反扫后显示消费者信息)
    '''

    _base_err = '查询消费者信息失败'

    @check('login')
    def GET(self):
        default_info = {
            'nickname': '微信支付顾客',
            'avatar': config.HJ_AVATAR,
            'gender': 3,
            'num': 0,
            'txamt': 0,
            'last_txdtm': ''
        }
        d = self.req.inputjson()
        userid = int(self.user.userid)

        customer_id = None
        if d.get('customer_id'):
            try:
                customer_id = hids.decode(d['customer_id'])[0]
            except:
                if is_valid_int(d['customer_id']):
                    customer_id = int(d['customer_id'])

        # 如果包含openid
        elif d.get('openid'):
            customer_id = thrift_call(OpenUser,
                'get_user_id_by_openid', config.OPENUSER_SERVER,
                config.OPENUSER_APPID, d['openid'])

        if customer_id <= 0:
            return self.write(success(default_info))

        # 获取消费者信息
        r = get_member_info(customer_id) or {}
        member = {}
        with get_connection('qf_mchnt') as db:
            member = db.select_one('member',
                where= {
                    'userid': userid,
                    'customer_id': customer_id
                }) or {}

        info = {}
        info['nickname'] = r.get('nickname') or default_info['nickname']
        info['avatar'] = r.get('avatar') or default_info['avatar']
        info['gender'] = r.get('gender') or default_info['gender']
        info['num'] = member.get('num') or default_info['num']
        info['txamt'] = member.get('txamt') or default_info['txamt']
        info['last_txdtm'] = (tstamp_to_str(member['last_txdtm'])
                if 'last_txdtm' in member else
                default_info['last_txdtm'])

        # 如果是储值交易
        # 获取储值信息
        if d.get('busicd', '').startswith('7'):
            balance =  self.get_balance(userid, customer_id)
            if balance is not None:
                info['balance'] = balance

        return self.write(success(info))

class List(BaseHandler):
    '''
    会员列表 - b端
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        r['userid'] = int(self.user.ses.get('userid', ''))

        # 排序信息
        allow_order_field = ['num', 'txamt', 'last_txdtm']
        allow_order_type  = ['desc', 'asc']
        order_field = d.get('order_field') or 'last_txdtm'
        order_type  = d.get('order_type') or 'desc'
        if order_field not in allow_order_field or order_type not in allow_order_type:
            raise ParamError('排序信息错误')
        r['orderby'] = 'order by %s %s' % (order_field, order_type)

        # 分页信息
        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息错误')
        r['offset'], r['limit'] = int(page)*int(pagesize), int(pagesize)

        # 商户付费信息
        r['mchnt_info'] = adjust_payinfo_ex(r['userid'],
                service_code= 'member_manage', groupid= self.get_groupid())

        return r

    def _get_members(self, d):
        limit_members = 10
        r = {}
        r['overdue_warn'], r['overdue_note'] = 0, ''
        with get_connection_exception('qf_mchnt') as db:
            where  = {'userid' : d['userid']}
            # total_num
            r['total_num'] = db.select_one('member', where=where, fields='count(1) as num')['num']

            # 若未开通服务或者付费过期
            if d['mchnt_info']['overdue'] and r['total_num']>limit_members and  (d['limit']+d['offset']>=limit_members):
                r['overdue_warn'] = 1
                r['overdue_note'] = '未开通会员服务，仅可显示{num}个会员信息'.format(num=limit_members)
                d['limit'] = max(min(limit_members-d['offset'], d['limit']), 0)

            # members
            r['members'] = []
            if d['limit']:
                fields = 'customer_id, txamt, num, last_txdtm, userid'
                other  = '%s limit %s offset %s' % (d['orderby'], d['limit'], d['offset'])
                r['members'] = db.select('member', where=where, other=other, fields=fields)

            # 统计今日增长笔数
            td = str_to_tstamp(time.strftime(DATE_FMT), DATE_FMT)
            r['add_members'] = db.select_one('member', where={'userid': d['userid'], 'ctime': ('>', td)},
                fields='count(1) as num')['num']

        cids = [i['customer_id'] for i in r['members']]
        if cids:
            spec = json.dumps({"user_id":cids})
            try:
                profiles = thrift_callex(config.OPENUSER_SERVER, OpenUser, 'get_profiles',
                    config.OPENUSER_APPID, spec)
                profiles = {i.user_id:i.__dict__ for i in profiles}
                # 处理返回值
                for m in r['members']:
                    info = profiles.get(m['customer_id'],{})
                    m['avatar'] = info.get('avatar') or config.HJ_AVATAR
                    m['gender'] = info.get('gender', 1)
                    m['nickname'] = info.get('nickname') or m['customer_id']
                    m['last_txdtm'] = tstamp_to_str(m['last_txdtm'], DATETIME_FMT)
            except:
                log.warn('get openuser_info error:%s' % traceback.format_exc())
                raise ThirdError('获取消费者信息失败')

        return r

    def _actv_state(self, d):
        r = {}
        now = int(time.time())
        where = {'userid' : d['userid'], 'status' : 1}
        inwhere, outwhere = {'expire_time' : ('>', now)}, {'expire_time' : ('<=', now)}
        inwhere.update(where)
        outwhere.update(where)
        with get_connection_exception('qf_mchnt') as db:
            r['indated_num'] = db.select_one('member_actv', where=inwhere, fields='count(1) as num')['num']
            r['outdated_num'] = db.select_one('member_actv', where=outwhere, fields='count(1) as num')['num']

        return r

    @check_login
    @raise_excp('获取会员列表失败')
    def GET(self):
        d = self._trans_input()
        # get members info
        r = self._get_members(d)
        # get promote info
        state = self._actv_state(d)

        return self.write(success({
            'now': time.strftime(DATETIME_FMT),
            'customers': r['members'],
            'total_num': r['total_num'],
            'add_customers': r['add_members'],
            'actv_state': state,
            'overdue_warn': r['overdue_warn'],
            'overdue_note': r['overdue_note']
        }))

class Txmore(BaseHandler):
    '''
    交易更多信息
    '''

    @check_login
    @raise_excp('获取数据失败')
    def GET(self):
        cids = self.req.input().get('customer_id') or ''
        cids = [cid for cid in cids.split(',') if cid.strip()]

        customer_ids = []
        for cid in cids:
            if cid.strip():
                try:
                    customer_ids.append(hids.decode(cid)[0])
                except:
                    pass
        if not customer_ids:
            return self.write(success({'info':[]}))

        infos = []
        try:
            spec = json.dumps({'user_id': customer_ids})
            profiles = thrift_callex(config.OPENUSER_SERVER, OpenUser, 'get_profiles',
                                     config.OPENUSER_APPID, spec)
            profiles = {i.user_id:i.__dict__ for i in profiles}
        except:
            log.warn('get openuser_info error:%s' % traceback.format_exc())
        for customer_id in customer_ids:
            if customer_id in profiles:
                profile = profiles[customer_id]
                info = {i:profile[i] or '' for i in ('avatar', 'gender', 'nickname')}
                info['gender'] = info['gender'] or 3
                info['customer_id'] = hids.encode(customer_id)
                infos.append(info)

        return self.write(success({'info': infos}))
