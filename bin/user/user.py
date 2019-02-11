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

from excepts import ParamError, SessionError, DBError, ThirdError
from decorator import (
    check_login, openid_or_login, raise_excp, with_validator
)
from constants import (
    MOBILE_PATTERN, CERT_NAME, OLD2NEW_CERT, EMAIL_PATTERN, DATETIME_FMT
)
from base import UserUtil, UserDefine, UserBase
from runtime import apcli, ms_redis_pool

from qfcommon.base.dbpool import with_database, get_connection, get_connection_exception
from qfcommon.thriftclient.apollo.ttypes import User, UserBrief, UserExt, ApolloException
from qfcommon.qfpay.apolloclient import Apollo
from qfcommon.base.qfresponse import QFRET,error,success

from qfcommon.web.validator import Field, T_REG, T_INT, T_STR, T_FLOAT
from qfcommon.qfpay.defines import (
    QF_USTATE_NEW, QF_USTATE_VARIFIED, QF_USTATE_ACTIVE,
    QF_USTATE_OK, QF_USTATE_DULL
)

# 允许登录的状态
ALLOW_STATE = (QF_USTATE_NEW, QF_USTATE_VARIFIED, QF_USTATE_ACTIVE,
               QF_USTATE_OK, QF_USTATE_DULL)


log = logging.getLogger()

class Info(BaseHandler):
    '''
    获取用户信息
    '''
    def _get_user_service(self):
        # 用户服务列表, 最少返回默认的列表
        user_service = Apollo(config.APOLLO_SERVERS).user_service(self.user.userid)
        user_service = {}.fromkeys([i['code'] for i in user_service]+config.DEFAULT_SERVICES).keys()

        # 获取版本号
        log.debug('user_agent:%s' % self.req.environ.get('HTTP_USER_AGENT',''))
        version, platform = get_app_info(self.req.environ.get('HTTP_USER_AGENT',''))
        log.info('version:%s  platform:%s' % (version, platform))
        # 根据版本号和平台获取服务列表
        services = get_services(version, platform)
        services.sort(key=lambda x: x.get('weight', 0), reverse=True)
        scodes = [i['code'] for i in services]

        return [i for i in scodes if i in user_service]

    @check_login
    @raise_excp('获取用户信息失败')
    def GET(self):
        ret = {}
        ret['user_service'] = self._get_user_service()

        # 用户基础信息
        userinfo = Apollo(config.APOLLO_SERVERS).user_by_id(self.user.userid)

        # 线下店铺信息
        user_ext = apcli_ex('getUserExt', int(userinfo['uid']))

        ret.update(UserUtil.ret_userinfo(userinfo, user_ext))

        return self.write(success(ret))

class Check(BaseHandler):
    '''
    检验用户是否注册
    '''

    @raise_excp('检验用户信息出错')
    def POST(self):
        d = self.req.input()
        mobile = d.get('username', '').strip()
        mode = d.get('mode', '').strip()

        if not mobile:
            raise ParamError('参数错误')
        ret = {}
        resperr = ''
        if mode == 'user':
            ret['is_signup'] = UserUtil.check_profile(**{'auth_user.mobile' : mobile})
            resperr =  '用户已注册' if ret['is_signup'] else ''
        else:
            ret.update(check_user(mobile))
            resperr = '非业务员' if ret['is_saleman'] else ''
        ret = {k:v for k,v in ret.iteritems() if k in ('is_signup', 'is_saleman')}
        return self.write(success(ret, resperr))


class ShopCreate(BaseHandler):
    '''
    创建店铺(补充商圈信息)
    '''

    _base_err = '补充店铺信息失败'

    @check('login')
    def POST(self):
        params = {k:v.strip() for k, v in self.req.input().iteritems()}

        userid = self.user.userid

        user = apcli.userprofile_by_id(int(userid))
        user_ext = UserExt(
            uid = int(userid),
            shoptype_id = int(params['typeid'] or UserDefine.DEFAULT_SHOPTYPE_ID),
            contact = params.get('landline', user['user']['telephone']),
            head_img = params.get('head_img'),
            logo_url = params.get('logo_url'),
        )
        if is_valid_int(params.get('regionid')):
            user_ext.regionid = int(params['regionid'])

        apcli_ex('bindUserExt', user_ext)

        return success({})


class GetQrcode(BaseHandler):
    '''
    获取用户的二维码
    返回二维码字符串
    '''

    def get_opinfo(self):
        if 'opuid' in self.user.ses:
            return {
                'opuid': self.user.ses['opuid'],
                'opname': self.user.ses.get('opname', '')
            }

        data = self.req.input()
        if data.get('opuid'):
            # 验证商户是否存在此opuid的操作员
            opuser = None
            with get_connection('qf_core') as db:
                opuser = db.select_one(
                        table = 'opuser',
                        where = {
                            'userid': int(self.user.userid),
                            'opuid': int(data['opuid']),
                            'status':1
                        },
                        fields= 'opuid, opname')
            if not opuser:
                raise ParamError('该商户下没有该操作员或操作员失效')

            return opuser

        return {}

    _base_err = '获取用户二维码失败'

    @check('login')
    def GET(self):

        params = self.req.input()
        if params.has_key("shopid"):
            shopid = params.get("shopid")
            try:
                userid = int(shopid)
            except:
                raise ParamError("子商户参数错误")
            # 判断下当前传入的userid是否是子商户
            if userid not in get_linkids(self.user.userid):
                raise ParamError("传入的子商户不属于此商户")
        else:
            userid = int(self.user.ses.get('userid', 0))

        url = config.QRCODE_URL % hids.encode(userid)

        # 获取用户信息
        user = apcli.user_by_id(userid)
        if not user:
            return self.write(error(QFRET.PARAMERR, respmsg='查询用户信息失败'))
        mchnt_name = user['shopname']

        # 获取图片信息
        img_conf = get_qd_conf_value(
            mode=None, key='qrcode',
            groupid=user['groupid']
        ) or {}

        if not params.has_key("shopid"):
            # 操作员信息
            opinfo = self.get_opinfo()
            opuid, opname = opinfo.get('opuid'), opinfo.get('opname', '')
            if opuid:
                url += '&o=' + str(opuid)
                op_img_conf = {k[3:]:v for k, v in img_conf.iteritems() if k.startswith('op_')}
                img_conf = op_img_conf or img_conf

                opname = '%04d' % int(opuid)
            else:
                img_conf = {k:v for k, v in img_conf.iteritems() if not k.startswith('op_')}
        else:
            return self.write(success({
                "qrcode": url,
                "img_conf": {k: v for k, v in img_conf.iteritems() if not k.startswith('op_')}
            }))

        return self.write(success({
            'qrcode':url,
            'img_conf':img_conf,
            'mchnt_name': mchnt_name,
            'opname': opname
        }))

class BankInfoHandler(BaseHandler):
    '''
    获取用户银行卡信息
    '''

    def del_cardno(self, cardno):
        len_cardno = len(cardno)
        if len_cardno < 4:
            return cardno[-4:]
        elif len_cardno < 10:
            return '*' * (len_cardno-4)+cardno[-4:]
        else:
            return cardno[:6]+ '*'*(len_cardno-10) + cardno[-4:]


    def _resolve(self, bankinfo):
        b = {k:v or '' for k, v in bankinfo.iteritems()}
        return {
            'cardno': self.del_cardno(b['bankaccount']),
            'name': b['bankuser'],
            'bank_name': b['headbankname'],
            'icon' : config.BANK_ICONS.get(bankinfo['headbankname'], config.DEFAULT_BANK_ICON)
        }

    def _get_audit_info(self, userid):
        def get_audit_memo(memo):
            try:
                data = json.loads(memo)['data']
                ret = sorted(data, key=lambda d:d['time'])[-1]['memo']
            except:
                return None
            return ret

        audit_info, apy = {}, {}
        with get_connection('qf_mis') as db:
            where = {'userid' : userid, 'modifytime' : ('>=', config.BANK_APPLY_ONLINE_TIME)}
            apy = db.select_one('bankchange_apply', where=where,
                        other='order by id desc') or {}

        # 未提交过信息
        if not apy:
            return {}

        if (apy['status'] == UserDefine.BANK_APPLY_SUCC and
            apy['sync_tl_status'] == UserDefine.BANK_SYNC_SUCC):
            # 审核通过
            return {
                'state': UserDefine.BANK_APPLY_STATE_SUCC,
                'title': '新卡变更成功',
                'content': ['{}后的交易款项会划款到您新卡中，请注意查收。'.format(
                    apy['modifytime'].strftime('%Y年%m月%d日'))
                ]
            }

        tips = config.BANK_AUDIT_TIPS
        apy['bankaccount'] =  apy['bankaccount'][-4:]
        # 审核关闭 或者 银行反馈失败
        if (apy['status'] == UserDefine.BANK_APPLY_CLOSED or
                apy['sync_tl_status'] == UserDefine.BANK_SYNC_FAIL):
            audit_info['state'] = UserDefine.BANK_APPLY_STATE_FAIL
            audit_info['title'] = tips['fail']['title'].format(apy)
            audit_info['content'] = []
            memo = get_audit_memo(apy['operatorinfo'])
            sync_memo = apy.get('sync_memo', '')
            if memo:
                audit_info['content'].append(memo)
            if sync_memo:
                audit_info['content'].append(sync_memo)
        # 审核中
        else:
            audit_info['title'] = tips['auditing']['title'].format(**apy)
            audit_info['content'] = tips['auditing']['content']
            audit_info['state'] = UserDefine.BANK_APPLY_STATE_ING
        return audit_info

    _base_err = '获取银行卡信息失败'

    @check('login')
    def GET(self):
        userid = int(self.user.userid)
        r = apcli.userprofile_by_id(userid)
        if not r:
            raise ParamError('未获取到银行卡信息')

        return self.write(success({
            'bankinfo':self._resolve(r['bankInfo']),
            'audit_info' : self._get_audit_info(userid)}))

class Change(BaseHandler):
    '''
    修改用户信息
    '''

    _validator_fields = [
        Field('shopname', T_STR),
        Field('location', T_STR),
        Field('address', T_STR),
        Field('telephone', T_STR),
        Field('longitude', T_FLOAT),
        Field('latitude', T_FLOAT),
        Field('logo_url', T_STR),
        Field('head_img', T_STR),
        Field('city', T_STR),
        Field('province', T_STR),
        Field('provinceid', T_STR),
    ]

    def update_ext(self, data):
        user_ext = UserExt(uid = int(self.user.userid))
        user_ext.head_img = data.get('head_img')
        user_ext.logo_url = data.get('logo_url')
        user_ext.contact = data.get('telephone', '')

        apcli('bindUserExt', user_ext)

    def update_apollo(self, data):
        val = {}
        for k in ('telephone', 'shopname', 'longitude', 'latitude'):
            if data[k]:
                val[k] = data[k]

        # 店铺地址
        if data['address'] or data['location']:
            addr = ((data['location'] or '') +
                    (data['address'] or ''))
            if not addr.startswith(self._user.city or ''):
                addr = (self._user.city or '') + addr
            val['businessaddr'] = val['address'] = addr

        if not val:return

        apcli_ex('updateUser', int(self.user.userid), User(**val))

    _base_err = '修改用户信息失败'

    @check(['login', 'validator'])
    def POST(self):
        data = self.validator.data
        values = {k:v for k, v in data.iteritems() if v is not None}
        if not values:
            return self.write(success({}))

        userid = int(self.user.userid)
        user = apcli_ex('findUserBriefById', userid)
        if not user:
            user = UserBrief(city='', uid=userid, province='')
        self._user =  user

        # 判断省份是否相同
        if (getattr(config, 'CHANGE_SAME_PROVINCE', True) and
                user.province and
                data['province'] and
                user.province != data['province']):
            raise ParamError('不能修改所在省')

        self.update_ext(data)

        self.update_apollo(data)

        return self.write(success({}))



class Change_v1(BaseHandler):
    '''
    修改商户名称
    '''

    _validator_fields = [
        Field('nickname', T_STR),
    ]


    @check_login
    @with_validator()
    @raise_excp('修改商户名称失败')
    def POST(self):
        data = self.validator.data
        values = {k:v for k, v in data.iteritems() if v is not None}
        import datetime
        data['nickname'] = data['nickname'].decode('utf-8','ignore')


        if not values:
            return self.write(success({}))

        userid = int(self.user.userid)
        user = apcli_ex('findUserBriefById', userid)
        if not user:
            user = UserBrief(city='', uid=userid, province='')

        dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        userids = []
        with get_connection('qf_mis') as db:
            userids = db.select(
                table='merchant_change_apply',
                where={'userid': ('in', [int(userid)]), 'changetype': ('in', [int(2)]), 'status': ('in', [1])},
                fields='id,userid,applyjson,status,createtime,modifytime,auditmemo')
        ret = userids

        if ret:
            return self.write(success({}))


        userids = []
        with get_connection('qf_mis') as db:
            userids = db.select(
                table='merchant_change_apply',
                where={'userid': ('in', [int(userid)]), 'changetype': ('in', [int(2)]), 'status': ('in',[3,4])},
                fields='id,userid,applyjson,status,createtime,modifytime,auditmemo')
        ret = userids

        pids = []
        with get_connection('qf_core') as db:
            pids = db.select(
                table='profile',
                where={'userid': ('in', [int(userid)])},
                fields='nickname')
        pet = pids

        if pet:
            _old = pet[0]['nickname']
        else:
            _old = ''

        _newname = data['nickname']
        _old = _old
        userid = str(userid)

        audit_data = {
            'userid': userid,
            'status': 1,
            'auditmemo':'',
            'changetype': 2,
            'reason': '来自客户端',
            'source': 5,
            'createtime': dt,
            'applyjson': '{"original": {"userid": "%s","nickname": "%s"}, "change_apply": {"nickname": "%s"}}' % (userid,_old,_newname)
        }


        if ret:
            with get_connection('qf_mis') as db:
                db.update('merchant_change_apply', audit_data, where={'id':ret[0]['id']})
        else:
            with get_connection('qf_mis') as db:
                db.insert('merchant_change_apply', audit_data)


        return self.write(success({}))


class Apply_info(BaseHandler):
    '''
    获取审核信息
    '''

    _validator_fields = [
        Field('mode', T_STR),
    ]


    @check_login
    @with_validator()
    @raise_excp('获取审核信息失败')
    def GET(self):
        data = self.validator.data
        values = {k:v for k, v in data.iteritems() if v is not None}

        if not values:
            return self.write(success({}))
        userid = int(self.user.userid)
        user = apcli_ex('findUserBriefById', userid)
        if not user:
            user = UserBrief(city='', uid=userid, province='')

        userids = []
        with get_connection('qf_mis') as db:
            userids = db.select(
                    table = 'merchant_change_apply',
                    where = {'userid': ('in',[int(userid)]),'changetype': ('in',[int(2)])},
                    fields = 'userid,applyjson,status,createtime,modifytime,auditmemo')
        ret = userids

        if ret:
            ret = ret[0]
        else:
            return self.write(success({
                'status': 3
            }))

        _applyjson = json.loads(ret['applyjson'])

        log.info("userid :%s",userid)

        if ret['status'] == 2:
            ret['status'] = 1

        return self.write(success({
            'change': _applyjson['change_apply']['nickname'],
            'auditmemo': ret['auditmemo'],
            'createtime': ret['createtime'],
            'audittime': ret['modifytime'],
            'status': ret['status']
        }))

class MchntInfo(BaseHandler):
    '''
    获取商户基础信息接口
    '''

    @check_login
    @raise_excp('获取商户基础信息失败')
    def GET(self):
        userid = int(self.user.userid)

        ret = {}
        userinfo = apcli('findUserByid', userid).__dict__
        ret['shopinfo'] = {}
        ret['shopinfo']['shopname'] = userinfo.get('shopname')
        ret['shopinfo']['city'] = userinfo.get('city')
        ret['shopinfo']['province'] = userinfo.get('province')
        ret['shopinfo']['telephone'] = userinfo.get('telephone')
        ret['shopinfo']['address'] = userinfo.get('address')

        # 同步审核后的商户名称
        apply_info = {}
        with get_connection('qf_mis') as db:
            apply_info = db.select_one(
                table = 'merchant_change_apply',
                where = {
                    'userid': userid, 'changetype': 2,
                    'status': 3
                },
                fields = 'applyjson',
                other = 'order by modifytime desc'
            )

        val = {}
        if apply_info:
            apply_dict = json.loads(apply_info['applyjson'])
            val['shopname'] = unicode_to_utf8(apply_dict['change_apply']['nickname'])
            if val['shopname'] != ret['shopinfo']['shopname']:
                apcli_ex('updateUser', int(userinfo['uid']), User(**val))
                ret['shopinfo']['shopname'] = val['shopname']

        return success(ret)


class VoucherInfo(BaseHandler):
    @openid_or_login
    @with_database('qf_mis')
    def GET(self):
        voucher_list = []
        token = ''
        try:
            uid = int(self._userid) if self._userid else 0
            vouchers = self.db.select('mis_upgrade_voucher',where={'user_id':uid})
            log.info("voucher :%s",vouchers)
            for v in vouchers:
                voucher_list.append({
                    'name'          :   v['name'],
                    'name_cn'       :   CERT_NAME.get(v['name']) if CERT_NAME.has_key(v['name']) else CERT_NAME.get(OLD2NEW_CERT.get(v['name'],''),''),
                    'url_middle'    :   self.makeImgurl(uid,v['name'],v['imgname'],'middle'),
                })
            token = hids.encode(uid,uid)
        except:
            log.warn('get vouchears fail: %s' % traceback.forat_exc())
            return self.write(error(QFRET.DBERR,respmsg='数据库错误'))
        return self.write(success({'token':token,'voucher_list':voucher_list}))


    def makeImgurl(self,userid, oldimgname, newimgname, size):
        '''
        生成图片
        '''
        sizesuffix = ""
        imgnamesuffix = newimgname
        if newimgname:
            sizesuffix = ""
            if size != 'original':
                sizesuffix = size + '_'
        else:
            sizesuffix = size + '_'
            imgnamesuffix = oldimgname

        return 'http://pic.qfpay.com/userprofile/%d/%d/%s%s' % (userid / 10000, userid, sizesuffix, imgnamesuffix)


class ResetPwd(UserBase):
    '''重置密码

    调用apollo修改密码

    Params:
        mode: change,reset (change不会验证code)
        src:
            大商户修改子商户密码: big-submchnt
            商户修改密码: mchnt
        code:
            mode为change时必传
        mobile: 商户手机号
        username: 商户登录账号
    '''

    MODE_REG = r'^(change|reset)$'
    SRC_REG = r'^(big-submchnt|mchnt)$'

    _validator_fields = [
        Field('src', T_REG, match=SRC_REG, default='mchnt'),
        Field('mode', T_REG, match=MODE_REG, default='reset'),
        Field('password', T_REG, match='^\S{6,20}$', isnull=False),
        Field('code', T_STR),
        Field('mobile', T_STR),
        Field('username', T_STR),
        Field('sub_username', T_STR),
    ]

    def get_userid(self, change_user):
        where = {}
        if re.match(MOBILE_PATTERN, change_user):
            where = {'mobile': change_user}
        elif re.match(EMAIL_PATTERN, change_user):
            where = {'email': change_user}
        else:
            where = {'username': change_user}

        # 商户是否存在
        user = None
        with get_connection('qf_core') as db:
            user = db.select_one('auth_user',
                    where = where, fields = 'id')
        if not user:
            raise ParamError('商户不存在')

        return user['id']

    def check_link(self, big_uid, userid):
        big_uids = apcli_ex('getUserReverseRelation', userid, 'merchant')
        big_uids = [i.userid for i in big_uids or []]
        if big_uid not in big_uids:
            raise ParamError('不能修改非自己子商户的密码')

    @check('validator')
    def POST(self):
        self.req.inputjson()['password'] = '*****'
        data = self.validator.data

        change_user = data['username'] or data['mobile']

        # 重置密码
        if data['mode'] == 'reset':
            if not data['code']:
                raise ParamError('验证码不能为空')

            if not change_user:
                raise ParamError('修改账号不能为空')
            # 验证验证码
            if not check_smscode(data['code'], change_user, 1):
                raise ParamError('验证码错误')

            userid = self.get_userid(change_user)

        # 修改密码
        else:
            if self.check_login():
                if data['src'] == 'big-submchnt':
                    userid = self.get_userid(change_user)
                    self.check_link(int(self.user.userid), userid)
                else:
                    userid = int(self.user.userid)
            else:
                raise SessionError('商户未登录')

        # 调用apollo修改密码
        apcli('changePwd', userid, data['password'])

        # 剔除所有正在登陆的商户
        kick_user(userid, mode='not_opuser')

        # 将商户从名单剔除
        self.kick_sign_tag(userid)

        return self.write(success({}))


class Protocol(BaseHandler):
    '''
    协议与条款
    '''

    @check_login
    @raise_excp('获取协议与条款失败')
    def GET(self):
        protocol = get_qd_conf_value(mode=None, key='protocol',
                                     groupid=self.get_groupid()) or []

        return self.write(success({'protocol' : protocol}))

class CSInfo(BaseHandler):
    '''
    获取商户客服信息
    '''

    @check_login
    @raise_excp('获取客服信息失败')
    def GET(self):
        csinfo = get_qd_conf_value(mode=None, key='csinfo',
                                     groupid=self.get_groupid()) or []
        return self.write(success({'csinfo': csinfo}))

class TabBadge(BaseHandler):
    '''
    导航栏标记
    '''

    _validator_fields = [
        Field('msg_stamp', T_INT, default=0),
        Field('data_stamp', T_INT, default=0),
    ]

    def _get_data_badges(self):
        timestamp = self.validator.data['data_stamp']
        if not timestamp: return 0

        badges = 0
        with get_connection('qf_mchnt') as db:
            badges = db.select_one(
                     table= 'actv_effect',
                     fields= 'count(1) as num',
                     where= {
                         'userid' : int(self.user.userid),
                         'ctime' : ('>', timestamp),
                     }
                    )['num']

        return badges

    def _get_msg_badges(self):
        timestamp = self.validator.data['msg_stamp']
        if not timestamp: return 0
        badges = 0

        try:
            badges = ms_redis_pool.zcount('merch_msg_{}_me'.format(self.user.userid),
                                           timestamp+1, '+inf')
        except:
            log.warn(traceback.format_exc())

        return badges

    @check_login
    @with_validator()
    @raise_excp('获取标记失败')
    def GET(self):
        ret = {}
        ret['data_badges'] = self._get_data_badges()
        ret['msg_badges'] = self._get_msg_badges()

        ret['total'] = sum(ret.values())

        return self.write(success(ret))


class SetManagePassword(BaseHandler):
    '''
    设置商户的管理密码
    '''

    @check("login")
    def POST(self):
        params = {k: str(v).strip() for k, v in self.req.input().iteritems()}
        passwd = params.get("password", '')
        code = params.get("code", '')
        if not passwd:
            raise ParamError("缺少password参数")

        userid = self.user.userid
        uinfo = get_userinfo(userid)
        mobile = uinfo.get("mobile")

        if code and not check_smscode(code, mobile, 1):
            raise ParamError('验证码错误')

        with get_connection("qf_core") as conn:
            row = conn.select_one("extra_mchinfo", where={"userid": userid}, fields="count(1) as count")
            now = time.strftime(DATETIME_FMT)
            values = {
                        "userid": userid,
                        "manage_password": enc_password(passwd),
                        "ctime": now
                    }
            try:
                if row['count']:
                    del values['userid'], values['ctime']
                    conn.update("extra_mchinfo", values=values, where={"userid": userid})
                else:
                    conn.insert("extra_mchinfo", values=values)
                return self.write(success(data={}))
            except:
                raise DBError("数据更新失败")


class ResetManagePassword(BaseHandler):
    '''
    重置商户的管理密码
    '''

    @check("login")
    def POST(self):
        userid = self.user.userid
        params = {k: str(v).strip() for k, v in self.req.input().iteritems()}
        origin_password = params.get("origin_password", "")
        new_password = params.get("new_password", "")
        if (not origin_password) or (not new_password):
            raise ParamError("缺少参数")

        # 验证商户是否已经设置过密码
        pwd_indbm, has_set = has_set_mpwd(userid)
        if not has_set:
            raise DBError("此商户尚未设置过管理密码")

        if not check_password(origin_password, pwd_indbm):
            raise DBError("原始密码输入错误")

        with get_connection("qf_core") as conn:
            try:
                affect_line = conn.update("extra_mchinfo", where={"userid": userid},
                                      values={"manage_password": enc_password(new_password)})
                if not affect_line:
                    raise DBError("更新数据失败")
                else:
                    return self.write(success(data={}))
            except:
                log.debug(traceback.format_exc())
                raise DBError("更新数据失败")


class ChangeUsername(BaseHandler):
    '''修改用户账号'''

    _base_err = '修改信息失败'

    def check_grant_code(self, userid, code):
        # 通过什么方式验证
        mode = self.req.input().get('mode', 'mobile')

        if mode == 'mobile':
            user = apcli_ex('findUserBriefById', userid)
            if not user:
                raise ParamError('商户不存在')

            if not check_smscode(code, user.username, mode = 1):
                raise ParamError('验证信息错误')
        else:
            user = apcli_ex('findUserByid', userid)
            if not user:
                raise ParamError('商户不存在')

            if (user.idnumber or '').upper() != code.upper():
                raise ParamError('身份证验证失败')

    @check('login')
    def POST(self):
        params = self.req.input()
        userid = int(self.user.userid)

        new_username = params.get('new_username', '').strip()
        if not new_username:
            raise ParamError('新账号不能为空')

        # 验证grant_code
        grant_code = params.get('grant_code') or ''
        self.check_grant_code(userid, grant_code)

        # 验证verify_code
        verify_code = params.get('verify_code') or ''
        if not check_smscode(verify_code, new_username, mode = 1):
            raise ParamError('验证信息错误')

        # 验证新账号是否被占用
        with get_connection_exception('qf_core') as db:
            new_user = db.select_one(
                'auth_user', where = {'username' : new_username}
            )
        if new_user:
            raise ParamError('新账号已经被占用')

        # apollo接口修改username
        try:
            apcli_ex('changeUsername', userid, new_username)
        except ApolloException as e:
            raise ThirdError(e.respmsg)

        # 将现有设备踢下线
        kick_user(userid, mode='all')

        return success({})
