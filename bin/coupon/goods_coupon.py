# coding=utf8

import traceback
import config
import datetime
import json

import logging

from collections import defaultdict

from runtime import hids
from constants import (
    DATE_FMT, COUPON_STATUS_BIND, COUPON_STATUS_USE,
    RECORD_STATUS_USE, ACTIVITY_SHARE_TYPE_GOODS_COUPON
)

from utils.base import BaseHandler
from utils.tools import getid
from utils.decorator import with_customer

from decorator import check_login, raise_excp
from excepts import ParamError, ThirdError, SessionError
from qfcommon.thriftclient.qf_marketing import QFMarketing
from qfcommon.thriftclient.qf_marketing.ttypes import CouponOperateArgs
from qfcommon.thriftclient.open_user import OpenUser
from qfcommon.base.tools import thrift_callex
from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.base.qfresponse import success
from qfcommon.server.client import ThriftClient

log = logging.getLogger()


class RecordList(BaseHandler):
    '''消费券列表'''

    @check_login
    @raise_excp('获取消费券记录失败')
    def GET(self):
        d = self.req.input()
        page = d.get('page', 0)
        pagesize = d.get('pagesize', 10)
        userid = self.user.userid

        paging = (int(pagesize), int(pagesize)*int(page))
        other = 'order by create_time desc limit {} offset {}'.format(*paging)
        ret = {'records': []}

        # 查询交易记录和消费品名称
        records = []
        titles = []
        titles_dict = {}
        with get_connection_exception('qf_marketing') as db:
            records = db.select(
                    table = 'record',
                    fields = ['customer_id', 'create_time',
                        'activity_id', 'xx_id'],
                    where = {
                        'type': RECORD_STATUS_USE,
                        'xx_type': ACTIVITY_SHARE_TYPE_GOODS_COUPON,
                        'use_mchnt_id': userid,
                        },
                    other = other)

            if not records:
                return self.write(success(ret))

            act_ids = [record.get('activity_id') for record in records]

            titles = db.select(
                    table = 'activity',
                    fields = ['title', 'id'],
                    where = {'id': ('in', act_ids)})
            if not titles:
                raise ParamError('获取兑换商品失败')

            titles_dict = {title['id']: title['title'] for title in titles}

        # 查询消费者信息
        cids = {i['customer_id'] for i in records}
        spec = json.dumps({'user_id': list(cids)})

        client = ThriftClient(config.OPENUSER_SERVER, OpenUser)
        client.raise_except = True
        infos = []
        try:
            infos = client.call('get_profiles', config.OPENUSER_APPID, spec)
            infos = {i.user_id:i.__dict__ for i in infos}
        except:
            log.warn(traceback.format_exc())
            raise ThirdError('获取用户信息失败')

        # 整理信息
        for i in records:
            cust_id = int(i['customer_id'])
            cust_info = infos.get(cust_id) or {}
            avatar_str = cust_info.get('avatar') or ''
            i['avatar_url'] = avatar_str.split(':', 1)[-1]
            i['gender'] = cust_info.get('gender') or 0
            i['nickname'] = cust_info.get('nickname') or '微信支付顾客'
            i['exchange_time'] = i['create_time'].strftime('%H:%M:%S')
            i['goods_name'] = titles_dict.get(i.pop('activity_id'), '未知商品')
            i['exchange_code'] = hids.encode(i.pop('xx_id'))

        date_records = defaultdict(list)
        for i in records:
            t = i.pop('create_time').strftime(DATE_FMT)
            date_records[t].append(i)

        # 查询每日的交易数量
        sql = (
                'select FROM_UNIXTIME(create_time, "%%Y-%%m-%%d") as date, '
                'count(id) as num from record '
                'where use_mchnt_id=%s and xx_type=%s and type=%d '
                'group by FROM_UNIXTIME(create_time, "%%Y%%m%%d") '
                'order by create_time desc'
                % (str(userid), ACTIVITY_SHARE_TYPE_GOODS_COUPON, RECORD_STATUS_USE)
                )
        data_infos = []
        with get_connection('qf_marketing') as db:
            data_infos = db.query(sql)
        if not data_infos:
            raise ParamError('获取消费者数量失败')

        # 整理返回信息
        ret = []
        for i in data_infos:
            date = i['date']
            tmp = {}
            tmp['date'] = i['date']
            tmp['use_cnt'] = i['num']
            tmp['customers'] = date_records.get(date) or []
            ret.append(tmp)
        return self.write(success({'records': ret}))


class Exchange(BaseHandler):
    '''兑换'''
    @check_login
    @raise_excp('兑换失败')
    def POST(self):
        userid = self.user.userid

        # 验证兑换码
        code = self.req.input().get('code')
        de_code = hids.decode(code)
        if not de_code:
            raise ParamError('兑换码不存在')
        cb_id = de_code[0]

        # 获取红包绑定信息和活动信息
        cb_info = {}
        act_id = ''
        with get_connection_exception('qf_marketing') as db:
            cb_info = db.select_one(
                    table = 'coupon_bind',
                    where={'id': cb_id})

            if not cb_info:
                raise ParamError('兑换码不存在')

            act_id = cb_info.get('activity_id')

            if not act_id:
                raise ParamError('查询活动信息失败')

        amt = cb_info.get('amt')

        start_time = cb_info.get('start_time')
        expire_time = cb_info.get('expire_time')

        status = cb_info.get('status')
        coupon_mchnt_id = cb_info.get('mchnt_id')
        coupon_rule_id = cb_info.get('coupon_rule_id')

        now = datetime.datetime.now()
        if not (start_time < now < expire_time):
            raise ParamError('不在活动时间内')
        if status != COUPON_STATUS_BIND:
            raise ParamError('这张消费券不能使用了！')

        if not coupon_mchnt_id:
            mchnt_id_list = []
            mchnt_id_json = ''
            with get_connection('qf_marketing') as db:
                mchnt_id_json = db.select_one(
                        fields = 'mchnt_id_list',
                        where = {'coupon_rule_id': coupon_rule_id})

            if not mchnt_id_json:
                raise ParamError('查询可使用商户列表失败')

            mchnt_id_list = json.loads(mchnt_id_json)

            if not (str(userid) in mchnt_id_list):
                raise ParamError('该消费券不能在该店铺使用')
        if int(coupon_mchnt_id) != int(userid):
            raise ParamError('该消费券不能在该店铺使用')


        # 使用红包
        coas = CouponOperateArgs()
        coas.coupon_code = cb_info.get('coupon_code')
        coas.src = cb_info.get('src')
        coas.type = COUPON_STATUS_USE
        coas.trade_amt = int(amt)
        coas.customer_id = str(cb_info.get('customer_id'))
        coas.out_sn = str(getid())
        coas.content = '交易使用消费券'
        coas.mchnt_id = userid

        try:
            thrift_callex(config.QF_MARKETING_SERVERS, QFMarketing,
                    'coupon_use', coas)
        except:
            log.warn(traceback.format_exc())
            raise ThirdError('使用红包失败')

        return self.write(success({}))


class Status(BaseHandler):
    '''获取消费券的状态'''

    @with_customer
    @raise_excp('获取状态失败')
    def GET(self):
        if not self.customer.is_login():
            raise SessionError('登录以后才可以使用！')

        customer_id = self.customer.customer_id

        code  = self.req.input().get('code')
        if not code:
            raise ParamError('未能获取二维码')

        decode = hids.decode(code)
        if not decode:
            raise ParamError('解析二维码失败')
        cb_id = decode[0]


        # 查询数据库
        status = {}
        with get_connection('qf_marketing') as db:
            status = db.select_one(
                    table = 'coupon_bind',
                    fields = 'status, customer_id',
                    where = {
                        'id': cb_id,
                        'customer_id': customer_id}
                    )

        if not status:
            raise ParamError('没能获取到券的状态')

        return self.write(success(status))
