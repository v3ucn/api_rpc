# coding:utf-8

import re
import json
import logging
import traceback
import time
import config

from util import (
    get_app_info, get_services, check_user, hids, get_qd_conf_value
)

from utils.valid import is_valid_int
from utils.base import BaseHandler
from utils.tools import (
    apcli_ex, check_smscode, get_linkids, get_userinfo,
    has_set_mpwd, unicode_to_utf8, kick_user
)
from utils.decorator import check
from util import enc_password, check_password
from user.base import UserUtil,UserDefine

from excepts import ParamError, SessionError, DBError, ThirdError
from decorator import (
    check_login, openid_or_login, raise_excp, with_validator,required_slsm_enable
)
from constants import (
    MOBILE_PATTERN, CERT_NAME, OLD2NEW_CERT, EMAIL_PATTERN, DATETIME_FMT
)
from runtime import apcli, ms_redis_pool

from qfcommon.base.dbpool import with_database, get_connection, get_connection_exception
from qfcommon.thriftclient.apollo.ttypes import User, UserBrief, UserExt, ApolloException
from qfcommon.qfpay.apolloclient import Apollo
from qfcommon.base.qfresponse import QFRET,error,success

from qfcommon.thriftclient.audit import AuditServer
from qfcommon.thriftclient.audit.ttypes import Audit
from qfcommon.server.client import ThriftClient

from qfcommon.web.validator import Field, T_REG, T_INT, T_STR, T_FLOAT
from qfcommon.qfpay.defines import (
    QF_USTATE_NEW, QF_USTATE_VARIFIED, QF_USTATE_ACTIVE,
    QF_USTATE_OK, QF_USTATE_DULL
)

# 允许登录的状态
ALLOW_STATE = (QF_USTATE_NEW, QF_USTATE_VARIFIED, QF_USTATE_ACTIVE,
               QF_USTATE_OK, QF_USTATE_DULL)


log = logging.getLogger()



class GetStatus(BaseHandler):
    '''
    获取审核状态
    '''

    @check_login
    @required_slsm_enable
    @raise_excp('获取商户审核状态信息出错')
    def GET(self):
        d = self.req.input()
        userid = d.get('userid', '').strip()
        type = d.get('type', '').strip()

        if (not userid) or (not type):
            raise ParamError('参数错误')

        with get_connection('qf_core') as db:
            opuser = db.select_one(
                table='profile',
                where={
                    'userid': int(userid)
                },
                fields='user_type')

        if not opuser:
            raise ParamError('该商户非法')

        with get_connection('qf_audit') as db:
            rows_type = db.select(
                table='salesman_event',
                where={'userid': ('in', [int(userid)])},
                fields='userid,state,ext,memo,type', other='order by ctime desc')

        with get_connection('qf_audit') as db:
            rows = db.select(
                table='salesman_event',
                where={'userid': ('in', [int(userid)]), 'type': ('in', [int(type)])},
                fields='userid,state')

        with get_connection('qf_audit') as db:
            rows_old = db.select(
                table='salesman_event',
                where={'userid': ('in', [int(userid)])},
                fields='userid,state')

        ret = {}

        if not rows_old:
            ret['oldusertype'] = opuser['user_type']
        else:
            ext_public = json.loads(rows_type[0]['ext'])
            ret['oldusertype'] = ext_public.get("oldusertype",opuser['user_type'])

        resperr = ''

        ret['usertype'] = opuser['user_type']

        enuserid = UserUtil.o2_syssn_encode(
            int(userid) +
            UserDefine.o2_BASE_MAGIC_NUMBER
        )

        ret['enuserid'] = enuserid

        if rows:
            ret['status'] = rows[0]['state']
        else:
            ret['status'] = 0


        return self.write(success(ret, resperr))


class Upload(BaseHandler):
    '''
    上传活动图片接口
    '''

    @check_login
    @required_slsm_enable
    @raise_excp('上传用户图片出错')
    def POST(self):
        d = self.req.input()
        userid = d.get('userid', '').strip()
        type = d.get('type', '').strip()
        name = d.get('name', '').strip()
        licensenumber = d.get('licensenumber', '').strip()
        licensephoto = d.get('licensephoto', '').strip()
        checkstand = d.get('checkstand', '').strip()
        checkin = d.get('checkin', '').strip()
        sls_uid = int(self.user.userid)
        usertype = d.get('usertype', '').strip()
        nickname = d.get('nickname', '').strip()
        shopphoto = d.get('shopphoto', '').strip()


        if not usertype:
            usertype = 0

        if (not userid) or (not type) or (not name) or (not licensenumber) or \
           (not licensephoto) or (not checkstand) or (not checkin) or (not nickname) or (not shopphoto):
            raise ParamError('参数错误')

        client = ThriftClient(config.AUDIT_SERVERS, AuditServer)
        client.raise_except = True

        ret = client.call('update_sales',userid=int(userid),type=int(type),name=str(name)
                          ,licensenumber=str(licensenumber),licensephoto=str(licensephoto),checkstand=str(checkstand)
                          ,checkin=str(checkin),sls_uid = sls_uid,nickname = nickname,usertype = int(usertype),shopphoto = shopphoto)


        if ret == 0:
            return self.write(success({}))
        else:
            raise ParamError('覆盖商户信息失败')


class Return(BaseHandler):
    '''
    返回数据接口
    '''

    @check_login
    @required_slsm_enable
    @raise_excp('返回商户数据出错')
    def GET(self):
        d = self.req.input()
        userid = d.get('userid', '').strip()
        type = d.get('type', '').strip()

        if (not userid) or (not type):
            raise ParamError('参数错误')


        with get_connection('qf_core') as db:
            opuser = db.select_one(
                table='profile',
                where={
                    'userid': int(userid)
                },
                fields='user_type,nickname')

        with get_connection('qf_mis') as db:
            opimg = db.select_one(
                table='mis_upgrade_voucher',
                where={
                    'user_id': int(userid),
                    'name': 'shopphoto'
                },
                fields='imgname')

        if not opuser:
            raise ParamError('该商户类型非法')

        rows_type = []
        with get_connection('qf_audit') as db:
            rows = db.select(
                table='salesman_event',
                where={'userid': ('in', [int(userid)])},
                fields='userid,state,ext,memo,type',other='order by ctime desc')
        for rows_l in xrange(len(rows)):
            if rows[rows_l]['type'] == int(type):
                rows_type = rows[rows_l]

        ret = {}
        resperr = ''

        def replace_img(imgname):
            ret = 'http://pic.qfpay.com/userprofile/%d/%d/%s' % (int(userid) / 10000,int(userid),imgname)
            return ret

        if rows and rows_type:
            ext_public = json.loads(rows[0]['ext'])
            ext = json.loads(rows_type['ext'])
            ret['name'] = ext_public.get("name",'')
            ret['licensenumber'] = ext_public.get("licensenumber", '')
            oldtype = opuser.get("user_type", '')
            ret['usertype'] = oldtype
            ret['nickname'] = ext_public.get("nickname",opuser.get("nickname", ''))
            ret['licensephoto'] = {}
            ret['licensephoto']['img'] = ext_public.get("licensephoto",'')
            ret['licensephoto']['url'] = replace_img(ext_public.get("licensephoto",''))

            ret['shopphoto'] = {}
            ret['shopphoto']['img'] = ext_public.get("shopphoto",opimg.get('imgname'))
            ret['shopphoto']['url'] = replace_img(ext_public.get("shopphoto",opimg.get('imgname')))

            ret['checkstand'] = {}
            ret['checkstand']['img'] = ext.get("checkstand",'')
            ret['checkstand']['url'] = replace_img(ext.get("checkstand",''))

            ret['checkin'] = {}
            ret['checkin']['img'] = ext.get("checkin",'')
            ret['checkin']['url'] = replace_img(ext.get("checkin",''))
            ret['memo'] = rows_type['memo']
            ret['status'] = rows_type['state']
        else:
            raise ParamError('该审核数据不存在')

        return self.write(success(ret, resperr))


