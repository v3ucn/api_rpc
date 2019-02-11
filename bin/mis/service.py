# encoding:utf-8

import logging
import types
log = logging.getLogger()

from decorator import check_ip, raise_excp
from util import BaseHandler, get_services
from config import SYSTEM_SERVICES, MODULES, DEFAULT_SERVICES

from qfcommon.base.qfresponse import success


class List(BaseHandler):
    '''
    获取所有的服务
    '''

    @check_ip()
    @raise_excp('获取所有服务列表失败')
    def GET(self):
        all_services = get_services('999999', 'ios')
        fields = ['name', 'code', 'icon']

        return self.write(success([{field : service[field] for field in fields}
                                    for service in all_services]))

class ServiceList(BaseHandler):
    '''
    获取服务分类和服务列表
    '''

    def _get_module(self, module):
        if isinstance(module, types.DictType):
            versions = module.keys()
            if len(versions) > 1: versions.remove('default')
            version = sorted(versions)[-1]
            log.info('latest version=%s' % version)
            return module[version]
        else:
            return module

    @check_ip()
    @raise_excp('获取所有服务列表失败')
    def GET(self):
        ret = {}
        module_services = {}
        module_services['all'] = []
        module_map = {}
        module_map['all'] = '全部'
        default_services = {}
        for module in MODULES:
            module_code = module.get('module', '')
            module_name = module.get('name', '')
            module_services[module_code] = []
            module_map[module_code] = module_name

        for service in SYSTEM_SERVICES:
            if not service.get('status', 0) == 1:
                continue
            service_dict = {}
            service_dict['code'] = code = service.get('code', '')
            service_dict['name'] = name = service.get('name', '')
            if code in DEFAULT_SERVICES:
                default_services[code] = name
            module = service.get('module', 'default')
            module_code = self._get_module(module)
            module_services[module_code].append(service_dict)
            ret['module_map'] = module_map
            ret['module_services'] = module_services
            ret['default_services'] = default_services

        return self.write(success(ret))


