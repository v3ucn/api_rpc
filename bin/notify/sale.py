# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import random
import json
import traceback
import time
import config
import requests
import logging

from cache import cache
from util import BaseHandler as BHandler, decode_from_utf8
from util import is_valid_int, hids, is_valid_num, future
from runtime import redis_pool
from decorator import raise_excp, check_login, check_ip
from excepts import ParamError
from base import SpecialApi, SpecialDefine
from constants import DATE_FMT

from utils.decorator import check, with_customer
from utils.tools import apcli_ex

from qfcommon.base.dbpool import get_connection_exception, get_connection
from qfcommon.qfpay.qfresponse import success
from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.open_user import OpenUser
from qfcommon.server.client import HttpClient

host = config.SALE_WEIDIAN_URL
log = logging.getLogger()


class Summary(BHandler):

    def _summary(self, userid):
        actvs = []
        with get_connection('qmm_wx') as db:
            where = {
                'qf_uid' : int(userid),
                'status' : ('!=', SpecialDefine.STATUS_DELETED),
                'atype' : 1
            }
            fields = 'id, price'
            actvs = db.select('market_activity', where=where, fields=fields)
        if not actvs: return {'tx_count':0, 'payment_count':0}

        sales = SpecialApi.get_actv_sales([i['id'] for i in actvs])
        tx_count = sum(sales.values())
        payment_count = sum(sales[i['id']] * i['price'] for i in actvs)

        return {'tx_count':tx_count, 'payment_count':payment_count}

    @check_login
    def GET(self):
        userid = int(self.user.ses.get('userid'))
        return self.write(success(self._summary(userid)))

@cache()
def get_all_buyers(last_days = 7):
    # 取出全部的特卖订单
    r = []
    with get_connection('qmm_wx') as db:
        st = future(days=-last_days).strftime('%Y-%m-%d 00:00:00')
        where = {
            'create_time' : ('>=', st),
            'good_name' : ('not like', '测试%'),
            'source' : 1,
            'activity_id' : ('!=', 0),
            }
        fields = 'openid, good_name'
        r = db.select('orders', where=where, fields=fields) or []

    # 筛选订单
    orders = []
    for i in r:
        if not i['good_name'] or not i['openid'].startswith('near_uid_'):
            continue
        customer_id = i['openid'].split('near_uid_')[-1]
        if not is_valid_int(customer_id): continue

        orders.append({'customer_id' : int(customer_id), 'goods_name':i['good_name']})

    # 获取头像, 昵称
    try:
        spec = json.dumps({'id' : list({i['customer_id'] for i in orders})})
        r  = thrift_callex(config.OPENUSER_SERVER, OpenUser,
            'get_profiles', config.OPENUSER_APPID, spec)
        cinfos = {i.user_id:((decode_from_utf8(i.nickname or '')[:1] or '*') +'**', i.avatar) for i in r}
    except:
        log.warn('get openuser info error:%s' % traceback.format_exc())
        cinfos = {}

    # 整理数据
    ret = []
    for i in orders:
        if i['customer_id'] in cinfos:
            info = cinfos[i['customer_id']]
            ret.append({
                'goods_name' : i['goods_name'],
                'name' : info[0],
                'avatar' : info[1]
            })

    return ret

class LatestOrders(BHandler):

    def GET(self):
        all_buyers = get_all_buyers() or []

        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        num = int(d.get('num', 10))

        latest_orders = random.sample(all_buyers, min(len(all_buyers), num))

        return self.write(success({'orders' : latest_orders}))

class List(BHandler):
    '''
    获取特卖活动列表
    '''

    def _list(self, userid, page=0, pagesize=10):
        actvs = []
        with get_connection('qmm_wx') as db:
            where = {
                'qf_uid' : int(userid),
                'status' : ('!=', SpecialDefine.STATUS_DELETED),
                'atype' : 1
            }
            fields = ('id, title, daily_quantity, quantity, img, status, audit_status, price, create_time,'
                'business_title,redeem_start_date, redeem_end_date, redeem_start_time, redeem_end_time, remark')
            other = 'order by create_time desc limit %s offset %s' % (pagesize, page*pagesize)
            actvs = db.select('market_activity', where=where,
                               fields = fields, other=other)
        if not actvs: return []

        ids = [i['id'] for i in actvs]
        # 兑换数量
        sales = SpecialApi.get_actv_sales(ids)
        # 查看信息
        query_infos = SpecialApi.get_actv_pv(ids)

        ret = []
        online_time = '2016-10-28 00:00:00'
        for i in actvs:
            tmp = {}
            tmp['img'] = i['img']
            tmp['shopname'] = i['business_title']
            tmp['activity_id'] = i['id']
            tmp['goods_title'] = i['title']
            tmp['status'] = SpecialApi.get_actv_status(i) # 通知状态
            tmp['state'] = SpecialApi.get_actv_state(i) # 活动状态
            tmp['buy_count'] = int(sales.get(i['id']) or 0) # 兑换数量
            tmp['total_count'] = i['daily_quantity'] or i['quantity'] # 总数量
            if i['daily_quantity']:
                tmp['sales_count'] = tmp['total_count'] - i['quantity'] # 购买数量
            tmp['payment_count'] = i['price'] * tmp['buy_count']
            tmp['redeem_start_date'] = str(i['redeem_start_date'])[5:]
            tmp['redeem_start_time'] = str(i['redeem_start_time'])
            tmp['redeem_end_date'] = str(i['redeem_end_date'])[5:]
            tmp['redeem_end_time'] = str(i['redeem_end_time'])
            tmp['notify_datetime'] = str(i['redeem_start_date']) + ' 11:00'
            tmp['query_info'] = query_infos.get(i['id'])
            if str(i['create_time']) >= online_time:
                tmp['total_query'] = sum([t['count'] for t in tmp['query_info']])
            tmp['audit_info'] = i['remark'] or ''
            ret.append(tmp)

        return ret


    @check_login
    @raise_excp('获取列表失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        userid = self.user.ses.get('userid')
        page = int(d.get('page', 0))
        pagesize = int(d.get('pagesize', 10))

        ret = {}
        # 是否能够创建特卖活动
        ret['allow_create'] = SpecialApi.check_allow_create(userid)
        # 获取特卖活动列表
        ret['activity_list'] = self._list(userid, page, pagesize)
        # 当前时间挫
        ret['timestamp'] = int(time.time())

        return self.write(success(ret))


class Rule(BHandler):
    '''
    特卖活动创建规则
    '''

    def GET(self):
        rule_descr =  config.ACTV_TIPS.get('sale', {}).get('rule', [])
        return self.write(success({
            'max_discount': '0.8',
            'timestamp': int(time.time()),
            'sale_max_count': 100,
            'max_expire_days': 14,
            'rule_descr': rule_descr
        }))

class Create(BHandler):
    '''创建特卖'''

    def create(self, img, title,
               origin_price, price,
               quantity,
               redeem_start_date,
               redeem_end_date,
               redeem_start_time="01:00",
               redeem_end_time="23:59",
               descr=''):

        sessionid = self.get_cookie('sessionid')
        redeem_start_time = max(redeem_start_time, '01:00')
        redeem_end_time = min(redeem_end_time, '23:59')
        item_price = '{:.2f}'.format(origin_price / 100.0)
        images='["%s"]' % (img, )

        client = HttpClient(config.SALE_SERVERS)
        headers = {'COOKIE': 'sessionid={}'.format(sessionid)}

        # 创建商品
        try:
            item_ret = json.loads(client.post(
                      path = '/qmm/near/item/new',
                      params = {
                          'title' : title,
                          'price' : item_price,
                          'descr' : descr,
                          'images' : images
                      },
                      headers = headers))
            if item_ret['respcd'] != '0000':
                raise
        except:
            raise ParamError('创建商品失败')

        # 创建活动
        item = item_ret['data']['item']
        price = '{:.2f}'.format(price/100.0)
        try:
            actv_ret = json.loads(client.post(
                path = '/qmm/near/activity/new',
                params = {
                    'item_id' : item['id'],
                    'atype' : SpecialDefine.ATYPE_SALE, 'atag' : 7,
                    'price' : price,
                    'quantity' : quantity,
                    'available_date' : '["%s","%s"]' % (redeem_start_date, redeem_end_date),
                    'available_time' : '["%s","%s"]' % (redeem_start_time, redeem_end_time)
                },
                headers = headers))
            if actv_ret['respcd'] != '0000':
                raise
        except:
            raise ParamError('创建特卖失败')

        activity_id = actv_ret['data']['activity']['id']

        # 修改活动状态为 审核成功和 上线
        with get_connection('qmm_wx') as db:
            db.update(
                table = 'market_activity',
                values = {
                    'audit_status' : SpecialDefine.AUDIT_STATUS_SUCCESS,
                    'status' : SpecialDefine.STATUS_NORMAL,
                },
                where = {'id' : activity_id})

        return activity_id

    @check(['login'])
    @raise_excp('创建特卖失败！')
    def POST(self):
        userid = self.user.userid
        if not SpecialApi.check_allow_create(userid):
            raise ParamError('禁止创建特卖通知！')

        args = self.req.input()
        # 参数
        params = {i : args.get(i) for i in ['title', 'descr', 'redeem_start_date',
                                            'redeem_end_date', 'img'] }

        params['redeem_start_time'] = args.get('redeem_start_time', "05:00")
        params['redeem_end_time'] = args.get('redeem_end_time', "23:00")
        params['quantity'] = int(args['quantity'])

        # 价格
        price, origin_price = int(args['price']), int(args['origin_price'])
        price_limit = int(redis_pool.get('_mchnt_api_sale_price_limit_') or 70000)
        if price > price_limit:
            raise ParamError('创建特卖失败')
        if price > origin_price * 0.8:
            raise ParamError('至少8折才有吸引力')
        params['price'] = price
        params['origin_price'] = origin_price

        result = self.create(**params)

        return self.write(success({'activity_id' : result}))

class Change(BHandler):
    '''
    修改特卖活动
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        userid = int(self.user.userid)
        # 若在黑名单
        if redis_pool.sismember('_mchnt_api_sale_limit_userids_', userid):
            raise ParamError('修改特卖活动失败')

        actv, actv_id = None, d.get('id') or ''
        with get_connection('qmm_wx') as db:
            where = {'qf_uid' : userid, 'id' : actv_id, 'atype' : SpecialDefine.ATYPE_SALE}
            actv = db.select_one('market_activity', where=where)
        # 若活动不存在
        if not actv:
            raise ParamError('活动不存在')

        # 审核状态
        state = SpecialApi.get_actv_state(actv)

        # 进行中
        if  state == SpecialDefine.STATE_ON:
            data = {i:d.get(i, '')for i in ['descr', 'img', 'quantity', 'redeem_start_time', 'redeem_end_time']}
            data['buyable_end_time'] = d['redeem_end_time']
            data['online_time'] = str(actv['redeem_start_date']) + ' ' + data['redeem_start_time']
            data['offline_time'] = str(actv['redeem_end_date']) + ' ' + data['redeem_end_time']

        # 审核失败
        elif state == SpecialDefine.STATE_REJECT:
            data = {i:d.get(i, '') for i in ['descr', 'img', 'quantity', 'title', 'price', 'origin_price']}
            if not is_valid_int(data['price']) and not is_valid_int(data['origin_price']):
                raise ParamError('价格必须为整数')
            # 价格限制
            price_limit = int(redis_pool.get('_mchnt_api_sale_price_limit_') or 70000)
            if int(data['price']) > price_limit:
                raise ParamError('修改特卖活动失败')

            data['redeem_start_date'] = d.get('redeem_start_date')
            data['redeem_end_date'] = d.get('redeem_end_date')
            data['redeem_start_time'] = d.get('redeem_start_time', "05:00")
            data['redeem_end_time'] = d.get('redeem_end_time', "23:00")
            data['buyable_start_date'] = time.strftime('%Y-%m-%d')
            data['buyable_end_date'] = d.get('redeem_end_date')
            data['buyable_start_time'] = time.strftime('%H:%M:%S')
            data['buyable_end_time'] = d['redeem_end_time']
            data['online_time'] = data['redeem_start_date'] + ' ' + data['redeem_start_time']
            data['offline_time'] = data['redeem_end_date'] + ' ' + data['redeem_end_time']
        else:
            raise ParamError('该活动不允许修改')

        if not is_valid_int(data['quantity']):
            raise ParamError('库存必须为整数')

        data['quantity'] = max(data['quantity'], 0)
        data['daily_quantity']  =  actv['daily_quantity'] or actv['quantity']
        data['daily_quantity'] += int(data['quantity']) - actv['quantity']
        data['audit_status'] = SpecialDefine.AUDIT_STATUS_PLACED

        return {'actv_id' : actv['id'], 'data' : data}

    @check(['login'])
    @raise_excp('修改特卖活动失败')
    def POST(self):
        param = self._trans_input()

        with get_connection_exception('qmm_wx') as db:
            where = {'id' : param['actv_id']}
            db.update('market_activity', param['data'], where=where)

        return self.write(success({}))

class Remove(BHandler):
    '''终止特卖活动'''

    def remove(self, sessionid, activity_id):
        url = "%s%s" % (host, '/near/activity/transtatus')
        data = dict(activity_id=activity_id, status = SpecialDefine.STATUS_DOWN)
        logging.info('access url: %s, data: %s', url, data)
        response = requests.post(url, data=data, cookies=dict(sessionid=sessionid))

        logging.info('response: %s', response.text)
        response = response.json()
        if response['respcd'] != "0000":
            logging.info('create sale activity failure: %s', response['resperr'])
            raise ParamError('删除推广活动失败！')

        logging.info('remove sale activity success: data: %s', data)
        result = {}
        return result

    @check(['login'])
    @raise_excp('删除推广活动失败！')
    def POST(self):
        sessionid = self.get_cookie('sessionid')
        activity_id = int(self.req.input()['activity_id'])
        result = self.remove(sessionid, activity_id)
        return self.write(success(result))

class NotifyList(BHandler):
    '''
    曾经消费过的店的特卖列表
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        try:
            r['customer_id'] = hids.decode(d['customer_id'])[0]
        except:
            import traceback
            log.debug(traceback.format_exc())
            if self.customer.customer_id:
                r['customer_id'] = self.customer.customer_id
            else:
                raise ParamError('参数错误')

        r['lng'], r['lat'] = float(d.get('longitude') or 0), float(d.get('latitude') or 0)

        return r

    @with_customer
    @raise_excp('获取列表失败！')
    def GET(self):
        d = self._trans_input()
        ret = {'notify_list' : [], 'total_count' : 0}

        userids = []
        with get_connection('qf_mchnt') as db:
            consumed_shops = db.select(
                        table = 'member',
                        where = {
                            'customer_id' : d['customer_id']
                        }, fields='userid') or []

            userids = [i['userid'] for i in consumed_shops]

        if userids:
            all_sales = SpecialApi.get_all_sales() or []
            consumed_sales = [sale for sale in all_sales if sale['qf_uid'] in userids]
            ret['notify_list'] = SpecialApi.tidy_sales(consumed_sales,
                    mode = 'consumed', lng = d['lng'], lat = d['lat'])
            ret['total_count'] = len(ret['notify_list'])

        return self.write(success(ret))

class OrderList(BHandler):
    '''获取订单列表'''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}

        try:
            r['customer_id'] = hids.decode(d['customer_id'])[0]
        except:
            raise ParamError('参数错误')

        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息错误')
        r['offset'], r['limit'] = int(page)*int(pagesize), int(pagesize)

    def get_order_list(self, customer_id, offset=0, limit=10):
        url = config.SALE_ORDER_LIST_HAOJIN_URL

        params = dict(near_uid=customer_id, order_type=1, offset=offset, pagesize=limit)
        log.info('url: %s, params: %s', url, params)

        response = requests.get(url, params=params)
        log.info('response: %s', response.text)
        response_json_body = response.json()
        if response_json_body['respcd'] != "0000":
            log.exception('query url failure: url: %s, params: %s, response: %s',
                          url, params, response_json_body)
            return []

        order_list = response_json_body['data']['orders']
        return order_list

    @raise_excp('获取列表失败！')
    def GET(self):
        d= self._trans_input()
        result = self.get_order_list(d['customer_id'], d['offset'], d['limit'])
        return self.write(success(result))

class NearSaleList(BHandler):
    '''
    获取附近特卖列表
    '''
    @raise_excp('获取特卖列表失败！')
    def GET(self):
        sales = []
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        lng, lat = d.get('longitude'), d.get('latitude')
        limit = int(d.get('limit') or 100)

        if is_valid_num(lng) and is_valid_num(lat):
            all_sales = SpecialApi.get_all_sales()
            sales = SpecialApi.tidy_sales(all_sales,
                mode = 'near', lng = float(lng), lat = float(lat)) or []
            sales.sort(key=lambda x: x.get('dist'))

        ret = SpecialApi.get_head_sales() + sales[:limit]

        # 增加pv
        SpecialApi.add_actv_pv([i['activity_id'] for i in ret], d.get('query_from'))

        return self.write(success(ret))

class Tips(BHandler):
    '''
    完成页特卖活动
    '''

    def _get_tips(self, userid, customer_id):
        limit = 3
        all_sales = SpecialApi.get_all_sales() or []

        # 当前店铺创建的特卖
        consumed_sales = [sale for sale in all_sales
                               if str(sale['qf_uid']) == userid ]
        if consumed_sales:
            return {'title' : config.CONSUMED_SALE_TITLE,
                    'sales' : SpecialApi.tidy_sales(consumed_sales, 'consumed')[:limit]}

        # 置顶特卖
        head_sales = SpecialApi.get_head_sales() or []

        # 附近特卖
        user = apcli_ex('findUserByid', int(userid))
        near_sales = []
        if user and user.longitude and user.latitude:
            near_sales = SpecialApi.tidy_sales(all_sales,
                    mode='near', lng=user.longitude, lat=user.latitude) or []
            near_sales.sort(key=lambda x: x['dist'])

        sales = head_sales + near_sales
        if sales:
            return {'title' : config.NEAR_SALE_TITLE,
                    'sales' : sales[:3]}
        else:
            return {'title' : '', 'sales' : []}

    @check_ip()
    @raise_excp('获取特卖失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}

        # 商户userid
        userid = d.get('userid')

        # 消费者id
        customer_id = d.get('customer_id')

        return self.write(success(self._get_tips(userid, customer_id)))

class AllSale(BHandler):
    '''所有的特卖'''

    @check_ip()
    def GET(self):
        sales, today = [], time.strftime(DATE_FMT)
        where = {
            'audit_status' : ('in', (SpecialDefine.AUDIT_STATUS_PLACED,
                                     SpecialDefine.AUDIT_STATUS_SUCCESS)),
            'status' : ('in', (SpecialDefine.STATUS_PLACED,
                               SpecialDefine.STATUS_NORMAL,
                               SpecialDefine.STATUS_TEST)),
            'redeem_start_date' : ('<=', today),
            'redeem_end_date' : ('>=', today),
            'atype' : SpecialDefine.ATYPE_SALE,
            'buyable_start_date' : ('<=', today),
            'buyable_end_date' : ('>=', today),
            'title' : ('not like', '测试%'),
            'quantity' : ('>', '0'),
        }
        with get_connection('qmm_wx') as db:
            sales = db.select(
                    table = 'market_activity',
                    where = where,
                    fields = 'title, business_title, price, qf_uid, id')

        if not sales: return []

        shops = []
        with get_connection('qf_core') as db:
            shops = db.select(
                'profile',
                fields = 'longitude, userid, latitude',
                where = {'userid': ('in', list({i['qf_uid'] for i in sales}))}
            )
        shops = {i['userid']: i for i in shops or []}

        for sale in sales:
            shopinfo = shops.get(int(sale['qf_uid'])) or {}
            sale['lng'] = shopinfo.get('longitude') or 0
            sale['lat'] = shopinfo.get('latitude') or 0

        return self.write(success({'sales' : sales}))

class Other(BHandler):
    '''特卖请求'''

    @check_login
    def GET(self):
        userid = self.user.userid
        aid = int(self.req.input().get('activity_id') or 0)

        sale, today = {}, time.strftime(DATE_FMT)
        with get_connection('qmm_wx') as db:
            sale = db.select_one(
                    table = 'market_activity',
                    where = {
                        'id' : ('!=', aid),
                        'qf_uid' : int(userid),
                        'audit_status' : ('in', (SpecialDefine.AUDIT_STATUS_PLACED,
                                                 SpecialDefine.AUDIT_STATUS_SUCCESS)),
                        'status' : ('in', (SpecialDefine.STATUS_PLACED,
                                           SpecialDefine.STATUS_NORMAL,
                                           SpecialDefine.STATUS_TEST)),
                        'redeem_start_date' : ('<=', today),
                        'redeem_end_date' : ('>=', today),
                        'atype' : SpecialDefine.ATYPE_SALE,
                        'buyable_start_date' : ('<=', today),
                        'buyable_end_date' : ('>=', today),
                        'title' : ('not like', '测试%'),
                        'quantity' : ('>', '0'),
                    },
                    fields = 'price, id, origin_price, business_title, title') or {}

        return self.write(success({'sale' : sale}))
