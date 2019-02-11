# encoding:utf-8

import config
import logging
log = logging.getLogger()

from utils.base import BaseHandler

from qfcommon.base.qfresponse import success

class Conf(BaseHandler):
    '''
    app初始化接口
    返回值:
        zip_conf: 离线包
        activity_conf: 红包活动配置
        pay_sequence: 支付序列
    '''

    def GET(self):
        log.debug('user_agent:%s' % self.req.environ.get('HTTP_USER_AGENT',''))
        app_conf = config.APP_CONFIG
        ret = {k:getattr(config, v) for k,v in app_conf.iteritems() if hasattr(config, v)}
        return self.write(success(ret))
