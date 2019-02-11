# encoding:utf-8
'''
活动结案报告脚本
红包活动, 集点活动, 特卖活动
'''

import os
import sys
import json
import time
import datetime
import traceback

from collections import defaultdict

HOME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HOME)
sys.path.append(os.path.join(os.path.dirname(HOME), 'conf'))

from qfcommon.base import loader
loader.loadconf_argv(HOME)

import config

from notify.base import SpecialDefine, SpecialApi
from coupon.base import CouponDefine

from qfcommon.base import dbpool
dbpool.install(config.DATABASE)
from qfcommon.base import logger
log = logger.install(config.LOGFILE)

from util import getid
from qfcommon.base.tools import thrift_call
from qfcommon.base.dbpool import get_connection
from qfcommon.qfpay.qfresponse import json_default_trans
from qfcommon.thriftclient.data_activiquer import activiquer
from qfcommon.server.client import HttpClient

TD = datetime.date.today()
YTD = datetime.date.today() - datetime.timedelta(days=1)
TD_TIMESTAMP = time.mktime(TD.timetuple())

def push_msgs(result, datas):
    if not datas or not result:return

    # 写入actv_effect
    insert_status = None
    with get_connection('qf_mchnt') as db:
        insert_status = db.insert_list('actv_effect', result)

    # 推送
    if not insert_status: return

    try:
        client = HttpClient(config.TRADE_PUSH_SERVER)
        for data in datas:
            data['busicd'] = 'actv_effect'
            client.get('/push/v2/msg', data)
    except:
        log.warn('push msg error:%s' % traceback.format_exc())

def get_data(aid):
    '''从数据组拉取数据'''
    datas = {}
    try:
        datas = json.loads(thrift_call(activiquer, 'activiq', config.DATAS_SERVERS,
                                      'activity', str(aid)))[0]
        datas['rk_p'] = datas['rk_p'] * 100
    except:
        log.debug('[id:{}]get_data error'.format(aid))
    return datas

def coupon_effect():
    '''红包活动'''
    with get_connection('qf_marketing') as db:
        fields = ('id, mchnt_id, type, title, total_amt, used_num, used_amt,'
                  'rule, start_time, expire_time, create_time, obtain_xx_id')
        actvs = db.select(
                table = 'activity',
                where =  {
                    'src' : 'QPOS',
                    'mchnt_id' : ('!=', 0),
                    'type' : ('in', CouponDefine.HJ_ACTVS),
                    'status' : CouponDefine.ACTV_STATUS_ENABLE,
                    'expire_time' : ('between', (TD_TIMESTAMP - 24 * 3600, TD_TIMESTAMP - 1)),
                },
                fields = fields) or []

        close_actvs = db.select(
                table = 'activity',
                where =  {
                    'src' : 'QPOS',
                    'mchnt_id' : ('!=', 0),
                    'type' : ('in', CouponDefine.HJ_ACTVS),
                    'status' : CouponDefine.ACTV_STATUS_CLOSED,
                    'update_time' : ('between', (TD_TIMESTAMP - 24 * 3600, TD_TIMESTAMP - 1)),
                },
                fields = fields) or []
        actvs = actvs + close_actvs
        if not actvs: return

        # 刺激消费,红包核销数,实际花销
        actids = [i['id'] for i in actvs]
        rrecords = db.select(
                table = 'record',
                where = {
                    'activity_id' : ('in', actids),
                    'type' : ('in', (CouponDefine.RD_STATUS_USE, CouponDefine.RD_STATUS_UNDO,
                                     CouponDefine.RD_STATUS_DESTROY)),
                },
                fields = 'amt, activity_id, total_amt, type') or []
        effects = {}
        for record in rrecords:
            aid = record['activity_id']
            atype = record['type']
            if aid not in effects:
                effects[aid] = defaultdict(int)
            # 核销的红包
            if atype == CouponDefine.RD_STATUS_USE:
                effects[aid]['t_amt'] += record['total_amt']
                effects[aid]['cnt'] += 1
                effects[aid]['t_coupon_amt'] += record['amt']
            # 撤销，还原的红包
            else:
                effects[aid]['t_amt'] -= record['total_amt']
                effects[aid]['cnt'] -= 1
                effects[aid]['t_coupon_amt'] -= record['amt']

    # 整理数据
    result, now = [], int(time.time())
    push_data = []
    for actv in actvs:
        teffect = effects.get(actv['id'], {})
        actv['t_coupon_amt'] = teffect.get('t_coupon_amt', 0) # 实际花销
        actv['cnt'] = teffect.get('cnt', 0) # 红包核销数

        effect = {
            'datas' : actv,
            'effect' : {
                'total_amt' : teffect.get('t_amt', 0),
            }
        }

        # 如果数据有数据
        datas = get_data(actv['id'])
        if datas:
            effect['rank'] = datas
            effect['effect']['c_cnt'] = datas['c_cnt']
        else:
            effect['effect']['c_cnt'] = 0


        if actv['type'] == CouponDefine.ACTV_TYPE_PAYMENT:
            # 消费返红包
            if not actv['obtain_xx_id']:
                actv_type = 3 # 消费返红包
            # 分享红包
            else:
                actv_type = 30 # 消费分享红包
        else:
            actv_type = 31 # 分发红包

        # 结案报告数据
        effect_id = getid()
        result.append({
            'id' : effect_id,
            'userid' : actv['mchnt_id'],
            'type' : actv_type,
            'ctime' : now,
            'content' : json.dumps(effect, default = json_default_trans),
        })

        # 推送数据
        push_data.append({
            'id' : effect_id,
            'actv_name' : actv['title'],
            'userid' : actv['mchnt_id'],
            'type' : actv_type,
            'actv_id' : actv['id']
            })

    push_msgs(result, push_data)

def sale_effect():
    '''特卖活动'''
    sales = None
    where = {
        'audit_status' : ('in', (SpecialDefine.AUDIT_STATUS_PLACED,
                                 SpecialDefine.AUDIT_STATUS_SUCCESS)),
        'status' : ('in', (SpecialDefine.STATUS_PLACED,
                           SpecialDefine.STATUS_NORMAL,
                           SpecialDefine.STATUS_TEST)),
        'redeem_end_date' : YTD,
        'atype' : SpecialDefine.ATYPE_SALE,
    }
    fields = ('qf_uid, id, price, origin_price, title, buyable_start_date,'
              'create_time, quantity, daily_quantity, redeem_end_date')
    with get_connection('qmm_wx') as db:
        sales = db.select('market_activity', where=where, fields=fields)
    if not sales: return None

    # 获取兑换数量
    tsales = SpecialApi.get_actv_sales([i['id'] for i in sales])

    # 曝光数
    query_infos = SpecialApi.get_actv_pv([i['id'] for i in sales])

    result, now = [], int(time.time())
    push_data = []
    for sale in sales:
        # 兑换数量
        sale['buy_count'] = int(tsales.get(i['id']) or 0)

        # 购买数量
        sale['sales_count'] = 0
        sale['total_count'] = sale['daily_quantity'] or sale['quantity'] # 总数量
        if sale['daily_quantity']:
            sale['sales_count'] = sale['total_count'] - sale['quantity']
        sale['sales_count'] = max(sale['buy_count'], sale['sales_count'])
        sale['total_cheap_amt'] = sale['sales_count'] * (sale['origin_price'] - sale['price'])

        effect = {
            'datas' : sale,
            'effect' : {
                'total_query' : sum([t['count'] for t in query_infos.get(sale['id'])]),
                'total_amt' : sale['price'] * sale['buy_count']
            }
        }

        # 结案数据
        effect_id = getid()
        result.append({
            'id' : effect_id,
            'userid' : sale['qf_uid'],
            'type' : 2, # 结案报告类型
            'ctime' : now,
            'content' : json.dumps(effect, default = json_default_trans)
            })

        # 推送数据
        push_data.append({
            'id' : effect_id,
            'userid' : sale['qf_uid'],
            'actv_name' : sale['title'],
            'actv_id' : sale['id'],
            'type' : 2
            })
    push_msgs(result, push_data)

def card_effect():
    '''集点活动'''
    def get_content(actv):
        '''获取报告'''
        effect = {}
        effect['datas'] = actv
        effect['effect'] = {}

        # 参与人数, 刺激消费, 会员复购数
        custs, total_amt, rebuy = [], 0, 0
        with get_connection('qf_mchnt') as db:
            # 参与人数
            custs = db.select(
                    table = 'member_pt',
                    where = {'activity_id' : actv['id']},
                    fields = 'customer_id')
            custs = [i['customer_id'] for i in custs or []]
            if custs:
                # 刺激消费
                tt = db.select(
                        table = 'pt_record',
                        where = {'activity_id' : actv['id']},
                        fields = 'type, sum(total_amt) as ttamt',
                        other = 'group by type'
                        ) or []
                tt_dict = {i['type']:i['ttamt'] for i in tt }
                total_amt = tt_dict.get(1, 0) - tt_dict.get(2, 0)

                # 会员复购数
                rebuy = db.select_one(
                        table = 'member',
                        where = {
                            'userid' : actv['userid'],
                            'customer_id' : ('in', custs),
                            'ctime' : ('<', actv['ctime'])
                        },
                        fields='count(1) as num')['num']
        effect['datas']['customer_num'] = len(custs)
        effect['effect']['total_amt'] = int(total_amt)
        effect['effect']['rebuy'] = rebuy
        # 实际花销 (礼品兑换数*礼品单价)
        effect['datas']['total_txamt'] = actv['exchange_num'] * actv['goods_amt']

        # 数据组排位信息
        datas = get_data(actv['id'])
        if datas:
            effect['rank'] = datas

        return effect

    actvs = None
    with get_connection('qf_mchnt') as db:
        actvs = db.select(
                    table = 'card_actv',
                    where = {
                        'expire_time' : ('between', (TD_TIMESTAMP-24*3600, TD_TIMESTAMP-1)),
                    })
    if not actvs: return

    result, now = [], int(time.time())
    push_data = []
    for actv in actvs:
        t = {}
        t['id'] = getid()
        t['userid'] = actv['userid']
        t['type'] = 1 # 结案报告类型
        t['ctime'] = now
        t['content'] = json.dumps(get_content(actv), default = json_default_trans)
        result.append(t)

        push_data.append({
            'id' : t['id'],
            'userid' : actv['userid'],
            'type' : 1,
            'actv_name' : u'兑换{}的集点活动'.format(actv['goods_name']),
            'actv_id' : actv['id'],
        })
    push_msgs(result, push_data)

funcs = {'coupon' : coupon_effect, 'sale' : sale_effect, 'card' : card_effect}
def actv_effect():
    log.debug('开始导入活动结案报告')
    efuncs = getattr(config, 'EFFECT_FUNCS', funcs.keys())
    for func_name in efuncs:
        if func_name in funcs:
            funcs[func_name]()

if __name__ == '__main__':
    actv_effect()
