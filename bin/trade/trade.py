# coding:utf-8

import time
import json
import logging
import config
import traceback
import hashlib

from runtime import hids
from utils.decorator import check
from utils.base import BaseHandler
from utils.valid import is_valid_int, is_valid_datetime
from utils.date_api import tstamp_to_str

from constants import DTM_FMT
from excepts import ParamError, ThirdError, MchntException

from qfcommon.server.client import HttpClient
from qfcommon.base.dbpool import get_connection_exception
from qfcommon.qfpay.qfresponse import success
from qfcommon.qfpay.defines import QF_BUSICD_PREPAID_CONSUME, QF_BUSICD_PREPAID_SWIPE

ALIPAY_BUSICD_LIST = ["800107","800101","800108"]
WXPAY_BUSICD_LIST = ["800207","800201","800208"]
JDPAY_BUSICD_LIST = ["800507","800501","800508"]
CARD_BUSICD_LIST = ["000000"]
QQ_BUSICD_LIST = ["800601","800607","800608"]

log = logging.getLogger()

def get_busicds(paytypes):
    pay_dict = {
        'alipay': ALIPAY_BUSICD_LIST,
        'wxpay': WXPAY_BUSICD_LIST,
        'jdpay': JDPAY_BUSICD_LIST,
        'card': CARD_BUSICD_LIST,
        'qqpay': QQ_BUSICD_LIST
    }
    paytypes = paytypes.split(',')

    alltypes = []
    ret = []
    for key, types in pay_dict.iteritems():
        alltypes.extend(types)
        if key in paytypes:
            ret.extend(types)

    return ret or alltypes


unicode2str = lambda s: s.encode('utf-8') if isinstance(s, unicode) else str(s)
def make_sign(data, appkey = config.WXY_QT2_CONF['appkey']):
    unsign_str = ''
    keys = data.keys()
    keys.sort()

    for i in keys:
        k = unicode2str(i)
        v = unicode2str(data[i])
        if v:
            if unsign_str:
                unsign_str += '&%s=%s'%(k,v)
            else:
                unsign_str += '%s=%s'%(k,v)

    unsign_str += unicode2str(appkey)
    s = hashlib.md5(unsign_str).hexdigest()
    return s.upper()


def qt2_requests(
        url, data, method='get',
        appcode=config.WXY_QT2_CONF['appcode'],
        appkey=config.WXY_QT2_CONF['appkey']
    ):
    '''qiantai2访问'''

    headers = {
        'X-QF-APPCODE': appcode,
        'X-QF-SIGN': make_sign(data, appkey)
    }
    try:
        client = HttpClient(config.QT2_SERVER)
        func = getattr(client, method)
        ret = func(url, data, headers=headers)
        data = json.loads(ret)

    except:
        log.warn(traceback.format_exc())
        raise ThirdError('服务内部错误')

    respcd = data.pop('respcd', None)

    if respcd == '0000':
        return data

    else:
        raise MchntException(data['respmsg'], data['resperr'], respcd)

def open_pt(userid):
    if not is_valid_int(userid):
        raise ParamError('商户不存在')

    with get_connection_exception('qf_mchnt') as db:
        user = db.select_one(
            'mchnt_control', where = {'userid' : int(userid)}
        )
        if not user or not user['pt_rule']:
            raise ParamError('该商户暂未开通积分功能')
    return user

class Payment(BaseHandler):
    '''创建订单'''


    @check()
    def POST(self):
        params = self.req.input()

        if not is_valid_int(params.get('txamt')):
            raise ParamError('txmat is must')

        for i in ('openid', 'out_trade_no', 'userid'):
            if not params.get(i):
                raise ParamError('%s is must' % i)

        pay_type = params.get('pay_type', '800207')
        if pay_type not in ('800207', '800213'):
            raise ParamError('暂不支持该支付类型')

        # 校验是否开通积分功能
        open_pt(params['userid'])

        data = {
            'txamt' : int(params['txamt']),
            'sub_openid' : params['openid'],
            'pay_type' : pay_type,
            'txcurrcd' : 'CNY',
            'out_trade_no' : params['out_trade_no'],
            'txdtm' : time.strftime(DTM_FMT),
            'goods_name' : params.get('goods_name', ''),
            'mchid' : hids.encode(config.WXY_QT2_CONF['app_uid'], int(params['userid']))
        }
        if is_valid_datetime(params.get('txdtm')):
            data['txdtm'] = params['txdtm']

        ret = qt2_requests('/trade/v1/payment', data, 'post')

        resperr = ret.pop('resperr', '')
        ret.pop('respmsg', '')

        return success(ret, resperr)


class Query(BaseHandler):
    '''查询订单'''

    @check()
    def GET(self):
        params = self.req.input()

        for i in ('out_trade_no', 'userid'):
            if not params.get(i):
                raise ParamError('%s is must' % i)

        # 校验是否开通积分功能
        open_pt(params['userid'])

        data = {
            #'userid' : params['userid'],
            'mchid' : hids.encode(config.WXY_QT2_CONF['app_uid'], int(params['userid'])),
            'out_trade_no' : params['out_trade_no']
        }

        ret = qt2_requests('/trade/v1/query', data, 'get')
        if not ret['data']:
            raise ParamError('out_trade_no不存在')

        return success(ret['data'][0])


class TradeTotal(BaseHandler):
    '''交易汇总'''

    @check('login')
    def GET(self):
        params = self.req.input()
        sttime = params.get('starttime', '')
        edtime = params.get('endtime', '')
        opuid = params.get('opuid', '0000')
        userid = int(self.user.userid)
        default = tstamp_to_str(int(time.time()), fmt='%Y-%m-%d') + ' 00:00:00'
        if not sttime:
            login_time = self.user.ses.data.get('login_time', '')
            sttime = tstamp_to_str(login_time) if login_time else default
        if not edtime:
            edtime = tstamp_to_str(int(time.time()))

        if not is_valid_datetime(sttime) or not is_valid_datetime(edtime):
            raise ParamError('参数错误')
        if sttime > edtime:
            raise ParamError('参数错误')

        where = {'retcd': '0000', 'opuid': int(opuid), 'userid': userid, 'cancel': 0}
        styear, stmonth = int(sttime[:4]), int(sttime[5:7])
        edyear, edmonth = int(edtime[:4]), int(edtime[5:7])
        where['sysdtm'] = 'between', (sttime, edtime)
        busicds = get_busicds('')
        where['busicd'] = 'in', [QF_BUSICD_PREPAID_CONSUME, QF_BUSICD_PREPAID_SWIPE] + busicds
        where['cancel'] = 0
        dec_month = (edyear - styear)*12 + edmonth - stmonth
        cur_month, cur_year = edmonth, edyear
        tables = []
        while dec_month >= 0:
            tables.append('record_%d%02d' % (cur_year, cur_month))
            cur_year, cur_month = cur_year - (cur_month==1), cur_month-1 or 12
            dec_month -= 1

        # 查询结果
        result = []
        fields = ('userid, opuid, sysdtm, busicd, note, txamt, coupon_amt')
        with get_connection_exception('qf_trade') as db:
            for table in tables:
                ret = db.select(table,
                        where=where, fields=fields,
                        other='order by sysdtm desc') or []
                result += ret

        t_txamt = order_amt = suc_num = 0
        for ii in result:
            try:
                ii['note'] = json.loads(ii['note'])
            except:
                ii['note'] = {}
            hj_coupon = ii['coupon_amt'] or 0
            mchnt_coupon = ii['note'].get('coupon_amt') or 0
            # 总金额
            total_amt = hj_coupon + ii['txamt'] + mchnt_coupon
            # 实收金额
            txamt = ii['txamt'] + hj_coupon
            suc_num += 1
            t_txamt += txamt
            order_amt += total_amt

        ret = {'order_amt': order_amt, 'total_amt': t_txamt, 'total_num': suc_num,
               'start_time': sttime, 'end_time': edtime}

        return self.write(success(ret))

