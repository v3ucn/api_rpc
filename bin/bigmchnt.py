# coding=utf-8

import logging
import traceback


import config
from decorator import check_ip, check_validator
from constants import MOBILE_PATTERN
from util import check_user, remove_emoji, BaseHandler
from excepts import (
    MchntException, ParamError, ThirdError
)

from qfcommon.web.validator import Field, T_REG
from qfcommon.qfpay.apolloclient import Apollo, ApolloRet
from qfcommon.base.qfresponse import QFRET,error,success
from qfcommon.thriftclient.apollo import ApolloServer
from qfcommon.thriftclient.apollo.ttypes import User, UserCate, UserRelation, UserProfile, ApolloException
from qfcommon.base.tools import thrift_callex

log = logging.getLogger()

apocli = Apollo(config.APOLLO_SERVERS)

class ToBigMchnt(BaseHandler):
    '''
    成为大商户
    会进行限制
    '''
    fields = [
        Field('username', T_REG, match=MOBILE_PATTERN, isnull=False),
        Field('password', T_REG, match='^\S{6,20}$', isnull=False),
        Field('shopname', isnull=False),
    ]

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {i:d[i] for i in ['username', 'password', 'shopname']}
        user = check_user(d.get('username'))
        if user['is_signup']:
            raise ParamError('该用户已经注册，请更换手机号')

        r['shopname'] = remove_emoji(r['shopname'])
        if not r['shopname']:
            raise ParamError('店名不能为空')

        return r

    def _get_UserProfile(self, d):
        '''用户信息'''
        def get_UserCate():
            return UserCate(code='bigmerchant', name='大商户')

        def get_User():
            p = {}
            p['mobile']  = d['username'] # 用户名
            p['password'] = d['password'] # 密码
            p['shopname'] = d['shopname'] # 店铺名
            p['userCates'] = [get_UserCate()]
            return User(**p)

        return UserProfile(user=get_User())

    @check_ip()
    @check_validator()
    def POST(self):
        try:
            # 转换输入
            d = self._trans_input()

            # 当商户已经注册时，提示错误
            userid, respmsg = apocli.signup(self._get_UserProfile(d), allow_exist=False)
            if not userid:
                raise ThirdError(respmsg)
            return self.write(success({}))
        except MchntException, e:
            log.warn('ToBigMchnt error: %s' % e)
            return self.write(error(e.errcode, respmsg=e.errmsg))
        except:
            log.warn('ToBigMchnt error: %s' % traceback.format_exc())
            return self.write(error(QFRET.PARAMERR, respmsg='注册失败，请稍后再试'))

class BindMchnt(BaseHandler):
    '''
    关联商户
    只验证ip
    '''

    def _check_user(self, username, password):
        try:
            thrift_callex(config.APOLLO_SERVERS, ApolloServer, 'checkUser', username, password)
        except ApolloException, e:
            if e.respcd == ApolloRet.APOLLO_ERR_USER_NOT_EXIST:
                raise ParamError('该账号未注册')
            elif e.respcd == ApolloRet.APOLLO_ERR_PASSWD:
                raise ParamError('账号、密码不匹配')
            else:
                raise ParamError('验证失败，请稍候再试')

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        log.info('input:%s' % d)
        r = {}

        # 验证userid
        r['userid'] = int(d.get('userid') or 0)
        if not r['userid']:
            raise ParamError('大商户userid不能为空')
        # 该商户是否是大商户
        bm = apocli.user_by_id(r['userid'])
        cate = next((i for i in bm['userCates'] or [] if i['code'] in ('bigmerchant', )), 0)
        if not bm or not cate:
            raise ParamError('该商户不是大商户')

        # 验证子商户信息
        self._check_user(d.get('username'), d.get('password'))
        user = apocli.user_by_mobile(d['username'])
        r['linkid'] = user['uid']
        if next((1 for i in user['userCates'] or [] if i['code'] in ('bigmerchant',)), 0):
            raise ParamError('该店不能被添加为分店')
        # 检验是否是子商户
        if apocli.reverse_userids(r['linkid'], 'merchant'):
            raise ParamError('该店已是别人的分店')

        # 检验子商户银行卡信息
        m = apocli.userprofile_by_id(r['linkid'])
        if (m['bankInfo']['bankuser'] or '') != (d.get('bankuser') or ''):
            raise ParamError('收款人姓名输入有误')
        if (m['bankInfo']['bankaccount'] or '') != (d.get('bankaccount') or ''):
            raise ParamError('银行卡号输入有误')

        return r

    def POST(self):
        try:
            # 转换并验证输入
            d = self._trans_input()

            # 关联老商户
            relation = UserRelation(userid=d['linkid'], link_cate='merchant')
            if not apocli.set_user_relation(d['userid'], relation)[0]:
                raise ParamError('关联失败，请稍候再试')

            return self.write(success({}))

        except MchntException, e:
            log.warn('BindMchnt error: %s' % e)
            return self.write(error(e.errcode, respmsg=e.errmsg))
        except:
            log.warn('BindMchnt error: %s' % traceback.format_exc())
            return self.write(error(QFRET.PARAMERR, respmsg='关联失败，等会儿再来试一试吧'))
