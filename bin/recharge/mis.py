# encoding:utf-8

import math
import random
import config
import json
import time
import datetime
import logging
log = logging.getLogger()

from base import PROMO_STATUS, PROMO_CODE_STATUS, PROMO_CODE_TYPE
from constants import (
    DATETIME_FMT, MCHNT_STATUS, MCHNT_STATUS_NORMAL,
    OPERATE_RECHARGE, OPERATE_ADD_PROMO, OPERATE_CHANGE_PROMO,
    OPERATE_ADD_PROMO_CODE, OPERATE_CHANGE_PROMO_CODE,
    OPERATE_ADD_NUM_PROMO_CODE
)
from decorator import check_ip, raise_excp, keep_operate

from excepts import ParamError

from utils.base import BaseHandler
from utils.valid import is_valid_datetime, is_valid_int
from utils.date_api import str_to_tstamp, future
from utils.tools import getids, getid

from qfcommon.base.dbpool import get_connection, get_connection_exception, DBFunc
from qfcommon.base.qfresponse import success

class GoodsList(BaseHandler):
    '''
    商品列表
    '''

    @check_ip()
    def GET(self):
        ret = {}
        for goods in config.PAYING_GOODS['goods']:
            ret[goods['code']] = goods['name']

        for goods in config.GOODS:
            if goods.get('is_gratis'):
                continue
            ret[goods['code']] = goods['name']

        return self.write(success(ret))

class AddPromoCode(BaseHandler):

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        data = {}
        # 验证userid
        data['userid'] = d.get('userid')
        if not data['userid']:
            raise ParamError('充值商户ID不能为空')
        # 码类型
        data['type'] = int(d.get('code_type', 1))
        if data['type'] not in PROMO_CODE_TYPE.values():
            raise ParamError('码类型不对')
        # opuserid, 备注
        data['content'] = d.get('content', '')

        # 余额类型码
        if data['type'] ==  PROMO_CODE_TYPE['balance']:
            data['num'], data['use_limit'] = int(d.get('num') or '0'), int(d.get('use_limit') or '0')
            if not data['num']:
                raise ParamError('生成0个推广码')
        # 余次类型码
        else:
            data['amt'] = d.get('amt') or 0
            data['total_num'] = int(d.get('total_num') or 0)
            if not data['total_num']:
                raise ParamError('总共可使用0次？')
            data['use_limit'] = int(d.get('per_num') or 0)
            if data['use_limit'] <= 0:
                raise ParamError('每个码的试用次数必须大于0')
            data['num'] = math.ceil(data['total_num']/(1.0*data['use_limit']))

        self.operate_type = (
            OPERATE_ADD_PROMO_CODE if data['type'] == 1 else
            OPERATE_ADD_NUM_PROMO_CODE
        )

        return data

    def get_codes(self, num):
        def gen_code(num=1, length=8, notin=None):
            if not notin: notin = {}
            ret = set()
            while num > 0:
                tmp = ''.join(random.choice('ABCDEFGHIJKLMNPQRSTUVWXYZ123456789') for _ in range(length))
                if tmp not in notin and tmp not in ret:
                    ret.add(tmp)
                    num -= 1
            return ret

        # 产生codes
        codes, total = set([]), 0
        with get_connection('qf_mchnt') as db:
            while total < num:
                new_codes = gen_code(num - total, notin=codes)

                exists = db.select(
                    table='promo_code',
                    where={'code': ('in', new_codes)},
                    fields='code'
                ) or []
                exists_codes = {i['code'] for i in exists}

                for code in new_codes:
                    if code not in exists_codes:
                        codes.add(code)

                total = len(codes)

        if num != len(codes):
            raise ParamError('产生兑换码失败')

        return codes

    @keep_operate()
    def _add(self, d):
        now = int(time.time())

        # 充值码
        codes = self.get_codes(d['num'])

        # id
        ids = getids(d['num'])

        indata = []
        for code, _id in zip(codes, ids):
            indata.append({
                'id': _id, 'code': code,
                'userid': d['userid'],
                'content': d['content'],
                'use_limit': d['use_limit'],
                'ctime': now, 'utime': now,
                'type': d['type']
            })
        if d['type'] == PROMO_CODE_TYPE['num'] and d['total_num'] % d['use_limit']:
            indata[-1]['use_limit'] = d['total_num'] % d['use_limit']

        with get_connection_exception('qf_mchnt') as db:
            db.insert_list('promo_code' , indata)

        # 余次类型更新promo表
        if d['type'] == PROMO_CODE_TYPE['num']:
            db.update(
                table='promo',
                values={'num': DBFunc('num+%s'%d['total_num'])},
                where = {'userid': d['userid']}
            )

        return self.write(success({'codes': [(i['code'],i['use_limit']) for i in indata]}))

    @check_ip()
    @raise_excp('添加渠道推广码失败')
    def POST(self):
        d = self._trans_input()

        self._add(d)

class ChangePromoCode(BaseHandler):
    '''
    修改渠道
    '''
    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}

        # 修改值
        update_data = {}
        if 'status' in d:
            if d['status'] not in  map(str, PROMO_CODE_STATUS.values()):
                raise ParamError('修改的状态不对')
            update_data['status'] = d['status']
        if 'use_limit' in d:
            if not  is_valid_int(d['use_limit']):
                raise ParamError('推广码的限制次数为数字')
            update_data['use_limit'] = d['use_limit']

        if not update_data:
            raise ParamError('渠道推广码未做任何修改')
        update_data['utime'] = int(time.time())
        r['update_data'] = update_data

        # 商户userid
        r['code'] = d.get('code')
        if not r['code']:
            raise ParamError('渠道推广码不能为空')

        return r

    @check_ip()
    @raise_excp('修改渠道失败')
    @keep_operate(OPERATE_CHANGE_PROMO_CODE)
    def POST(self):
        d = self._trans_input()

        # 修改渠道
        with get_connection('qf_mchnt') as db:
            db.update('promo_code', d['update_data'], {'code': d['code']})

        return self.write(success({}))

class AddPromo(BaseHandler):
    '''
    添加渠道
    '''
    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        # 渠道userid
        r['userid'] = d.get('userid')
        if not r['userid']:
            raise ParamError('添加的渠道userid不能为空')

        return r

    @check_ip()
    @raise_excp('添加渠道失败')
    @keep_operate(OPERATE_ADD_PROMO)
    def POST(self):
        d = self._trans_input()
        now = int(time.time())

        # 插入渠道
        with get_connection('qf_mchnt') as db:
            promo_data = {'id': getid(), 'userid': d['userid'], 'balance': 0,
                    'status': PROMO_STATUS['normal'], 'ctime': now, 'utime':now}
            db.insert('promo', promo_data)
        return self.write(success({}))

class ChangePromo(BaseHandler):
    '''
    修改渠道
    '''
    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        # 修改值
        update_data = {}
        if 'status' in d:
            if d['status'] not in  map(str, PROMO_STATUS.values()):
                raise ParamError('修改的状态不对')
            update_data['status'] = d['status']

        if 'balance' in d:
            if d['mode'] not in ('fixed', 'addon'):
                raise ParamError('修改余额的模式不对')
            if not is_valid_int(d['balance']):
                raise ParamError('余额必须为数字')

            if d['mode'] == 'fixed':
                update_data['balance'] = d['balance']
            else:
                update_data['balance'] = DBFunc('balance+%d' % int(d['balance']))

        if not update_data:
            raise ParamError('商户未做任何修改')
        update_data['utime'] = int(time.time())
        r['update_data'] = update_data

        # 商户userid
        r['userid'] = d.get('userid')
        if not r['userid']:
            raise ParamError('渠道商户ID不能为空')

        return r

    @check_ip()
    @raise_excp('修改渠道失败')
    @keep_operate(OPERATE_CHANGE_PROMO)
    def POST(self):
        d = self._trans_input()

        # 修改渠道
        with get_connection('qf_mchnt') as db:
            where = {'userid': d['userid']}
            db.update('promo', d['update_data'], where)

        return self.write(success({}))

# 旧服务
old_services = {}
for good in config.PAYING_GOODS.get('goods'):
    old_services[good['code']] = config.PAYING_GOODS.get('free', 0)

# 新服务
new_services = {}
for good in config.GOODS:
    new_services[good.get('code')] = good.get('free', 0)

class Recharge(BaseHandler):
    '''
    会员付费
    '''
    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}

        # 商户userid
        r['userid'] = json.loads(d.get('userid') or '')
        if not r['userid']:
            raise ParamError('充值商户ID不能为空')

        # 调整截止日期模式
        r['mode'] = d.get('mode', 'dtm')
        if r['mode'] == 'dtm':
            # 商户过期时间
            expdtm = d.get('expire_time')
            if not is_valid_datetime(expdtm):
                raise ParamError('截止日期时间格式不对')
            r['expire_time'] = str_to_tstamp(expdtm, DATETIME_FMT)
        elif r['mode'] == 'param':
            if not all(map(is_valid_int, (d.get('year'), d.get('month'), d.get('day')))):
                raise ParamError('日期参数必须为整数')

            r['year'] = int(d.get('year', '0'))
            r['month'] = int(d.get('month', '0'))
            r['day'] = int(d.get('day', '0'))

            if not any((r['year'], r['month'], r['day'])):
                raise ParamError('延长日期不能为0')

        # 备注
        r['content'] = d.get('content', '')

        # 商户状态
        if d.get('status') in map(str, MCHNT_STATUS):
            r['status'] = int(d.get('status'))

        # 会员服务
        r['goods_code'] = d.get('goods_code', 'card')

        return r

    def _recharge(self, d):
        def _insert(userids, expire_time):
            if not userids: return
            with get_connection_exception('qf_mchnt') as db:
                status = d.get('status') or MCHNT_STATUS_NORMAL
                now = int(time.time())
                indata = [{'id': getid(), 'userid': i, 'goods_code': d['goods_code'],
                    'status':status, 'expire_time': expire_time,
                    'content': d['content'], 'ctime': now, 'utime': now}
                    for i in userids ]
                db.insert_list('recharge', indata)

        def _update(userids, **cf):
            if not userids: return
            with get_connection_exception('qf_mchnt') as db:
                updata = {'content': d['content'], 'utime': now}
                updata.update(cf)
                if d.get('status'):
                    updata['status'] = d.get('status')
                db.update('recharge', updata, {'userid': ('in', userids), 'goods_code' : d['goods_code']})

        def dtm():
            update_userids = {i['userid'] for i in mchnts}
            insert_userids = list(set(d['userid']) - update_userids)
            # 插入新的会员
            expire_time = d['expire_time']
            _insert(insert_userids, expire_time)

            # 更新会员
            _update(update_userids, expire_time=d['expire_time'])

        def param():
            td = time.strftime(DATETIME_FMT)
            update_userids = {i['userid'] for i in mchnts}
            insert_userids = list(set(d['userid']) - update_userids)
            outdate_userids = {i['userid'] for i in mchnts if str(i['expire_time']) < td}
            indate_userids = {i['userid'] for i in mchnts if str(i['expire_time']) > td}

            # 默认免费体验时间
            free = 0
            for services in (old_services, new_services):
                if d['goods_code'] in services:
                    free = services[d['goods_code']]
                    break

            st = datetime.date.today()
            expire_time = str_to_tstamp(str(future(st, years=d['year'],
                    months=d['month'], days=d['day'])) + ' 23:59:59', DATETIME_FMT)
            _insert(insert_userids, expire_time+free*24*3600)

            # 更新会员(已过期)
            _update(outdate_userids, expire_time=expire_time)

            # 更新会员(未过期)
            exp = (d['year'] * 365 + d['month'] * 30+ d['day']) * 24 * 3600
            expire_time = DBFunc('expire_time+%d'%exp)
            _update(indate_userids, expire_time = expire_time)

        now = int(time.time())

        # 所有的商户信息
        where = {'userid': ('in', d['userid']), 'goods_code' : d['goods_code']}
        with get_connection_exception('qf_mchnt') as db:
            mchnts = db.select('recharge', where=where, fields='userid, expire_time') or []

        if d['mode'] == 'dtm':
            dtm()
        elif d['mode'] == 'param':
            param()

    @check_ip()
    @raise_excp('商户充值失败')
    @keep_operate(OPERATE_RECHARGE)
    def POST(self):
        # 转化输入
        d = self._trans_input()

        # 充值
        self._recharge(d)

        self.write(success({}))
