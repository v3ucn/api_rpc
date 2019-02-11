# coding=utf-8

'''
交易流水相关
'''

import time
import logging
import config
import copy
import traceback

from constants import DTM_FMT
from runtime import redis_pool

from utils.date_api import future, str_diffdays
from utils.base import BaseHandler
from utils.decorator import check
from utils.qdconf_api import get_qd_conf_value

from qfcommon.base.dbpool import get_connection
from qfcommon.base.qfresponse import success
from qfcommon.qfpay.defines import (
    QF_BUSICD_ALIPAY_PRECREATE, QF_BUSICD_ALIPAY_H5, QF_BUSICD_ALIPAY_SWIPE,
    QF_BUSICD_WEIXIN_PRECREATE, QF_BUSICD_WEIXIN_PRECREATE_H5, QF_BUSICD_WEIXIN_SWIPE,
    QF_BUSICD_ALIPAY_REFUND, QF_BUSICD_WEIXIN_REFUND
)

log = logging.getLogger()

receipt_key = '_mchnt_api_receipt_key_'

# 打印日结算单最长时间
RECEIPT_MAX_DAYS = getattr(config, 'RECEIPT_MAX_DAYS', 60)

# 支付宝支付
receipt_pay_type = [{
    'name': 'wx',
    'busicd': (
        QF_BUSICD_WEIXIN_PRECREATE, QF_BUSICD_WEIXIN_PRECREATE_H5,
        QF_BUSICD_WEIXIN_SWIPE
    ),
    'refund_busicd': (QF_BUSICD_WEIXIN_REFUND, )
}, {
    'name': 'alipay',
    'busicd': (
        QF_BUSICD_ALIPAY_PRECREATE, QF_BUSICD_ALIPAY_H5, QF_BUSICD_ALIPAY_SWIPE
    ),
    'refund_busicd': (QF_BUSICD_ALIPAY_REFUND, )
}]


class Receipt(BaseHandler):
    '''商户打印结算单数据'''

    _base_err = '获取数据失败'

    def get_stat(self, busicds, refund_busicd, start_time, end_time):
        '''统计数据'''
        # 计算跨表
        styear, stmonth = int(start_time[:4]), int(start_time[5:7])
        edyear, edmonth = int(end_time[:4]), int(end_time[5:7])
        tables = []
        while (edyear, edmonth) >= (styear, stmonth):
            tables.append('record_%d%02d' % (edyear, edmonth))
            edyear, edmonth= edyear - (edmonth==1), edmonth-1 or 12
        log.debug(tables)

        where = {
            'retcd' : '0000',
            'sysdtm' :  ('between', (start_time, end_time)),
            'userid' : int(self.user.userid),
        }
        # 支付成功
        succ_where = copy.deepcopy(where)
        succ_where['busicd'] = ('in', busicds)

        # 退款
        refund_where = copy.deepcopy(where)
        refund_where['busicd'] = ('in', refund_busicd)

        ret = {
            'consume_num' : 0,
            'consume_amt' : 0,
            'refund_num' : 0,
            'refund_amt' : 0,
            'net_amount_num' : 0,
            'net_amount_amt' : 0,
        }
        with get_connection('qf_trade') as db:
            for table in tables:
                succ = db.select_one(
                    table, where=succ_where,
                    fields = 'sum(txamt) amt,count(1) num,sum(coupon_amt) cp_amt'
                )
                log.debug(succ)
                if succ:
                    ret['consume_num'] += (succ['num'] or 0)
                    ret['consume_amt'] += (succ['amt'] or 0) + (succ['cp_amt'] or 0)

                refund = db.select_one(
                    table, where=refund_where,
                    fields = 'sum(txamt) amt,count(1) num,sum(coupon_amt) cp_amt'
                )
                log.debug(refund)
                if refund:
                    ret['refund_num'] += (refund['num'] or 0)
                    ret['refund_amt'] += (refund['amt'] or 0) + (refund['cp_amt'] or 0)

        ret['net_amount_num'] = ret['consume_num'] - ret['refund_num']
        ret['net_amount_amt'] = ret['consume_amt'] - ret['refund_amt']

        return ret

    @check('login')
    def GET(self):
        userid = self.user.userid

        now = time.strftime(DTM_FMT)

        # 开始时间 和 引用计数
        info = (
            redis_pool.hget(receipt_key, userid) or
            future(days = -1, fmt_type = 'str', fmt = DTM_FMT) + ',' + '1'
        )

        start_time, ref_num = info.split(',')

        log.debug(start_time)
        if str_diffdays(now, start_time, DTM_FMT) >= RECEIPT_MAX_DAYS:
            start_time = future(days = -1, fmt_type = 'str', fmt = DTM_FMT)

        # 支付方式
        groupid = self.get_groupid()
        pay_seq = get_qd_conf_value(
            groupid = groupid, mode = 'service', key = 'PAY_SEQUENCE',
            default_key = int(groupid not in config.QF_GROUPIDS),
            default_val = config.PAY_SEQUENCE
        )

        ret = {
            'start_time': start_time,
            'end_time': now,
            'ref_num': ref_num,
            'stat':  [],
        }
        for i in receipt_pay_type:
            if i['name'] in pay_seq:
                tmp = {'paytype': i['name']}
                tmp.update(self.get_stat(
                    i['busicd'], i['refund_busicd'],
                    start_time, now
                ))
                ret['stat'].append(tmp)

        # 如果大于1种支付方式, 需要加总结列
        if len(ret['stat']) >= 1:
            tmp = {}
            fields = (
                'consume_num', 'consume_amt', 'refund_num', 'refund_amt',
                'net_amount_num', 'net_amount_amt'
            )
            for field in fields:
                tmp[field] = sum(i.get(field, 0) for i in ret['stat'])
            tmp['paytype'] = 'total'
            ret['stat'].append(tmp)

        return success(ret)


class UpReceiptInfo(BaseHandler):
    '''上传打印信息'''

    @check('login')
    def POST(self):
        try:
            userid = self.user.userid

            now = time.strftime(DTM_FMT)

            # 开始时间 和 引用计数
            info = (
                redis_pool.hget(receipt_key, userid) or
                future(days = -1, fmt_type = 'str', fmt = DTM_FMT) + ',' + '1'
            )

            start_time, ref_num = info.split(',')

            redis_pool.hset(receipt_key, userid, ','.join([now, str(int(ref_num) + 1)]))
        except:
            log.warn(traceback.format_exc())

        return success({})
