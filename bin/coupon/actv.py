# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import traceback
import time
import config
import json

import logging
log = logging.getLogger()

from constants import DATETIME_FMT, DATE_FMT
from util import (
    str_len, rule_json2dic, json2dic, remove_emoji,
    covert, prelogin_lock, postlogin_lock
)

from utils.valid import is_valid_date
from utils.date_api import str_to_tstamp, str_diffdays
from utils.payinfo import get_payinfo_ex
from utils.qdconf_api import get_qd_conf_value
from utils.base import BaseHandler
from utils.decorator import check
from runtime import apcli

from decorator import (
    check_login, check_login_ex, raise_excp, with_validator
)
from excepts import (
    MchntException,  ParamError, ThirdError, DBError
)
from base import (
    CouponUtil, ACTIVITY_SRC, ACTIVITY_TYPE_PAYMENT,
    COUPON_RULE_STATUS_CLOSE, ACTIVITY_SHARE_TYPE_COUPON
)
from qfcommon.thriftclient.qf_marketing import QFMarketing
from qfcommon.thriftclient.qf_marketing.ttypes import (
    CouponRule, CouponRuleProfile, Activity, ActivityExt, Share
)
from qfcommon.web.validator import Field, T_INT, T_REG
from qfcommon.base.dbpool import get_connection, DBFunc
from qfcommon.base.qfresponse import success
from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.apollo.ttypes import UserBrief
from qfcommon.thriftclient.actv_template import tempalService

class Template(BaseHandler):
    '''
    获取红包活动模板
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        r['userid'] = self.user.ses.get('userid', '')

        # 红包金额类型 1:固定金额 2:随机金额
        r['mode'] = int(d.get('mode') or 1)
        if r['mode'] not in (1, 2):
            raise ParamError('参数错误')

        # 有效时间
        start_time, expire_time = d.get('start_time'), d.get('expire_time')
        if not all(map(is_valid_date, [start_time,expire_time])):
            raise ParamError('时间格式不对')
        # 红包截止日期
        if start_time > expire_time:
            raise ParamError('活动开始时间大于截止时间')
        r['diffdays'] = max(str_diffdays(start_time, expire_time), 1)

        return r

    def _template(self, d):
        # 获取模板信息
        tp = json.loads(thrift_callex(config.TEMPlATE_SERVERS, tempalService, 'tempal', str(d['userid'])))
        log.debug('template:%s' % tp)
        if not tp: return

        r = {}
        tp = tp[0]
        # 红包金额, 预算
        camt = tp.get('coupon_amt') or 0
        if not camt: return

        get_yuan = lambda x: (int(x) + 50) / 100 * 100
        # 每日红包数量
        daycnt = tp.get('day_get_cnt') or 1
        if d['mode'] == 1:
            r['amt_min'] = r['amt_max'] = camt
            r['num'] = int(d['diffdays'] * daycnt)
        else:
            vp = min(tp.get('var_p') or 50, 100)
            vpamt = int(camt * vp / 100.0)
            r['amt_min'], r['amt_max'] = camt-vpamt, camt+vpamt
            total_amt = max(int(d['diffdays'] * daycnt * (r['amt_min']+r['amt_max']) / 2.0), 100)
            r['total_amt'] = get_yuan(total_amt)

        # 红包领取条件
        r['obtain_limit_amt'] = get_yuan(max(tp.get('get_amt'), r['amt_max'], 100))

        # 使用门槛
        r['use_limit_amt'] = get_yuan(max(tp.get('use_amt'), r['amt_max'], 100))

        # 红包有效期
        r['coupon_lifetime'] = max(tp.get('vperiod') or 7, 1)
        r['coupon_offset'] =  0

        return r

    @check_login
    def GET(self):
        try:
            # 转化input参数
            d = self._trans_input()
            # 创建优惠劵
            r = self._template(d) or {}
            return self.write(success(r))
        except:
            log.warn('get activity template error: %s' % traceback.format_exc())
            return self.write(success({}))

class Create(BaseHandler):
    '''
    创建活动
    成功返回活动id
    '''

    _validator_fields = [
        Field('title', isnull=False),
        Field('obtain_limit_amt', T_INT, isnull=False),
        Field('use_limit_amt', T_INT, isnull=False),
        Field('coupon_lifetime', T_INT, isnull=False),
        Field('start_time', isnull=False),
        Field('expire_time', isnull=False),
    ]

    def _trans_input(self):
        data = {k:v.strip() for k, v in self.req.input().iteritems()}
        userid = int(self.user.userid)

        # 验证商户付费状态
        if getattr(config, 'COUPON_CHECK_PAYINFO', True):
            mchnt = get_payinfo_ex(userid, service_code='coupon',
                                   groupid=self.get_groupid())
            if not mchnt:
                raise ParamError('你的会员服务尚未开通，请联系业务员开通后再进行设置。')
            elif str(mchnt['expire_time']) <= time.strftime(DATETIME_FMT):
                raise ParamError('只有续费才能创建哦')

        fields = ('amt', 'num', 'obtain_limit_amt', 'use_limit_amt',
            'coupon_lifetime', 'amt_min', 'amt_max', 'total_amt')
        for i in fields:
            data[i] = int(data.get(i) or 0)

        # 去除表情符
        data['title'] = remove_emoji(data['title'])
        if not (1 <= str_len(data['title']) <= 12):
            raise ParamError('活动名称长度是1至12位')
        # 固定金额, 需要处理下
        if data['num']:
            data['total_amt'] = data['num'] * data['amt']
            data['amt_min'] = data['amt_max'] = data['amt']
        # 红包金额小于100
        if data['amt_max'] > 10000:
            raise ParamError('红包金额应小于100')
        # 红包最小金额小于最大金额
        if data['amt_min'] > data['amt_max']:
            raise ParamError('红包奖励最大金额应该大于最小金额')
        # 红包奖励金额
        if not data['amt_max']:
            raise ParamError('红包奖励金额应该大于0')
        # 红包预算
        if not (0 < data['total_amt'] < 1000000):
            raise ParamError('红包预算应该大于0小于10000元')
        # 使用金额和红包金额
        if data['use_limit_amt'] < data['amt_max']:
            raise ParamError('红包使用金额大于等于红包金额')
        # 有效时间
        if not all(map(is_valid_date, [data['start_time'],data['expire_time']])):
            raise ParamError('时间格式不对')
        # 红包有效期
        if data['coupon_lifetime'] <= 0:
            raise ParamError('优惠劵的有效时间大于0')
        # 红包截止日期
        if data['start_time'] > data['expire_time']:
            raise ParamError('活动开始时间大于截止时间')

        data['type'] = covert(data.get('type', ''), int, 20)
        data['coupon_offset'] = covert(data.get('coupon_offset', ''), int, 0)
        data['start_time'] = str_to_tstamp(data['start_time'], DATE_FMT)
        data['expire_time'] = str_to_tstamp(data['expire_time'], DATE_FMT) + (24*60*60-1)
        data['userid'] = str(userid)

        return data

    def _create_coupon(self, data):
        c = {}
        c['status'] = 2
        c['src'] = ACTIVITY_SRC
        c['mchnt_id'] = data['userid']
        c['title'] = data['title']
        c['amt_max'], c['amt_min'] = data['amt_max'], data['amt_min']
        c['start_time'], c['expire_time'] = data['start_time'], data['expire_time']
        c['use_rule'] = json.dumps([['amt', '>=', data['use_limit_amt']]])
        c['profile'] = CouponRuleProfile(**{
            'mchnt_limit' : 2,
            'effect_type' : 2,
            'effect_offset' : data['coupon_offset'],
            'effect_len' : data['coupon_lifetime']
        })

        try:
            coupon =  CouponRule(**c)
            cid = thrift_callex(config.QF_MARKETING_SERVERS, QFMarketing, 'coupon_rule_create', coupon)
        except:
            log.warn('create coupon error: %s' % traceback.format_exc())
            raise ThirdError('调用创建红包接口失败')

        return cid

    def _get_act_ext(self, data):
        user = None
        try:
            user = apcli('findUserBriefById', int(data['userid']))
        except:
            log.warn(traceback.format_exc())
        userinfo = (user or UserBrief()).__dict__
        share = Share()
        share.title = config.SHARE_ACT_DEFAULT_CONF['title'].format(**userinfo)
        share.desc  = config.SHARE_ACT_DEFAULT_CONF['desc']
        share.icon_url = config.SHARE_ACT_DEFAULT_CONF['icon_url']

        return ActivityExt(**{'share':share})

    def _create_activity(self, cid, data):
        try:
            a = {}
            a['status'] = 2
            a['src'] = ACTIVITY_SRC
            a['type'] = ACTIVITY_TYPE_PAYMENT
            a['mchnt_id'] = data['userid']
            a['total_amt'] = data['total_amt']
            a['xx_type'] = ACTIVITY_SHARE_TYPE_COUPON
            obtain_rule, share_rule = [], []
            # 消费返劵
            if data['type'] == 20:
                a['sponsor_xx_id'] = cid
                a['sponsor_award_num'] = 1
                obtain_rule = [["amt", ">=", data['obtain_limit_amt']], ["num_type", "=", 1], ["obtain_num", "<=", 1]]
            # 消费分享劵
            else:
                a['obtain_xx_id'] = a['sponsor_xx_id'] = cid
                a['sponsor_award_num'] = 1
                a['obtain_num'] = config.OBTAIN_NUM
                a['ext'] = self._get_act_ext(data)
                obtain_rule = [["amt", ">=", data['obtain_limit_amt']]]
                share_rule = [["amt", ">=", data['obtain_limit_amt']], ]
            a['title'] = data['title']
            a['start_time'], a['expire_time'] = data['start_time'], data['expire_time']
            a['rule'] = json.dumps({"obtain_rule": obtain_rule, 'share': share_rule})
            r = thrift_callex(config.QF_MARKETING_SERVERS, QFMarketing, 'activity_create', Activity(**a))
            return r
        except:
            log.warn('create activity error: %s' % traceback.format_exc())
            raise ThirdError('调用活动接口失败')

    @check_login_ex(prelogin_lock, postlogin_lock)
    @check(['check_perm'])
    @with_validator()
    @raise_excp('创建活动失败')
    def POST(self):
        # 转化input参数
        data = self._trans_input()
        # 创建优惠劵
        cid = self._create_coupon(data)
        # 创建活动
        aid = self._create_activity(cid, data)
        return self.write(success({'id':aid}))

class Info(BaseHandler):
    '''
    获取活动详细信息
    '''

    _validator_fields = [
        Field('id', T_INT, isnull=False),
    ]

    def get_info(self, mchnt_id):
        '''获取活动信息'''
        def _actinfo():
            r = None
            actid = self.validator.data['id']
            with get_connection('qf_marketing') as db:
                big_uid = self.get_big_uid(mchnt_id)
                userids = (mchnt_id, big_uid) if big_uid else (mchnt_id, )
                r = db.select_one(
                        table='activity',
                        where={
                            'id': actid,
                            'create_mchnt_id': ('in', userids),
                            'src': ACTIVITY_SRC,
                            'type': ACTIVITY_TYPE_PAYMENT
                        },
                        fields=[
                            'id', 'mchnt_id', 'type', 'title',
                            'total_amt', 'obtain_num', 'obtain_xx_id',
                            'status', 'used_amt', 'rule', 'sponsor_award_num',
                            'sponsor_xx_id', 'start_time', 'expire_time',
                            'create_time', 'create_mchnt_id'
                        ])
            if not r:
                raise ParamError('该活动不存在')

            r['type'] = 21 if r['obtain_xx_id'] else 20
            # 活动obtain_limit_amt
            if r['type'] == 20:
                rule = rule_json2dic(r.pop('rule', ''), 'obtain_rule')
                r['obtain_limit_amt'] = rule.get('amt', 0)
            else:
                rule = rule_json2dic(r.pop('rule', ''), 'share')
                r['obtain_limit_amt'] = rule.get('amt', 0)

            # 活动状态 1:进行中 2:已结束
            r['state'] = CouponUtil.get_actv_state(r)

            # 活动统计
            stat = CouponUtil.get_actv_stats(actid)
            r.update(stat)

            # 如果是消费分享劵会加上奖励的券
            if r['type'] == 21:
                r['obtain_num'] += r['award_num']
                r['obtain_amt'] += r['award_amt']

            # 消费者信息
            r['customer_num'], r['customer_info'] = CouponUtil.get_customer(actid)
            r['pv'] = CouponUtil.get_actv_pv(actid)

            # 大商户创建标记
            r['big_create'] = int(r['create_mchnt_id'] != str(mchnt_id))

            return r

        def _couponinfo(couponid):
            with get_connection('qf_marketing') as db:
                fields = ['id', 'title', 'amt_max', 'amt_min', 'status',
                    'start_time', 'expire_time', 'use_rule', 'profile']
                r = db.select_one('coupon_rule', where={'id':couponid}, fields=fields)
            # if coupon rule not exists
            if not r:
                raise ParamError('该活动规则不存在')

            use_rule, profile = r.pop('use_rule'), r.pop('profile')
            rule = rule_json2dic(use_rule, 'rule')
            profile = json2dic(profile)
            r.update({
                'use_limit_amt' : rule.get('amt', 0),
                'mchnt_limit' : profile.get('mchnt_limit', 1),
                'effect_offset' : profile.get('effect_offset', 1),
                'effect_type' : profile.get('effect_type', 1),
                'effect_len' : profile.get('effect_len', 7)
            })
            return r

        try:
            r = _actinfo()
            k = 'sponsor_coupon_info' if r['type'] == 20 else 'obtain_coupon_info'
            r[k] = _couponinfo(r['sponsor_xx_id'] or r['obtain_xx_id'])
            r['num'] = r['total_amt'] / max(r[k]['amt_min'], r[k]['amt_max'], 1)
            return r
        except MchntException:
            raise
        except:
            log.warn('query activity ifno error: %s' % traceback.format_exc())
            raise DBError('查询活动详细信息失败')

    @check_login
    @with_validator()
    @raise_excp('查询活动信息失败')
    def GET(self):
        userid = int(self.user.userid)

        # 获取活动信息
        r = self.get_info(userid)
        r['now'] = time.strftime(DATETIME_FMT)
        r['promotion_url'] = get_qd_conf_value(userid,
                'coupon', groupid=self.get_groupid())

        return self.write(success(r))


class List(BaseHandler):
    '''
    获取活动列表
    '''

    STATE_PATTERN = r'(1|2)'

    _validator_fields = [
        Field('state', T_REG, match=STATE_PATTERN, isnull=False),
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
    ]

    def get_big_actvids(self):
        big_uid = self.get_big_uid()
        if not big_uid:
            return []

        actvids = actvs = None
        userid = self.user.userid
        with get_connection('qf_marketing') as db:
            actvs = db.select_join(
                    table1= 'activity a', table2= 'activity_mchnt am',
                    on= {'a.id': 'am.activity_id'},
                    where= {
                        'a.create_mchnt_id': str(big_uid),
                        'a.type':  ACTIVITY_TYPE_PAYMENT,
                        'a.status': ('in', (1, 2)),
                        'a.mchnt_id': DBFunc('0 and locate(\'"{}"\', '
                                'am.mchnt_id_list)'.format(userid))
                    },
                    fields= 'a.id')
            actvids = [actv['id'] for actv in actvs ]

        self._bigids = actvids or []
        return actvids

    def get_actvs(self, userid):
        '''
        获取活动列表
        '''
        def get_where():
            now = int(time.time())

            big_actvids = self.get_big_actvids()
            where = '(create_mchnt_id={userid} {bigids}) '.format(
                    userid= userid,
                    bigids= ('' if not big_actvids else
                        ' or id in ({})'.format(
                            ','.join(str(int(i))for i in big_actvids))
                    ))
            where += ('and src="{src}" and type={type} '.format(
                    src= ACTIVITY_SRC, type= ACTIVITY_TYPE_PAYMENT))
            # 启用的
            if self.validator.data['state']== '1':
                where += ('and expire_time>={now} and status=2 and '
                          'used_amt<total_amt'.format(now=now))
            # 关闭的
            else:
                where += ('and ((expire_time<{now}) or (used_amt>=total_amt) '
                          'or (status=3))'.format(now=now))
            return where

        data =  self.validator.data
        actvs = None
        with get_connection('qf_marketing') as db:
            sql = ('select {fields} from activity where {where} '
                   'order by create_time desc limit {limit} '
                   'offset {offset}'.format(
                        fields=(
                            'id, mchnt_id, type, title, total_amt, '
                            'obtain_xx_id, obtain_num, sponsor_award_num, '
                            'sponsor_xx_id, rule, start_time, expire_time, '
                            'create_time, create_mchnt_id'
                        ),
                        where=get_where(),
                        limit=data['pagesize'],
                        offset=data['pagesize'] * data['page']
                       ))
            actvs =  db.query(sql)
        if not actvs:
            return []

        cids = {i['sponsor_xx_id'] or i['obtain_xx_id'] for i in actvs}
        coupons = {}
        if cids:
            if cids:
                cps = None
                with get_connection('qf_marketing') as db:
                    cps = db.select(
                            table= 'coupon_rule',
                            fields= 'id, amt_max, amt_min',
                            where = {'id': ('in', cids)})
                for cp in cps:
                    coupons[cp['id']] = {
                        'coupon_amt_max': cp['amt_max'],
                        'coupon_amt_min': cp['amt_min']
                    }

        # 获取统计信息
        actids = [i['id'] for i in actvs]
        stats = CouponUtil.get_actv_stats(actids)

        # 整理数据
        promotion_url = get_qd_conf_value(userid, 'coupon',
                                          groupid=self.get_groupid())
        for act in actvs:
            # 加入优惠劵信息
            act.update(coupons.get(act['sponsor_xx_id'] or act['obtain_xx_id']))
            # 活动rule
            act['num'] = act['total_amt'] / max(act['coupon_amt_min'], act['coupon_amt_max'], 1)

            # 活动统计
            act.update(stats.get(act['id']))
            # 活动类型
            act['type'] = 21 if act['obtain_xx_id'] else 20
            # 物料信息
            act['promotion_url'] = promotion_url

            # 活动obtain_limit_amt
            if act['type'] == 20:
                rule = rule_json2dic(act.pop('rule', ''), 'obtain_rule')
                act['obtain_limit_amt'] = rule.get('amt', 0)
            else:
                rule = rule_json2dic(act.pop('rule', ''), 'share')
                act['obtain_limit_amt'] = rule.get('amt', 0)
                act['obtain_num'] += act['award_num']
                act['obtain_amt'] += act['award_amt']

            # 大商户创建的标记
            act['big_create'] = int(act['create_mchnt_id'] != str(userid))

        return actvs

    def get_actv_num(self, userid):
        '''
        获取活动数量
        '''
        share_num = sponsor_num = 0
        with get_connection('qf_marketing') as db:
            nums = db.select(
                    'activity',
                    where={
                        'create_mchnt_id': userid,
                        'src': ACTIVITY_SRC,
                        'type': ACTIVITY_TYPE_PAYMENT
                    },
                    fields='obtain_xx_id , count(1) as num',
                    other='group by (obtain_xx_id > 0)')
            for num in nums:
                if num['obtain_xx_id'] > 0:
                    share_num = num['num']
                else:
                    sponsor_num = num['num']
        return share_num, sponsor_num

    @check_login
    @with_validator()
    @raise_excp('获取数据失败')
    def GET(self):
        userid = int(self.user.userid)

        # 获取活动列表
        actvs = self.get_actvs(userid)

        # 获取当前正在进行的活动
        share_num, sponsor_num = self.get_actv_num(userid)

        return self.write(success({
            'left_warn_day': 7,
            'activities': actvs,
            'now': time.strftime(DATETIME_FMT),
            'act_num': share_num + sponsor_num,
            'share_act_num' : share_num,
            'sponsor_act_num' : sponsor_num
        }))

class Change(BaseHandler):
    '''
    修改活动列表
    目前只允许关闭活动
    '''

    _validator_fields = [
        Field('id', T_INT, isnull=False),
    ]

    @check(['login', 'check_perm'])
    @with_validator()
    @raise_excp('修改活动失败')
    def POST(self):
        actv = None
        with get_connection('qf_marketing') as db:
            actv = db.select_one(
                    table= 'activity',
                    where= {
                        'id':self.validator.data['id'],
                         'src':ACTIVITY_SRC
                    },
                    fields= 'id, create_mchnt_id, status')
        if not actv:
            raise ParamError('活动不存在')

        if actv['create_mchnt_id'] != str(self.user.userid):
            if actv['create_mchnt_id'] == str(self.get_big_uid()):
                raise ParamError('此活动为总账户创建，你无法执行修改~')
            raise ParamError('暂无修改此活动的权限')

        if actv['status'] != COUPON_RULE_STATUS_CLOSE:
            try:
                act = Activity(id=actv['id'], status=COUPON_RULE_STATUS_CLOSE,
                               src=ACTIVITY_SRC)
                thrift_callex(config.QF_MARKETING_SERVERS, QFMarketing,
                              'activity_change', act)
            except:
                log.warn(traceback.format_exc())
                raise ThirdError('关闭活动失败')

        return self.write(success({}))


class Customer(BaseHandler):
    '''
    获取消费者详细信息
    '''

    _validator_fields = [
        Field('activity_id', T_INT, isnull=False),
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
    ]

    @check_login
    @with_validator()
    @raise_excp('查询活动消费者信息失败')
    def GET(self):
        userid = int(self.user.userid)
        data = self.validator.data
        actv = None
        with get_connection('qf_marketing') as db:
            big_uid = self.get_big_uid()
            userids = (userid, big_uid) if big_uid else (userid, )
            actv = db.select_one(
                    table= 'activity',
                    where= {
                        'create_mchnt_id': ('in', userids),
                        'id': data['activity_id'],
                        'src': ACTIVITY_SRC
                    },
                    fields= 'id')
        if not actv:
            raise ParamError('未查询到该活动')

        num, info =  CouponUtil.get_customer(
                actid=actv['id'],
                limit=data['pagesize'],
                offset=data['pagesize']*data['page'],
                raise_ex=True)

        return self.write(success({
                'customer_num': num,
                'customer_info': info}))
