# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import time, datetime
import config
import logging
import json
log = logging.getLogger()

from util import get_app_info, BaseHandler, timestamp_str
from decorator import check_login
from constants import DATE_FMT, DATETIME_FMT, DTM_FMT

from qfcommon.base.tools import thrift_callex
from qfcommon.base.dbpool import get_connection
from qfcommon.qfpay.qfresponse import success
from . import base

from qfcommon.thriftclient.data_coupon_recall import couprecall

class Summary(BaseHandler):
    '''
    获取会员活动总结
    '''

    def get_summary(self, merchant_id):
        result = dict(member_count = 0,
                      payment_count=0)
        try:
            r = json.loads(thrift_callex(config.PROMOTION_COUPON_REPORT_SERVERS, couprecall,
                                        "coupspr", str(merchant_id)))

            result['member_count'] = sum([x['tx_cnt'] for x in r])
            result['payment_count'] = sum([x['tx_amt'] for x in r])
            log.info('coupon_data_report: %s' % result)

        except Exception as e:
            log.exception('call yupeng data report thrift server failure: %s', e)

        return result

    @check_login
    def GET(self):
        user_id = self.user.ses.get('userid')
        result = self.get_summary(user_id)
        return self.write(success(result))

class Preview(BaseHandler):
    '''
    会员活动通知预览
    '''

    def GET(self):
        preview = config.ACTV_TIPS.get('promotion', {}).get('preview', [])
        return self.write(success(preview))

class EffectList(BaseHandler):
    '''
    会员推广列表
    '''

    def get_promotion_data_report(self, merchant_id):
        try:
            response = json.loads(thrift_callex(config.PROMOTION_COUPON_REPORT_SERVERS, couprecall,
                                        "coupspr", str(merchant_id)))

            return {long(d['actv_id']): dict(member_count = d['cstm_cnt'],
                                             transaction_count = d['tx_cnt'],
                                             payment_count = d['tx_amt']) for d in response}

        except Exception as e:
            log.exception('call yupeng data report thrift server failure: %s', e)
            return {}

    def get_effect_list(self, user_id, page_number, page_size, req=None):
        result = []
        data_report_map = self.get_promotion_data_report(user_id)

        # 活动状态
        status = [1,2,3]
        if req:
            version, platform = get_app_info(req.environ.get('HTTP_USER_AGENT',''))
            if version and version < "030300":
                status = [1,2]

        # 活动列表
        actvs = []
        with get_connection('qf_mchnt') as conn:
            where = dict(userid=user_id, status=('in', status), type=1)
            actvs = conn.select('member_actv', where=where,
                    other="order by id desc limit %d, %d" %(page_number, page_size))

        now = datetime.datetime.now()
        for actv in actvs:
            new = {}
            new['id'] = actv['id']
            new['content'] = actv['content'] or actv['title']
            new['start_time'] = actv['start_time'].strftime(DATE_FMT)
            new['end_time'] = actv['expire_time'].strftime(DATE_FMT)

            ctime = datetime.datetime.fromtimestamp(actv['ctime'])
            notify_datetime = base.get_notify_datetime(ctime)
            new['notify_time'] = notify_datetime.strftime('%Y-%m-%d %H:%M')
            new['ctime'] = timestamp_str(actv['ctime'], DATETIME_FMT)

            # 被终止
            if actv['status'] == 3:
                new['state'] = new['status'] = 4
            # 审核失败
            elif actv['status'] == 2:
                new['state'] = new['status'] = 3
                new['audit_info'] = actv['audit_info']
            # 已结束
            elif actv['expire_time'] < now:
                new['state'] = new['status'] = 2
            # 进行中
            else:
                new['state'] = new['status'] = 1
                if now < notify_datetime:
                    new['status'] = 0

            # get data resport
            _report = dict(member_count=0, transaction_count=0, payment_count=0)
            data_report = data_report_map.get(actv['id'], _report.copy())
            new.update(data_report)
            result.append(new)

        return dict(allow_create = self.check_allow_create(user_id),
                    promotion_list = result)

    def check_allow_create(self, userid):
        num = 0
        with get_connection('qf_mchnt') as db:
            num = db.select_one('member_actv',
                    where = {
                        'userid': int(userid),
                        'expire_time': ('>', int(time.time())),
                        'status': 1,
                        'type': 1
                    },
                    fields = 'count(1) as num')['num']

        return bool(not num)


    @check_login
    def GET(self):
        user_id = self.user.ses.get('userid')
        page_number = int(self.req.input().get('page', 0))
        page_size = int(self.req.input().get('pagesize', 10))

        offset = page_size * page_number
        result = self.get_effect_list(user_id, offset, page_size, self.req)
        return self.write(success(result))


class Rule(BaseHandler):
    '''
    会员活动创建规则
    '''

    def GET(self):
        rule_descr = config.ACTV_TIPS.get('promotion', {}).get('rule', [])
        return self.write(success({
            'period_days': 14,
            'current_datetime': time.strftime(DTM_FMT),
            'rule_descr': rule_descr
        }))
