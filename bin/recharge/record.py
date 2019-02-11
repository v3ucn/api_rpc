# encoding:utf-8

import logging
log = logging.getLogger()

from constants import DATETIME_FMT
from base import ORDER_STATUS
from decorator import check_login, raise_excp

from utils.valid import is_valid_int
from utils.date_api import tstamp_to_str

from excepts import ParamError

from qfcommon.base.dbpool import get_connection_exception
from qfcommon.web.core import Handler
from qfcommon.base.qfresponse import success

class List(Handler):
    '''
    购买记录 - (未支付,支付成功,支付失败)
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        r['userid'] = int(self.user.ses.get('userid', ''))

        # 活动状态
        r['status'] = int(d.get('status') or 0)
        if r['status'] not in ORDER_STATUS.values():
            raise ParamError('查询状态不存在')

        # 分页信息
        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息不正确')
        r['offset'], r['limit'] = int(page) * int(pagesize), int(pagesize)

        return r

    @check_login
    @raise_excp('免费体验失败')
    def GET(self):
        d = self._trans_input()

        with get_connection_exception('qf_mchnt') as db:
            fields = ['id', 'goods_name', 'txamt', 'total_amt', 'ctime', 'status']
            where = {'userid': d['userid']}
            if d['status']:
                where['status'] = d['status']
            other = 'order by ctime desc limit %s offset %s' % (d['limit'], d['offset'])
            r = db.select('paying_order', where=where, other=other, fields=fields) or []

        for i in r:
            i['ctime'] = tstamp_to_str(i['ctime'], DATETIME_FMT)

        return self.write(success({'records': r}))
