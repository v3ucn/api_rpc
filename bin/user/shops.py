# coding:utf-8

import config
import logging
import traceback
import time

from utils.decorator import check
from utils.base import BaseHandler
from utils.tools import (
    get_linkids, get_userinfo, get_user_detail_info, get_user_bank_info,
    get_img_info, get_qd_mchnt, apcli_ex, kick_user
)
from excepts import ParamError, DBError, ThirdError
from base import UserDefine, APPLY_STATE
from runtime import apcli
from util import check_password
from constants import VALID_OPUSER_STATUS, RECEIVE_PUSH, NO_RECEIVE_PUSH, DTM_FMT

from qfcommon.base.qfresponse import success, error, QFRET
from qfcommon.base.dbpool import get_connection, get_connection_exception, with_database
from qfcommon.thriftclient.apollo import ApolloServer
from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.apollo.ttypes import ApolloException, UserExt

log = logging.getLogger()


# 获取审核状态,以及给前端返回一个审核状态的标志:'1'-审核中，'2'-审核成功，'3'-审核失败
def re_audit_info(uid):

    # 增加对多个uid的支持
    if isinstance(uid, (list, tuple)):
        userids = [int(i) for i in uid]
    else:
        userids = [int(uid)]

    # 获取审核信息
    with get_connection('qf_mis') as db:
        audit_state = db.select('apply', where={'user': ('in', userids)}, fields='user, state') or []
        if type(audit_state) != list:
            audit_state = list(audit_state)

    # 如果有子商户在表里没有数据,按照审核通过
    for uid in userids:
        if uid not in [i['user'] for i in audit_state]:
            audit_state.append({"user": uid, "state": APPLY_STATE.get("pass")})

    # 根据state,增加audit_str, audit_flag

    fail_userid = []  # 存储审核失败的userid

    def re_str_flag(state):
        if int(state) == APPLY_STATE.get("pass"):
            flag = '2'
            audit_str = "审核成功"
        elif int(state) in (APPLY_STATE.get("refuse"), APPLY_STATE.get("fail")):
            flag = '3'
            audit_str = "审核失败"
        else:
            flag = '1'
            audit_str = "审核中"
        return flag, audit_str

    for i in audit_state:
        i.update({"audit_str": re_str_flag(i['state'])[1], "audit_flag": re_str_flag(i['state'])[0], "audit_fail_reason": ""})
        if i['audit_flag'] == "3":
            fail_userid.append(i['user'])

    # 查询失败原因
    if fail_userid:
        with get_connection('qf_mis') as db:
            fields = "user_id, memo, create_date"
            where = {'user_id': ('in', fail_userid)}
            r = db.select('mis_auditlog', where=where, fields=fields) or {}
        if r:

            from itertools import groupby
            from operator import itemgetter
            r_g = groupby(r, itemgetter("user_id"))

            r_g = dict([(int(key), list(group)) for key, group in r_g])

            for j in audit_state:
                if j['user'] in fail_userid:
                    j.update({"audit_fail_reason": max(r_g.get(j['user']), key=itemgetter("create_date")).get('memo')})
    return {i['user']: i for i in audit_state}


class Shops(BaseHandler):
    '''
    我的商户列表
    '''
    @check('login')
    def GET(self):

        params = self.req.input()
        audit_status = str(params.get('audit_status', '0'))

        need_all = params.get("need_all", 'notall')

        if audit_status not in ['', '0', '1', '2', '3']:
            raise ParamError("审核状态参数错误")
        try:
            page = int(params.get('page', '0'))
            length = int(params.get('length', '10'))
        except:
            raise ParamError("分页参数错误")

        start = page * length

        userid = self.user.userid
        cate = self.get_cate()
        if cate == "bigmerchant":
            sub_uids = get_linkids(userid)

            if not sub_uids:
                return self.write(success(data={"shops": []}))

            all_userinfo = get_userinfo(sub_uids)  # 调Apollo的商户信息接口

            # 对子店排序,按照创建时间倒叙
            sub_uids = sorted(sub_uids, key=lambda x: all_userinfo[x].get('jointime', ''), reverse=True)

            user_exts = apcli_ex('getUserExts', sub_uids)
            user_exts = {i.uid:i for i in user_exts}

            # 获取审核状态信息
            all_audit_state = re_audit_info(sub_uids)
            all_res = []
            for uid in sub_uids:
                one_res = dict()
                # 获取审核状态, 审核标志
                audit_state = all_audit_state.get(int(uid))
                audit_flag = audit_state.get("audit_flag", '')

                if audit_status == '' or audit_status == '0' or audit_flag == audit_status:  # 筛选audit_status

                    one_res['audit_flag'] = audit_flag
                    one_res['audit_fail_reason'] = audit_state.get("audit_fail_reason", '')
                    one_res['audit_str'] = audit_state.get("audit_str", '')

                    userinfo = all_userinfo.get(uid, {})
                    user_ext = user_exts.get(uid, UserExt())

                    one_res['login_account'] = userinfo.get('mobile', '') if userinfo else ''
                    one_res['shopname'] = userinfo.get('shopname', '') if userinfo else ''
                    one_res['logo'] = user_ext.logo_url or config.DEFAULT_SHOP_LOGO_URL
                    one_res['shopid'] = int(uid)
                    all_res.append(one_res)

            return self.write(success(data={"shops": all_res[start: start+length] if need_all != "all" else all_res}))

        else:
            raise DBError('角色错误')


class Detail(BaseHandler):
    '''
    获取商户的详细信息
    '''
    @check('login')
    def GET(self):

        params = self.req.input()
        shopid = params.get("shopid", '')
        if not shopid:
            raise ParamError("商户id参数错误")

        # 验证是否是当前商户的子商户
        userid = self.user.userid
        cate = self.get_cate()
        if cate == "bigmerchant":
            subids = get_linkids(userid)
            shopid = int(shopid)
            if shopid not in subids:
                raise ParamError("非大商户的子商户")
        else:
            pass

        try:
            res = {}
            user_ext = apcli_ex('getUserExt', int(shopid))

            user_detail_info = get_user_detail_info(shopid)

            audit_info = re_audit_info(shopid).get(shopid)
            res['audit_str'], res['audit_flag'], res['audit_fail_reason'] = audit_info.get('audit_str'), audit_info.get('audit_flag'), audit_info.get('audit_fail_reason')

            res['login_account'] = user_detail_info.get("mobile", '') if user_detail_info else ''
            res['shopname'] = user_detail_info.get("shopname", '') if user_detail_info else ''
            res['logo'] = user_ext.logo_url or config.DEFAULT_SHOP_LOGO_URL
            res['register_time'] = user_detail_info.get("jointime", '') if user_detail_info else ''
            res['telephone'] = user_detail_info.get('telephone', '') if user_detail_info else ''
            res['address'] = user_detail_info.get("address", '') if user_detail_info else ''
            # 获取银行信息
            bank_info = get_user_bank_info(shopid)
            res['payee'] = bank_info.get("bankuser", '') if bank_info else ''
            bank_account = bank_info.get("bankaccount", '') if bank_info else ''
            res['bank_account'] = self.del_cardno(bank_account)
            res['branch_bank_name'] = bank_info.get("bankname", '') if bank_info else ''

            return self.write(success(data=res))
        except:
            log.warn('Get shop detail error:%s' % traceback.format_exc())
            raise DBError('获取商户详细信息失败')

    def del_cardno(self, cardno):
        len_cardno = len(cardno)
        if len_cardno < 4:
            return cardno[-4:]
        elif len_cardno < 10:
            return '*' * (len_cardno-4)+cardno[-4:]
        else:
            return cardno[:6]+ '*'*(len_cardno-10) + cardno[-4:]


class Delete(BaseHandler):
    '''
    解除门店关联
    '''
    @check('login')
    def POST(self):

        cate = self.get_cate()

        params = self.req.input()
        sub_mchnt_id = params.get('shopid', '')
        try:
            userid = self.user.userid
            sub_mchnt_id = int(sub_mchnt_id)
            if not sub_mchnt_id:
                raise ParamError("子商户错误")
            else:
                if cate == "bigmerchant":
                    subids = get_linkids(userid)
                    if sub_mchnt_id not in subids:
                        raise ParamError("非大商户的子商户")
        except:
            log.warn('sub merchant error : %s ' % traceback.format_exc())
            raise ParamError("无法识别子商户")

        try:
            thrift_callex(config.APOLLO_SERVERS, ApolloServer, 'unbindRelation', int(userid), int(sub_mchnt_id), 'merchant')
        except:
            log.warn('user ({userid}) remove sub merchant({sub_mchnt_id}) error : {reason}'.format(userid=userid, sub_mchnt_id = sub_mchnt_id, reason = traceback.format_exc()))
            return self.write(error(QFRET.THIRDERR))
        return self.write(success(data={}))


class ValidatePassword(BaseHandler):
    '''
    判断密码是否正确

    如果session中有opuid按照验证操作员密码的方式,
    没有则按照验证主账户的密码的方式
    '''

    @check('login')
    def POST(self):
        userid = int(self.user.userid)
        params = self.req.inputjson()
        password = params.get('password', '')
        mode = params.get('mode', '')

        if not password:
            raise ParamError('密码为空')

        # 支持收银员切换
        if mode == 'opuser':
            opuid = params.get('opuid', '')
        else:
            opuid = self.user.ses.data.get('opuid', '')

        # 验证管理员密码
        if mode == 'manage':
            with get_connection_exception('qf_core') as conn:
                row = conn.select_one(
                    'extra_mchinfo', where={'userid': userid},
                    fields='manage_password'
                )
            if not row or not row['manage_password']:
                raise DBError('未设置过管理密码')
            else:
                if not check_password(password, row['manage_password']):
                    return success(data={'result': 'fail'})
                else:
                    return success(data={'result': 'success'})

        # 验证普通密码
        # 先判断是否opuid有值, 没有opuid属性说明是主账号
        if opuid:
            with get_connection('qf_core') as db:
                opuser = db.select_one(
                    'opuser', fields='password',
                    where={
                        'userid': userid,
                        'opuid': int(opuid),
                        'status': VALID_OPUSER_STATUS
                    }
                )
            if not opuser:
                raise DBError('该操作员不存在')

            if not check_password(password, opuser['password']):
                return success(data={'result': 'fail'})
            else:
                return success(data={'result': 'success'})

        else:
            try:
                apcli('checkByUid', userid, password)
                return success(data={'result': 'success'})
            except ApolloException as e:
                if e.respcd == '1008':
                    return success(data={'result': 'fail'})
                else:
                    raise DBError('密码验证失败')


class ShopQuestionHandler(BaseHandler):
    '''
    连锁店说明
    '''

    @check('login')
    def GET(self):

        return self.write(success(config.SHOP_QUESTIONS))


class GetLatestShopInfo(BaseHandler):
    '''
    userid参数没有hash
    获取最新创建的商户部分信息 给创建商户渲染页面使用
    '''

    @check('login')
    def GET(self):

        params = self.req.input()
        userid = params.get("userid", '')
        usertype = params.get("usertype", '')
        try:
            usertype = int(usertype)
        except:
            raise ParamError("usertype参数错误")
        if usertype not in UserDefine.SIGNUP_USERTYPES:
            raise ParamError("usertype参数错误")
        if not userid:
            raise ParamError("userid参数错误")

        # 验证传入的userid是否属于当前业务员
        curr_uid = self.user.userid

        qd_info = get_qd_mchnt(userid)
        if qd_info:
            slsm_uid = qd_info.slsm_uid
            if slsm_uid != int(curr_uid):
                return self.write(error(QFRET.DBERR, respmsg="商户id参数与当前操作员无绑定关系"))

        cate = self.get_cate(userid=userid)
        if cate == "bigmerchant":
            sub_uids = get_linkids(userid)

            if not sub_uids:
                return self.write(success(data={}))
            else:

                # 先筛选出状态为审核通过的商户 最新商户信息从审核通过商户中选取
                with get_connection('qf_mis') as db:
                    rows = db.select('apply', where={'user': ('in', sub_uids), 'state': APPLY_STATE.get("pass")}, fields='user')
                if rows:
                    sub_uids = [i['user'] for i in rows]
                else:
                    return self.write(success(data={}))

                ret = dict()

                # 查询出最新的userid, name和legalname
                with get_connection("qf_core") as db:
                    rows = db.select("profile", where={"userid": ("in", sub_uids), "user_type": usertype},
                                     fields="userid, name, legalperson, user_type", other="order by jointime desc")
                    if len(rows) <= 0:
                        return self.write(success(data={}))
                    latest_uid = rows[0]['userid']

                    usertype = int(rows[0]['user_type'])
                    name = rows[0]['name']
                    legal_name = rows[0]['legalperson']

                    if usertype == UserDefine.SIGNUP_USERTYPE_TINY:
                        ret['name'] = name
                    else:
                        ret['name'] = legal_name

                try:
                    detail_info = apcli('userprofile_by_id', latest_uid)
                except:
                    log.debug(traceback.format_exc())
                    raise ThirdError("获取商户详情失败")
                user_info = detail_info['user']
                bank_info = detail_info['bankInfo']

                ret['banktype'] = bank_info['banktype']
                ret['bankuser'] = bank_info['bankuser']
                ret['bankaccount'] = bank_info['bankaccount']
                ret['bankmobile'] = bank_info['bankmobile']
                ret['bankProvince'] = bank_info['bankProvince']
                bank_city = bank_info.get('bankCity', '')
                head_bankname = bank_info.get('headbankname', '')
                ret['bankCity'] = bank_city
                ret['headbankname'] = head_bankname
                with get_connection_exception('qf_mis') as db:
                    r = db.select_one('tools_areacity', where={'city_name': bank_city}, fields='city_no, city_name') or {}
                    head_bank = db.select_one('tools_bank', where={'bank_name': head_bankname, 'bank_display': 1},
                                              fields='bank_name, bank_no') or {}
                ret['city_id'] = r.get('city_no', '')
                ret['headbankid'] = head_bank.get('bank_no', '')
                ret['bankcode'] = bank_info.get('bankcode', '')
                ret['bankname'] = bank_info['bankname']

                ret['idnumber'] = user_info['idnumber']
                ret['address'] = user_info['address']


                user_ext = apcli_ex('getUserExt', int(latest_uid))
                ret['shoptype_id'] = ''
                if user_ext:
                    ret['shoptype_id'] = user_ext.shoptype_id

                # 身份证有效期, 照片,
                cert_names = ["idcardfront", "idcardback", "idcardinhand", "licensephoto"]

                # 常量对应
                cert_imgurl = {"idcardfront": 'idcardfront_url', "idcardback": 'idcardback_url',
                               "idcardinhand": "idcardinhand_url", "licensephoto": "license_photo_url"}

                all_img_info = get_img_info(latest_uid, cert_names)

                for i in all_img_info:
                    ret.update({cert_imgurl[i['name']]: i['imgurl']})

                with get_connection('qf_mis') as db:
                    db_ret = db.select('apply', fields="idstatdate, idenddate",
                                       where={"user": latest_uid}, other="limit 1")
                    if db_ret:
                        ret.update(db_ret[0])
                    else:
                        ret.update({
                            "idstatdate": "",  # 身份证起始时间
                            "idenddate": "",  # 身份证结束时间
                        })
                return self.write(success(data=ret))

        else:
            raise ParamError("角色错误")


class ModifyShopPassword(BaseHandler):

    @check('login')
    def POST(self):
        params = self.req.input()
        shopid = params.get("shopid", '')
        newpwd = params.get("newpwd", '')
        if not shopid or not newpwd:
            raise ParamError("参数错误")

        # 验证是否是当前商户的子商户
        userid = self.user.userid
        cate = self.get_cate()
        if cate == "bigmerchant":
            subids = get_linkids(userid)
            shopid = int(shopid)
            if shopid not in subids:
                raise ParamError("非大商户的子商户")

            try:
                apcli("changePwd", uid=shopid, password=newpwd)

                kick_user(int(shopid), mode = 'not_opuser')
                return self.write(success(data={"result": "success"}))
            except:
                log.debug(traceback.format_exc())
                return self.write(success(data={"result": "fail"}))
        else:
            raise ParamError("角色错误")


class IsReceivePush(BaseHandler):
    '''
    是否接收收银员播报
    Returns: is_receive: 0不接收, 1接收
    '''

    # 获取收银员推送是否退给主账号
    def get_is_push_master(self, userid):
        try:
            with get_connection_exception("qf_mchnt") as db:
                row = db.select_one("mchnt_control", fields="push_master", where={"userid": int(userid), "status": 1}, other="limit 1")
                if row:
                    is_receive = row['push_master']
                else:
                    is_receive = 0

                return is_receive
        except:
            log.debug(traceback.format_exc())
            raise DBError("读取mchnt_control表出错")

    @check('login')
    def GET(self):
        userid = self.user.userid
        is_receive = self.get_is_push_master(userid)
        return self.write(success(data={"is_receive": is_receive}))


class SetReceivePush(BaseHandler):
    '''
    开启/关闭接收收银员播报
    params: push_status 0-关闭 1-开启
    '''

    @check('login')
    @with_database("qf_mchnt")
    def POST(self):

        params = self.req.input()
        push_status = params.get("push_status", '')
        try:
            push_status = int(push_status)
            if push_status not in (RECEIVE_PUSH, NO_RECEIVE_PUSH):
                raise ParamError("push_status参数错误")
        except:
            raise ParamError("push_status参数错误")

        userid = self.user.userid

        curr_time = time.strftime(DTM_FMT)
        try:
            row = self.db.select_one("mchnt_control", fields="push_master", where={"userid": int(userid), "status": 1})
            if row:
                db_push_status = row['push_master']  # 数据库存储的转态
                if db_push_status == push_status:
                    return self.write(success(data={"result": "fail"}))

                self.db.update("mchnt_control", {"push_master": push_status}, where={"userid": int(userid), "status": 1})
                return self.write(success(data={"result": "success"}))

            else:
                if push_status == RECEIVE_PUSH:
                    self.db.insert("mchnt_control", values={"push_master": RECEIVE_PUSH, "userid": int(userid),
                                                           "push_opuser": 0, "status": 1, "ctime": curr_time})
                    return self.write(success(data={"result": "success"}))
                else:
                    raise ParamError("接收收银员播报已经是关闭状态")
        except:
            log.info(traceback.format_exc())
            raise DBError("数据库执行出错")

