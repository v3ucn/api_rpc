# coding=utf-8

import time
import config
import logging
import traceback

from excepts import ParamError, DBError
from utils.base import BaseHandler
from utils.decorator import check
from constants import MEMBER_AUTH, MEMBER_AUTH_UNSET, MEMBER_AUTH_ON, MEMBER_AUTH_OFF, DTM_FMT
from utils.qdconf_api import get_qd_conf_value

from qfcommon.base.qfresponse import success
from qfcommon.base.dbpool import get_connection_exception

log = logging.getLogger()


class GetInfo(BaseHandler):
    '''
    获取当前商户是否开启会员实名认证， 和会员总数，实名总数信息
    '''

    _base_err = '获取数据失败'

    def get_member_auth(self, userid):
        with get_connection_exception("qf_mchnt") as conn:
            row = conn.select_one("mchnt_control", fields="member_auth", where={
                "status": 1,
                "userid": userid
            })
        if row:
            return row['member_auth']
        else:
            return MEMBER_AUTH_UNSET

    def get_real_count(self, userid):
        with get_connection_exception('qf_mchnt') as db:
            where = {'userid': userid}
            # total_num
            total_num = db.select_one('member', where=where, fields='count(1) as num')['num']

            where.update({"submit": 1})
            real_num = db.select_one("member_tag",
                                     where=where,
                                     fields="count(1) as num")['num']

            return total_num, real_num

    @check('login')
    def GET(self):
        userid = self.user.userid

        # 先获取当前商户的 如果等于0 则去获取渠道的 如果渠道的也未设置 则给赋值配置文件的
        member_auth = self.get_member_auth(userid)
        if member_auth == MEMBER_AUTH_UNSET:
            groupid = self.get_groupid(userid=userid)
            qd_ext = get_qd_conf_value(groupid, mode=None, key='ext')
            if qd_ext:
                member_auth = qd_ext.get('need_auth', MEMBER_AUTH_OFF)
            else:
                member_auth = getattr(config, "DEFAULT_MEMBER_AUTH", MEMBER_AUTH_OFF)

        count, real_count = self.get_real_count(userid)
        return self.write(success(data={
            "is_real_auth": 1 if member_auth == MEMBER_AUTH_ON else 0,
            "count": count,
            "real_count": real_count
        }))


class SetMemberAuth(BaseHandler):
    '''
    设置商户的实名认证状态
    '''

    @check('login')
    def POST(self):

        params = self.req.input()
        status = params.get("status", "")
        try:
            status = int(status)
        except:
            raise ParamError("参数不合法")

        if status == "":
            raise ParamError("参数为空")

        if status not in (0, 1):
            raise ParamError("参数错误")

        member_auth = MEMBER_AUTH_ON if int(status) == 1 else MEMBER_AUTH_OFF

        userid = self.user.userid

        where = {
            "userid": userid,
            "status": 1
        }
        curr_time = time.strftime(DTM_FMT)
        with get_connection_exception("qf_mchnt") as conn:
            num = conn.select_one("mchnt_control", where=where, fields="count(1) as num")['num']
            if num > 0:
                affected_line = conn.update("mchnt_control", values={"member_auth": member_auth},
                                            where=where)
                if affected_line >= 1:
                    return self.write(success(data={}))
                else:
                    raise DBError("更新数据库失败")
            else:
                try:
                    conn.insert("mchnt_control", values={
                        "userid": userid,
                        "member_auth": member_auth,
                        "ctime": curr_time
                    })
                    return self.write(success(data={}))
                except Exception as e:
                    log.debug(traceback.format_exc())
                    raise DBError("插入数据库失败")


class GetDocAndImg(BaseHandler):
    '''
    获取描述页面的内容和图片
    '''

    @check("login")
    def GET(self):
        return self.write(success(data=getattr(config, 'MEMBER_AUTH_CONTENT', '未设置')))