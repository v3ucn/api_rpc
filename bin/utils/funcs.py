# encoding:utf-8

import json
import traceback
import copy
import config
import time
import datetime
import logging
log = logging.getLogger()

from collections import defaultdict
from constants import DATE_FMT, DTM_FMT
from utils.tools import get_value

from notify.base import SpecialDefine, SpecialApi
from coupon.base import CouponDefine
from qfcommon.base.dbpool import get_connection
from qfcommon.server.client import HttpClient

# 数据函数dict
data_funcs = {}

def func_register(mode='datas'):
    '''注册接口'''
    def _(func):
        if mode == 'datas':
            data_funcs[func.__name__] = func
        return func
    return _

def adjust_data(mode, data, **kw):
    '''数据统计整理数据接口'''
    version = kw.get('version')
    platform = kw.get('platform')

    try:
        if not data or mode not in config.DATA_PANELS: return

        panel = copy.deepcopy(config.DATA_PANELS[mode])

        # actvinfo
        if panel['dismode'] == 'actv':
            for k,v in panel['actv_info'].iteritems():
                if ('_actv_'+k) in data:
                    panel['actv_info'][k] = data['_actv_'+k]
                else:
                    if k == 'desc' and data['ondays'] <= 0:
                        panel['actv_info']['desc'] = config.DATA_TIPS['actv_default_desc']
                    else:
                        panel['actv_info'][k] = v.format(**data)

        # data
        for d in panel['datas']:
            for k,v in d.iteritems():
                if ('_datas_'+k) in data:
                    d[k] = data['_datas_' + k]
                else:
                    d[k] = v.format(**data)

        for k,v in data.iteritems():
            if k.startswith('_cm_'):
                panel[k[4:]] = v
        # 创建时间
        panel['create_time'] = (
            get_value(panel.get('create_time'), platform, version) or
            data.get('create_time', 0))

        return panel
    except:
        log.debug(traceback.format_exc())

@func_register()
def sale_data(userid, **kw):
    '''特卖数据'''
    sales, today = [], time.strftime(DATE_FMT)
    where = {
        'audit_status' : ('in', (SpecialDefine.AUDIT_STATUS_PLACED,
                                 SpecialDefine.AUDIT_STATUS_SUCCESS)),
        'status' : ('in', (SpecialDefine.STATUS_PLACED,
                           SpecialDefine.STATUS_NORMAL,
                           SpecialDefine.STATUS_TEST)),
        'redeem_end_date' : ('>=', today),
        'atype' : SpecialDefine.ATYPE_SALE,
        'buyable_start_date' : ('<=', today),
        'buyable_end_date' : ('>=', today),
        'quantity' : ('>', '0'),
        'qf_uid' : userid
    }
    fields = 'qf_uid, id, title, buyable_start_date, create_time, quantity, daily_quantity'
    with get_connection('qmm_wx') as db:
        sales = db.select('market_activity', where=where, fields=fields)

    if not sales: return None

    tsales = SpecialApi.get_actv_sales([i['id'] for i in sales])
    # 查看信息
    query_infos = SpecialApi.get_actv_pv([i['id'] for i in sales])
    td = datetime.date.today()
    panels = []
    for sale in sales:
        # 兑换数量
        sale['buy_count'] = int(tsales.get(i['id']) or 0)

        # 购买数量
        sale['sales_count'] = 0
        sale['total_count'] = sale['daily_quantity'] or sale['quantity'] # 总数量
        if sale['daily_quantity']:
            sale['sales_count'] = sale['total_count'] - sale['quantity']
        sale['sales_count'] = max(sale['buy_count'], sale['sales_count'])
        sale['total_query'] = sum([t['count'] for t in query_infos.get(sale['id'])])
        sale['ondays'] = max(0, (td-sale['buyable_start_date']).days+1)
        sale['create_time'] = time.mktime(sale['create_time'].timetuple())

        panel = adjust_data('sale_data', sale, **kw)
        if panel:
            panels.append(panel)
    return panels

@func_register()
def card_data(userid, **kw):
    '''集点数据'''
    panels = []
    with get_connection('qf_mchnt') as db:
        # 集点活动
        cwhere = {'expire_time' : ('>',int(time.time())), 'userid' : userid, 'status' : 1}
        cfields = 'id, goods_name, exchange_pt, exchange_num, start_time, ctime'
        actvs = db.select('card_actv', where=cwhere, fields=cfields)
        if not actvs: return

        # 参与人数
        custwhere = {'activity_id' : ('in', [i['id'] for i in actvs ])}
        custfields ='activity_id, customer_id'
        custs = db.select('member_pt', where=custwhere, fields=custfields) or []
        cust_dict = defaultdict(set)
        for cust in custs or []:
            cust_dict[cust['activity_id']].add(cust['customer_id'])
        customer_nums = {i:len(cust_dict[i]) for i in cust_dict }

        # 会员复购数
        rebuys = {}
        actv_stimes = {i['id']:time.mktime(i['start_time'].timetuple())  for i in actvs}
        for aid, mems in cust_dict.iteritems():
            memwhere = {
                'userid' : userid,
                'customer_id' : ('in', list(mems)),
                'ctime' : ('<', actv_stimes[aid])
            }
            rebuys[aid] = db.select_one('member', where=memwhere,
                                        fields='count(1) as num')['num']

        # 拼接数据
        td = datetime.date.today()
        for actv in actvs:
            actv['customer_num'] = customer_nums.get(actv['id'], 0)
            actv['rebuy'] = rebuys.get(actv['id'], 0)
            actv['create_time'] = actv['ctime']
            actv['ondays'] = max(0, (td-actv['start_time'].date()).days+1)

            panel = adjust_data('card_data', actv, **kw)
            if panel:
                panels.append(panel)

    return panels

@func_register()
def today_data(userid, **kw):
    '''今日数据'''

    data = {}

    # 今日交易总笔数, 总金额
    data['total_amt'] = data['total_count'] = 0
    try:
        # 获取今日数据
        stat = json.loads(HttpClient(config.OPENAPI_TRADE_SERVERS).get(
                path = '/trade/v1/tradestat',
                headers = {'COOKIE': 'sessionid={}'.format(kw.get('sesid', ''))})
                )['data']
        td = time.strftime(DATE_FMT)
        stat = next((i for i in stat if i['date'] == td), None)
        if stat:
            fields = getattr(config, 'TRADE_STATE_FIELDS', ['alipay', 'weixin', 'jdpay', 'qqpay', 'card'])
            for key, v in stat.iteritems():
                if key in fields:
                    data['total_amt'] += v['sum']
                    data['total_count'] += v['count']
        data['total_amt'] /= 100.0
    except:
        log.debug(traceback.format_exc())

    # 新增会员, 回头客
    data['add_num'] = data['old_num'] = 0
    with get_connection('qf_mchnt') as db:
        now = int(time.mktime(datetime.date.today().timetuple()))
        r = db.select('member',
            fields = '(ctime > {}) as state, count(1) as num'.format(now),
            where = {'userid' : userid, 'utime' : ('>=', now)},
            other = 'group by ctime > {}'.format(now))

        records = {i['state']:i['num'] for i in r}
        data['add_num'] = records.get(1, 0)
        data['old_num'] = records.get(0, 0)

    return adjust_data('today_data', data, **kw)

@func_register()
def coupon_data(userid, **kw):
    '''红包数据'''
    panels = []
    with get_connection('qf_marketing') as db:
        mwhere = {'mchnt_id' : userid, 'src' : 'QPOS',
                 'type' : ('in', CouponDefine.HJ_ACTVS),
                 'status' : CouponDefine.ACTV_STATUS_ENABLE,
                 'expire_time' : ('>', int(time.time()))}
        mfields = ('id, mchnt_id, type, title, total_amt, used_num, used_amt,'
                   'rule, start_time, expire_time, create_time, obtain_xx_id')
        actvs = db.select('activity', where=mwhere, fields=mfields)
        actvs = [actv for actv in actvs if not(actv['type'] == CouponDefine.ACTV_TYPE_PAYMENT
                                               and actv['used_amt'] >= actv['total_amt'])]

        if not actvs: return

        actids = [i['id'] for i in actvs]
        # 活动使用次数
        uwhere = {'activity_id': ('in', actids), 'status' : CouponDefine.CP_STATUS_USE}
        ufields = 'activity_id, count(1) as num'
        uother = '' if len(actids) == 1 else 'group by activity_id'
        uses = db.select('coupon_bind', where=uwhere, fields=ufields, other=uother)
        uses = {i['activity_id']:(i['num'] or 0) for i in uses if i['activity_id']}

        # 刺激消费
        twhere = {
            'activity_id' : ('in', actids),
            'type' : ('in', (CouponDefine.RD_STATUS_USE, CouponDefine.RD_STATUS_UNDO,
                             CouponDefine.RD_STATUS_DESTROY))
        }
        tfields = 'activity_id, type, sum(total_amt) as amt'
        tother = 'group by type' if len(actids) == 1 else 'group by activity_id,type'
        totals = db.select('record', where=twhere, fields=tfields, other=tother)
        dr = defaultdict(dict)
        for i in totals:
            dr[i['activity_id']]['use' if i['type'] == CouponDefine.RD_STATUS_USE else 'destroy'] = i['amt']
        total_amts  = {k:(v.get('use', 0)-v.get('destroy', 0)) for k, v in dr.iteritems()}

        td = datetime.date.today()
        for actv in actvs:
            actv['ondays'] = (td-actv['start_time'].date()).days + 1
            # 分发红包通知
            if actv['type'] == CouponDefine.ACTV_TYPE_COMMON:
                actv['_cm_link'] = config.DATA_TIPS['notify_cp_link']
                actv['_cm_title'] = config.DATA_TIPS['notify_cp_title']
                if actv['ondays'] <= 0:
                    actv['_actv_desc'] = config.DATA_TIPS['notify_cp_desc']
            # 消费返红包, 分享红包
            elif actv['type'] == CouponDefine.ACTV_TYPE_PAYMENT:
                if not actv['obtain_xx_id']:
                    actv['_cm_title'] = config.DATA_TIPS['back_cp_title']
                else:
                    actv['_cm_title'] = config.DATA_TIPS['share_cp_title']
            # 其他红包活动
            else:
                pass
            actv['create_time'] = time.mktime(actv['create_time'].timetuple())
            actv['total_amt'] = int(total_amts.get(actv['id'], 0))/100.0
            actv['use'] = uses.get(actv['id'], 0)

            panel = adjust_data('coupon_data', actv, **kw)
            if panel:
                panels.append(panel)

    return panels

@func_register()
def prepaid_data(userid, **kw):
    '''储值面板'''
    actvs = None
    try:
        # 获取储值信息
        actvs = json.loads(HttpClient(config.PREPAID_SERVERS).get(
                path = '/prepaid/v1/api/b/activity_history?pos=0&count=1',
                headers = {'COOKIE': 'sessionid={}'.format(kw.get('sesid', ''))}
                ))['data']
        actvs = [actv for actv in actvs or [] if actv['status'] == 1]
    except:
        log.warn(traceback.format_exc())
    if not actvs:
        return None

    pannels = []
    now = datetime.datetime.now()
    for actv in actvs:
        try:
            info = json.loads(HttpClient(config.PREPAID_SERVERS).get(
                    path = '/prepaid/v1/api/b/stat/activity/{}'.format(actv['activity_id']),
                    headers = {'COOKIE': 'sessionid={}'.format(kw.get('sesid', ''))})
                    )['data']

            start_time = datetime.datetime.strptime(actv['start_time'], DTM_FMT)
            actv['ondays'] = max(0, (now-start_time).days+1)
            actv['create_time'] = time.mktime(start_time.timetuple())
            actv['total_pay_amt'] = int(actv['total_pay_amt'])/100.0
            actv['total_txamt'] = int(actv['total_txamt'])/100.0
            actv['today_total_pay_amt'] = int(info['today_total_pay_amt'])/100.0

            pannel = adjust_data('prepaid_data', actv, **kw)
            if pannel:
                pannels.append(pannel)
        except:
            log.warn(traceback.format_exc())

    return pannels
