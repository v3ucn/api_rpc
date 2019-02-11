# coding:utf-8

import copy
import random
import json
import time
import config
import logging
import traceback

from concurrent import futures
from util import get_app_info

from runtime import redis_pool
from excepts import ParamError
from base import UserUtil, UserBase
from constants import (
    DATE_FMT, MCHNT_STATUS_FREE, DATETIME_FMT,
    MulType
)

from utils.decorator import check
from utils.valid import is_valid_int
from utils.payinfo import adjust_payinfo_ex
from utils.base import BaseHandler
from utils.qdconf_api import get_qd_conf_value_ex, get_qd_conf_value
from utils.date_api import str_to_tstamp
from utils.funcs import data_funcs
from utils.tools import get_value, get_qudaoinfo, apcli_ex
from utils.language_api import get_constant

from decorator import check_login, raise_excp, login_or_ip
from notify.base import SpecialDefine

from qfcommon.server.client import ThriftClient
from qfcommon.web.validator import Field, T_REG, T_INT
from qfcommon.base.qfresponse import success
from qfcommon.base.dbpool import get_connection
from qfcommon.base.tools import thrift_callex
from qfcommon.qfpay.apolloclient import Apollo
from qfcommon.thriftclient.data_activiquer import activiquer
from qfcommon.thriftclient.qudao import QudaoServer

log = logging.getLogger()


class Info(UserBase):
    '''
    获取用户信息
    '''
    def _get_modules(self, userid):
        # 分组
        modules = [
            {'module': 'member', 'name': '会员功能','services': []},
            {'module': 'special', 'name': '营销功能','services': []},
            {'module': 'diancan', 'name': '智慧餐厅','services': []},
            {'module': 'default', 'name': '其他功能','services': []},
        ]
        return self.get_user_modules(
            pos='all',
            addon=['module', 'note', 'recharge_link'],
            modules=modules
        )

    @check_login
    @raise_excp('获取用户信息失败')
    def GET(self):
        userid = self.user.userid
        ret = {}

        # 获取九宫格模块
        ret['modules'] = self._get_modules(userid)

        # 是否允许余额
        ret['balance_enable'] = int('balance' in self._user_service)

        # 用户基础信息
        userinfo = Apollo(config.APOLLO_SERVERS).user_by_id(userid)

        # 线下店铺信息
        user_ext = apcli_ex('getUserExt', int(userid))

        ret.update(UserUtil.ret_userinfo(userinfo, user_ext))

        # 获取审核信息
        ret.update(self.get_audit_info())

        return self.write(success(ret))

class PayInfo(BaseHandler):

    @login_or_ip
    @raise_excp('获取商户付费情况失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        try:
            userid = self.user.ses['userid']
            groupid = self.get_groupid()
        except:
            userid = d.get('userid')
            groupid = self.get_groupid(userid=userid)
        if not userid or not is_valid_int(userid):
            raise ParamError('商户ID不能为空')

        service_code = d.get('service_code') or d.get('code') or 'card_actv'
        goods_code = d.get('goods_code')

        mchnt_info = adjust_payinfo_ex(
                userid, goods_code, service_code, groupid=groupid)
        mchnt_info['now'] = time.strftime(DATETIME_FMT)

        # 登录状态时, 返回会员数
        if self._ck_mode == 'sid':
            with get_connection('qf_mchnt') as db:
                mchnt_info['member_num'] = db.select_one('member',
                    where={'userid': int(userid)}, fields='count(*) as num')['num']

        # 是否是直营商户
        mchnt_info['is_qfgroup'] = int(groupid in config.QF_GROUPIDS)

        return self.write(success(mchnt_info))

class Stats(BaseHandler):
    '''
    获取init接口的统计信息
    '''
    def _trans_input(self):
        r = {}
        r['userid'] = int(self.user.ses.get('userid', ''))

        # 商户付费情况
        r['mchnt_info'] = UserUtil.get_recharge_info(r['userid'], self.get_groupid())
        return r

    def _modules_note(self, d):
        def is_create_actv(userid):
            '''是否创建过活动'''
            if not userid: return False
            key = '__mchnt_api_is_create_actv__'
            if redis_pool.sismember(key, userid):
                return True
            flag = None
            # 会员集点活动
            with get_connection('qf_mchnt') as db:
                flag = db.select_one('card_actv', where={'userid': int(userid)}, fields='id')
            if flag:
                redis_pool.sadd(key, userid)
                return True
            # 会员通知
            with get_connection('qf_mchnt') as db:
                flag = db.select_one('member_actv', where={'userid': int(userid)}, fields='id')
            if flag:
                redis_pool.sadd(key, userid)
                return True
            # 红包活动
            with get_connection('qf_marketing') as db:
                flag= db.select_one('activity', where={'mchnt_id': str(userid)}, fields='id')
            if flag:
                redis_pool.sadd(key, userid)
                return True
            return False

        mchnt = d['mchnt_info']
        title, link = '', ''
        # 新用户
        if not mchnt['status']:
            title = '回头客少？好近会员帮你'
            link  = config.OPEN_SERVICE_LINK
        # 付费和体验用户
        else:
            # 若付费已经过期
            if mchnt['overdue']:
                title = '服务到期,去续费' if not mchnt.get('num') else '%s个会员等待服务,去续费'%mchnt['num']
                link  = config.OPEN_SERVICE_LINK
            # 若付费未过期
            else:
                if mchnt['left_day'] <= 5:
                    tip = ('体验{day}到期，去开通' if mchnt['status'] == MCHNT_STATUS_FREE
                            else '服务{day}到期,去续费')
                    title = tip.format(day='%s天后'%mchnt['left_day'] if mchnt['left_day'] else '今日')
                    link  = config.OPEN_SERVICE_LINK
                elif is_create_actv(d['userid']):
                    num = 0
                    with get_connection('qf_mchnt') as db:
                        td = str_to_tstamp(time.strftime(DATE_FMT), DATE_FMT)
                        where = {'userid': d['userid'], 'ctime': ('<', td), 'last_txdtm': ('>', td)}
                        num = db.select_one('member', where=where, fields='count(1) as num')['num']
                    title = '今日回头客%s人'%num if num else ''
                    link = ''

        return {'member': {'title': title, 'link': link}}

    def _stats(self, d):
        def _get_coupon_stats():
            '''红包活动(使用红包的数量)'''
            num = 0
            with get_connection('qf_marketing') as db:
                where = {'use_mchnt_id': str(d['userid']), 'create_time': ('>', td), 'type': ('in', (1, 2, 3))}
                fields = 'count(1) as num, type'
                records = db.select('record', where=where, fields=fields, other='group by type') or []
                nums = {i['type']:i['num'] for i in records}
                num = max(nums.get(1, 0)-nums.get(2, 0)-nums.get(3, 0), 0)
            return {'num': num} if num else None

        def _get_member_stats():
            '''会员管理(新增会员数)'''
            num = 0
            with get_connection('qf_mchnt') as db:
                where = {'userid': d['userid'], 'ctime': ('>', td)}
                fields = 'count(1) as num'
                num = db.select_one('member', where= where, fields= fields)['num']
            return {'num': num} if num else None

        def _get_tx_stats():
            '''数据魔方 (今日交易金额)'''
            amt = 0
            with get_connection('qf_mchnt') as db:
                where = {'userid': d['userid'], 'ctime': ('>', td)}
                fields = 'sum(txamt) as amt'
                amt = db.select_one('member', where= where, fields= fields)['amt']
                amt = int(amt or 0)
            return {'amt': '{amt:.{width}f}'.format(amt=amt/100.0, width=2 if amt%100 else 0)} if amt else None

        def _get_card_stats():
            '''会员集点 (今日集点数)'''
            num = 0
            with get_connection('qf_mchnt') as db:
                where = {'userid': d['userid'], 'ctime': ('>', td)}
                fields = 'sum(pts) as num, type'
                records = db.select('pt_record', where= where, fields= fields, other= 'group by type') or []
                nums = {i['type']:i['num'] for i in records}
                num = max(nums.get(1, 0) - nums.get(2, 0), 0)
            return {'num': num} if num else None

        td = str_to_tstamp(time.strftime(DATE_FMT), DATE_FMT)
        funcs = {
            'HJ0009': _get_coupon_stats,
            'HJ0011': _get_member_stats,
            'HJ0014': _get_tx_stats,
            'HJ0016': _get_card_stats,
        }

        # 获取会员功能服务列表
        services = filter(lambda x: x.get('module')=='member', config.SYSTEM_SERVICES)
        services = {i['code']:i for i in services }

        # 付费过期, 未付费
        if d['mchnt_info']['overdue'] == 1 or not d['mchnt_info']['status']:
            return {k:v.get('note', '') for k,v in services.iteritems()}
        else:
            r = {}
            for k,v in services.iteritems():
                if not v.get('stats_note'):
                    r[k] = v.get('note') or ''
                else:
                    stats  = funcs[k]()
                    if not stats:
                        r[k] = v.get('note', '')
                    else:
                        r[k] = v['stats_note'].format(**stats)
        return r

    @check_login
    @raise_excp('获取统计信息失败')
    def GET(self):
        d = self._trans_input()

        # 模块提示信息
        modules = self._modules_note(d)

        # 九宫格模块统计信息
        services = self._stats(d)

        return self.write(success({
            'modules': modules,
            'services': services,
            'mchnt_info': d['mchnt_info'],
        }))

class HomePage(UserBase):
    '''
    商户首页
    '''

    def get_services(self):
        '''获取用户首页功能模块'''
        ret = []
        services = self.get_user_services(
            pos='home_page',
            addon=['recharge_link', 'tip'],
            limit=getattr(config, 'HOME_PAGE_LIMIT', 8),
        )

        # 按权重排序
        services.sort(key=lambda x: x.get('weight', 0), reverse=True)

        # 调整输出
        fields = ['code', 'name', 'link', 'icon', 'tip']
        for i in services:
            ret.append({
                field:i.get(field, '') for field in fields
                    if field != 'tip' or i.get(field)
            })
        return ret

    _base_err = '获取首页数据失败'

    @check('login')
    def GET(self):
        userid = self.user.userid
        groupid = self.get_groupid()
        ret = {}

        # 获取商户付费情况
        ret['mchnt_info'] = UserUtil.get_recharge_info(userid, groupid)

        # 获取功能模块
        ret['services'] = self.get_services()

        # 获取审核信息
        ret.update(self.get_audit_info())

        # 是否允许余额
        ret['balance_enable'] = int('balance' in self._user_service)

        # 是否是直营
        ret['is_qfgroup'] = int(self.get_groupid() in config.QF_GROUPIDS)

        return success(ret)

class Service(UserBase):
    '''
    商户功能模块
    '''

    _base_err = '获取功能模块失败'

    @check('login')
    def GET(self):
        # 商户功能模块
        modules = self.get_user_modules(
            pos='all',
            addon=['module', 'recharge_link', 'tip'],
            fields=['code', 'name', 'link', 'icon', 'tip'],
        )

        return success({'modules' : modules})

# 当前统计
func_names = getattr(config, 'DATA_FUNCS', data_funcs.keys())

class Data(UserBase):
    '''
    商户今日数据
    '''

    def _get_panel(self, funcname):
        '''获取面板'''
        try:
            if funcname in data_funcs:
                userid = self.user.userid
                sesid = self.user.ses._sesid
                return data_funcs[funcname](
                    userid, sesid=sesid, version=self.version,
                    platform=self.platform)
        except:
            log.warn(traceback.format_exc())

    _base_err = '获取数据失败'

    @check('login')
    def GET(self):
        # 如果是大商户或者操作员, 暂不展示
        user_cate = self.get_user_cate()
        if user_cate in ('bigmerchant', 'opuser'):
            return success({'panels': []})

        # 版本号
        ua = self.req.environ.get('HTTP_USER_AGENT','')
        self.version, self.platform = get_app_info(ua)

        # 根据渠道获取面板数据
        default_func_names = getattr(config,
                'DATA_FUNCS', data_funcs.keys())
        func_names = get_qd_conf_value_ex(
            mode= 'data_func_names', key= 'ext',
            groupid= self.get_groupid(),
            default= default_func_names)

        funcs = get_value(func_names, self.platform, self.version)

        panels = []
        if funcs:
            with futures.ThreadPoolExecutor(10) as executor:
                for panel in executor.map(
                        self._get_panel, funcs):
                    if panel:
                        panels += (panel
                                if isinstance(panel, MulType)
                                else [panel])
            panels.sort(key = lambda d: d.get('create_time'), reverse=True)
        return success({'panels' : panels})


class Advice(UserBase):
    '''
    好近建议
    '''

    # mode模式
    # random: 随机返回好近建议
    # normal: 正常返回好近建议
    MODE_PATTERN = r'^(normal|random)$'

    _validator_fields = [
        Field('mode', T_REG, match=MODE_PATTERN, default='random'),
        Field('index', T_INT, default=0),
    ]

    def eval_advice(self, datas_from, data):
        ret = []
        default = config.DEFAULT_ADVICE
        fields = ['title', 'color', 'desc', 'link', 'button_desc']
        for index, advice in enumerate(config.ADVICES):
            if advice.get('from') != datas_from:
                continue

            try:
                if eval(advice.get('limit', 'True'), {'data' : data}):
                    result = {i : advice.get(i, default.get(i, '')).format(**data)
                              for i in fields}
                    result['index'] = index
                    ret.append(result)
                    self._result[index] = result
            except:
                pass

        return ret

    def _datas(self, userid):
        '''从数据组拉取数据'''
        datas = {}
        try:
            datas = json.loads(thrift_callex(config.DATAS_SERVERS, activiquer,
                                  'activiq', 'advice', str(userid)))[0]
            log.debug('datas:%s' % datas)
            for i in ('newc_7d_rank_p', 'activec_30d_rank_p', 'lossc_60d_rank_p'):
                if i in datas:
                    datas[i] *= 100
        except:
            pass
            #log.debug(traceback.format_exc())

        return self.eval_advice('datas', datas)

    def _vip(self, userid):
        '''获取商户充值信息'''
        mchnt_info = adjust_payinfo_ex(userid,
                service_code='card_actv', groupid=self.get_groupid())
        log.debug('mchnt_info:%s' % mchnt_info)
        return self.eval_advice('vip', mchnt_info)

    def _sale(self, userid):
        '''特卖'''
        sales, today = [], time.strftime(DATE_FMT)
        where = {
            'audit_status' : ('in', (SpecialDefine.AUDIT_STATUS_PLACED,
                                     SpecialDefine.AUDIT_STATUS_SUCCESS)),
            'status' : ('in', (SpecialDefine.STATUS_PLACED,
                               SpecialDefine.STATUS_NORMAL,
                               SpecialDefine.STATUS_TEST)),
            'redeem_start_date' : ('<=', today),
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

        ret = []
        for sale in sales:
            # 购买数量
            sale['total_count'] = sale['daily_quantity'] or sale['quantity'] # 总数量
            sale['quantity_p'] = sale['total_count'] * 100 / sale['quantity'] # 百分比

            ret.extend(self.eval_advice('sales', sale))
        return ret

    def get_advice_seqs(self):
        advice_num = len(config.ADVICES)
        mode = self.validator.data['mode']
        seqs = get_qd_conf_value(
                mode='advice_sequence', key='service',
                groupid=self.get_groupid(), default=range(advice_num))
        advice_num = len(seqs)
        if mode == 'random':
            random.shuffle(seqs)
        elif mode == 'normal':
            index = (self.validator.data['index'] % advice_num) + 1
            seqs = seqs[index:] + seqs[:index]

        return seqs

    _base_err = '获取建议失败'

    @check(['validator', 'login'])
    def GET(self):
        # 如果是大商户或者操作员, 暂不展示
        user_cate = self.get_user_cate()
        if user_cate in ('bigmerchant', 'opuser'):
            return success({})

        self._runned_funcs = set()
        self._result = {}

        userid = int(self.user.userid)

        advice = {}
        seqs = self.get_advice_seqs()
        log.debug(seqs)
        for index in seqs:
            advice_conf = config.ADVICES[index]
            func_name = '_'+advice_conf.get('from', '')
            if func_name not in self._runned_funcs:
                func = getattr(self, func_name, None)
                if callable(func):
                    func(userid)
                self._runned_funcs.add(func_name)

            if index in self._result:
                advice = self._result[index]
                break

        return success(advice)


class Menu(UserBase):
    '''
     获取用户我的菜单列表
    '''

    # mode模式
    # main: 主菜单
    # settings: 设置项的菜单

    _base_err = '获取菜单失败'

    def get_slsm_info(self, userid):
        try:
            client = ThriftClient(config.QUDAO_SERVERS, QudaoServer, framed=True)
            mchnts = client.mchnt_get([userid, ])

            if not mchnts:
                return None

            slsm_info = apcli_ex('findUserByid', mchnts[0].slsm_uid)
            if slsm_info:
                return slsm_info.__dict__
        except:
            log.warn(traceback.format_exc())

        return None


    @check('login')
    def GET(self):
        mode = self.req.input().get('mode')
        if mode not in ('main', 'settings'):
            mode = 'main'


        # 版本号, 平台
        version, platform = get_app_info(
            self.req.environ.get('HTTP_USER_AGENT','')
        )
        platform = platform or 'ios'
        prefix = platform + ('' if mode == 'main' else '_'+mode)

        # 用户角色
        user_cate = self.get_user_cate()

        # 用户groupid
        groupid = self.get_groupid()

        # 用户信息
        userinfo = {}
        user = apcli_ex('findUserByid', int(self.user.userid))
        if user:
            userinfo = user.__dict__
            userinfo['userid'] = userinfo['uid']

        # 菜单配置
        menus= get_qd_conf_value_ex(
            mode=prefix+'_menu', key='service',
            groupid=groupid) or []
        menus = copy.deepcopy(menus)

        language = self.get_language()
        # 根据条件配置
        ret_menus = []
        for group in menus:
            t = []
            for menu in group['menu']:
                # 操作员管理不展示
                if (menu['tag'] == 'operator' and
                    user_cate == 'opuser'):
                    continue

                # 根据角色控制展示
                cate_control = menu.pop('cate_control', None)
                if (cate_control is not None and
                    user_cate not in cate_control):
                    continue

                # 根据版本号控制
                app_control = menu.pop('app_control', None)
                if app_control is None:
                    tmp_menu = menu
                elif (app_control and
                    get_value(app_control, platform, version)):
                    tmp_menu = {k: get_value(v, platform, version)
                            for k, v in menu.iteritems()}
                else:
                    continue

                # 如果需要展示联系业务员
                if menu['tag'] == 'contact_salesman':
                    slsm_info = self.get_slsm_info(int(self.user.userid))
                    if not slsm_info:
                        continue

                    tmp_menu['content'] = slsm_info['telephone'] or slsm_info['mobile']
                    if not tmp_menu['content']:
                        continue


                tmp_menu['link'] = str(tmp_menu['link']).format(**userinfo)

                # 語言控制
                if 'title' in tmp_menu:
                    tmp_menu['title'] = get_constant(
                        tmp_menu['title'], language)

                t.append(tmp_menu)

            if t:
                ret_menus.append({'menu': t})

        # 能否修改基本信息
        # 国家不是中国的, 暂不支持修改
        qdinfo = get_qudaoinfo(groupid)
        support_cates = getattr(
            config, 'EDIT_INFO_CATES',
            ['bigmerchant', 'merchant', 'submerchant']
        )
        if qdinfo['country'] != "CN" or user_cate not in support_cates:
            edit_info = 0

        else:
            edit_info = get_qd_conf_value(
                mode=platform+'_edit_info', key='service',
                groupid=groupid, default=1
            )

        return success({
            'menus': ret_menus,
            'edit_info': edit_info
        })


class Tabs(BaseHandler):
    '''
     获取客户端tabs
    '''

    _base_err = '获取tabs失败'

    @check('login')
    def GET(self):
        groupid = self.get_groupid()
        version, platform = get_app_info(
            self.req.environ.get('HTTP_USER_AGENT',''))
        platform = platform or 'ios'

        # tabs配置
        menus= get_qd_conf_value(
            mode=platform+'_tabs', key='service',
            groupid=groupid) or []
        menus = copy.deepcopy(menus)

        language = self.get_language()
        for menu in menus:
            # 語言控制
            if 'name' in menu:
                menu['name'] = get_constant(menu['name'], language)

        return self.write(success({
            'tabs': menus,
        }))




