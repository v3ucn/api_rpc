# coding:utf-8

import traceback
import config
import logging
import time
from util import check_password, get_qd_conf_value

from utils.base import BaseHandler
from utils.tools import get_qudaoinfo, decode_from_utf8
from utils.decorator import check
from utils.language_api import get_constant
from utils.tools import apcli_ex, has_set_mpwd

from excepts import ParamError, ThirdError, UserError
from base import UserUtil
from runtime import apcli, redis_pool

from qfcommon.base.dbpool import get_connection
from qfcommon.base.qfresponse import success
from qfcommon.qfpay.apollouser import user_from_session

from qfcommon.qfpay.apollouser import ApolloUser
from qfcommon.qfpay.defines import (
    QF_USTATE_NEW, QF_USTATE_VARIFIED, QF_USTATE_ACTIVE,
    QF_USTATE_OK, QF_USTATE_DULL
)

# 允许登录的状态
ALLOW_STATE = (
    QF_USTATE_NEW, QF_USTATE_VARIFIED, QF_USTATE_ACTIVE,
    QF_USTATE_OK, QF_USTATE_DULL
)


log = logging.getLogger()


class Logout(BaseHandler):
    '''
    用户登出
    '''

    def GET(self):
        try:
            sessionid = self.get_cookie('sessionid')
            if sessionid:
                log.debug('sessionid: %s' % sessionid)
                self.resp.del_cookie('sessionid')
                user = user_from_session(sessionid, False)
                user.ses.logout()
        except:
            log.warn(traceback.format_exc())

        return self.write(success({}))


class Login(BaseHandler):
    '''
    用户登录
    '''

    def set_session(self, udid, userinfo, opuid=None, cate=None, **kw):
        ''' 设置登录session

        session包含:
            cate: bigmerchant|submerchant|merchant 商户角色
            opuid: 有表示为操作员， 无即是普通商户
            groupid: 渠道id
            language: 语言
            udid: 设备识别码
            userid: 商户userid

        '''
        user = ApolloUser(userinfo['uid'], expire = 86400*3)

        # 设置user session
        user.ses['udid'] = udid
        user.ses['groupid'] = userinfo['groupid']
        user.ses['chnlid'] = 0

        #设置登录时间
        user.ses['login_time'] = int(time.time())
        user.ses['cate'] = cate
        if hasattr(self, '_big_uid') and self._big_uid:
            user.ses['big_uid'] = self._big_uid

        # 如果是大商户, 存下他的连锁店id
        if cate == 'bigmerchant':
            relats = apcli_ex(
                'getUserRelation', int(userinfo['uid']),
                'merchant'
            ) or []
            link_ids = [i.userid for i in relats]
            user.ses['link_ids'] = link_ids

        if opuid:
            user.ses['opuid'] = str(opuid)

        for k,v in kw.iteritems():
            user.ses[k] = v

        user.login(userinfo['uid'])
        user.ses.save()

        return user.ses._sesid

    def check_op(self, userid, password, opuid):
        opuser = None
        with get_connection('qf_core') as db:
            opuser = db.select_one(
                'opuser',
                fields = 'password, opname, opuid',
                where = {
                    'userid' : userid,
                    'opuid' : int(opuid),
                    'status' : 1
                }
            )
        if not opuser:
            raise UserError('该操作员不存在')

        if not check_password(password, opuser['password']):
            self.password_error(userid, password, opuid)
            raise UserError('账号或密码有误,请重新输入')

        return {
            'opname' : opuser['opname'] or '',
            'opuid' : str(opuser['opuid']).rjust(4, '0')
        }

    def get_user(self, username):
        '''验证用户账号信息'''
        user = None
        with get_connection('qf_core') as db:
            if '@' in username:
                where = {'auth_user.email': username}
            else:
                where = {'auth_user.username': username}
            user = db.select_join_one(
                table1 = 'auth_user', table2= 'profile',
                on = {
                    'auth_user.id': 'profile.userid'
                },
                where = where,
                fields = (
                    'auth_user.id as userid, auth_user.state, '
                    'auth_user.password, profile.groupid'
                )
            )

        # 若用户未注册
        if not user:
            raise ParamError('您的账号未注册，请先注册一下吧')

        # 若用户状态错误
        elif user['state'] not in ALLOW_STATE:
            phone = get_qd_conf_value(mode='phone',
                key='csinfo', groupid=user['groupid'])
            errinfo = get_constant(
                '账号状态有问题哟，联系客服问问吧。电话',
                self.get_language()
            )
            raise UserError(errinfo+decode_from_utf8(phone))

        return user

    pwderr_fmt = 'mchnt_api_{userid}_{opuid}_{udid}'

    pwderr_conf = getattr(
        config, 'PWDERR_CONF',
        {'cnt': 5, 'time': 60 * 60, 'retry_time': 60 * 30},
    )

    def password_error(self, userid, password, opuid=None):
        '''密码错误'''
        log.debug('[userid:%s opuid:%s password:%s]错误密码' % (userid, opuid, password))

        if self.pwderr_conf.get('can_many_pwderr'): return

        redis_key = self.pwderr_fmt.format(
            userid=userid, opuid=opuid or 0, udid=self.req.input().get('udid')
        )

        if not redis_pool.get(redis_key):
            redis_pool.set(redis_key, 1, self.pwderr_conf['time'])

        else:
            redis_pool.incr(redis_key)

    def check_user(self, userid, opuid):
        if self.pwderr_conf.get('can_many_pwderr'): return

        redis_key = self.pwderr_fmt.format(
            userid=userid, opuid =opuid or 0, udid=self.req.input().get('udid')
        )

        # 密码错误频繁, 用户需要稍后重试
        pwderr_cnt = int(redis_pool.get(redis_key) or 0)
        if pwderr_cnt >= self.pwderr_conf['cnt']:
            if pwderr_cnt == self.pwderr_conf['cnt']:
                retry_time = self.pwderr_conf['retry_time']
                redis_pool.incr(redis_key)
                redis_pool.expire(redis_key, retry_time)
            else:
                retry_time = redis_pool.ttl(redis_key)

            errinfo = '密码错误频繁, 请{}分钟后重试'.format(retry_time / 60)
            raise UserError(errinfo)

    _base_err = '账号或密码有误,请重新输入'

    @check()
    def POST(self):
        params = self.req.input()
        username = params['username']
        password = params['password']
        udid = params.get('udid')
        opuid = params.get('opuid')
        params['password'] = '******'

        user = self.get_user(username)
        opinfo = None

        self.check_user(user['userid'], opuid)

        if opuid:
            opinfo = self.check_op(user['userid'], password, opuid)

        else:
            if not check_password(password, user['password']):
                self.password_error(user['userid'], password)
                raise UserError('账号或密码有误,请重新输入')

        # 获取用户信息
        userinfo = apcli.user_by_id(user['userid'])
        if not userinfo:
            log.debug('[username:{} pwd:{}]'.format(username, password))
            raise ThirdError('账号或密码有误,请重新输入')

        # 线下店铺信息
        user_ext = apcli_ex('getUserExt', int(userinfo['uid']))

        cf = {}

        # 线下店铺信息
        cf['cate'] = self.get_cate(userinfo['uid'], userinfo['userCates'])

        # 如果禁止大商户登录
        if (not getattr(config, 'BIGMCHNT_LOGIN_ALLOWED', True) and
            cf['cate'] == 'bigmerchant'):
            raise ParamError('商户角色错误')

        # 获取渠道信息
        cf['qdinfo'] = self._qdinfo = get_qudaoinfo(userinfo['groupid'])

        # 设置用户session
        sid = self.set_session(
            udid=udid, userinfo=userinfo,
            opuid=opuid, cate=cf['cate'],
            language=self._qdinfo['language']
        )

        # 支持刷卡设备获取terminalids
        terminalids = []
        user_agent = self.req.environ.get('HTTP_USER_AGENT','').upper()

        if any(True for i in config.UA_CARD if i in user_agent):
            terms = None
            with get_connection('qf_core') as db:
                terms = db.select(
                    'termbind', where= {'userid': user['userid']},
                    fields=  'terminalid')
            terminalids = [i['terminalid'] for i in terms or []]

        ret = UserUtil.ret_userinfo(
            userinfo, user_ext, sessionid= sid,
            opinfo= opinfo, terminalids= terminalids,
            **cf
        )

        self.resp.set_cookie('sessionid', sid, **config.COOKIE_CONFIG)

        conf_group_client_url = config.GROUP_CONF_CLIENT_URL.get(str(userinfo['groupid']),
                                                                 config.DEFAULT_CLIENT_URL)
        ret['pay_url'] = conf_group_client_url.get("pay_url",
                                                   config.DEFAULT_CLIENT_URL.get("pay_url"))
        ret['pay_trade_query_url'] = conf_group_client_url.get("pay_trade_query_url",
                                                               config.DEFAULT_CLIENT_URL.get("pay_url"))
        _, has_set = has_set_mpwd(user['userid'])
        ret['has_set_mpwd'] = 1 if has_set else 0
        return success(ret)
