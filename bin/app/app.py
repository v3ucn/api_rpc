# encoding:utf-8

import config
import logging
log = logging.getLogger()

from util import get_app_info, get_services
from qfcommon.base.qfresponse import success
from qfcommon.web import core

class Init(core.Handler):
    '''
    app初始化接口
    返回值:
        system_services: 好近商户版九宫格
        zip_conf: 离线包
        activity_conf: 红包活动配置
        pay_sequence: 支付序列
    '''

    def GET(self):
        log.debug('user_agent:%s' % self.req.environ.get('HTTP_USER_AGENT',''))
        version, platform = get_app_info(self.req.environ.get('HTTP_USER_AGENT',''))
        log.info('version:%s  platform:%s' % (version, platform))

        # 获取服务列表
        # 早期版本没有带version
        default = 'middle' if 'version' in self.req.input() else 'origin'
        services = get_services(version, platform, default)
        services.sort(key=lambda x: x.get('weight', 0), reverse=True)

        return self.write(success({
            'system_services' : services,
            'zip_conf' : config.ZIP_CONFIG,
            'activity_conf' : config.ACT_CONF,
            'pay_sequence' : config.PAY_SEQUENCE,
            }))
