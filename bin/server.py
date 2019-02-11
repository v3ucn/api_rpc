# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import os
import sys
HOME = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(os.path.join(os.path.dirname(HOME), 'conf'))

from gevent import monkey
monkey.patch_all()

from qfcommon.base import logger,loader
if __name__ == '__main__':
    loader.loadconf_argv(HOME)
else:
    loader.loadconf(HOME)

import config
import urls

# 导入服务日志
if config.LOGFILE:
    log = logger.install(config.LOGFILE)
else:
    log = logger.install('stdout')

from qfcommon.web import core
from qfcommon.web import runner

if getattr(config, 'REDIS_LOG', True):
    from qfcommon.base.redispool import patch
    patch()

# 导入WEB URLS
config.URLS = urls.urls

app = core.WebApplication(config)

if __name__ == '__main__':
    # 导入自定义服务端口
    if len(sys.argv) > 2:
        config.PORT = int(sys.argv[2])
    runner.run_simple(app, host=config.HOST, port=config.PORT)

