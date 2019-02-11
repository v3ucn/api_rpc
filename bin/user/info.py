# coding:utf-8

import time
import logging
import config
import traceback

from runtime import hids
from excepts import DBError, ParamError

from utils.base import BaseHandler
from utils.tools import apcli_ex
from utils.decorator import check


from qfcommon.base.dbpool import get_connection
from qfcommon.base.qfresponse import success

log = logging.getLogger()

class BaseInfo(BaseHandler):
    '''获取用户信息

    通过userid和opuid获取相关信息

    params:
        userid: 商户userid(不传默认取登录userid)
        opuid: 操作元id(不传默认为主账号)
    '''

    _base_err = '获取信息失败'

    def set_user_linkids(self):
        link_ids = []
        try:
            relats = apcli_ex(
                'getUserRelation', int(self.user.userid),
                'merchant'
            ) or []
            link_ids = [i.userid for i in relats]

            self.user.ses.data['link_ids'] = link_ids
        except:
            log.warn(traceback.format_exc())

        return link_ids


    def check_relation(self, userid):
        ''' 检验传入userid和登录sessionid的userid的关系

        若相等, 则直接返回
        否则, 传入的userid必须是sessionid的userid的子商户
        '''
        if userid == int(self.user.userid):
            return

        link_ids = self.user.ses.data.get('link_ids', [])
        if userid in link_ids:
            return

        link_ids = self.set_user_linkids() or []
        if userid not in link_ids:
            raise DBError('身份错误')

    @check('login')
    def GET(self):
        params = self.req.input()

        userid = int(params.get('userid') or self.user.userid)
        opuid =  int(params.get('opuid') or 0)

        self.check_relation(userid)

        ret = {
            'shopname': '',
            'opname': ''
        }

        user = apcli_ex('findUserBriefById', int(userid))
        if user:
            ret['shopname'] = user.shopname

        if not opuid:
            ret['opname'] = getattr(config, 'MASTER_OP_NAME', '主账号')
        else:
            with get_connection('qf_core') as db:
                opuser = db.select_one(
                    table = 'opuser',
                    where = {
                        'userid': userid,
                        'opuid': int(opuid),
                        },
                    fields = 'opname, status, mobile'
                )
            if not opuser:
                raise DBError('操作员不存在')
            ret['opname'] = opuser['opname']

        return success(ret)


class Valid(BaseHandler):
    '''
    验证商户信息
    '''

    _base_err = '验证信息失败'

    @check('login')
    def POST(self):
        idnumber = self.req.input().get('idnumber', '').strip()
        if not idnumber:
            raise ParamError('身份证号码必填')

        userid = int(self.user.userid)

        user = apcli_ex('findUserByid', int(self.user.userid))
        if not user:
            raise DBError('商户不存在')

        if (user.idnumber or '').upper() != idnumber.upper():
            raise ParamError('身份证不匹配')

        code = hids.encode(userid, int(time.time()))

        return success({'code' : code})
