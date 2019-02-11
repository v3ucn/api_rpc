# coding:utf-8

import time
import json
import config
import logging
import traceback

from decorator import check_login, raise_excp, with_validator
from excepts import ThirdError, ParamError

from runtime import hids
from utils.base import BaseHandler
from utils.qdconf_api import get_qd_conf_value
from utils.payinfo import adjust_payinfo_ex
from utils.valid import is_valid_int
from utils.tools import fen_to_yuan
from utils.date_api import (
    future, tstamp_to_str, get_day_begin_ts
)
from utils.decorator import check
from base import MemBase, MemDefine

from qfcommon.thriftclient.qf_customer import QFCustomer
from qfcommon.web.validator import Field, T_REG, T_INT, T_STR
from qfcommon.base.tools import thrift_callex
from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.base.qfresponse import success

log = logging.getLogger()


class CheckMember(MemBase):
    '''
    添加会员
    '''

    _base_err = '无法识别该会员，请确认二维码来自公众号会员中心'

    @check('login')
    def POST(self):
        userid = int(self.user.userid)

        params = self.req.input()
        if not params.get('encid'):
            raise ParamError(self._base_err)

        encode = params.get('encid').lstrip(self.MEMBER_PRE_CODE)

        customer_id, tstmp = hids.decode(encode)

        limit = getattr(config, 'ADD_MEMBER_LIMIT', 30)
        if time.time()- tstmp > limit:
            raise ParamError('二维码过期了')

        is_new = self.be_member(userid, customer_id)

        return success({
            'is_new': is_new,
            'customer_id': hids.encode(customer_id)
        })


class Head(BaseHandler):
    '''
    会员管理列表头部
    '''

    FILTER_PATTERN = r'^(all|lose|card|prepaid|submit)$'

    _validator_fields = [
        Field('filter_key', T_REG, match=FILTER_PATTERN, default='all'),
    ]

    @check_login
    @with_validator()
    @raise_excp('获取数据失败')
    def GET(self):
        userid = self.user.userid

        mode = self.validator.data['filter_key']
        ret = {}
        summary = {}
        summary['total_num'] = summary['td_num'] = 0
        with get_connection('qf_mchnt') as db:
            where = {'userid': userid}
            if mode in ('all', 'lose'):
                # 总数
                if mode == 'lose':
                    where['last_txdtm'] = ('<=',
                            future(days=-60, fmt_type='timestamp'))
                summary['total_num']= db.select_one(
                        table= 'member',
                        where= where,
                        fields= 'count(1) as num')['num']

            elif mode in ('card', 'prepaid', 'submit'):
                summary['total_num'] = db.select_one(
                        'member_tag',
                        where= {
                            'userid': userid,
                            mode: ('>=', 1)
                        },
                        fields= 'count(1) as num')['num']


            summary['td_num']= db.select_one(
                    table= 'member',
                    where= {
                        'userid': userid,
                        'ctime': ('>', get_day_begin_ts())
                    },
                    fields= 'count(1) as num')['num']
        ret['summary'] = summary

        for k in ('filters', 'sorts', 'flags'):
            ret[k] = get_qd_conf_value(mode='member_'+k, key='service',
                                       groupid=self.get_groupid())
        ret['filters'] = ret['filters'] or config.MEMBER_FILTERS
        ret['sorts'] = ret['sorts'] or config.MEMBER_SORTS
        ret['flags'] = ret['flags'] or config.MEMBER_FLAGS

        return self.write(success(ret))

class List(MemBase):
    '''
    会员列表
    '''
    SORT_PATTERN = r'^(last_txdtm|num|txamt)(\|desc)?$'
    FILTER_PATTERN = r'^(all|lose|card|prepaid|submit)$'

    _validator_fields = [
        Field('sort_key', T_REG, match=SORT_PATTERN, default='last_txdtm|desc'),
        Field('filter_key', T_REG, match=FILTER_PATTERN, default='all'),
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
    ]

    def get_overdue(self, limit, offset):
        '''
        会员服务过期
        '''
        member_limit = get_qd_conf_value(mode='member_limit', key='service',
                                         groupid=self.get_groupid(), default=10)

        overdue = {'limit': member_limit, 'warn': 0, 'note': ''}
        if limit+offset < member_limit:
            return overdue

        payinfo = adjust_payinfo_ex(self.user.userid,
                service_code= 'member_manage', groupid= self.get_groupid())
        if payinfo['overdue']:
            overdue['warn'] = 1
            overdue['note'] = ('未开通会员服务，仅可显示{}个会'
                               '员信息'.format(member_limit))
            overdue['limit'] = max(min(member_limit-offset, limit), 0)

        return overdue

    def get_members_ext(self, mode):
        data = self.validator.data
        userid = int(self.user.userid)

        orderby = 'order by m.{}'.format(' '.join(data['sort_key'].split('|')))
        if mode in ('all', 'lose'):
            where = {'userid': userid}
            if mode == 'lose':
                where['last_txdtm'] = ('<=',
                    future(days=-60, fmt_type='timestamp'))
            with get_connection('qf_mchnt') as db:
                members = db.select(
                        table= 'member m',
                        where= where,
                        other= '{} limit {} offset {}'.format(
                               orderby, data['pagesize'],
                               data['page']*data['pagesize']),
                        fields= 'customer_id, txamt, num, last_txdtm, userid')

        # 需要联member_tag表查询
        elif mode in ('card', 'prepaid', 'submit'):
            with get_connection('qf_mchnt') as db:
                members = db.select_join(
                        table1= 'member m',
                        table2= 'member_tag mt',
                        on= {
                            'm.userid': 'mt.userid',
                            'm.customer_id': 'mt.customer_id'
                        },
                        where= {
                            'm.userid': userid,
                            'mt.userid': userid,
                            'mt.'+mode: ('>', 0),
                        },
                        other= '{} limit {} offset {}'.format(
                               orderby, data['pagesize'],
                               data['page']*data['pagesize']),
                        fields= ('m.customer_id, m.txamt, m.num, '
                                 'm.last_txdtm, m.userid'))
        return members

    def get_members(self):
        members = self.get_members_ext(self.validator.data['filter_key'])
        if not members:
            return []

        cids = [i['customer_id'] for i in members]
        profiles, tags = {}, {}
        if cids:
            spec = json.dumps({'user_id': cids})
            try:
                profiles = thrift_callex(config.OPENUSER_SERVER, QFCustomer, 'get_profiles',
                                         config.OPENUSER_APPID, spec)
                profiles = {i.user_id:i.__dict__ for i in profiles}
            except:
                log.warn('get openuser_info error:%s' % traceback.format_exc())
                raise ThirdError('获取消费者信息失败')

            tags = self.get_tags(cids)
            tags_dict = {flag.keys()[0]:flag.values()[0]
                    for flag in config.MEMBER_FLAGS}

        for m in members:
            customer_id = m['customer_id']
            info = profiles.get(customer_id,{})
            m['avatar'] = info.get('avatar') or config.HJ_AVATAR
            m['gender'] = info.get('gender', 1)
            m['nickname'] = info.get('nickname') or customer_id
            m['last_txdtm'] = tstamp_to_str(m['last_txdtm'])
            m['tag'] = tags[customer_id]
            mem_tags = tags[customer_id]
            m['tag'] = [tag for tag in mem_tags
                         if tag in tags_dict]
            m['is_auth'] = 1 if 'submit' in tags[customer_id] else 0
            m['customer_id'] = hids.encode(customer_id)
        return members

    @check_login
    @with_validator()
    @raise_excp('获取数据失败')
    def GET(self):
        data = self.validator.data

        overdue = self.get_overdue(data['pagesize'],
                                   data['page']*data['pagesize'])
        if overdue['limit']:
            members = self.get_members()
        else:
            members = []

        return success({
            'members': members,
            'overdue': overdue
        })


class Info(MemBase):
    '''
    获取消费详细信息
    '''

    def get_actv_prepaid(self, userid, customer_id):
        actv = {'desc': '0元', 'title': '储值状态', 'link': ''}

        balance = self.get_balance(userid, customer_id) or 0
        actv['desc'] = '余额:{}元'.format(fen_to_yuan(balance))
        actv['link'] = getattr(config, 'MEMBER_PREPAID_LINK', '').format(
                hids.encode(int(customer_id)))
        return actv

    _base_err = '获取数据失败'

    @check('login')
    def GET(self):
        input_cid = self.req.input().get('customer_id')
        try:
            customer_id = hids.decode(input_cid)[0]
        except:
            customer_id = input_cid
        if not is_valid_int(customer_id):
            raise ParamError('参数错误')

        customer_id = int(customer_id)
        userid = int(self.user.userid)
        userids = self.get_link_ids() or []
        userids.append(userid)

        member = None
        with get_connection('qf_mchnt') as db:
            member = db.select_one(
                table= 'member',
                where= {
                    'userid': ('in', userids),
                    'customer_id': customer_id
                },
                fields= 'customer_id, txamt, num, last_txdtm, userid'
            )
        if not member:
            raise ParamError('暂未获得会员信息~')

        profile = {}
        try:
            profile = thrift_callex(
                config.OPENUSER_SERVER, QFCustomer,
                'get_profiles', config.OPENUSER_APPID,
                json.dumps({'user_id': customer_id})
            )[0].__dict__
        except:
            log.warn('get openuser_info error:%s' % traceback.format_exc())

        tags = self.get_tags(customer_id)
        tags_dict = {flag.keys()[0]:flag.values()[0] for flag in config.MEMBER_FLAGS}

        default_val = '暂无'

        member['per_txamt'] = member['txamt'] / (member['num'] or 1)
        member['avatar'] = profile.get('avatar') or config.HJ_AVATAR
        member['gender'] = profile.get('gender', 1)
        member['birthday'] = default_val
        member['mobile'] = default_val
        member['name'] = default_val
        member['is_auth'] = 0
        if 'submit' in tags:
            member['birthday'] = profile.get('birthday') or default_val
            member['mobile'] = profile.get('mobile') or default_val
            member['name'] = profile.get('cname') or default_val
            member['is_auth'] = 1

        member['nickname'] = profile.get('nickname') or default_val
        member['last_txdtm'] = tstamp_to_str(member['last_txdtm'])
        member['tag'] = [tags_dict[tag] for tag in tags
                         if tag in tags_dict]
        member['customer_id'] = hids.encode(customer_id)

        actvinfo = []
        actvinfo.append(self.get_actv_card(userid, customer_id))
        actvinfo.append(self.get_actv_prepaid(userid, customer_id))

        return success({
            'baseinfo': member,
            'actvinfo': actvinfo
        })

class AddTag(MemBase):
    '''
    获取消费详细信息
    '''

    TAG_PATTERN = r'^(coupon|card|prepaid|sale|diancan|submit)$'

    _validator_fields = [
        Field('customer_id', T_INT, isnull=False),
        Field('userid', T_INT, isnull=False),
        Field('tag', T_STR, isnull=False),
        Field('src', T_INT, default=4),
    ]

    _base_err = '更新消费者tag失败'

    @check(['check_ip', 'validator'])
    def POST(self):
        data = self.validator.data
        userid = data['userid']
        customer_id = data['customer_id']
        src = data['src']
        self.add_tag(userid, customer_id, data['tag'], src)

        return self.write(success({}))


class Privilege(MemBase):
    '''
    获取会员特权
    '''

    _base_err = '获取会员特权失败'

    @check(['check_ip', ])
    def GET(self):
        userid = self.req.input().get('userid')
        if not is_valid_int(userid):
            raise ParamError('userid为空')

        content = ''
        with get_connection('qf_mchnt') as db:
            privilege = db.select_one(
                'member_actv',
                where= {
                    'userid': userid,
                    'type': MemDefine.ACTV_TYPE_PRIVI
                }
            ) or {}
            content = privilege.get('content') or ''

        return self.write(success({'content': content}))


class Cardno(MemBase):
    '''
    获取会员卡号
    '''

    _base_err = '获取会员特权失败'

    @check(['check_ip', ])
    def GET(self):
        userid = self.req.input().get('userid')
        if not is_valid_int(userid):
            raise ParamError('userid为空')

        customer_id = self.req.input().get('customer_id')
        if not is_valid_int(customer_id):
            raise ParamError('商户id为空')

        cardno = None
        with get_connection_exception('qf_mchnt') as db:
            member = db.select_one(
                'member',
                where= {
                    'userid': userid,
                    'customer_id': customer_id
                }
            )

        if member:
            cardno = member['id']

        else:
            self.be_member(userid, customer_id, MemDefine.MEMBER_SRC_CARD)
            cardno = getattr(self, '_cardno', '')

        return self.write(success({'cardno': cardno}))
