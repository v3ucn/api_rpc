# encoding:utf-8

import re
import config
import traceback
import logging
log = logging.getLogger()
from runtime import apcli

from excepts import SessionError, ParamError

from .valid import is_valid_int
from .tools import groupid_cache, get_qudaoinfo
from .decorator import data_funcs, with_customer

from qfcommon.web.core import Handler
from qfcommon.qfpay.apollouser import ApolloUser

# 从useragent中获取language
UA_LANGUAGE_PATTERN = re.compile('Language[\:\/]([\w-]*)')


class BaseHandler(Handler):

    def initial(self):
        self.set_headers({'Content-Type': 'application/json; charset=UTF-8'})

    @with_customer
    def get_cid(self):
        '''
        获取customer_id
        '''
        if not self.customer.is_login():
            raise SessionError('用户未登录')

        return self.customer.customer_id


    def get_language(self, userid=None):
        ''' 获取商户的语言

        从useragnet中获取, 若没有从session中获取，
        session中如果没有从渠道获取对应的语言
        '''

        if hasattr(self, '_language'):
            return self._language

        language = 'zh-cn'
        # 从useragent获取
        try:
            ua = self.req.environ.get('HTTP_USER_AGENT','')
            groups = UA_LANGUAGE_PATTERN.search(ua)
            self._language = groups.group(1).lower()
            return self._language
        except:
            pass

        # 从session中获取
        try:
            self._language = self.user.ses.data['language']
            return self._language
        except:
            pass

        # 从渠道中获取
        groupid = self.get_groupid(userid=userid)
        if groupid:
            language = get_qudaoinfo(groupid)['language'].lower()
            try:
                self.user.ses.data['language'] = language
            except:
                pass
        self._language = language

        return language


    def get_cate(self, userid=None, cates=None):
        ''' 用户角色

        salesman 和 qudao 回自动忽略

        Params:
            userid: 商户userid，不传即从self.user获取
            cates: 商户角色, 不传将自动获取
        Returns:
            bigmerchant: 大商户
            submerchant: 子商户
            merchant: 商户
        '''
        try:
            if not userid:
                return self.user.ses.data['cate']
        except:
            pass

        if cates is None:
            try:
                userid = userid or self.user.userid
                if userid:
                    cates = apcli.get_user_cate(userid)
            except:
                cates = []

        if not userid:
            return 'merchant'

        cate_dict = {cate['code'] for cate in cates or []}
        if 'bigmerchant' in cate_dict:
            cate = 'bigmerchant'
        else:
            big_uid = apcli.reverse_userids(userid, 'merchant')
            if big_uid:
                self._big_uid = big_uid[0].userid
                cate = 'submerchant'
            else:
                cate = 'merchant'

        try:
            self.user.ses.data['cate'] = cate
        except:
            pass

        return cate

    def check_login(self):
        '''
        method: 验证商户是否登录
        return: 是否登录并会将session值写入self
        '''
        try:
            sessionid = self.get_cookie('sessionid')
            self.user = ApolloUser(sessionid=sessionid)
            if not self.user.is_login():
                return False
        except:
            log.warn('check_login error: %s' % traceback.format_exc())
            return False
        return True

    def check_ip(self):
        '''验证ip'''
        ips = (getattr(config, 'IP_LIMIT', None) or
            ('192.30.*.*', '192.10.*.*', '127.0.0.1','172.100.*.*'))
        remote_ip = self.req.clientip()
        for ip in ips:
            index = ip.find('*')
            if ((index == -1 and remote_ip == ip) or
                remote_ip[:index - 1] == ip[:index - 1]):
                    return True
        log.debug(remote_ip)
        return False

    def get_groupid(self, userid=None, **kw):
        '''获取商户的groupid'''
        groupid = None
        try:
            if not userid:
                return self.user.ses.data['groupid']
        except:
            pass

        try:
            userid = userid or self.user.userid
        except:
            userid = None

        if userid:
            try:
                groupid = groupid_cache[int(userid)]
                self.user.ses.data['groupid'] = groupid
            except:
                #log.debug(traceback.format_exc())
                pass

        return groupid


    def is_baipai(self, groupid):
        '''是否是白牌商户'''
        return int(groupid in config.BAIPAI_GROUPIDS)


    def get_big_uid(self, userid=None):
        '''
        获取商户的大商户id
        '''
        big_uid = None
        try:
            if not userid:
                return self.user.ses.data['big_uid']
        except:
            pass

        try:
            userid = userid or self.user.userid
        except:
            userid = None

        if userid:
            try:
                relate = apcli('getUserReverseRelation',
                               int(userid), 'merchant')
                big_uid = relate[0].userid if relate else 0

                self.user.ses.data['big_uid'] = big_uid
            except:
                return big_uid

        return big_uid

    def get_userids(self, userid=None):
        '''获取商户列表

        Params:
            userid:商户userid

        Returns:
            若商户为大商户的子商户时, 返回大商户id和商户id列表
            否则返回的列表仅包含商户id
        '''

        userids = [userid] if userid else [self.user.userid]
        big_uid = self.get_big_uid(userid)
        if big_uid:
            userids.append(big_uid)
        return userids

    def get_link_ids(self, userid=None):
        '''获取大商户的子商户id列表'''
        cate = self.get_cate(userid)
        if cate != 'bigmerchant':
            return []

        link_ids = None
        try:
            if not userid:
                return self.user.ses.data['link_ids']
        except:
            pass

        try:
            userid = userid or self.user.userid
        except:
            userid = None

        if userid:
            try:
                relats = apcli(
                    'getUserRelation', int(userid),
                    'merchant'
                ) or []
                link_ids = [i.userid for i in relats]

                self.user.ses.data['link_ids'] = link_ids
            except:
                return link_ids

        return link_ids

    def get_userid_login_or_ip(self):
        '''
        通过session或者ip获取userid
        '''
        userid = None
        # 好近商户版登陆
        if self.check_login():
            userid = self.user.userid

        # qiantai2 调用
        elif self.check_ip():
            userid = self.req.input().get('userid')

        if not is_valid_int(userid):
            raise SessionError('无操作权限')

        return userid

    def get_pageinfo(self):
        params = self.req.input()

        page = params.get('page', 0)
        pagesize = params.get('pagesize', 10)

        if not is_valid_int(page) or not is_valid_int(pagesize):
            raise ParamError('分页信息错误')

        limit = int(pagesize)

        offset = limit * int(page)

        return limit, offset


    def get_other(self, fields=None, default_field='ctime', default_type='desc'):
        params = self.req.input()

        orderby = ''
        if fields:
            order_field = params.get('order_field', default_field)
            order_type = params.get('order_type', default_type)
            fields = [i.split('.')[-1] for i in fields]
            if (order_field.split('.')[-1] not in fields or
                order_type not in ('desc', 'asc')):
                raise ParamError('排列信息错误')

            orderby = 'order by {order_field} {order_type}'.format(
                order_field=order_field, order_type=order_type)

        return (
            '{orderby} limit {limit} offset {offset}'.format(
                orderby = orderby,
                limit = int(params.get('pagesize', 10)),
                offset = int(params.get('page', 0)) * int(params.get('pagesize', 10))
            )
        )


class DecMeta(type):

    def __new__(cls, cls_nm, cls_parents, cls_attrs):
        for method in ('POST', 'GET'):
            if method in cls_attrs:
                dec_funcs = cls_attrs.get('_{}_DEC_FUNCS'.format(method), [])
                func = cls_attrs[method]
                for dec_func in dec_funcs[::-1]:
                    if callable(dec_func):
                        func = func(dec_func)
                    elif dec_func in data_funcs:
                        func = data_funcs[dec_func](func)
                cls_attrs[method] = func

        return super(DecMeta, cls).__new__(cls, cls_nm, cls_parents, cls_attrs)

class DecBase(BaseHandler):
    '''
    带装饰器的头部
    '''

    __metaclass__ = DecMeta
