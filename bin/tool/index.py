#coding:utf-8

import config
import logging

from runtime import hids
from utils.base import BaseHandler
from utils.decorator import with_customer

from qfcommon.qfpay.qfresponse import QFRET, success, error

log = logging.getLogger()


class Test(BaseHandler):

    def POST(self):
        d = self.req.input()
        log.debug('input:%s' % d)


class Ping(BaseHandler):

    def GET(self):
        return self.write('ok')

    def POST(self):
        return self.write('ok')


class CheckCsid(BaseHandler):

    @with_customer
    def GET(self):
        if self.customer.is_login():
            return self.write(success({
                'customer_id': hids.encode(self.customer.customer_id),
                'csid' : self.get_cookie('csid')
            }))
        else:
            # 如果校验失败， 删除cookie
            del_domains = getattr(config, 'DEL_DOMAINS', ['o.qfpay.com'])
            for domain in del_domains:
                self.resp.del_cookie(
                    'csid', domain = domain
                )
            return self.write(error(QFRET.SESSIONERR))


class SetCookie(BaseHandler):

    def GET(self):
        data = self.req.input()
        print self.req.cookie
        if data:
            for k, v in data.iteritems():
                if v:
                    self.set_cookie(k, v, **config.COOKIE_CONFIG)
                else:
                    self.resp.del_cookie(k, domain=config.COOKIE_CONFIG.get('domain'))

        return ''


class IsBaiPai(BaseHandler):
    '''是否是白牌商户'''

    def GET(self):
        params = self.req.input()

        groupid = None

        if 'userid' in params:
            groupid = self.get_groupid(userid=params['userid'])

        elif 'enuserid' in params:
            userid = hids.decode(params['enuserid'])
            if userid:
                groupid = self.get_groupid(userid=userid)

        else:
            if self.check_login():
                groupid = self.get_groupid()

        return self.write(success({
            'is_baipai': self.is_baipai(groupid)
        }))
