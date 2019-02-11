# coding:utf-8

import logging
import time
import json

from excepts import ParamError, UserError
from constants import DATETIME_FMT, SIMPLE_MOBILE_PATTERN, PASSWORD_PATTERN
from base import UserUtil
from runtime import hids

from util import enc_password, check_password
from utils.decorator import check
from utils.base import BaseHandler
from utils.language_api import get_constant
from utils.valid import is_valid_int
from utils.tools import unicode_to_utf8, kick_user

from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.base.qfresponse import success, error, QFRET
from qfcommon.web.validator import Field, T_STR, T_REG, T_INT

log = logging.getLogger()


class List(BaseHandler):
    '''
    获取操作员列表
    '''


    _validator_fields = [
        Field('mode', T_STR, default='page'),
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
        Field('status', T_STR),
        Field('userid', T_STR, default=None),
    ]

    _base_err = '获取操作员列表失败'

    def get_mchnt_info(self, userid):
        mchnt_info = {}
        with get_connection('qf_core') as db:
            mchnt_info = db.select_one(
                    table = 'auth_user',
                    fields = ['state as status', 'mobile'],
                    where = {'id': userid})

        if not mchnt_info:
            raise ParamError('主账号信息不存在')

        opname = get_constant('门店主账户', self.get_language())
        mchnt_info['opuid'] = '0000'
        mchnt_info['opname'] = opname

        return mchnt_info

    @check(['login', 'validator'])
    def GET(self):
        ret = {}
        tmp = []
        d = self.validator.data

        mode = d['mode']
        page = d['page']
        pagesize = d['pagesize']
        userid = d.get('userid')

        if not userid:
            userid = int(self.user.userid)
        else:
            try:
                userid = int(userid)
            except:
                raise ParamError('userid参数错误')

        log.debug('userid={}'.format(userid))


        # 判断分页显示或者全部显示，根据status筛选
        other = 'order by create_time desc limit {limit} offset {offset}'.format(
                limit = pagesize, offset = pagesize * page)
        if mode == 'all':
            other = 'order by create_time desc'
            tmp.append(self.get_mchnt_info(userid))

        where = {'userid': userid}
        if d['status'] != '':
            where['status'] = int(d['status'])

        # 获取商户下操作员
        opusers = []
        with get_connection('qf_core') as db:
            opusers = db.select(
                    table = 'opuser',
                    where = where,
                    fields = 'opname, mobile, status, opuid, perms',
                    other = other)

        for opuser in opusers:
            source_opuid = opuser['opuid']
            prefix = (4 - len(str(source_opuid))) * '0'
            opuser['opuid'] = prefix + str(source_opuid)
            try:
                perms = json.loads(opuser['perms'])
                refund = perms.get('refund', 0)
            except:
                refund = 0
            opuser['refund'] = refund
            tmp.append(opuser)
        ret['opusers'] = tmp

        return self.write(success(ret))


class Info(BaseHandler):
    '''
    获取用户信息
    '''

    _base_err = '获取用户信息失败'
    @check('login')
    def GET(self):
        d = self.req.input()
        userid = int(self.user.userid)

        # opuid设置
        opuid = d.get('opuid', '')
        if not opuid:
            raise ParamError('获取收银员编号错误')

        # 查询操作员信息
        opuser_info = {}
        with get_connection('qf_core') as db:
            opuser_info = db.select_one(
                    table = 'opuser',
                    where = {
                        'userid': userid,
                        'opuid': int(opuid),
                        },
                    fields = 'opname, status, mobile')
        if not opuser_info:
            raise ParamError('未能查询到该收银员')

        opuser_info['opuid'] = opuid

        return self.write(success(opuser_info))


class Change(BaseHandler):
    '''
    修改用户信息
    '''

    _validator_fields = [
        Field('opuid', T_INT, isnull=False),
        Field('mobile', T_REG, match=SIMPLE_MOBILE_PATTERN, default=None),
        Field('password', T_REG, match=PASSWORD_PATTERN, default=None),
        Field('opname', T_STR, default=None),
        Field('status', T_INT, default=None),
    ]

    _base_err = '修改收银员失败'

    @check('validator')
    def POST(self):
        userid = self.get_userid_login_or_ip()

        d = self.validator.data
        update_data = {}
        if d['status'] not in [None, 0, 1]:
            raise ParamError('状态非法')


        with get_connection_exception('qf_core') as db:
            opuser = db.select_one(
                table= 'opuser',
                where= {'userid': int(userid), 'opuid': int(d['opuid'])}
            ) or {}
        if not opuser:
            raise UserError('操作员不存在')

        fields = ['mobile', 'status', 'opname', 'password']
        for field in fields:
            if d[field] is not None:
                if field == 'password':
                    if not check_password(d['password'], opuser['password']):
                        update_data[field] = enc_password(d['password'])
                elif d[field] != unicode_to_utf8(opuser[field]):
                    update_data[field] = d[field]

        if not update_data:
            return success({})

        with get_connection('qf_core') as db:
            db.update('opuser', update_data,
                where={'userid': userid, 'opuid': int(d['opuid'])})

        # 如果更新了状态，则剔除操作员
        if update_data.get('status')  == 0 or update_data.get('password'):
            kick_user(userid, int(d['opuid']), mode='opuser')

        return success({})


class Opuid(BaseHandler):
    '''
    获取opuid
    '''
    _base_err = '获取新的收银员编号失败'
    @check('login')
    def GET(self):
        ret = {}

        max_opuid = UserUtil.get_max_opuid(int(self.user.userid))
        if not max_opuid:
            ret['opuid'] = '0001'
            return self.write(success(ret))

        # 新的uid增长一
        max_opuid = max_opuid + 1
        prefix = (4 - len(str(max_opuid))) * '0'
        ret['opuid'] = prefix + str(max_opuid)

        return self.write(success(ret))

class AddOpuser(BaseHandler):
    '''
    添加操作员
    '''
    _validator_fields = [
        Field('opuid', T_STR),
        Field('mobile', T_REG, match=SIMPLE_MOBILE_PATTERN),
        Field('password', T_REG, match=PASSWORD_PATTERN, isnull=False),
        Field('opname', T_STR, isnull=False),
    ]

    def check_opuid(self, userid):
        '''
        检查传入的opuid是否已经存在
        '''
        data = self.validator.data

        if not is_valid_int(data['opuid'] or 0):
            raise ParamError('opuid 错误')

        max_opuid = int(UserUtil.get_max_opuid(int(userid)) or 0)
        if not data['opuid']:
            opuid = max_opuid + 1

        else:
            if max_opuid and int(data['opuid']) <= max_opuid:
                raise ParamError('收银员编号:{}已经存在'.format(data['opuid']))
            opuid = int(data['opuid'])

        return opuid

    _base_err = '添加收银员失败'

    @check('validator')
    def POST(self):
        userid = self.get_userid_login_or_ip()

        now = time.strftime(DATETIME_FMT)
        d = self.validator.data
        opuid = int(self.check_opuid(int(userid)))

        data = {}
        data['opname'] = d['opname']
        data['mobile'] = d['mobile']
        data['opuid'] =  int(opuid)
        data['userid'] = userid
        data['password'] = enc_password(d['password'])
        data['status'] = 1
        data['create_time'] = now
        data['last_login'] = now
        data['modify_time'] = now

        with get_connection_exception('qf_core') as db:
            db.insert('opuser', data)

        return self.write(success({'opuid': opuid}))


class DebitBackList(BaseHandler):
    '''
    获取操作员退款权限列表
    '''

    _validator_fields = [
        Field('mode', T_STR, default='page'),
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
        Field('userid', T_STR, default=None),
    ]

    _base_err = '获取操作员列表失败'

    @check(['login', 'validator'])
    def GET(self):
        ret = {}
        tmp = []
        d = self.validator.data

        mode = d['mode']
        page = d['page']
        pagesize = d['pagesize']
        userid = d.get('userid')

        if not userid:
            userid = int(self.user.userid)
        else:
            userid_tuple = hids.decode(userid)
            if userid_tuple:
                userid = userid_tuple[0]
            else:
                if not userid.isdigit():
                    raise ParamError('用户编号不存在')

        log.debug('decoded userid={}'.format(userid))

        # 操作员登录，返回空列表
        if 'opuid' in self.user.ses:
            ret['opusers'] = []
            return self.write(success(ret))

        # 判断分页显示或者全部显示，根据status筛选
        other = 'order by create_time desc limit {limit} offset {offset}'.format(
                limit=pagesize, offset=pagesize * page)
        if mode == 'all':
            other = 'order by create_time desc'

        where = {'userid': userid}

        # 获取商户下操作员
        opusers = []
        with get_connection('qf_core') as db:
            opusers = db.select(
                    table='opuser',
                    where=where,
                    fields='opname, opuid, perms',
                    other=other)
        for opuser in opusers:
            result = {}
            source_opuid = opuser['opuid']
            prefix = (4 - len(str(source_opuid))) * '0'
            result['opuid'] = prefix + str(source_opuid)
            try:
                perms = json.loads(opuser['perms'])
                refund = perms.get('refund', 0)
            except:
                refund = 0
            result['refund'] = refund
            result['opname'] = opuser['opname']
            tmp.append(result)
        ret['opusers'] = tmp

        return self.write(success(ret))


class ChangePerm(BaseHandler):
    '''
    修改用户权限
    '''

    _validator_fields = [
        Field('opuid', T_INT, isnull=False),
        Field('type', T_STR, default=None),
        Field('status', T_INT, default=None),
    ]

    _base_err = '修改用户权限失败'

    @check(['login', 'validator'])
    def POST(self):
        '''
        修改用户权限
        '''
        d = self.validator.data
        userid = int(self.user.userid)

        if not d['opuid']:
            raise ParamError('参数错误')
        if d['status'] is not None and d['status'] not in [0, 1]:
            raise ParamError('状态非法')
        if d['type'] is None:
            type = 'refund'
        else:
            type = d['type']

        # 更新数据
        where = {
            'userid': userid,
            'opuid': int(d['opuid'])
        }
        perms = {}
        with get_connection('qf_core') as db:
            opuser = db.select_one(
                    table='opuser', fields=['perms'], where=where)
            if opuser:
                try:
                    perms = json.loads(opuser['perms'])
                    perms[type] = d['status']
                except:
                    perms[type] = d['status']
                finally:
                    db.update('opuser', {'perms': json.dumps(perms)}, where)

                return self.write(success({}))
            else:
                return self.write(error(QFRET.PARAMERR, respmsg='操作员信息不存在'))


class UserPerm(BaseHandler):
    '''
    获取用户权限
    '''

    _base_err = '获取用户权限失败'

    @check(['login'])
    def GET(self):

        perms_list = {'refund': 1, 'coupon': 1, 'member': 1,
                      'sales': 1, 'prepaid': 1, 'card': 1, 'shop_notice': 1}
        userid = int(self.user.userid)
        opuid = int(self.user.ses.get('opuid', 0))
        if opuid:
            where = {
                'userid': userid,
                'opuid': opuid
            }
            with get_connection('qf_core') as db:
                opuser = db.select_one(
                        table='opuser', fields=['perms'], where=where)
                if opuser:
                    try:
                        perms = json.loads(opuser['perms'])
                        for i in perms_list.keys():
                            perms_list[i] = perms.get(i, 0)
                    except:
                        keys = perms_list.keys()
                        perms_list = dict.fromkeys(keys, 0)

                    return self.write(success(perms_list))
                else:
                    return self.write(error(QFRET.PARAMERR, respmsg='操作员信息不存在'))
        else:
            return self.write(success(perms_list))
