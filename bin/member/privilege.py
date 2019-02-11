# coding=utf-8

import time
import config
import logging

from excepts import ParamError
from utils.base import BaseHandler
from utils.tools import getid, remove_emoji, str_len
from utils.qdconf_api import get_qd_conf_value
from decorator import check_login, raise_excp, with_validator
from utils.decorator import check
from base import MemDefine

from qfcommon.base.qfresponse import success
from qfcommon.base.dbpool import get_connection
from qfcommon.web.validator import Field, T_STR, T_INT, T_REG

log = logging.getLogger()

class Display(BaseHandler):
    '''
    特权预览页
    '''

    _validator_fields = [
        Field('mode', T_STR, default='rule'),
    ]

    @check_login
    @with_validator()
    def GET(self):
        privilege = config.ACTV_TIPS.get('privilege') or {}
        mode = self.validator.data['mode']

        display = privilege.get(mode) or []

        return self.write(success(display))

class Create(BaseHandler):
    '''
    创建特权活动
    '''

    _validator_fields = [
        Field('content', T_STR, is_null = False),
    ]

    @check(['login', 'check_perm'])
    @with_validator()
    @raise_excp('创建活动失败')
    def POST(self):
        userid = int(self.user.userid)
        actv = None
        with get_connection('qf_mchnt') as db:
            actv = db.select_one(
                    'member_actv',
                    where= {
                        'userid': userid,
                        'type': MemDefine.ACTV_TYPE_PRIVI
                    })
        if actv:
            raise ParamError('已经创建过特权活动了.')


        content = self.validator.data['content']
        content = remove_emoji(content)
        if str_len(content) > 80:
            raise ParamError('活动内容不超过80字')

        now = int(time.time())
        data = {}
        data['id'] = getid()
        data['title'] = ''
        data['content'] = content
        data['userid'] = userid
        data['status'] = MemDefine.ACTV_STATUS_ON
        data['ctime'] = data['utime'] =  now
        data['start_time'] = now
        data['expire_time'] = now + 20 * 365 * 24 * 3600
        data['type'] = MemDefine.ACTV_TYPE_PRIVI
        with get_connection('qf_mchnt') as db:
            db.insert('member_actv', data)

        return self.write(success({}))


class Index(BaseHandler):
    '''
    会员特权首页信息
    '''

    @check_login
    @raise_excp('获取数据失败')
    def GET(self):
        userid = int(self.user.userid)

        actv = None
        with get_connection('qf_mchnt') as db:
            actv = db.select_one(
                    'member_actv',
                    where= {
                        'userid': userid,
                        'type': MemDefine.ACTV_TYPE_PRIVI
                    },
                    fields= 'id, status, content')
        if actv:
            actv['promotion_url'] = get_qd_conf_value(userid,
                    'privilege', groupid=self.get_groupid())


        return self.write(success({'privilege': actv or {}}))

class Manage(BaseHandler):
    '''
    操作会员特权
    '''
    STATUS_PATTERN = r'(1|3)'

    _validator_fields = [
        Field('id', T_INT, isnull=False),
        Field('status', T_REG, match=STATUS_PATTERN, default=None),
        Field('content', T_STR, default=''),
    ]

    def edit(self):
        data = self.validator.data

        values= {i:data[i] for i in ('status', 'content') if data[i]}
        if values:
            with get_connection('qf_mchnt') as db:
                db.update(
                        'member_actv',
                        values= values,
                        where= {
                            'userid': int(self.user.userid),
                            'id': int(self.validator.data['id'])
                        })

        return self.write(success({}))

    @check(['login', 'check_perm'])
    @with_validator()
    @raise_excp('操作特权失败')
    def POST(self, mode):
        func = getattr(self, mode, None)
        if callable(func):
            return func()
