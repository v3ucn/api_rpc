# encoding:utf-8

import os
import re
import types
import traceback
import logging
import urlparse
import urllib
import math
import config
import json

from math import (
    radians, atan, tan, sin, cos, acos
)

from constants import MOBILE_PATTERN
from runtime import apcli, qfcache, redis_pool
from excepts import ParamError, ThirdError, DBError

from .valid import is_valid_int

from qfcommon.web.cache import CacheDict
from qfcommon.server.client import ThriftClient
from qfcommon.thriftclient.spring import Spring
from qfcommon.thriftclient.captcha import CaptchaServer
from qfcommon.thriftclient.qudao import QudaoServer
from qfcommon.thriftclient.salesman import SalesmanServer, ttypes as salesman_ttypes
from qfcommon.conf import SESSION_CONF
from qfcommon.thriftclient.session import Session

from qfcommon.base.dbpool import (
    get_connection, get_connection_exception
)
from qfcommon.base.tools import thrift_callex

log = logging.getLogger()


unicode_to_utf8 = lambda v: v.encode('utf-8') if isinstance(v, unicode) else str(v)
decode_from_utf8 = lambda v: v if isinstance(v, unicode) else v.decode('utf-8')

# 手机号
re_mobile = re.compile(MOBILE_PATTERN)

def url_add_query(url, d):
    try:
        o = urlparse.urlparse(url)
        query = urlparse.parse_qs(o.query)
        query.update(d)
        return  o._replace(query=urllib.urlencode(query, doseq=True)).geturl()
    except:
        log.warn('url_add_query error:%s' % traceback.format_exc())
        raise ParamError('param error')

def apcli_ex(func, *args, **kw):
    ret = None
    try:
        ret = apcli(func, *args, **kw)
    except:
        log.debug(traceback.format_exc())

    return ret

def fen_to_yuan(amt):
    '''
    将分转化为元
    '''
    if not is_valid_int(amt):
        raise ParamError('amt必须为整数')

    yuan = amt / 100.0

    return str(int(yuan)) if int(yuan) == yuan else str(yuan)

# 统计字符串长度
def str_len(s):
    try:
        l = len(s or '')
        return len(s.decode('utf-8'))
    except:
        return l

def getid():
    '''通过spring生成id'''
    return ThriftClient(config.SPING_SERVERS, Spring).getid()

def getids(num=1):
    '''通过spring生成id'''
    if num:
        return ThriftClient(config.SPING_SERVERS, Spring).getids(num)

def remove_emoji(data):
    """
    去除表情
    :param data:
    :return:
    """
    if not data:
        return data
    if not isinstance(data, basestring):
        return data

    try:
        data = data.decode('utf-8')
    except:
        data = data

    try:
    # UCS-4
        patt = re.compile(u'([\U00002600-\U000027BF])|([\U0001f300-\U0001f64F])|([\U0001f680-\U0001f6FF])')
    except re.error:
    # UCS-2
        patt = re.compile(u'([\u2600-\u27BF])|([\uD83C][\uDF00-\uDFFF])|([\uD83D][\uDC00-\uDE4F])|([\uD83D][\uDE80-\uDEFF])')

    return unicode_to_utf8(patt.sub('', data))

def load_relations(relation=None):
    '''
    获取所有关系
    '''
    relations = apcli_ex('getRelationDict', [], 'merchant')

    r = {}
    for userid,linkids in relations.iteritems():
        for linkid in linkids:
            r[linkid] = userid
    return r
qfcache.set_value('relation', None, load_relations, 3600)

def get_relations():
    return qfcache.get_data('relation')


def check_smscode(code, mobile, mode=0):
    '''验证验证码

    通过captcha服务验证验证码

    Params:
        code: 验证码
        mobile: 手机号
        mode: 0 验证后不删除, 1:验证后删除code, 2:验证后删除ucode下的所有code

    '''
    try:
        ret = thrift_callex(config.CAPTCHA_SERVERS, CaptchaServer,
                'captcha_check_ex', code=code, mode=mode, ucode=mobile,
                src=config.CAPTCHA_SRC)
        if not ret:
            return True

    except:
        log.warn(traceback.format_exc())

    return False

def hide_str(ostr, mode='mobile', isnull=True):
    if not ostr and isnull:
        return ostr

    ostr = decode_from_utf8(ostr or '')

    if mode == 'name':
        return (ostr[:1] or '*') + '**'

    str_len = len(ostr)
    per_len = int(math.ceil(str_len / 3.0))
    post = per_len
    pre = (str_len - post) / 2
    hide = str_len - post - pre

    return ostr[:pre] + '*'*hide + ostr[-post:]

def get_value(values, platform, version):
    # 若非字典
    if not isinstance(values, types.DictType):
        return values

    # 有版本号和平台
    if version and platform:
        try:
            _max = None,
            for k,v in values.iteritems():
                if k.startswith(platform) or k.startswith('app'):
                    vrange = k.split('-')[1].split('~')
                    start, end= vrange[0], vrange[1] if len(vrange) > 1 else '999999'
                    if (start <= version <= end) and (_max[0] < start):
                        _max = start, v
            if _max[0]:
                return _max[1]
        except:
            log.warn('get index error:%s' % traceback.format_exc())

    return values.get('default')

def get_qd_mchnt(userid):
    '''
    获取商户的渠道信息
    '''
    try:
        client = ThriftClient(config.QUDAO_SERVERS, QudaoServer, framed=True)
        ret = client.mchnt_get([int(userid)])
    except:
        log.warn(traceback.format_exc())

    return {} if not ret else ret[0]

def get_qd_salesman(userid):
    '''
    获取业务员的信息
    '''
    log.info('req userid: %s ',str(userid))
    try:
        client = ThriftClient(config.QUDAO_SERVERS, QudaoServer, framed=True)
        ret = client.slsm_get([int(userid)])
        log.info('qudao_api ret: %s', ret)
        return ret
    except Exception, e:
        print e
        log.warn('qudao_api error: %s', str(e))
        raise ParamError('覆盖商户信息失败')


## 获取groupid
def get_groupid(userid, data=None):
    '''获取商户groupid'''
    user = apcli_ex('findUserBriefById', int(userid))

    if not user:
        raise ParamError('商户不存在')

    return user.groupid

groupid_cache = CacheDict(
    get_groupid,
    getattr(config, 'GROUPID_CACHE', 3600)
)


## 获取rate
def get_rate(foreign_currency, data=None):
    '''获取rate'''
    with get_connection('qf_core') as db:
        rate = db.select_one(
            'rate_table',
            where = {
                'foreign_currency' : foreign_currency,
                'base_currency' : getattr(config, 'BASE_CURRENCY', 'CNY')
            }
        )
        if rate:
            return rate['rate'] / (rate['unit'] * 1.0)
    return 0

rate_cache = CacheDict(
    get_rate,
    getattr(config, 'RATE_CACHE', 3600)
)

def get_userid(qd_uid, data=None):
    '''获取渠道下的所有的商户'''

    if not qd_uid:
        return []
    qd_uid = int(qd_uid)

    userid_list = []
    userids = {}
    where = {'groupid': qd_uid}
    with get_connection('qf_core') as db:
        userids = db.select(
                table = 'profile',
                fields = 'userid',
                where = where)
    userid_list = [userid['userid'] for userid in userids]
    return userid_list

userid_cache = CacheDict(
    get_userid,
    getattr(config, 'QUDAO_MCHNTID_CACHE', 3600))

def get_qudaoinfo(groupid):
    '''根据groupid获取渠道信息

    默认是中文配置, 暂时先不缓存
    '''
    qdinfo = {
        'country': 'CN', 'timezone': '+0800',
        'currency': 156, 'rate': 100,
        'currency_sign': '￥', 'language': 'zh-cn',
        'amt_limit': 6, 'allow_point': 1
    }
    try:
        if groupid:
            client = ThriftClient(config.QUDAO_SERVERS, QudaoServer, framed=True)
            qdprofile = client.qd_get_profiles([int(groupid), ]).get(groupid)
            fields = ('country', 'timezone', 'currency')
            if qdprofile:
                # 渠道相关信息
                for i in fields:
                    qdinfo[i] = getattr(qdprofile, i)

            # redis存储的扩展信息
            rkey = '_mchnt_api_curr_{}_'.format(qdinfo['currency'])
            data = redis_pool.hgetall(rkey)
            for k, v in data.iteritems():
                if k not in fields:
                    qdinfo[k] = v
    except:
        log.warn('获取渠道信息失败:%s' % traceback.format_exc())

    return qdinfo


def get_linkids(userid):
    '''
    获取子商户
    '''
    try:
        relates = apcli('getUserRelation', int(userid), 'merchant')
        linkids = [i.userid for i in relates]
    except:
        raise ThirdError('获取子商户列表失败')

    return linkids


def get_userinfo(userid):
    '''获取店铺信息

    通过apollo.findUserBriefsByIds获取商户的信息

    Params:
        userids: 商户userid,
            若userid为list或者tuple返回字典
            否则, 返回直接返回商户信息

    Raises:
        仅当apollo报错时会抛出错误
    '''
    if isinstance(userid, (list, tuple)):
        mode = 'mul'
        userids = [int(i) for i in userid]
    else:
        mode = 'one'
        userids = [int(userid)]

    try:
        userinfos = apcli('findUserBriefsByIds', userids) or []
    except:
        raise ThirdError('获取商户信息失败')

    userinfos = {i.uid:i.__dict__ for i in userinfos}

    return userinfos.get(int(userid)) if mode == 'one' else userinfos

def get_user_detail_info(userid):

    try:
        detail_info = apcli('findUserByid', userid) or {}
    except:
        raise ThirdError('获取商户详细信息失败')

    detail_info = detail_info.__dict__
    return detail_info

def get_user_bank_info(userid):

    try:
        bank_info = apcli('userprofile_by_id', userid)['bankInfo'] or {}
    except:
        raise ThirdError('获取商户详细信息失败')

    return bank_info

get_imgurl = lambda userid, out_name: os.path.join('http://pic.qfpay.com/userprofile', os.path.join(str(userid/10000), str(userid)), out_name)

# 根据userid, 凭证name列表获取商户的图片url
def get_img_info(userid, cert_names):
    try:
        voucher_list = []
        with get_connection("qf_mis") as db:
            vouchers = db.select("mis_upgrade_voucher",
                                 fields="name, imgname",
                                 where={"user_id": userid, "name": ('in', cert_names)})
            log.info("voucher :%s", vouchers)
            for v in vouchers:
                voucher_list.append({
                    'name':   v['name'],
                    'imgurl': get_imgurl(userid, v['imgname']),
                })

        # 数据库里没有数据用''
        for cname in cert_names:
            if cname not in [v['name'] for v in voucher_list]:
                voucher_list.append({"name": cname, "imgurl": ""})

        return voucher_list
    except:
        log.debug(traceback.format_exc())
        raise DBError("数据库错误")


# 根据给定的userid判断商户是否已经设置了管理密码
def has_set_mpwd(userid=None):
    if not userid:
        raise ParamError("缺少参数userid")

    with get_connection("qf_core") as conn:
        row = conn.select_one("extra_mchinfo", where={"userid": userid}, fields="manage_password")
        if not row or not row['manage_password']:
            return '', False
        else:
            return row['manage_password'], True

def guess_user_agent(useragent):
    '''根据useragent判断终端'''
    pay_type = ''
    if 'MicroMessenger' in useragent:
        pay_type = 'weixin'

    elif 'WalletClient' in useragent:
        pay_type = 'jdpay'

    elif 'AlipayClient' in useragent:
        pay_type = 'alipay'

    elif 'QQ' in useragent:
        pay_type = 'qqpay'

    # 好近商户app
    elif (
            useragent.startswith('nearmerchant') or
            useragent.startswith('near-merchant-android')
        ):
        pay_type = 'qfhj'

    return pay_type

def get_mysql_constants(key, data):
    try:
        with get_connection_exception('qf_mchnt') as db:
            ret = db.select_one(
                'constants', where = {'key': key, 'status': 1},
                fields = 'value, type'
            )

            if ret:
                if ret['type'] == 1:
                    return ret['value']
                else:
                    return json.loads(ret['value'])
    except:
        log.warn(traceback.format_exc())

    return data

constants_cache = CacheDict(
    get_mysql_constants,
    getattr(config, 'MYSQL_CONSTANTS_CACHE', 3600)
)


def get_big_uid(userid, data):
    # 大商户userid
    big_uid = -1
    try:
        relate = apcli('getUserReverseRelation', int(userid), 'merchant')
        if relate:
            big_uid = relate[0].userid
    except:
        log.warn(traceback.format_exc())
        return data

    return big_uid

big_uid_cache = CacheDict(
    get_big_uid,
    getattr(config, 'BIG_UID_CACHE', 24 * 3600)
)

def calcDistance(lng_a, lat_a, lng_b, lat_b):
    '''
    TODO: 由两点计算距离
    Input:
        lng_A 经度A
        lat_A 纬度A
        lng_B 经度B
        lat_B 纬度B
    output
        dist 距离
    '''
    if (lng_a, lat_a) == (lng_b, lat_b):
        return 0
    try:
        ra = 6378.140  # 赤道半径 (km)
        rb = 6356.755  # 极半径 (km)
        flatten = (ra - rb) / ra  # 地球扁率
        rad_lat_A = radians(lat_a)
        rad_lng_A = radians(lng_a)
        rad_lat_B = radians(lat_b)
        rad_lng_B = radians(lng_b)
        pA = atan(rb / ra * tan(rad_lat_A))
        pB = atan(rb / ra * tan(rad_lat_B))
        xx = acos(sin(pA) * sin(pB) + cos(pA) * cos(pB) * cos(rad_lng_A - rad_lng_B))
        c1 = (sin(xx) - xx) * (sin(pA) + sin(pB)) ** 2 / cos(xx / 2) ** 2
        c2 = (sin(xx) + xx) * (sin(pA) - sin(pB)) ** 2 / sin(xx / 2) ** 2
        dr = flatten / 8 * (c1 - c2)
        dist = ra * (xx + dr)
    except ZeroDivisionError:
        log.debug(traceback.format_exc())
        return 0
    else:
        return dist


def kick_user(userid, opuid=None, mode='all'):
    '''将用户踢下线'''
    try:
        client = ThriftClient(SESSION_CONF, Session)
        sessions = client.session_get_keys(int(userid))

        for session in sessions.keys:
            # 删除所有
            if mode == 'all':
                client.session_delete(session)
                continue

            ses_val = client.session_get(session)
            if not ses_val.value:
                continue

            value = json.loads(ses_val.value)
            # 删除非操作员
            if mode == 'not_opuser':
                if not value.get('opuid'):
                    client.session_delete(session)

            # 删除指定操作员
            elif mode == 'opuser':
                if int(value.get('opuid') or 0) == opuid:
                    client.session_delete(session)
    except:
        log.warn(traceback.format_exc())
