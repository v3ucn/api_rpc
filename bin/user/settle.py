#coding:utf-8

import datetime
import types
import config
import logging
log = logging.getLogger()

from collections import defaultdict
from constants import DATE_FMT, DATETIME_FMT
from excepts import ThirdError, ParamError
from decorator import check_login, raise_excp

from utils.valid import is_valid_int
from utils.base import BaseHandler

from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.finance import Finance
from qfcommon.base.qfresponse import QFRET, success, error

# 到账状态
DEBIT_STATUS = {
    'riskdelay': '风控延迟',
    'accountdelay': '账务延迟',
    'nopay': '等待划款',
    'havepay': '已划款',
    'inaccount': '已到账'
}

ACCOUNT_PERIOD_CACHE = {}

class List(BaseHandler):
    '''
    到账记录列表
    '''

    @check_login
    @raise_excp('获取列表失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        # userid
        userid = int(self.user.ses.get('userid', ''))

        # 分页信息
        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息错误')

        try:
            records = thrift_callex(config.FINANCE_SERVERS, Finance, 'get_debitinfo',
                    userid=userid, appsrc='qf', page=int(page)+1, maxnum=int(pagesize))
        except:
            raise ThirdError('第三方服务错误')

        if not records:
            return error(QFRET.NODATA)

        searchdate = []
        for r in records:
            if r.expectdate in ACCOUNT_PERIOD_CACHE:
                continue
            searchdate.append(r.expectdate)

        acnt_period_date = []
        if searchdate:
            try:
                acnt_period_date = thrift_callex(config.FINANCE_SERVERS, Finance,
                        "get_account_period", search_date_list=searchdate)
            except:
                raise ThirdError('第三方服务错误')
            if not acnt_period_date:
                return error(QFRET.NODATA)
            #将新的更新到缓存中
            for d in acnt_period_date:
                ACCOUNT_PERIOD_CACHE[d.search_date] = d

        data_lst = []
        sys_time = datetime.datetime.now()
        for r in records:
            period_date = ACCOUNT_PERIOD_CACHE.get(r.expectdate, '')
            if not period_date:
                continue
            expectdate_tm = '' if not r.status else datetime.datetime.strptime(r.expectdate + " 18:00:00", DATETIME_FMT)
            #如果是已经划款
            if r.status == 'havepay':
                #超过18:00点，则变成已经到账
                if expectdate_tm and expectdate_tm < sys_time:
                    r.status = 'inaccount'
            data = {'status': DEBIT_STATUS.get(r.status, '未知'),
                    'payamt': r.payamt,
                    'biznum': r.biznum,
                    'expectdate': r.expectdate,
                    'week_day': datetime.datetime.strptime(r.expectdate, DATE_FMT).isoweekday(),
                    'period': {"end": period_date.end_date,
                                "start": period_date.start_date,
                                "paydate": "" if not r.paytime else datetime.datetime.strptime(r.paytime, DATETIME_FMT).strftime(DATE_FMT),
                                "paytime": r.paytime,
                                 }
                    }
            data_lst.append(data)

        return success({'count': len(data_lst), 'systime': sys_time,
                'records': data_lst, 'total': len(data_lst)})

class Info(BaseHandler):

    @check_login
    @raise_excp('获取到账详细信息失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        biznum = d.get('biznum')
        if not biznum:
            raise ParamError('参数错误')
        try:
            records = thrift_callex(config.FINANCE_SERVERS, Finance,
                    'get_tradeinfo_by_biznum', biznum)
            if not records:
                return error(QFRET.NODATA)
        except:
            raise ThirdError('第三方服务错误')

        try:
            monthfees = thrift_callex(config.FINANCE_SERVERS, Finance,
                    "get_withhold_history_by_biznum", str(biznum))
        except:
            raise ThirdError('第三方服务错误')

        # 到账记录详细信息
        cp_chnlids = getattr(config, 'SETTLE_CP_CHNLIDS', [])
        totalmoney = totalfee = 0
        detaillist = []
        bills = defaultdict(int)
        for r in records:
            totalmoney += r.tradeamt
            totalfee += r.fee

            cp_amt = 0
            # 特定的通道将红包金额加入好近补贴
            if r.chnlid in cp_chnlids:
                bills['hj_coupon'] += r.coupon_amt
                cp_amt = r.coupon_amt
            # 到账分支付类型总计
            bills[r.tradetype] += (r.tradeamt - r.fee - cp_amt)

            detaillist.append({'tradetime': r.tradetime, 'tradeamt': r.tradeamt, 'fee': -r.fee,
                'type': r.tradetype, 'coupon_fee': r.ori_coupon_amt - r.coupon_amt, 'ori_coupon_amt': r.ori_coupon_amt})

        # 到账分支付类型总计
        billlist = []
        # 支付类型列表
        bill_types = getattr(config, 'BILL_TYPES', ('alipay', 'tenpay', 'jdpay', 'card', 'hj_coupon'))
        for i in bill_types:
            if not bills[i] or i not in config.BILL_TYPE_DETAIL: continue
            billlist.append({
                'name' : config.BILL_TYPE_DETAIL[i],
                'value' : bills[i],
                'type': i
            })

        # 扣款列表
        fee_detail_list = []
        for monthfee in monthfees:
            #费用是正的是补给用户的，加到总额里面去
            if monthfee.amount > 0:
                totalmoney += monthfee.amount
            #扣费加到手续费里面去
            else:
                totalfee += -monthfee.amount

            is_rent_fee = False
            if isinstance(monthfee.title, types.UnicodeType):
                monthfee.title = monthfee.title.encode('utf-8')
            #修改title如果是月租费的话 etc 12月QPOS月服务费
            if monthfee.title == 'QPOS月服务费':
                monthfee.title = '%s月%s' % (monthfee.evidence_date[5:7], monthfee.title)
                is_rent_fee = True
            #存在的话，就合并
            is_exist = False
            for fee in fee_detail_list:
                if monthfee.title == fee['name'] and is_rent_fee:
                    fee['value'] += monthfee.amount
                    is_exist = True
                    break
            if not is_exist:
                fee_detail_list.append({'name': monthfee.title, 'value': monthfee.amount, 'month': monthfee.evidence_date})

        return success({'totalmoney': totalmoney,
                        'totalfee': -totalfee,
                        'detaillist': detaillist,
                        'feedetail': fee_detail_list,
                        'billlist': billlist})
