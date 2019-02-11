# coding:utf-8
'''
商户紧急补件H5的后端支持
'''

import logging
import time
import re
import traceback
log = logging.getLogger()

from utils.base import BaseHandler
from utils.decorator import check
from utils.tools import get_userinfo, get_img_info
from excepts import DBError, ParamError
from constants import ALREADY_SUPPLIED, NO_SUPPLIED, DATE_FMT, DATETIME_FMT, \
    IMG_AUDIT_PASS, IMG_NOT_PASS, IMG_WAITE_AUDIT, IMG_NOT_UPLOAD
from base import UserDefine
from utils.valid import is_valid_datetime

from qfcommon.base.qfresponse import success, error, QFRET
from qfcommon.base.dbpool import get_connection_exception


def get_imgurl_res(userid):
    cert_names = ['licensephoto', 'authcertphoto', 'idcardfront', 'idcardback', 'authbankcardfront']
    try:
        imgurl_res = get_img_info(int(userid), cert_names)
    except:
        raise DBError("获取图片失败")
    return imgurl_res


class SuppliedInfo(BaseHandler):
    '''
    H5页面渲染的数据
    '''

    @check("login")
    def GET(self):
        userid = self.user.userid

        uinfo = get_userinfo(userid)
        mobile = uinfo.get("mobile", '')

        imgurl_res = get_imgurl_res(userid)

        all_imgnames = ("licensephoto", "authcertphoto", "idcardfront", "idcardback", 'authbankcardfront')
        res = {"mobile": mobile, "userid": userid}
        for i in imgurl_res:
            res.update({i["name"]: {"imgurl": i["imgurl"], "state": IMG_NOT_UPLOAD}})

        with get_connection_exception("qf_mis") as conn:
            rows = conn.select("mis_upgrade_voucher", where={
                "user_id": userid,
                "name": ("in", all_imgnames)
            }, fields="name, state")

        if rows:
            for i in rows:
                res[i["name"]].update({"state": i["state"]})

        with get_connection_exception("qf_core") as conn:
            row = conn.select_one("extra_mchinfo", where={"userid": userid}, fields="is_supplied, wechat_no")

            if row:

                # 暂时让这个值都等于 没有补过
                # res['all_supplied'] = ALREADY_SUPPLIED if row['is_supplied'] else NO_SUPPLIED
                res['all_supplied'] = NO_SUPPLIED
                res['wechat_no'] = row['wechat_no']
            else:
                res['all_supplied'] = NO_SUPPLIED
                res['wechat_no'] = ''

        with get_connection_exception("qf_mis") as conn:
            row = conn.select_one("apply", fields="licensenumber, name, usertype", where={"user": userid})
            res["licensenumber"] = row["licensenumber"] if row and row["licensenumber"] else ""
            res["name"] = row['name'] if row else ""
            res["user_type"] = row["usertype"] if row else 0

        return self.write(success(data=res))


class SupplyInfo(BaseHandler):
    '''
    补件
    '''

    @check("login")
    def POST(self):

        params = self.req.input()

        userid = self.user.userid
        is_in_extra_table = False

        # 先判断商户是否在表里 是否补充过信息
        with get_connection_exception("qf_core") as db:
            row = db.select_one("extra_mchinfo", fields="is_supplied", where={"userid": userid})
            if row:
                is_in_extra_table = True
        try:
            user_type = int(params.get("user_type", 0))
        except:
            raise ParamError("user_type参数错误")

        # 校验user_type, name, licensenumber参数
        name = params.get("name", '')
        licensenumber = params.get("licensenumber", '')
        with get_connection_exception("qf_mis") as db:
            row = db.select_one("apply", fields="usertype, name, licensenumber", where={"user": userid})
            if row:
                if (int(row['usertype']) not in UserDefine.SIGNUP_USERTYPES) and (not user_type):
                    raise ParamError("user_type必填")
                if not row['name'] and not name:
                    raise ParamError("name必填")
                if not row['licensenumber'] and not licensenumber:
                    raise ParamError("licensenumber必填")

        wechat_no = params.get("wechat_no", '')
        if not wechat_no:
            raise ParamError("微信号必填")

        # 去掉微信号 剩下的就是图片信息{name: imgname, ...}形式
        if 'wechat_no' in params:
            del params["wechat_no"]
        img_infos = params

        # 先把图片信息插入mis_upgrade_voucher表
        td, now = time.strftime(DATE_FMT), time.strftime(DATETIME_FMT)

        # 增加判断下 图片是否是审核失败的 这状态的需要重新上传
        # 找出审核通过的
        with get_connection_exception("qf_mis") as db:
            rows = db.select("mis_upgrade_voucher", fields="name, state", where={
                "user_id": userid,
                "name": ('in', ('licensephoto', 'authcertphoto', 'idcardfront', 'idcardback', 'authbankcardfront'))
            })

            already_in_imgnames = [i["name"] for i in rows if int(i["state"]) in (IMG_AUDIT_PASS, IMG_WAITE_AUDIT)]

        # 用户传递的参数中的去掉微信号的键
        params_img_keys = img_infos.keys()

        # 使用所有需要的图片键 - 已经加入数据库并且审核通过的图片键
        needed_params = {"licensephoto", "authcertphoto", "idcardfront", "idcardback", 'authbankcardfront'} - \
                        set(already_in_imgnames)

        # 求出所有需要传递但是未传递的图片键
        un_imgparams = needed_params - (needed_params & set(params_img_keys))
        if un_imgparams:
            raise ParamError("缺少图片参数: %s" % ', '.join(un_imgparams))

        # 对用户传入的图片参数进行清洗 如果不是在needed_params 则去除
        dela_img_infos = dict()
        for k, v in img_infos.iteritems():
            if k in needed_params:
                dela_img_infos[k] = img_infos[k]

        # 根据上面rows找到的图片状态判断该update还是insert
        update_keys = set([i['name'] for i in rows])

        if dela_img_infos:
            for code in dela_img_infos.keys():

                insert_data = {
                            "user_id": userid, "upgrade_id": 0, "apply_level": 0,
                            "cert_type": UserDefine.CERT_TYPE[code], "name": code, "submit_time": now,
                            "state": IMG_WAITE_AUDIT, "input_state": 1, "typist_user": 0,
                            "typist_time": now, "imgname": dela_img_infos[code]
                        }
                with get_connection_exception("qf_mis") as db:
                    try:
                        if code in update_keys:
                            del insert_data['typist_time']
                            db.update("mis_upgrade_voucher", where={'user_id': userid, "name": code}, values=insert_data)
                        else:
                            db.insert('mis_upgrade_voucher', insert_data)
                    except:
                        log.debug(traceback.format_exc())
                        raise DBError("插入或者更新图片数据出现异常")

        with get_connection_exception("qf_core") as db:
            supply_date = {
                "userid": userid,
                "is_supplied": ALREADY_SUPPLIED,
                "wechat_no": wechat_no,
                "supply_time": now,
                "ctime": now,
                "utime": now
            }
            try:

                if is_in_extra_table:
                    del supply_date["userid"]
                    del supply_date["ctime"]
                    db.update("extra_mchinfo", values=supply_date, where={"userid": userid})
                else:
                    db.insert("extra_mchinfo", supply_date)
            except:
                log.debug(traceback.format_exc())
                raise DBError("extra_mchinfo出现异常")

        # 更新apply表
        values = {}
        if licensenumber:
            values.update({"licensenumber": licensenumber})
        if name:
            values.update({"name": name})
        if user_type:
            values.update({"usertype": str(user_type)})

        if values:
            with get_connection_exception("qf_mis") as db:
                db.update("apply", where={"user": userid}, values=values)

        return self.write(success(data={}))


class QuerySuppliedUserid(BaseHandler):
    '''
    根据时间段查询已经补过件的商户ids
    '''

    def GET(self):

        params = self.req.input()
        begin_time = params.get("begin_time", '')
        end_time = params.get("end_time", '')
        if not begin_time or not end_time:
            return self.write(error(QFRET.PARAMERR, respmsg="开始时间或者结束时间没有"))

        if not is_valid_datetime(begin_time) or not is_valid_datetime(end_time):
            return self.write(error(QFRET.PARAMERR, respmsg="开始时间或者结束时间格式不对"))

        with get_connection_exception("qf_core") as db:
            try:
                rows = db.select("extra_mchinfo", where={"supply_time": ("between", (begin_time, end_time))},
                                 fields="userid")
            except:
                log.debug(traceback.format_exc())
                return self.write(error(QFRET.DBERR, respmsg="查询出现异常"))

        return self.write(success(data={"supplied_userids": [i['userid'] for i in rows]}))