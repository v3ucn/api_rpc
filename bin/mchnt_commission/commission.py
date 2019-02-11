# encoding:utf-8

import re
import logging
import traceback
import xlwt
import StringIO
import math
import base64
from qfcommon.library.mail import MailMessage, MailSender
from utils.tools import unicode_to_utf8
from operator import itemgetter
from utils.base import BaseHandler
from utils.decorator import check
from constants import DATETIME_FMT, EMAIL_PATTERN
from utils.tools import apcli_ex

from excepts import (
    ParamError, ThirdError, SessionError, UserError,
    DBError
)

from qfcommon.base.dbpool import (
    with_database, get_connection, get_connection_exception
)
from qfcommon.base.qfresponse import QFRET, error, success

from qfcommon.web.validator import Field, T_REG, T_INT, T_STR, T_FLOAT
from constants import ACT_ENABLED, ACT_CLOSED, RECORD_STATUS_USE, RECORD_STATUS_DESTROY, \
    ACTIVITY_SHARE_TYPE_COUPON, DATETIME_FMT

log = logging.getLogger()


def re_trade_status(trade_type):
    return {
        RECORD_STATUS_DESTROY: '已撤销',
        RECORD_STATUS_USE: '交易成功'
    }.get(trade_type, '')


def get_union_activty(userid):

    with get_connection('qf_marketing') as db:
        rows = db.select('coupon_rule_mchnt', fields='mchnt_id_list, coupon_rule_id',
                         where={'mchnt_id_list': ('like', '%{}%'.format(userid))})
        if not rows:
            return {}

        sponsor_xx_ids = [i['coupon_rule_id'] for i in rows]
        # 根据sponer_xx_id去取activity表的union_id
        where = {'sponsor_xx_id': ('in', sponsor_xx_ids)}
        rows = db.select('activity', fields='sponsor_xx_id, union_id', where=where)
        if not rows:
            return {}

        # 找出union_id: sponsor_xx_id的对应关系
        union_sponsor = dict()
        for i in rows:
            union_sponsor.update({i['sponsor_xx_id']: i['union_id']})

        union_ids = [i['union_id'] for i in rows]

        # 根据可用的规则id查找对应的红包活动关联的门店id
        where = {'type': ('in', (1, 2)), 'id': ('in', union_ids),
                 'status': ('in', (ACT_ENABLED, ACT_CLOSED))}

        rows = db.select('activity_union', fields='id, title, cmn_id, status, ctime', where=where)
        # 转换为{红包id: {}}的格式
        coupon_dic = dict()
        # 找出union_id: cmn_id的对应关系
        union_cmn = dict()

        if not rows:
            return {}
        for i in rows:
            coupon_dic.update({i['id']: {'title': i['title'], 'status': i['status'], 'ctime':i['ctime']}})
            union_cmn.update({i['id']: i['cmn_id']})

        cmn_ids = [i['cmn_id'] for i in rows]

        rows = db.select('commission_rules', fields='id, mchnt_rate',
                         where={'id': ('in', cmn_ids), 'status': 1})

        # 计算一个规则id对应的抽佣比例对照dict
        commission_rate_dic = dict()
        # if not rows:
        #     return {}
        for i in rows:
            commission_rate_dic.update({i['id']: i['mchnt_rate']})

        for k, v in union_cmn.iteritems():
            coupon_dic[k]['rate'] = commission_rate_dic.get(v, 0)

        return {
                    'coupon_dic': coupon_dic,  # 记录了红包id和title的信息 最后页面使用
                }


class CommissionSummary(BaseHandler):
    '''
    抽佣汇总接口
    '''

    fields = [
        Field('page', isnull=False),
        Field('pageSize', isnull=False),
    ]

    @check('login')
    def GET(self):
        try:
            params = self.req.inputjson()
            userid = self.user.userid

            try:
                page = int(params.get('page', 0))
                pagesize = int(params.get('pagesize', 10))
            except:
                log.debug(traceback.format_exc())
                return self.write(error(QFRET.PARAMERR, respmsg=u"分页参数错误"))

            union_activity = get_union_activty(userid)
            coupon_dic = union_activity.get('coupon_dic', {})
            all_actids = coupon_dic.keys()  # 这个id是activity_union表的id

            res = dict()
            res['total_num'] = 0
            res['total_amount'] = 0
            res['commission_amount'] = 0
            res['coupon_amount'] = 0
            res['count'] = 0
            res['is_activity'] = 0
            res['activitys'] = []

            if not all_actids:
                return self.write(success(data=res))

            else:
                # 再关联下activity表的id
                with get_connection('qf_marketing') as db:
                    rows = db.select('activity', fields='id, union_id',
                                     where={'union_id': ('in', all_actids)})
                if rows:
                    activity_ids = set()
                    # coupon_dic2 = dict()
                    # 增加一个变量记录下activity_id: union_id的对应关系
                    actid_union_dic = {}
                    for i in rows:
                        activity_ids.add(i['id'])
                        # coupon_dic2.update({i['id']: coupon_dic[i['union_id']]})
                        actid_union_dic.update({i['id']: i['union_id']})

                    where = {'xx_type': ACTIVITY_SHARE_TYPE_COUPON, 'activity_id': ('in', activity_ids),
                             'use_mchnt_id': userid, 'type': ('in', (RECORD_STATUS_USE, RECORD_STATUS_DESTROY))}

                    with get_connection_exception('qf_marketing') as conn:
                        rows = conn.select('record',
                                           fields='use_mchnt_id, activity_id, amt, (total_amt - amt) as payamt, type, out_sn, orig_out_sn',
                                           where=where)

                    # 先找出所有的origin_out_sn的数据,撤销交易要原单号
                    all_orig_out_sns = []
                    destory_trade = {}
                    for i in rows:
                        if i['type'] == 3:
                            all_orig_out_sns.append(i['orig_out_sn'])
                            destory_trade.update({i['orig_out_sn']: i})
                    temp = dict()
                    for i in all_actids:
                        temp.update({'{}'.format(i): {'trade_amount': 0,
                                 'commi_amount': 0,
                                 'trade_num': 0,
                                 'commi_rate': coupon_dic.get(int(i)).get('rate', 0),
                                 'actname': coupon_dic.get(int(i)).get('title', ''),
                                 'status':  0 if coupon_dic.get(int(i)).get('status', '') == 3 else 1,
                                 'ctime': coupon_dic.get(int(i)).get('ctime', ''),
                                 'actid': str(i),
                                 'coupon_amount': 0,
                                 }})
                    for i in rows:
                        if int(i['type']) == RECORD_STATUS_DESTROY:
                            continue
                        if i['out_sn'] in set(all_orig_out_sns):
                            continue
                        key = '{}'.format(actid_union_dic.get(i['activity_id']))

                        rate = coupon_dic.get(int(actid_union_dic.get(i['activity_id']))).get('rate')
                        res['total_num'] += 1
                        res['total_amount'] += int(i['payamt'])
                        res['coupon_amount'] += int(i['amt'])
                        temp[key]['trade_num'] += 1
                        temp[key]['trade_amount'] += int(i['payamt'])
                        temp[key]['coupon_amount'] += int(i['amt'])
                        fee = float(i['payamt']) * float(rate) / 100.0 / 100.0
                        fee = math.floor(fee * 100)
                        temp[key]['commi_amount'] += fee
                        res['commission_amount'] += fee

                    for k, v in temp.iteritems():
                        res['activitys'].append(v)
                    res['activitys'] = sorted(res['activitys'], key=itemgetter('status', 'ctime'), reverse=True)
                    res['count'] = len(res['activitys'])
                    start = page * pagesize
                    end = page * pagesize + pagesize
                    res['activitys'] = res['activitys'][start:end]
                    res['is_activity'] = 1
                    return self.write(success(data=res))

        except:
            log.warn('error :%s' % traceback.format_exc())
            return self.write(error(QFRET.SERVERERR, respmsg=u"服务错误"))


class CommissionDetail(BaseHandler):
    '''
    抽佣明细接口
    '''

    fields = [
        Field('act_id', isnull=False),
        Field('email', isnull=False),
    ]

    def get_activity_info(self, act_id):

        # 根据可用的规则id查找对应的红包活动关联的门店id
        with get_connection('qf_marketing') as db:
            where = {'type': ('in', (1, 2)), 'id': act_id,
                     'status': ('in', (ACT_ENABLED, ACT_CLOSED))}

            rows = db.select('activity_union', fields='id, title, cmn_id, status, ctime', where=where)
            # 转换为{红包id: {}}的格式
            coupon_dic = dict()
            # 找出union_id: cmn_id的对应关系
            union_cmn = dict()

            if not rows:
                return {}
            for i in rows:
                coupon_dic.update({i['id']: {'title': i['title'], 'status': i['status'], 'ctime':i['ctime']}})
                union_cmn.update({i['id']: i['cmn_id']})

            cmn_ids = [i['cmn_id'] for i in rows]

            rows = db.select('commission_rules', fields='id, mchnt_rate',
                             where={'id': ('in', cmn_ids), 'status': 1})

            # 计算一个规则id对应的抽佣比例对照dict
            commission_rate_dic = dict()
            # 有可能出现没有佣金规则的情况
            # if not rows:
            #     return {}
            for i in rows:
                commission_rate_dic.update({i['id']: i['mchnt_rate']})

            for k, v in union_cmn.iteritems():
                coupon_dic[k]['rate'] = commission_rate_dic.get(v, 0)

            return {
                        'coupon_dic': coupon_dic,  # 记录了红包id和title的信息 最后页面使用
                    }

    @check('login')
    def GET(self):
        try:
            params = self.req.inputjson()
            act_id = params.get('actid', '')
            email = params.get('email', '')
            userid = self.user.userid
            try:
                page = int(params.get('page', 0))
                pagesize = int(params.get('pagesize', 10))
            except:
                log.debug(traceback.format_exc())
                return self.write(error(QFRET.PARAMERR, respmsg=u"分页参数错误"))

            if not act_id:
                return self.write(error(QFRET.PARAMERR, respmsg='参数错误'))
            if email and not re.match(EMAIL_PATTERN, email):
                return self.write(error(QFRET.PARAMERR, respmsg='邮箱不合法'))

            union_activity = self.get_activity_info(act_id)
            coupon_dic = union_activity.get('coupon_dic', {})
            all_actids = coupon_dic.keys()  # 这个id是activity_union表的id

            res = dict()
            res['total_num'] = 0
            res['total_amount'] = 0
            res['commission_amount'] = 0
            res['coupon_amount'] = 0
            res['count'] = 0
            res['records'] = []

            try:
                userinfos = apcli_ex('findUserBriefsByIds', [int(userid),]) or []
            except:
                raise ThirdError('获取商户信息失败')

            userinfos = {i.uid: i.__dict__ for i in userinfos}

            # 再关联下activity表的id
            with get_connection('qf_marketing') as db:
                rows = db.select('activity', fields='id, union_id', where={'union_id': act_id})
            if rows:
                activity_ids = set()
                # coupon_dic2 = dict()
                # 增加一个变量记录下activity_id: union_id的对应关系
                actid_union_dic = {}
                for i in rows:
                    activity_ids.add(i['id'])
                    # coupon_dic2.update({i['id']: coupon_dic[i['union_id']]})
                    actid_union_dic.update({i['id']: i['union_id']})

                where = {
                    'xx_type': ACTIVITY_SHARE_TYPE_COUPON, 'activity_id': ('in', activity_ids),
                    'use_mchnt_id': userid, 'type': ('in', (RECORD_STATUS_USE, RECORD_STATUS_DESTROY))}

                with get_connection_exception('qf_marketing') as conn:
                    rows = conn.select('record',
                                       fields='amt, (total_amt - amt) as payamt, type, create_time, orig_out_sn, out_sn',
                                       where=where, other='order by create_time desc')

                # 先找出所有的origin_out_sn的数据,撤销交易要原单号
                all_orig_out_sns = []
                destory_trade = {}
                for i in rows:
                    if i['type'] == 3:
                        all_orig_out_sns.append(i['orig_out_sn'])
                        destory_trade.update({i['orig_out_sn']: i})

                rate = coupon_dic.get(int(act_id), {}).get('rate', 0)
                actname = coupon_dic.get(int(act_id), {}).get('title', '')
                shopname = userinfos.get(int(userid), {}).get('shopname', '')
                status = 0 if coupon_dic.get(int(act_id), {}).get('status', '') == 3 else 1
                for i in rows:
                    status = int(i['type'])
                    if status == RECORD_STATUS_DESTROY:
                        continue
                    if i['out_sn'] in set(all_orig_out_sns):
                        i = destory_trade.get(i['out_sn'])
                    temp = dict()
                    temp['actname'] = actname
                    temp['shopname'] = shopname
                    temp['commi_rate'] = rate
                    temp['trade_time'] = i['create_time'].strftime(DATETIME_FMT)
                    temp['syyn'] = str(i['orig_out_sn']) if i['orig_out_sn'] else str(i['out_sn'])
                    temp['trade_status'] = int(i['type'])

                    temp['trade_amount'] = i['payamt']
                    temp['coupon_amount'] = i['amt']
                    commi_amount, temp['commi_amount'] = 0, 0
                    if int(i['type']) == RECORD_STATUS_USE:
                        res['total_num'] += 1
                        commi_amount = float(i['payamt']) * float(rate) / 100.0 / 100.0
                        temp['commi_amount'] = math.floor(commi_amount * 100)
                        res['total_amount'] += i['payamt']
                        res['coupon_amount'] += i['amt']
                        res['commission_amount'] += temp['commi_amount']
                    res['records'].append(temp)

                res['status'] = status
                res['rate'] = rate
                res['actname'] = actname
                res['count'] = len(res['records'])

            if email:
                wb = xlwt.Workbook(encoding="utf-8")
                ws = wb.add_sheet("%s" % u'抽佣明细')
                head_remit = (u"交易门店", u'活动名称', u"交易时间", u"交易流水号", u"交易状态", u"交易金额/元",
                              u'抽佣比例', u"抽佣金额/元")
                for index, value in enumerate(head_remit):
                    ws.write(0, index, value)

                if res['records']:
                    for index, value in enumerate(res['records']):
                        ws.write(index+1, 0, value.get('shopname', ''))
                        ws.write(index+1, 1, value.get('actname', ''))
                        ws.write(index+1, 2, value.get('trade_time', ''))
                        ws.write(index+1, 3, value.get('syyn', 0))
                        ws.write(index+1, 4, re_trade_status(value.get('trade_status', 0)))
                        ws.write(index+1, 5, float('%.2f' % (value.get('trade_amount', 0) / 100.0)))
                        ws.write(index+1, 6, str(value.get('commi_rate', 0)) + '%')
                        ws.write(index+1, 7, float('%.2f' % (value.get('commi_amount', 0) / 100.0)))
                sio = StringIO.StringIO()
                wb.save(sio)
                #标题
                subject = unicode_to_utf8(actname)
                m = MailMessage(subject, 'service@qfpay.com', email, '')
                sio.seek(0)
                filename1 = '{}_抽佣明细.xls'.format(subject)
                m.append_data(sio.read(), attachname='=?utf-8?b?' + base64.b64encode(filename1) + '?=')
                sender = MailSender('smtp.exmail.qq.com', 'service@qfpay.com', 'Aa!@#$%^7')
                send_status = sender.send(m)
                if send_status:
                    log.info('send mail success, msg:mail to {}'.format(email))
                    return self.write(success({}))
                else:
                    log.info('send mail fail, msg:mail to {}'.format(email))
                    return self.write(error(QFRET.SERVERERR, respmsg=u"服务错误"))

            else:
                start = page * pagesize
                end = page * pagesize + pagesize
                res['records'] = res['records'][start: end]
                return self.write(success(data=res))
        except:
            log.warn('error :%s' % traceback.format_exc())
            return self.write(error(QFRET.SERVERERR, respmsg=u"服务错误"))
