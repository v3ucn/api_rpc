# encoding:utf-8

import traceback
import datetime
import time
import sys
import logging
import config

from decorator import raise_excp
from constants import DATETIME_FMT
from excepts import ParamError
from base import RechargeUtil, PROMO_CODE_TYPE, PROMO_CODE_STATUS

from utils.base import BaseHandler
from utils.date_api import str_to_tstamp, future
from utils.tools import getid
from utils.decorator import check

from qfcommon.base.dbpool import get_connection_exception, DBFunc, get_connection
from qfcommon.base.qfresponse import success

log = logging.getLogger()
paying_goods = config.PAYING_GOODS


class PriceList(BaseHandler):
    '''
    推广价格列表
    '''

    @raise_excp('获取推广活动价格列表失败')
    def GET(self):
        goods_code = self.req.input().get('goods_code', 'card')
        goods = RechargeUtil.get_goods(goods_code)

        r = [{'code': i['code'], 'goods_name':i['goods_name']}
                for i in goods['price']]

        return self.write(success({'prices': r}))


class Recharge(BaseHandler):
    '''
    推广码充值
    '''

    def update_mchnt(self, userid, goods_codes, months):
        st = datetime.date.today()
        with get_connection('qf_mchnt') as db:
            # 获取当前的信息
            infos = db.select(
                table = 'recharge',
                where = {
                    'goods_code': ('in', goods_codes),
                    'userid': userid
                }
            ) or []
            infos = {i['goods_code']:i for i in infos}

            for code in goods_codes:
                try:
                    if code in infos:
                        exptm = infos[code]['expire_time']
                        if str(exptm) > time.strftime(DATETIME_FMT):
                            st = datetime.date(year=exptm.year, month=exptm.month, day=exptm.day)
                    end = str_to_tstamp(
                        str(future(st, months = months)) + ' 23:59:59',
                        DATETIME_FMT
                    )

                    if code in infos:
                        db.update(
                            table = 'recharge',
                            values = {
                                'expire_time' : end,
                                'utime' : int(time.time()),
                                'status' : 2
                            },
                            where = {
                                'userid' : userid,
                                'goods_code' : code
                            }
                        )
                    else:
                        db.insert(
                            table = 'recharge',
                            values = {
                                'id' : getid(),
                                'userid' : userid,
                                'goods_code' : code,
                                'status' : 2,
                                'expire_time' : end,
                                'ctime' : int(time.time()),
                                'utime' : int(time.time()),
                            }
                        )
                except:
                    log.warn('更新消费者有效期失败:%s' % traceback.format_exc())


    def GET(self):
        return self.POST()

    _base_err = '充值失败'

    @check()
    def POST(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}

        # 查找商户信息
        username = d.get('mobile') or d.get('username', '')
        user = None
        with get_connection('qf_core') as db:
            if '@' in username:
                where = {'auth_user.email': username}
            else:
                where = {'auth_user.username': username}
            user = db.select_join_one(
                table1 = 'auth_user', table2= 'profile',
                on = {
                    'auth_user.id': 'profile.userid'
                },
                where = where,
                fields = (
                    'auth_user.id as userid, auth_user.state, '
                    'auth_user.password, profile.groupid'
                )
            )
        if not user:
            raise ParamError('商户不存在')


        # 开通的服务
        goods_codes = set([])
        # 0渠道 1直营
        code_idx = int(user['groupid'] in config.QF_GROUPIDS)
        for i in d.get('goods_code', 'card').split(','):
            if i in config.PROMO_GOODS_DICT:
                goods_codes.add(config.PROMO_GOODS_DICT[i][code_idx])
        if not goods_codes:
            raise ParamError('未选中服务')

        # 月份
        price_code = d.get('price_code', 'month')
        months = int(price_code.strip('month') or 1)

        # 推广码
        promo_code = d.get('promo_code', '')
        with get_connection('qf_mchnt') as db:
            promo_info = db.select_join_one(
                'promo_code', 'promo',
                'inner', on = {'promo.userid': 'promo_code.userid'},
                where = {'promo_code.code': promo_code},
                fields = (
                    'promo.userid, promo.balance, promo.status as pstatus, '
                    'promo.num, promo_code.type, promo_code.use_limit, '
                    'promo_code.use_num, promo_code.status as pcstatus'
                )
            ) or {}
        if not promo_info:
            raise ParamError('推广码不存在')
        if promo_info['pcstatus'] != PROMO_CODE_STATUS['normal']:
            raise ParamError('该推广码状态不对')
        if promo_info['pstatus'] != PROMO_CODE_STATUS['normal']:
            raise ParamError('该渠道状态不对')
        if promo_info['type'] == PROMO_CODE_TYPE['balance']:
            raise ParamError('暂不支持余额码')

        # 检查使用次数
        if (
            (promo_info['use_num'] + len(goods_codes)) >
            (promo_info['use_limit'] or sys.maxint)
           ):
            raise ParamError('你的开通码已经超过使用次数')

        now = int(time.time())
        # 更新promo
        with get_connection_exception('qf_mchnt') as db:
            db.update(
                table = 'promo',
                values = {
                    'num' : DBFunc('num - %d' %  len(goods_codes)),
                    'utime' : now,
                },
                where = {'userid' : promo_info['userid']}
            )

        # 更新promo_code
        with get_connection_exception('qf_mchnt') as db:
            db.update(
                table = 'promo_code',
                values = {
                    'use_num': DBFunc('use_num + %s' % len(goods_codes)),
                    'utime': now
                },
                where = {'code': promo_code}
            )

        # 插入promo_record
        with get_connection_exception('qf_mchnt') as db:
            db.insert(
                table = 'promo_record',
                values = {
                    'id' : getid(),
                    'userid' : promo_info['userid'],
                    'mchntid' : user['userid'],
                    'promo_code' : promo_code,
                    'service_code' : price_code,
                    'amt' : 0,
                    'promo_amt' : 0,
                    'content' : d.get('goods_code', 'card'),
                    'ctime': now,
                }
            )

        # 更新商户付费信息
        self.update_mchnt(user['userid'], goods_codes, months)

        return success({})
