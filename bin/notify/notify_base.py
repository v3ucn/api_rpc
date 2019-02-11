# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import json
import time, datetime
import config
import logging
log = logging.getLogger()

from util import get_app_info
from decorator import check_login
from runtime import redis_pool

from base import SpecialDefine
from qfcommon.web import core
from qfcommon.base.dbpool import get_connection_exception, get_connection
from qfcommon.qfpay.qfresponse import success
import util

class TypeList(core.Handler):
    '''会员通知展示列表'''

    def get_coupon_use_info(self, userid):
        _result = dict(max_count=config.NOTIFY_MAX_COUNT_MONTH, used_count=0, used_coupon=False)
        with get_connection_exception('qf_marketing') as conn:
            # 检测是否已经创建过
            where = dict(mchnt_id=userid,
                         type=3,
            )
            result = conn.select_one('activity', where=where)
            if result is not None:
                _result['used_coupon'] = True

            # 检测已经使用次数
            timeline = datetime.date.today()
            timeline = timeline.replace(day=1)
            where = dict(mchnt_id=userid,
                         type=3,
                         status=('in', [1,2]),
                         start_time=('>=', util.convert_date_to_timestamp(timeline)))
            result = conn.select_one('activity', where=where, fields="count(1) as used_count")
            if result is not None:
                _result['used_count']  = result['used_count']

        return _result

    def get_promotion_use_info(self, userid):
        database = 'qf_mchnt'
        table = 'member_actv'

        _result = dict(max_count=config.NOTIFY_MAX_COUNT_MONTH, used_count=0, used_coupon=False)
        with get_connection_exception(database) as conn:
            # 检测是否已经创建过
            where = dict(userid=userid)
            result = conn.select_one(table, where=where)
            if result is not None:
                _result['used_coupon'] = True
                pass

        # 检测已经使用次数
        SEND_KEY = '_mchnt_api_promote_%s_' % time.strftime('%Y%m')
        _result['used_count'] = int(redis_pool.hget(SEND_KEY, userid) or 0)

        return _result

    def get_sale_use_info(self, userid):
        month_1st = datetime.date.today().replace(day=1).strftime('%Y-%m-%d')
        r = 0
        with get_connection('qmm_wx') as db:
            where = {
                'qf_uid' : int(userid),
                'redeem_start_date' : ('>=', month_1st),
                'atype' : 1,
                'status' : ('in', (SpecialDefine.STATUS_PLACED, SpecialDefine.STATUS_NORMAL,
                                   SpecialDefine.STATUS_TEST)),
                'audit_status' : ('!=', SpecialDefine.AUDIT_STATUS_FAILED)
            }
            r = db.select_one('market_activity', where=where, fields='count(1) as num')['num']

        try:
            max_count = int(redis_pool.hget('mchnt_api_notify_conf', 'sale_max'))
        except:
            max_count = config.NOTIFY_MAX_COUNT_MONTH

        return {'max_count':max_count, 'used_count':r, 'used_sale':bool(r)}


    def get_type_list(self, userid, app_version):
        result = {
            'coupon' : {
                'name' : '红包通知',
                'descr' : '想要回头客不断?快给会员发个红包吧!',
                'id' : 1,
                'icon_url' : 'http://near.m1img.com/op_upload/117/147036543546.png',
            },
            'promotion' : {
                'name' : '活动通知',
                'descr' : '优惠活动能直接发给会员啦~快试试!',
                'id' : 2,
                'icon_url' : 'http://near.m1img.com/op_upload/117/147036541399.png',
            },
            'sale' : {
                'name' : '特卖通知',
                'descr' : '发布一款特卖商品，让会员抢购吧!',
                'id' : 3,
                'icon_url' : 'http://near.m1img.com/op_upload/137/14722050228.png',
            }
        }

        # 获取展示列表
        typelist = ['coupon', 'promotion']
        try:
            alltypes = redis_pool.hgetall('_mchnt_api_type_list_')
            log.debug(alltypes)
            max_v = '000000'
            for k,v in alltypes.iteritems():
                if k > max_v and k <= app_version:
                    typelist, max_v = json.loads(v), k
        except:
            typelist = ['coupon', 'promotion']
        log.debug(typelist)
        # 获取数据
        rtypes = []
        for _type in typelist:
            if _type not in result: continue

            func = getattr(self, 'get_{}_use_info'.format(_type), None)
            if callable(func):
                result[_type].update(func(userid))
                rtypes.append(result[_type])

        return rtypes

    @check_login
    def GET(self):
        userid = self.user.ses.get('userid')

        # 获取版本号
        req = self.req
        log.debug('user_agent:%s' % req.environ.get('HTTP_USER_AGENT',''))
        version, platform = get_app_info(req.environ.get('HTTP_USER_AGENT',''))
        log.info('version:%s  platform:%s' % (version, platform))

        type_list = self.get_type_list(userid, version)
        return self.write(success(type_list))


class Summary(core.Handler):
    @classmethod
    def get_summary(cls, user_id):
        retval = dict(member_count=0,
                      inactive_member_count=0,
                      active_member_count=0,
                      period="30天")

        current_timestamp = time.time()
        basetime = current_timestamp - (30*24*3600)

        with get_connection_exception('qf_mchnt') as conn:
            result = conn.select_one('member', where=dict(userid=user_id), fields='count(1) as member_count')
            if result['member_count']:
                retval['member_count'] = result['member_count']
                pass


            args = dict(userid=user_id, last_txdtm=(">", basetime))
            result = conn.select_one('member', where=args, fields='count(1) as active_member_count')

            if result['active_member_count']:
                retval['active_member_count'] = result['active_member_count']
                pass

            retval['inactive_member_count'] = max(0, retval['member_count'] - retval['active_member_count'])
            pass

        return retval

    @check_login
    def GET(self):

        user_id = self.user.ses.get('userid')
        result = self.get_summary(user_id)

        return self.write(success(result))
    pass

