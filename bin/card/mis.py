# encoding:utf-8

import traceback
import time
import logging
log = logging.getLogger()

from constants import DATE_FMT, DATETIME_FMT
from util import remove_emoji, str_len

from decorator import check_ip, raise_excp
from excepts import DBError, ParamError

from utils.valid import is_valid_date
from utils.date_api import str_to_tstamp

from qfcommon.web.core import Handler
from qfcommon.base.dbpool import get_connection_exception
from qfcommon.base.qfresponse import success

class Change(Handler):
    '''
    修改会员集点活动
    集点条件obtain_amt, 商品名goods_name,
    商品价格goods_amt, 有效期expire_time*(延长)
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        r['id'] = d.get('id') or ''

        # actv info
        with get_connection_exception('qf_mchnt') as db:
            info = db.select_one('card_actv', where={'id': r['id']})
        if not info:
            raise ParamError('活动不存在')
        info['start_time'] = int(time.mktime(info['start_time'].timetuple()))
        expire_time = d.get('expire_time', info['expire_time'])
        if not is_valid_date(expire_time):
            raise ParamError('活动截止时间格式不对')
        r['expire_time'] = str_to_tstamp(expire_time, DATE_FMT) + 86399
        #if r['expire_time'] < info['start_time']:
            #raise ParamError('修改活动的截止日期不能小于起始日期')

        r['obtain_amt'] = int(d.get('obtain_amt', info['obtain_amt']) or 0)
        if r['obtain_amt'] <= 0:
            raise ParamError('集点条件大于0元')

        r['goods_name'] = remove_emoji(d.get('goods_name', info['goods_name']))
        if not 1 <= str_len(r['goods_name']) <= 8:
            raise ParamError('商品名长度是1至8位')

        r['goods_amt'] = int(d.get('goods_amt', info['goods_amt']) or 0)
        if r['goods_amt'] <= 0:
            raise ParamError('商品价格应大于0')

        r['content'] = (info['content'] or '') + (d.get('content') or '%smis修改'%(time.strftime(DATETIME_FMT)))

        return r

    def _change(self, d):
        try:
            now = int(time.time())
            fields = ['obtain_amt', 'goods_name', 'goods_amt', 'expire_time']
            udata = {i:d[i]  for i in fields}
            udata['utime'] = now
            with get_connection_exception('qf_mchnt') as db:
                db.update('card_actv', udata, {'id': d['id']})
        except:
            log.warn('extend activity error: %s' % traceback.format_exc())
            raise DBError('修改失败')

    @check_ip()
    @raise_excp('修改活动失败')
    def POST(self):
        log.debug('yyk')
        data = self._trans_input()
        # change
        self._change(data)

        return self.write(success({'id': data['id']}))
