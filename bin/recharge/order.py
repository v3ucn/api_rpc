# encoding:utf-8

import datetime
import time
import json
import traceback
import config
import re

paying_goods = config.PAYING_GOODS

import logging
log = logging.getLogger()

from constants import DATETIME_FMT
from decorator import check_login, check_login_ex, raise_excp, check_ip
from util import getid, prelogin_lock, postlogin_lock

from base import RechargeUtil, ORDER_STATUS
from excepts import ParamError, ThirdError

from utils.date_api import (
    str_to_tstamp, tstamp_to_str, future
)

from qfcommon.web.core import Handler
from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.base.qfresponse import success
from qfcommon.server.client import HttpClient
from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.qf_customer import QFCustomer
from constants import MOBILE_PATTERN
from qfcommon.qfpay.presmsclient import PreSms
from qfcommon.base.qfresponse import QFRET, error, success
from utils.tools import unicode_to_utf8



class Create(Handler):
    '''
    创建订单
    返回qt2需要的支付参数
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        r['goods_code'] = d.get('goods_code') or ''
        r['price_code'] = d.get('price_code') or ''
        r['promo_code'] = d.get('promo_code') or ''
        r['userid'] = int(self.user.ses.get('userid', ''))

        # 商品价格和名称
        price = RechargeUtil.get_price(r['goods_code'], r['price_code'])
        r['total_amt'] = r['txamt'] = price['amt']
        r['goods_name'] =  price['goods_name']

        # 如果有优惠码
        if r['promo_code']:
            promo_amt = RechargeUtil.check_promo_code(**r)
            r['txamt'] = max(r['total_amt']-promo_amt, 1)

        return r

    def _create_order(self, d):
        # 订单信息
        fields = ('userid', 'goods_code', 'txamt', 'total_amt', 'price_code', 'promo_code', 'goods_name')
        order = {i:d[i] for i in fields}
        order['id'] = getid()
        order['out_sn'] = 0
        order['ext'] = order['promo_code'][:2]
        order['promo_code'] = order['promo_code'][2:]
        order['status'] = ORDER_STATUS['undo']
        order['ctime'] = order['utime'] = int(time.time())
        # 插入paying_order
        with get_connection_exception('qf_mchnt') as db:
            db.insert('paying_order', order)

        # 返回值
        r = {}
        r['goods_name'] = d['goods_name']
        r['txamt'] = d['txamt']
        r['txcurrcd'] = 'CNY'
        r['txdtm'] = time.strftime(DATETIME_FMT)
        r['out_trade_no'] = order['id']
        r['udid'] = 'mchnt_api'
        r['appcode'] = config.QT2_APP_CODE
        r['sign'] = RechargeUtil.make_sign(r)
        return r

    @check_login_ex(prelogin_lock, postlogin_lock)
    @raise_excp('下单失败')
    def POST(self):
        # 转化input参数
        d = self._trans_input()
        # 创建订单
        r = self._create_order(d)

        return self.write(success(r))

def update_mchnt(order):
    def _update_v1():
        '''
        老版本更新
        '''
        with get_connection('qf_mchnt') as db:
            # 获取当前的信息
            upwhere = {'goods_code': order['goods_code'], 'userid': order['userid']}
            try:
                info = db.select_one('recharge', where=upwhere)
            except:
                info = None

            # 更新当前级别的信息
            try:
                price = RechargeUtil.get_price(order['goods_code'], order['price_code'])
                st = datetime.date.today()
                if info:
                    exptm = info['expire_time']
                    if str(exptm) > time.strftime(DATETIME_FMT):
                        st = datetime.date(year=exptm.year, month=exptm.month, day=exptm.day)
                add_conf = {price['alidity']['unit']: price['alidity']['key']}
                end = str_to_tstamp(str(future(st, **add_conf)) + ' 23:59:59', DATETIME_FMT)
                # 若不存在，则直接插入
                if info:
                    updata  = {'expire_time': end, 'utime': int(time.time()), 'status': 2}
                    db.update('recharge', updata, upwhere)
                else:
                    indata = {}
                    indata['id'] = getid()
                    indata['userid'] = order['userid']
                    indata['goods_code'] = order['goods_code']
                    indata['status'] = 2
                    indata['expire_time'] = end + config.PAYING_GOODS['free'] * 24 * 3600
                    indata['ctime'] = indata['utime'] = int(time.time())
                    db.insert('recharge', indata)
            except:
                log.warn('更新消费者有效期失败:%s' % traceback.format_exc())

    def _update():
        '''
         最新版本
        '''
        # 获取当前服务
        cur_goods = err = None
        for goods in config.GOODS:
            if goods['code'] == goods_code:
                if goods.get('is_gratis'):
                    err = '服务是免费'
                    break
                cur_goods = goods
                break
        else:
            err = '未找到服务'
        if cur_goods['price']['code'] != order['price_code']:
            err = '服务没有该价格'
        if err:
            log.debug(err)
            return

        with get_connection('qf_mchnt') as db:
            # 获取当前的信息
            upwhere = {'goods_code': order['goods_code'], 'userid': order['userid']}
            try:
                info = db.select_one('recharge', where=upwhere)
            except:
                info = None

            # 更新当前级别的信息
            try:
                st = datetime.date.today()
                if info:
                    exptm = info['expire_time']
                    if str(exptm) > time.strftime(DATETIME_FMT):
                        st = datetime.date(year=exptm.year, month=exptm.month, day=exptm.day)
                add_conf = {cur_goods['price']['alidity']['unit']:
                            cur_goods['price']['alidity']['key']}
                end = str_to_tstamp(str(future(st, **add_conf)) + ' 23:59:59', DATETIME_FMT)
                # 若不存在，则直接插入
                if info:
                    updata  = {'expire_time': end, 'utime': int(time.time()), 'status': 2}
                    db.update('recharge', updata, upwhere)
                else:
                    indata = {}
                    indata['id'] = getid()
                    indata['userid'] = order['userid']
                    indata['goods_code'] = order['goods_code']
                    indata['status'] = 2
                    indata['expire_time'] = end + cur_goods.get('free', 0) * 24 * 3600
                    indata['ctime'] = indata['utime'] = int(time.time())
                    db.insert('recharge', indata)
            except:
                log.warn('更新消费者有效期失败:%s' % traceback.format_exc())

            # 更新低级别的服务
            low_codes = {goods['code'] for goods in config.GOODS
                         if not goods.get('is_gratis') and goods['vip'] < cur_goods['vip']}
            if low_codes:
                content = '{}购买了{}高级服务,将所有低级服务折算'.format(
                           time.strftime(DATETIME_FMT), order['goods_code'])
                now = int(time.time())
                db.update(
                    table= 'recharge',
                    where= {
                        'goods_code': ('in', low_codes),
                        'userid': order['userid'],
                        'expire_time': ('>', now),
                    },
                    values= {
                        'content': content,
                        'expire_time': now,
                        'utime': now
                    })

    goods_code = order['goods_code']
    for goods in config.PAYING_GOODS['goods']:
        if goods['code'] == goods_code:
            _update_v1()
            return
    else:
        _update()


def update_order(p):
    '''更新订单信息'''
    # 查询订单
    with get_connection_exception('qf_mchnt') as db:
        order = db.select_one('paying_order',
            where={'id': int(p.get('out_trade_no') or 0)})
        if not order:
            raise ParamError('订单不存在')

    # 订单状态
    # 支付成功
    if p['cancel'] == '0' and p['respcd'] == '0000':
        status = ORDER_STATUS['done']
    # 未支付
    elif p['cancel'] == '0' and p['respcd'] in ('1143', '1145'):
        status = ORDER_STATUS['undo']
    # 支付失败
    else:
        status = ORDER_STATUS['fail']

    # 更新订单
    with get_connection_exception('qf_mchnt') as db:
        where = {
            'id': int(p.get('out_trade_no') or 0),
            'status': ('in', (ORDER_STATUS['undo'], ORDER_STATUS['fail']))
        }
        where['status'] = ORDER_STATUS['undo']
        data = {'utime': int(time.time()), 'out_sn': p['syssn'], 'status': status}
        updated = db.update('paying_order', data, where)

    # 若更新payding_order且订单状态为已支付,
    # 则更新商户付费有效期
    if updated and status == ORDER_STATUS['done']:
        if order['goods_code'] == 'message':
            log.info('begin send message')
            send_message(order)
        else:
            update_mchnt(order)

    return {'syssn': p['syssn'], 'txamt': p['txamt'],
            'status': status, 'txdtm':order['ctime']}

def send_message(p):
    where = {'id': int(p.get('id') or 0)}
    with get_connection_exception('qf_mchnt') as db:
        messages = db.select_one(table='messages', where=where)
    if not messages:
        raise ParamError('订单不存在')
    content = unicode_to_utf8(messages.get('content', '')) + ' 回复TD退订'
    # s_content = content[0] + ' 回复TD退订【'+ content[1]

    userid = p['userid']
    with get_connection('qf_mchnt') as db:
        members = db.select_join(
                table1='member m',
                table2='member_tag mt',
                on={
                    'm.userid': 'mt.userid',
                    'm.customer_id': 'mt.customer_id'
                },
                where={
                    'm.userid': userid,
                    'mt.userid': userid,
                    'mt.submit': ('>', 0),
                },
                fields=('m.customer_id, m.userid'))
        cids = [i['customer_id'] for i in members]
        profiles = {}
        if cids:
            spec = json.dumps({'user_id': cids})
            try:
                profiles = thrift_callex(config.OPENUSER_SERVER, QFCustomer, 'get_profiles',
                                         config.OPENUSER_APPID, spec)
                profiles = {i.user_id: i.__dict__ for i in profiles}
            except:
                log.warn('get openuser_info error:%s' % traceback.format_exc())
        mobiles = []
        for m in members:
            customer_id = m['customer_id']
            info = profiles.get(customer_id, {})
            mobile = info.get('mobile', '')
            if mobile and re.match(MOBILE_PATTERN, mobile):
                mobiles.append(mobile)
        if mobiles:
            try:
                r, respmsg = PreSms(config.PRESMS_SERVERS).sendSms(mobile=mobiles, content=content, tag=config.PRESMS_MARKETING_CONFIG['tag'], source=config.PRESMS_MARKETING_CONFIG['source'], target=config.PRESMS_MARKETING_CONFIG['target'])
                if not r:
                    log.info('调起发送短信服务失败:%s' % respmsg)
                else:
                    log.info('update messages')
                    with get_connection_exception('qf_mchnt') as db:
                        where = {
                            'id': int(p.get('id') or 0),
                        }
                        data = {'utime': int(time.time()), 'out_sn': p['out_sn'], 'status': 1}
                        updated = db.update('messages', data, where)

            except Exception, e:
                log.warn(traceback.format_exc())


class Query(Handler):
    '''
    订单查询
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        r['out_sn']  = d.get('syssn')
        if not r['out_sn']:
            raise ParamError('订单不存在')
        return r

    def _query(self, d):
        def _query_qt2():
            '''从qt2查询订单信息'''
            p = {'syssn': d['out_sn']}
            headers = {
                'X-QF-APPCODE': config.QT2_APP_CODE,
                'X-QF-SIGN': RechargeUtil.make_sign(p)
            }
            try:
                client = HttpClient(config.QT2_SERVER)
                r = json.loads(client.get('/trade/v1/query', params=p, headers=headers))
                if r['respcd'] == '0000' and r['data']:
                    return r['data'][0]
            except:
                log.warn('qt2 query error:%s' % traceback.format_exc())
            raise ThirdError('获取订单信息失败')

        with get_connection_exception('qf_mchnt') as db:
            pwhere = {'out_sn': d['out_sn'], 'status': ORDER_STATUS['done']}
            info = db.select_one('paying_order', where=pwhere)
            if info:
                return {'syssn': info['out_sn'], 'txamt': info['txamt'],
                        'status': info['status'], 'txdtm': info['ctime']}

        return update_order(_query_qt2())

    @check_login
    @raise_excp('查询订单失败')
    def GET(self):
        # 转化input参数
        d = self._trans_input()
        # 消费者列表
        r = self._query(d)
        r['txdtm'] = tstamp_to_str(r['txdtm'], DATETIME_FMT)
        return self.write(success(r))

class Notify(Handler):
    '''
    接受qt2异步通知接口
    '''

    @check_ip()
    def POST(self):
        d = self.req.inputjson()
        log.debug('input:%s' % d)

        try:
            d = {k:v.strip() for k,v in d.iteritems() }
            update_order(d)
        except:
            log.warn(traceback.format_exc())

        return self.write('SUCCESS')
