# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import json
import time
import config
import datetime
import logging
log = logging.getLogger()
import traceback

from util import json2dic
from decorator import raise_excp,check_login, with_validator
from excepts import ParamError, ThirdError
from utils.decorator import check
from utils.base import BaseHandler
from utils.date_api import date_to_tstamp, get_day_begin_ts
from base import get_notify_datetime

from qfcommon.base.dbpool import get_connection_exception, get_connection, DBFunc
from qfcommon.qfpay.qfresponse import success
from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.qf_marketing import QFMarketing
from qfcommon.thriftclient.qf_marketing.ttypes import CouponRule, Activity, ServerError
from qfcommon.thriftclient.data_coupon_recall import couprecall
from qfcommon.web.validator import Field, T_INT

def check_allow_create(userid):
    num = 0
    allow_create = True
    where = {
        'create_mchnt_id': userid,
        'type': 3,
        'status': ('in', [1, 2]),
    }
    td_ts = get_day_begin_ts()
    notify_ts = td_ts + 11 * 3600
    if int(time.time()) > notify_ts:
        where['create_time'] = ('>=', td_ts)
    else:
        where['create_time'] = ('>', td_ts - 24 * 3600)
    with get_connection('qf_marketing') as db:
        num = db.select_one(
                table= 'activity',
                where= where,
                fields= 'count(1) as num')['num']
    if num >= 1:
        allow_create = False

    return allow_create

class Summary(BaseHandler):
    @classmethod
    def get_summary(cls, user_id):
        result = dict(coupon_count=0,
                      payment_count=0,
                      )
        with get_connection_exception('qf_marketing') as conn:
            # 获取红包数量
            args = dict(mchnt_id=user_id, type=3)
            retval = conn.select_one('activity', where=args, fields="sum(used_num) as coupon_count")
            if retval['coupon_count']:
                result['coupon_count'] = retval['coupon_count']

            # 消费金额
            retval = conn.select('activity', where=args, fields='id')
            activity_id_list = [a['id'] for a in retval]

            if activity_id_list:
                args = dict(mchnt_id=user_id, activity_id=('in', list(activity_id_list)))
                retval = conn.select_one('record', where=args, fields="sum(total_amt) as payment_count")

                if retval['payment_count']:
                    result['payment_count'] = retval['payment_count']
            pass

        return result

    @check_login
    def GET(self):
        user_id = self.user.ses.get('userid')
        result = self.get_summary(user_id)
        return self.write(success(result))

class EffectList(BaseHandler):
    '''
     会员通知红包列表
    '''

    _validator_fields = [
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
    ]

    def get_coupon_data_report(self, userid):
        reports = {}
        big_uid = self.get_big_uid()
        for i in (big_uid, userid):
            if not i:
                continue
            try:
                result = thrift_callex(config.PROMOTION_COUPON_REPORT_SERVERS,
                                       couprecall, "couprec", str(i))

                result = json.loads(result)
                reports.update({int(d['actv_id']): d for d in result})
            except Exception as e:
                log.warn(str(e))

        return reports

    def get_coupon_info(self, userid, actv_ids):
        if not actv_ids:
            return {}

        result = {i: {'id': i, 'used_coupon_count':0,
                       'payment_count':0, 'inactive_member_count': 0}
                  for i in actv_ids }

        data_report = self.get_coupon_data_report(userid)

        for actv_id, report in data_report.iteritems():
            if int(actv_id) not in actv_ids:
                continue

            actv = result[actv_id]
            actv['used_coupon_count'] = report['tx_cnt']
            actv['payment_count'] = report['tx_amt']
            actv['inactive_member_count'] = report['recall_cnt']

        return result

    def get_stats(self, userid, actv_ids):
        stats = None
        with get_connection('qf_marketing') as db:
            stats= db.select(
                    'record',
                    where= {
                        'activity_id': ('in', actv_ids)
                    },
                    fields= ('activity_id, sum(total_amt) payment_count',
                             'count(1) used_coupon_count'),
                    other= 'group by activity_id')
        return {i['activity_id']: i for i in stats or []}

    def get_coupon_rules(self, ruleids):
        rules = []
        with get_connection('qf_marketing') as db:
            rules = db.select('coupon_rule',
                              where={'id': ('in', ruleids)},
                              fields='id, amt_min')
        return {i['id']:i for i in rules or [] }

    def get_big_actvids(self):
        big_uid = self.get_big_uid()
        if not big_uid:
            return []

        actvids = actvs = None
        userid = self.user.userid
        with get_connection('qf_marketing') as db:
            actvs = db.select_join(
                    table1= 'activity a', table2= 'coupon_rule_mchnt crm',
                    on= {'a.obtain_xx_id': 'crm.coupon_rule_id'},
                    where= {
                        'a.create_mchnt_id': str(big_uid),
                        'a.type': 3,
                        'a.status': ('in', (1, 2)),
                        'a.mchnt_id': DBFunc('0 and locate(\'"{}"\', '
                                'crm.mchnt_id_list)'.format(userid))
                    },
                    fields= 'a.id')
            actvids = [actv['id'] for actv in actvs ]

        return actvids

    def get_effect_list(self, userid):
        result = []
        data = self.validator.data

        big_actvids = self.get_big_actvids()
        actvs = None
        with get_connection('qf_marketing') as db:
            where = '(create_mchnt_id={userid} {bigids}) '.format(
                    userid= userid,
                    bigids= ('' if not big_actvids else
                        ' or id in ({})'.format(
                            ','.join(str(int(i))for i in big_actvids))
                    ))
            where += 'and type=3 and status in (1,2)'
            sql = ('select * from activity where {where} {other}'.format(
                    where= where,
                    other=('order by id desc limit %d offset %d' %
                           (data['pagesize'], data['page']*data['pagesize']))))

            actvs = db.query(sql)

        if not actvs:
            return []

        actv_ids = [actv['id'] for actv in actvs]
        # 红包信息
        coupon_infos = self.get_coupon_info(userid, actv_ids)
        # 统计信息
        stats = self.get_stats(userid, actv_ids)
        # coupon rule
        rules = self.get_coupon_rules([i['obtain_xx_id'] for i in actvs])

        result = []
        now = datetime.datetime.now()
        for actv in actvs:
            aid = actv['id']
            if actv['obtain_xx_id'] not in rules or aid not in coupon_infos:
                continue
            info = coupon_infos[aid]
            stat = stats.get(aid) or {}
            info.update(stat)

            info['notify_time'] = get_notify_datetime(actv['create_time'])
            if now < info['notify_time']:
                info['status'] = 0
            elif now >= info['notify_time'] and now<=actv['expire_time']:
                info['status'] = 1
            else:
                info['status'] = 2

            info['coupon_count'] = (actv['used_num'] or
                                    (actv['total_amt']/rules[actv['obtain_xx_id']]['amt_min']))

            # 大商户创建的标记
            info['big_create'] = int(actv['create_mchnt_id'] != str(userid))

            result.append(info)

        return result

    @check_login
    @with_validator()
    @raise_excp('获取活动列表失败')
    def GET(self):
        userid = int(self.user.userid)

        coupon_list = self.get_effect_list(userid)
        allow_create = check_allow_create(userid)

        return self.write(success({
            'coupon_list': coupon_list,
            'allow_create': allow_create
        }))

class Verbose(BaseHandler):
    '''
    会员通知详细信息红包
    '''

    def get_verbose(self, user_id, coupon_id):
        big_uid = self.get_big_uid(user_id)
        userids = (user_id, big_uid) if big_uid else (user_id, )
        with get_connection_exception('qf_marketing') as db:
            act = db.select_one(
                    "activity",
                    where= {
                        'create_mchnt_id' : ('in', userids),
                        'id' : coupon_id
                    })
            if not act:
                raise ParamError('活动不存在')

            rule = db.select_one("coupon_rule", where={'id' : act['obtain_xx_id']})
            if not rule:
                raise ParamError('活动规则不存在')

        result = {}
        rule_data = json.loads(rule['use_rule'])['rule']
        result['lower_price'] = filter(lambda x:x[0] == 'amt', rule_data)[0][2]
        result['member_count'] = act['used_num'] or int(act['total_amt']/rule['amt_min'])
        result['price'] = rule['amt_min']
        result['notify_time'] = act['start_time'].strftime('%Y-%m-%d 11:00')

        # 大商户创建的标记
        result['big_create'] = int(act['create_mchnt_id'] != str(user_id))

        # 红包的有效期
        cp_profile = json2dic(rule['profile'])
        if cp_profile.get('effect_type') == 2:
            result['period_days'] = cp_profile['effect_len']
        else:
            result['period_days'] = int((rule['expire_time'] - rule['start_time']).total_seconds()) / (24*3600)

        # 活动状态
        now = datetime.datetime.now()
        notify_datetime = get_notify_datetime(act['create_time'])
        if now < notify_datetime:
            result['status'] = 0
        elif now >= notify_datetime and now<=act['expire_time']:
            result['status'] = 1
        else:
            result['status'] = 2

        return result

    @check_login
    @raise_excp('获取详细信息失败')
    def GET(self):
        user_id = int(self.user.userid)
        coupon_id = self.req.input()['coupon_id']
        result = self.get_verbose(user_id, coupon_id) or {}
        return self.write(success(result))

class Rule(BaseHandler):
    '''
    红包通知创建规则
    '''

    def GET(self):
        notify_dt =  datetime.datetime.now() + datetime.timedelta(days=1)
        notify_dtm = notify_dt.replace(hour=11, minute=0, second=0)
        rule_descr = config.ACTV_TIPS.get('coupon', {}).get('rule', [])
        return self.write(success({
            'notify_time': notify_dtm.strftime('%Y-%m-%d %H:%M'),
            'lower_price': 2000,
            'period_days': 14,
            'rule_descr':  rule_descr
            }))

class Preview(BaseHandler):
    '''
    红包通知预览
    '''

    def GET(self):
        preview = config.ACTV_TIPS.get('coupon', {}).get('preview', [])
        return self.write(success(preview))


class Create(BaseHandler):

    @classmethod
    def create_coupon(cls, user_id, lower_price, coupon_price, expire_days):
        today = datetime.date.today()
        title = "店铺会员红包"

        total_amt = 0
        with get_connection_exception('qf_mchnt') as conn:
            where = dict(userid=user_id)
            result = conn.select_one('member', where=where, fields="count(1) as count")
            total_amt = max(result['count'] * coupon_price, coupon_price)

        userid = str(user_id)
        use_rule = [['amt', '>=', lower_price]]
        rule_args = CouponRule()
        rule_args.src = 'qpos'
        rule_args.mchnt_id = userid
        rule_args.title = title
        rule_args.amt_max = coupon_price
        rule_args.amt_min = coupon_price
        rule_args.use_rule = json.dumps(use_rule)
        rule_args.status = 2
        rule_args.start_time  = int(time.mktime((today + datetime.timedelta(days = 1)).timetuple()))
        rule_args.expire_time = int(time.mktime((today + datetime.timedelta(days = expire_days+1)).timetuple()))
        rule_id = None
        try:
            rule_id = thrift_callex(config.QF_MARKETING_SERVERS, QFMarketing, 'coupon_rule_create', rule_args)
            log.warn('create coupon rule id: %s', rule_id)
        except ServerError as e:
            log.error('coupon_rule_create failure: %s, %s', e.code, e.msg)
            raise

        create_args = Activity()
        create_args.src = 'qpos'
        create_args.mchnt_id = userid
        create_args.type = 3
        create_args.title = title
        create_args.total_amt = total_amt
        create_args.xx_type = 1
        create_args.status = 2
        create_args.obtain_award_num = 1
        create_args.obtain_xx_id = rule_id
        create_args.rule = json.dumps([])
        create_args.start_time = date_to_tstamp(today+datetime.timedelta(days=1))
        create_args.expire_time = int(time.mktime((today + datetime.timedelta(days = expire_days+1)).timetuple()))

        try:
            activity_id = thrift_callex(config.QF_MARKETING_SERVERS, QFMarketing, 'activity_create', create_args)
            log.warn('create activity id: %s', activity_id)
        except ServerError as e:
            log.error('activity_create failure: %s, %s', e.code, e.msg)
            raise

        return

    @check(['login'])
    @raise_excp('创建红包活动失败！')
    def POST(self):
        args = {k:v.strip() for k, v in self.req.input().iteritems()}
        #args = dict(lower_price=200, coupon_price=20, userid=1000)
        lower_price = int(args['lower_price'])
        coupon_price = int(args['coupon_price'])
        expire_days = 14

        user_id = int(self.user.ses.get('userid'))

        result = dict(status=False)

        if not check_allow_create(user_id):
            raise ParamError('活动结束后才能再创建哦')

        try:

            self.create_coupon(user_id, lower_price, coupon_price,
                               expire_days)

            result['status'] = True
        except:
            log.exception('create coupon')
            raise

        return self.write(success(result))


class Remove(BaseHandler):
    '''
    删除红包活动
    '''

    _validator_fields = [
        Field('coupon_id', T_INT, isnull=False),
    ]

    @check(['login'])
    @with_validator()
    @raise_excp('终止红包推广活动失败')
    def POST(self):
        actv = None
        with get_connection('qf_marketing') as db:
            actv = db.select_one(
                    table= 'activity',
                    where= {
                        'id': self.validator.data['coupon_id'],
                    },
                    fields= 'id, create_mchnt_id, status, create_time')
        if not actv:
            raise ParamError('活动不存在')

        if actv['create_mchnt_id'] != str(self.user.userid):
            if actv['create_mchnt_id'] == str(self.get_big_uid()):
                raise ParamError('此活动为总账户创建，你无法执行修改~')
            raise ParamError('暂无修改此活动的权限')

        # 已经进行的活动不能删除
        now = datetime.datetime.now()
        notify_datetime = get_notify_datetime(actv['create_time'])
        if not now < notify_datetime:
                raise ParamError('不能删除已经进行的红包推广活动！')

        if actv['status'] != 3:
            try:
                act = Activity(id=actv['id'], status=3,
                               src='qpos')
                thrift_callex(config.QF_MARKETING_SERVERS, QFMarketing,
                              'activity_change', act)
            except:
                log.warn(traceback.format_exc())
                raise ThirdError('关闭活动失败')

        return self.write(success({}))
