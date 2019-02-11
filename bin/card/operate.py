# coding:utf-8
'''
c端调用接口
'''

import traceback
import time
import logging
import random

from collections import defaultdict

from constants import DATETIME_FMT
from base import (
    CardBase, CODE_STATUS_EXCHANGED, CODE_STATUS_CREATE,
    CODE_STATUS_CANCEL
)
from decorator import raise_excp
from excepts import ParamError, SessionError
from runtime import hids

from utils.decorator import check, with_customer
from utils.tools import getid, apcli_ex, apcli, userid_cache
from utils.valid import is_valid_int
from utils.date_api import str_to_tstamp

from qfcommon.base.qfresponse import success, error, QFRET
from qfcommon.base.dbpool import get_connection_exception, get_connection

log = logging.getLogger()


class Tips(CardBase):
    '''
    获取集点活动tips (c端服务器调用， 会验证ip)
    '''

    _base_err = '获取tip失败'

    @check('check_ip')
    def GET(self):
        userid = int(self.req.input().get('userid').strip())
        r = None
        with get_connection('qf_mchnt') as db:
            now = int(time.time())
            r = db.select_one(
               'card_actv',
               where= {
                   'userid': self.get_userid_condition(userid),
                   'expire_time': ('>', now),
                   'start_time': ('<', now)
               },
               fields= [
                   'exchange_pt', 'goods_name', 'goods_amt',
                   'obtain_amt', 'status', 'obtain_limit'
               ],
               other='order by ctime desc'
            ) or {}

        if not r:
            return error(QFRET.NODATA)

        return success(r)


class ExchangeCode(CardBase):
    '''
    获取会员集点活动兑换码
    '''

    _base_err = '获取数据失败'

    def tidy_codes(self, codes, customer, actv):
        cur_num = customer['cur_pt'] / actv['exchange_pt']
        codes_num = len(codes)

        # 若兑换卡数相同
        if cur_num == codes_num:
            return  codes

        now = int(time.time())
        # 当前卡数大于实际卡数
        if cur_num < codes_num:
            cancel_num = codes_num - cur_num
            cancel_codes = [codes[i]['id'] for i in range(cancel_num)]
            with get_connection('qf_mchnt') as db:
                db.update(
                    table='exchange_record',
                    values={
                        'utime': now,
                        'status': CODE_STATUS_CANCEL
                    },
                    where={
                        'id': ('in', cancel_codes)
                    }
                )
            return codes[cancel_num:]

        # 实际卡数大于当前卡数
        with get_connection('qf_mchnt') as db:
            records = db.select(
                table='exchange_record',
                fields='code, status',
                where={'activity_id': actv['id']}
            )
        allcodes = defaultdict(set)
        # allcodes:
        # 0: 所有code 1: 已兑换 2:创建优惠码 3:已撤销
        for i in records or []:
            allcodes[0].add(i['code'])
            allcodes[i['status']].add(i['code'])

        add_num = cur_num - codes_num
        choose, allchoose = [], set(range(1, 10000))
        if 9999 - len(allcodes[0]) > add_num:
            choose = random.sample(list(allchoose-allcodes[0]), add_num)
        else:
            try:
                choose = random.sample(
                    list(allchoose-allcodes[CODE_STATUS_CREATE]),
                    add_num
                )
            except:
                log.error('兑换码不够,error:%s' % traceback.format_exc())

        data = []
        for code in choose:
            data.append({
                'id': getid(), 'code': code,
                'userid': actv['userid'], 'ctime': now,
                'utime': now, 'customer_id': customer['customer_id'],
                'activity_id': actv['id'], 'status': CODE_STATUS_CREATE
            })
        if data:
            codes.extend(data)
            with get_connection('qf_mchnt') as db:
                db.insert_list('exchange_record', data)

        return codes

    def card_info(self, actv):
        r = {}

        # 活动信息
        fields = (
            'goods_name', 'goods_amt', 'exchange_pt',
            'obtain_amt', 'obtain_limit', 'status',
            'start_time', 'expire_time'
        )
        for i in fields:
            r[i] = actv.get(i) or ''
        r['start_time'] = str_to_tstamp(str(r['start_time']), DATETIME_FMT)
        r['expire_time'] = str_to_tstamp(str(r['expire_time']), DATETIME_FMT)

        # 店铺信息
        user = apcli_ex('findUserBriefById', actv['userid'])
        r['shopname'] = getattr(user, 'shopname', '')
        r['addr'] = getattr(user, 'address', '')

        return r

    @check()
    def GET(self):
        # customer_id
        customer_id = self.get_customer_id()

        # 活动id
        activity_id = self.req.input().get('activity_id')
        if not is_valid_int(activity_id):
            raise ParamError('集点活动不存在')
        activity_id = int(activity_id)

        # 活动信息
        actv = None
        with get_connection('qf_mchnt') as db:
            actv = db.select_one('card_actv', where={'id': activity_id})
        if not actv:
            raise ParamError('活动不存在')

        with get_connection_exception('qf_mchnt') as db:
            where = {
                'activity_id': activity_id,
                'customer_id': customer_id
            }
            customer = db.select_one('member_pt', where= where)
            # 若未有集点卡记录
            if not customer:
                raise ParamError('未领取集点卡')

            # 消费者records现有的兑换码
            where['status'] = CODE_STATUS_CREATE
            codes = db.select(
                table='exchange_record', where=where,
                other='order by ctime desc'
            ) or []

        codes = self.tidy_codes(codes, customer,  actv)

        return success({
            'codes': [
                {
                    'id': str(i['id']),
                    'code': '{:0>4d}'.format(i['code']),
                    'qrcode': ''.join([
                            self.pre_code,
                            hids.encode(i['code'], actv['id'], i['id'])
                        ])
                } for i in codes
            ],
            'card_info': self.card_info(actv)
        })


class ExchangeQuery(CardBase):
    '''
    查询兑换码是否被兑换 (c端页面调用)
    '''

    @raise_excp('查询兑换码是否被兑换失败')
    def GET(self):
        where = {'status' : CODE_STATUS_EXCHANGED}
        params = self.req.input()
        if is_valid_int(params.get('id')):
            where['id'] =int(params['id'])

        elif 'code' in params:
            try:
                code = params['code']
                encode = code[len(self.pre_code):]
                code, actv_id, code_id = hids.decode(encode)
                code = '{:0>4d}'.format(code)
                where['id'] = code_id
            except:
                raise ParamError('兑换码不存在')

        else:
            raise ParamError('兑换码不存在')

        with get_connection_exception('qf_mchnt') as db:
            r = db.select_one('exchange_record', where=where)

        return success({'exchanged': int(bool(r))})


class CardList(CardBase):
    '''
    我的卡包-列表(c端页面调用)
    '''

    def card_list(self, d):
        with get_connection_exception('qf_mchnt') as db:
            where = {
                'mp.customer_id': d['customer_id'],
                'ca.expire_time': ('>', int(time.time()))
            }
            if d.get('groupid') and not userid_cache[d['groupid']]:
                return [], 0

            if d['mchnt_id']:
                link_ids = apcli.userids_by_linkid(
                        int(d['mchnt_id']), 'merchant') or []
                link_ids = {i.userid for i in link_ids}
                link_ids.add(d['mchnt_id'])
                where['ca.userid'] = ('in', link_ids)

            elif d.get('groupid') and userid_cache[d['groupid']]:
                where['ca.userid'] = ('in', userid_cache[d['groupid']])

            on = {'mp.activity_id': 'ca.id'}
            fields = ['mp.'+i for i in ('cur_pt', 'id', 'activity_id')]
            fields += ['ca.'+i for i in
                    ('obtain_amt', 'obtain_limit', 'start_time',
                     'expire_time', 'exchange_pt','goods_amt',
                     'goods_name', 'status', 'userid')]
            r = db.select_join('member_pt mp', 'card_actv ca',
                    on= on, where= where, fields= fields,
                    other= ('order by mp.cur_pt desc '
                            'limit {} offset {}'.format(
                            d['limit'], d['offset']))) or []

            total_num = db.select_join_one(
                    'member_pt mp', 'card_actv ca',
                    on= on, where=where, fields='count(1) as num')['num']
            if not r: return r, total_num

        # 用户信息
        userids = [i['userid'] for i in r]
        users = apcli_ex('findUserBriefsByIds', userids)
        users = {i.uid:i.__dict__ for i in users}
        for i in r:
            t = users.get(i['userid']) or {}
            i['id'] = str(i['id'])
            i['activity_id'] = str(i['activity_id'])
            i['shopname'] = t.get('shopname') or ''
            i['addr'] = t.get('address') or ''
            i['diff_exchange'] = max(i['exchange_pt']-i['cur_pt']%i['exchange_pt'], 0)
            i['exchange'] = i['cur_pt'] / i['exchange_pt']
            i['start_time'] = str_to_tstamp(str(i['start_time']))
            i['expire_time'] = str_to_tstamp(str(i['expire_time']))

        return r, total_num

    @with_customer
    @raise_excp('获取列表失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        data = {}

        # userid
        try:
            data['mchnt_id'] = hids.decode(d['mchnt_id'])[0]
        except:
            data['mchnt_id'] = int(d.get('mchnt_id') or 0)

        # customer_id
        try:
            data['customer_id'] = hids.decode(d['customer_id'])[0]
        except:
            if self.customer.customer_id:
                data['customer_id'] = self.customer.customer_id
            else:
                raise SessionError('消费者未登录')
        # groupid
        groupid = d.get('groupid')
        if is_valid_int(groupid):
            data['groupid'] = groupid

        # 分页信息
        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息错误')
        data['offset'], data['limit'] = int(page)*int(pagesize), int(pagesize)

        # 获取列表
        r, total_num = self.card_list(data)

        return self.write(success({'cards': r, 'total_num': total_num}))


class CardInfo(CardBase):
    '''
    我的卡包-详细(c端页面调用)
    '''

    @with_customer
    @raise_excp('获取卡详细信息失败')
    def GET(self):
        customer_id = self.get_cid()
        aid = int(self.req.input().get('id'))

        actv = None
        with get_connection_exception('qf_mchnt') as db:
            where = {'mp.customer_id': customer_id, 'mp.id': aid}
            on = {'mp.activity_id': 'ca.id'}
            fields  = ['mp.'+i for i in ('cur_pt', 'userid', 'id', 'activity_id')]
            fields += ['ca.'+i for i in ('obtain_amt', 'start_time', 'expire_time',
                    'obtain_limit', 'exchange_pt', 'goods_amt', 'goods_name', 'status')]
            actv = db.select_join_one(
                    'member_pt mp', 'card_actv ca', on=on,
                     where=where, fields=fields) or {}
        if not actv:
            raise ParamError('未找到该卡信息')

        user = apcli_ex('findUserBriefById', actv['userid']) or {}
        if user: user = user.__dict__
        actv['id'] = str(actv['id'])
        actv['activity_id'] = str(actv['activity_id'])
        actv['shopname'] = user.get('shopname') or ''
        actv['addr'] = user.get('address') or ''
        actv['diff_exchange'] = max(
                actv['exchange_pt'] - actv['cur_pt']%actv['exchange_pt'], 0)
        actv['exchange'] = actv['cur_pt'] / actv['exchange_pt']
        actv['start_time'] = str_to_tstamp(str(actv['start_time']), DATETIME_FMT)
        actv['expire_time'] = str_to_tstamp(str(actv['expire_time']), DATETIME_FMT)
        actv['is_baipai'] = self.is_baipai(user['groupid'])

        return self.write(success(actv))
