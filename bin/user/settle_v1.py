#coding:utf-8

import traceback
import time
import datetime
import types
import config
import logging
log = logging.getLogger()

from cache import cache
from itertools import groupby
from collections import defaultdict
from excepts import ThirdError, ParamError
from decorator import check_login, raise_excp
from constants import DATE_FMT
from util import get_bigmchntid

from utils.base import BaseHandler
from utils.tools import get_linkids
from utils.valid import is_valid_int, is_valid_date
from runtime import hids

from base import UserUtil, UserDefine
from qfcommon.base.dbpool import get_connection
from qfcommon.qfpay.qfresponse import success
from qfcommon.thriftclient.fund import FundService

from qfcommon.base.tools import thrift_call

# 到账状态
DEBIT_STATUS = {
    'riskdelay': '风控延迟',
    'accountdelay': '账务延迟',
    'nopay': '等待划款',
    'havepay': '已划款',
    'inaccount': '已到账'
}


# 检查传入的shopid参数,并给方法传入userid
def check_shopid_param(func):
    def _(self, *args, **kwargs):
        userid = int(self.user.userid)

        params = self.req.input()
        if params.has_key("shopid"):
            shopid = params.get("shopid", '')
            if not shopid:
                raise ParamError("商户id参数错误")

            try:
                shopid = hids.decode(shopid)[0]
            except:
                raise ParamError("商户id参数错误")

            # 验证是否是当前商户的子商户
            cate = self.get_cate()
            if cate == "bigmerchant":
                subids = get_linkids(userid)
                if shopid not in subids:
                    raise ParamError("非大商户的子商户")
                else:
                    userid = shopid

        ret = func(self,  userid)
        return ret
    return _


class Head(BaseHandler):
    '''划款列表头部信息'''

    @check_login
    @raise_excp('获取数据失败')
    @check_shopid_param
    def GET(self,  userid=None):

        # 微信通道实名商户
        wx_oauth_mchnt, chnlbind = 0, {}
        with get_connection('qf_core') as db:
            chnlbind = db.select_one('chnlbind',
                    where = {'userid' : ('in', (0, userid)),
                             'available' : 1,
                             'tradetype' : UserDefine.CHNLBIND_TYPE
                    },
                    other = 'order by priority',
                    fields = 'key3, mchntid, chnlid, termid')
            # 微信通道下实名商户为微信特约商户
            if (chnlbind['chnlid'] == config.WX_CHNLID and
                chnlbind['key3'] != 'wxeb6e671f5571abce'):
                wx_oauth_mchnt = 1

        # T1或者D1
        settle_type = UserDefine.SETTLE_TYPE_T1
        bigmchntids = set(get_bigmchntid() or [])
        if not chnlbind or not bigmchntids:
            settle_type = UserDefine.SETTLE_TYPE_T1
        elif (chnlbind['chnlid'] in config.D1_CHNLIDS and
              '{}_{}'.format(chnlbind['mchntid'], chnlbind['termid']) not in bigmchntids):
            settle_type = UserDefine.SETTLE_TYPE_D1
        else:
            settle_type = UserDefine.SETTLE_TYPE_T1

        # period
        # 若是t1需要获取账期
        period = {}
        if settle_type == UserDefine.SETTLE_TYPE_T1:
            td = time.strftime(DATE_FMT)
            period = UserUtil.get_periods(td) or {}

        return success({
            'wx_oauth_mchnt' : wx_oauth_mchnt,
            'settle_type' : settle_type,
            'period' : period
        })


class List(BaseHandler):
    '''划款记录列表'''

    @check_login
    @raise_excp('获取列表失败')
    @check_shopid_param
    def GET(self, userid=None):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        # 分页信息
        page, pagesize = int(d.get('page', 0)), int(d.get('pagesize', 10))

        # 获取数据
        try:
            # 获取账期
            dates = thrift_call(FundService, 'findDebitpageInfo',
                    config.FUND_SERVERS, userid, page, pagesize)
            if not dates:
                return self.write(success({'settles' : []}))

            # 获取划款列表
            debits = thrift_call(FundService, 'findDebitInfo',
                    config.FUND_SERVERS, userid, dates)
            if not debits:
                return self.write(success({'settles' : []}))
            debits = [i.__dict__ for i in debits]
            debits.sort(key=lambda d:d['expectdate'], reverse =True)
        except:
            raise ThirdError('获取列表失败')

        # 划款数据整理
        settles = []
        for expectdate, records in groupby(debits, lambda d:d['expectdate']):
            records = list(records)
            status_dict = defaultdict(int)
            total_payamt, cnt = 0, len(records)
            week_day = datetime.datetime.strptime(expectdate, DATE_FMT).isoweekday()
            for record in records:
                status_dict[record['status']] += 1
                total_payamt += record['payamt']
            # 全部已划款
            if status_dict['havepay'] == cnt:
                status = UserDefine.SETTLE_STATUS_HAVE
            # 全部未划款
            elif status_dict['nopay'] == cnt:
                status = UserDefine.SETTLE_STATUS_NO
            # 部分划款
            else:
                # 只有已划款和等待划款
                if status_dict['havepay'] + status_dict['nopay'] == cnt:
                    status = UserDefine.SETTLE_STATUS_PART
                # 包含划款失败
                elif status_dict['havepay'] or status_dict['nopay']:
                    status = UserDefine.SETTLE_STATUS_PART_FAIL
                # 全部划款失败
                else:
                    status = UserDefine.SETTLE_STATUS_FAIL

            settles.append({
                'expectdate' : expectdate,
                'week_day' : week_day,
                'status' : status,
                'records' : records,
                'total_payamt' : total_payamt,
                'cnt' : cnt})
        return self.write(success({'settles' : settles}))

@cache()
def get_settle_statis(userid, expectdate):
    try:
        ret = thrift_call(FundService, 'findActtradeStatis',
            config.FUND_SERVERS, userid, expectdate)
        return [i.__dict__ for i in ret]
    except:
        log.warn(traceback.format_exc())

class Summary(BaseHandler):
    '''划款详细列表总结信息'''

    @check_login
    @raise_excp('获取数据失败')
    @check_shopid_param
    def GET(self, userid=None):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        expectdate = d.get('expectdate')
        if not is_valid_date(expectdate):
            raise ParamError('账期格式错误')

        # 数据总结
        settle_statis = get_settle_statis(userid, expectdate)
        totalmoney = totalfee = totalmonthfee = 0
        for i in settle_statis:
            totalmoney += i['tradeamt']
            totalfee += i['fee']

        # 获取扣款历史
        monthfees = []
        try:
            monthfees = thrift_call(FundService, 'findWithholdHistory',
                config.FUND_SERVERS, userid, expectdate)
        except:
            log.warn(traceback.format_exc())

        # 扣款历史
        fee_detail_list = []
        for monthfee in monthfees:
            # 费用是正的是补给用户的，加到总额里面去
            if monthfee.amount > 0:
                totalmoney += monthfee.amount
            else:
                totalmonthfee += monthfee.amount
            is_rent_fee = False
            if isinstance(monthfee.title, types.UnicodeType):
                monthfee.title = monthfee.title.encode('utf-8')
            # 修改title如果是月租费的话 etc 12月QPOS月服务费
            if monthfee.title == 'QPOS月服务费':
                monthfee.title = '%s月%s' % (monthfee.evidence_date[5:7], monthfee.title)
                is_rent_fee = True
            # 存在的话，就合并
            is_exist = False
            for fee in fee_detail_list:
                if monthfee.title == fee['name'] and is_rent_fee:
                    fee['value'] += monthfee.amount
                    is_exist = True
                    break
            if not is_exist:
                fee_detail_list.append({
                    'name': monthfee.title,
                    'value': monthfee.amount,
                    'month': monthfee.evidence_date
                })

        return self.write(success({
                    'total_amt' : totalmoney-totalfee+totalmonthfee,
                    'total_trade_amt' : totalmoney,
                    'totalfee' : totalfee,
                    'feedetail' : fee_detail_list}))


class Details(BaseHandler):
    '''对账表详细信息'''

    @check_login
    @raise_excp('获取数据失败')
    @check_shopid_param
    def GET(self, userid=None):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        # 账期
        expectdate = d.get('expectdate')
        if not is_valid_date(expectdate):
            raise ParamError('账期格式错误')

        # 分页信息
        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息错误')

        # 到账详细信息
        details = defaultdict(list)
        try:
            trade_rs = thrift_call(FundService, 'findActtradeInfo',
                config.FUND_SERVERS, userid, expectdate, int(page), int(pagesize))
            for r in trade_rs:
                details[r.tradetime[:10]].append({
                    'tradetime':r.tradetime, 'tradeamt': r.tradeamt,
                    'fee':r.fee, 'type': r.tradetype,
                    'coupon_fee': r.ori_coupon_amt - r.coupon_amt,
                    'ori_coupon_amt': r.ori_coupon_amt})
        except:
            log.warn(traceback.format_exc())

        # 头部信息
        statis = get_settle_statis(userid, expectdate)
        statis.sort(key=lambda d:d['tradedt'], reverse=True)
        ret = []
        for i in statis:
            records = details.get(i['tradedt'])
            if records:
                ret.append({
                    'txdt' : i['tradedt'],
                    'cnt' : i['cnt'],
                    'fee' : i['fee'],
                    'tradeamt' : i['tradeamt'],
                    'details' : records
                })
        return self.write(success(ret))
