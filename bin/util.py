# coding: utf-8

import types
import re
import redis
import hashlib
import time, datetime
import config
import json
import logging
import traceback
import urlparse
import urllib
from cache import cache
from StringIO import StringIO
import uuid
import calendar

from copy import deepcopy
from functools import partial
from hashids import Hashids
from PIL import ImageDraw
from PIL import ImageFont
from PIL import Image

from constants import MOBILE_PATTERN, DATE_FMT, DATETIME_FMT
from qfcommon.qfpay.apolloclient import Apollo
from qfcommon.library import createid
from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.base.http_client import RequestsClient
from qfcommon.base.tools import thrift_callex
from qfcommon.thriftclient.spring import Spring
from qfcommon.thriftclient.open_user import OpenUser
from qfcommon.server.client import ThriftClient
from qfcommon.web.core import Handler
from qfcommon.qfpay.apollouser import ApolloUser
from qfcommon.thriftclient.qudao import QudaoServer, ttypes as qudao_ttypes

from runtime import qfcache
from excepts import ParamError, DBError, ThirdError, ReqError
from qiniu import Auth, put_data

from utils.tools import get_qd_salesman

log = logging.getLogger()
apcli = Apollo(config.APOLLO_SERVERS)

decode_from_utf8 = lambda v: v if isinstance(v, unicode) else v.decode('utf-8')
unicode_to_utf8 = lambda v: v.encode('utf-8') if isinstance(v, unicode) else str(v)
unicode_to_utf8_ex = lambda v: v.encode('utf-8') if isinstance(v, unicode) else v
hids = Hashids(config.QRCODE_SALT)

# redis连接池
redis_conf = config.CACHE_CONF['redis_conf']
redis_pool = redis.Redis(host=redis_conf['host'],
    port=redis_conf['port'], password=redis_conf['password'])

# 参数转化
def covert(param, func=int, default=None):
    try:
        return func(param)
    except:
        return default or (0 if func in (int, float) else '')

def params_to_str(params, not_include_key=('sign', 'sign_type'), not_include_value=('', None), fmt='%s=%s', is_sort=True):
    if isinstance(params, unicode):
        return unicode_to_utf8(params)
    elif not isinstance(params, dict):
        return ''
    msg = []
    convert_value = lambda v: '' if v is None else v
    keys = params.keys()
    is_sort and keys.sort()
    for k in keys:
        if k in not_include_key or params[k] in not_include_value:
            continue
        msg.append(fmt % (unicode_to_utf8(k), unicode_to_utf8(convert_value(params[k]))))
    return '&'.join(msg)

# 参数签名
def param2sign(params, key, charset='utf-8'):
    key = unicode_to_utf8(key)
    params_str = params_to_str(params, not_include_key=('sign', ), not_include_value=())
    md5 = hashlib.md5()
    md5.update("%s%s" % (params_str, key))
    return md5.hexdigest()

# 统计字符串长度
def str_len(s):
    try:
        l = len(s or '')
        return len(s.decode('utf-8'))
    except:
        return l

def is_valid(s, func):
    try:
        func(s)
        return True
    except:
        return False

# 判断是否是日期
is_valid_date = partial(is_valid, func=lambda s: time.strptime(s, DATE_FMT))

# 判断是否是时间
is_valid_datetime = partial(is_valid, func=lambda s: time.strptime(s, DATETIME_FMT))

# 判断是否是数字
is_valid_num= partial(is_valid, func=float)

# 判断是否是整形
is_valid_int= partial(is_valid, func=int)

# 判断是否能json.dumps
is_valid_json= partial(is_valid, func=json.dumps)

# 判断是否datetime
def is_date_type(v):
    return isinstance(v, (datetime.date, datetime.time))

# 获取相对时间
def future(st=None, years=0, months=0, weeks=0, days=0, hours=0,
    minutes=0, seconds=0, milliseconds=0, microseconds=0):
    st = st or datetime.datetime.now()
    if not is_date_type(st):
        raise ParamError('时间格式不正确')

    if seconds or minutes or hours or days or weeks:
        delta = datetime.timedelta(weeks=weeks, days=days, hours=hours,
                                   minutes=minutes, seconds=seconds,
                                   milliseconds=milliseconds,
                                   microseconds=microseconds)
        st += delta

    if months:
        addyears, months = divmod(months, 12)
        years += addyears
        if not (1 <= months + st.month <= 12):
            addyears, months = divmod(months + st.month, 12)
            months -= st.month
            years += addyears
    if months or years:
        year = st.year + years
        month = st.month + months
        try:
            st = st.replace(year=year, month=month)
        except ValueError:
            _, destination_days = calendar.monthrange(year, month)
            st = st.replace(year=year, month=month, day=destination_days)

    return st

# 将字符串的时间转换为时间戳
def str_timestamp(s, fmt):
    return int(time.mktime(time.strptime(s, fmt)))

# 将时间戳转化为字符串
def timestamp_str(stamp, fmt=DATETIME_FMT):
    return time.strftime(fmt, time.localtime(stamp))

# 两个日期相隔多少天
def str_diffdays(sDate, eDate, fmt='%Y-%m-%d'):
    return (datetime.datetime.strptime(eDate, fmt) - datetime.datetime.strptime(sDate, fmt)).days

# 两个日期相隔天的字符串列表
def str_datelist(sDate, eDate, fmt='%Y-%m-%d'):
    s = datetime.datetime.strptime(sDate, fmt)
    return [(s + datetime.timedelta(i)).strftime(fmt) for i in range(0, str_diffdays(sDate, eDate) + 1)]

def rule_json2dic(r, key):
    try:
        r = json.loads(r).get(key, {})
        dic = {}
        for i in r:
            dic[i[0]] = i[2]
    except:
        log.warn('rule_json2dic error, %s' % traceback.format_exc())
        return {}
    return dic

def json2dic(d):
    try:
        return json.loads(d)
    except:
        log.warn('rule2dic error, %s' % traceback.format_exc())
        return {}

def url_add_query(url, d):
    try:
        o = urlparse.urlparse(url)
        query = urlparse.parse_qs(o.query)
        query.update(d)
        return  o._replace(query=urllib.urlencode(query, doseq=True)).geturl()
    except:
        log.warn('url_add_query error:%s' % traceback.format_exc())
        raise ParamError('param error')

def openid2userid(openid):
    if not openid:
        raise ParamError('未获取到openid')

    try:
        r = RequestsClient().get(config.OPENAPI_URL+'/push/v2/bind_query', {'openid':openid})
        r = json.loads(r)
    except:
        log.warn('bind wx openid error: %s' % traceback.format_exc())
        raise ThirdError('第三方服务失败')

    if r['respcd'] != '0000':
        raise ThirdError(u'第三方服务返回:%s' % (r['respmsg'] or r['resperr']))

    return 0  if r['data']['userid'] == -1 else r['data']['userid']

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

# 创建id
def create_id(conn=None):
    '''创建表的id'''
    ret = 0
    if conn:
        ret = createid.new_id64(conn=conn)
    else:
        with get_connection('qf_mchnt') as conn:
            ret = createid.new_id64(conn=conn)
    return ret

def getid():
    '''通过spring生成id'''
    return ThriftClient(config.SPING_SERVERS, Spring).getid()
    #return ThriftClient(config.SPING_SERVERS, Spring, framed=True).getid()

def get_app_info(user_agent):
    if not user_agent: return None, None
    version, platform = '', ''
    try:
        user_agent = user_agent.lower()
        # ios, 样例:NearMerchant/020502 (iPhone; iOS 9.3.1; Scale/3.00)
        if user_agent.startswith('nearmerchant'):
            platform = 'ios'
            v = user_agent.split()[0].split('/')[1]
            if not v.isdigit() or len(v) not in (3, 6):
                version = '000000'
            elif len(v) == 3:
                version = '%02d%02d%02d' % (int(v[0]), int(v[1]), int(v[2]))
            else:
                version = v
        # and, 样例:Near-Merchant-Android;version_name:v1.7.2;version_code:3736;channel:haojin;model:MI 3;release:4.4.4
        elif user_agent.startswith('near-merchant-android'):
            platform = 'and'
            v = user_agent.split(';')[1].split(':')[1]
            v = v[1:] if v.startswith('v') else v
            if not ''.join(v.split('.')).isdigit():
                version = '000000'
            else:
                v = v.split('.')
                version = '%02d%02d%02d' % (int(v[0]), int(v[1]), int(v[2]))
    except:
        log.warn('get app info error:%s' % traceback.format_exc())

    return version, platform

def get_services(version, platform, default='default', addon=None, **kw):
    def get_value(values):
        # 若非字典
        if not isinstance(values, types.DictType):
            return values

        # 原始版本
        if default == 'origin':
            return values.get('default')
        # 中期版本后
        else:
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

            return values['middle'] if 'middle' in values else values.get('default')

    r, services = [], deepcopy(config.SYSTEM_SERVICES)
    if 'sys_services' in kw:
        services =  deepcopy(kw['sys_services'])

    for service in services:
        if not service['status']: continue
        t = {}
        t['link'] = get_value(service['link'])
        if t['link'] is None:
            continue
        for i in ['code', 'name', 'weight', 'icon', 'pos'] + (addon or []):
            t[i] = get_value(service.get(i, ''))
        t['is_display'] = 1
        r.append(t)

    return r

def get_lock(key, src=None, expire=5):
    '''获取锁'''
    if not key: return
    r = redis.Redis(host=redis_conf['host'],
        port=redis_conf['port'], password=redis_conf['password'])
    rkey = 'mchnt_api_lock_%s_%s_' % (key, src or '')
    if r.get(rkey):
        return False
    else:
        r.set(rkey, 1, expire)
        return True

def release_lock(key, src=None):
    '''释放锁'''
    if not key: return
    r = redis.Redis(host=redis_conf['host'],
        port=redis_conf['port'], password=redis_conf['password'])
    rkey = 'mchnt_api_lock_%s_%s_' % (key, src or '')
    r.delete(rkey)

def prelogin_lock(self):
    src = '.'.join([self.__module__, self.__class__.__name__])
    key = self.user.ses.get('userid', '')
    if not get_lock(key, src):
        self._is_release_lock = False
        raise ReqError('操作过于频繁')

def postlogin_lock(self):
    if not getattr(self, '_is_release_lock', True): return
    src = '.'.join([self.__module__, self.__class__.__name__])
    key = self.user.ses.get('userid', '')
    release_lock(key, src)

def check_user(mobile):
    '''验证用户的状态'''
    if not re.match(MOBILE_PATTERN, mobile):
        raise ValueError('手机号格式不对')

    ret = {
        'is_signup' : 0,
        'is_saleman' : 0
    }
    try:
        r = apcli.user_by_mobile(mobile)
        log.debug('r:%s' % r)
    except:
        log.warn('is_saleman, error:%s' % traceback.format_exc())
        raise ParamError('查询用户信息失败')

    if r:
        ret['is_signup']  = 1
        ret['is_saleman'] = next((1 for i in r['userCates'] or []
                                  if i['code'] == 'saleman' or i['code'] == 'qudao'), 0)
        ret['userid'] = r['uid']
        ret['groupid'] = r['groupid']

    return ret

def qiniu_upload(file_bytes, bucket_name, save_path):
    """七牛上传文件
    save_path 直接包含文件名，故此字段请在外部生成
    返回 url, 应该等于 save_path
    """
    assert bucket_name in ('honey', 'near'), '非法仓库名'
    q = Auth(config.QINIU_ACCESS_KEY, config.QINIU_SECRET_KEY)
    token = q.upload_token(bucket_name, save_path)
    ret, info = put_data(token, save_path, file_bytes, check_crc=True)
    if not ret:
        return None
    if info.exception:
        raise info.exception
    if bucket_name == 'near':
        return 'http://near.m1img.com/' + ret['key']
    elif bucket_name == 'honey':
        #return settings.PREFIX_PIC_URL + ret['key']
        return 'http://near.m1img.com/' + ret['key']

paying_goods = config.PAYING_GOODS
def get_mchnt_paying(userid, code='card_actv'):
    '''
    返回优先级最高的goods
    code: service_code
    '''
    codes = {}
    for v in paying_goods['goods']:
        if next((True for _ in v['services'] if _['code'] == code), False):
            codes[v['code']] = v['priority']

    if not codes: return None

    where = {'userid': int(userid), 'goods_code': ('in', codes.keys())}
    with get_connection_exception('qf_mchnt') as db:
        r =  db.select('recharge', where=where, fields='expire_time, status, goods_code')

    now = time.strftime(DATETIME_FMT)
    return sorted(r, key=lambda x: (bool(str(x['expire_time'])>now), codes[x['goods_code']]))[-1] if r else {}

def add_free(userid, service_code='card_actv'):
    '''
    给userid开通免费体验
    '''
    free = paying_goods.get('free')
    if not free:
        raise ParamError('该服务暂不支持免费体验')

    # 免费体验的产品
    free_code = paying_goods['free_code']
    goods = next((i for i in paying_goods['goods'] if i['code'] == free_code), None)
    if not goods:
        raise ParamError('该服务暂不支持免费体验')
    if not  next((i for i in goods['services'] if i['code'] == service_code), None):
        raise ParamError('该服务暂不支持免费体验')

    try:
        now = int(time.time())
        expire_time = str_timestamp(time.strftime(DATE_FMT), DATE_FMT)+(free+1)*24*3600-1
        d = {
            'id': getid(), 'userid': userid,
            'ctime': now, 'utime': now, 'goods_code': free_code,
            'status': 1, 'expire_time': expire_time
        }
        with get_connection_exception('qf_mchnt') as db:
            db.insert('recharge', d)
        return d['id']
    except:
        log.warn('create activity error: %s' % traceback.format_exc())
        raise DBError('开通免费体验失败')

def get_mchnt_info(userid, code='coupon'):
    '''商户付费情况'''
    paygoods = config.PAYING_GOODS
    r = get_mchnt_paying(userid, code) or {}

    # 商户状态 0:新 1:免费体验商户 2:付费商户
    r['status'] = r['status'] if r else 0
    r['overdue'] = 1

    # 剩余天数
    left_day, left_warn = 0, 0
    if r.get('expire_time'):
        r['overdue'] = 1 if time.strftime(DATETIME_FMT) > str(r['expire_time']) else 0
        left_day = max(str_diffdays(time.strftime(DATE_FMT), str(r['expire_time'])[:10]), 0)
        # 剩余天数小于5天会提醒
        left_warn = 0 if left_day > 5 else 1

        r['goods_name'] = next((i['name'] for i in paygoods['goods'] if i['code'] ==  r['goods_code']), '')
    r['left_day'] =  left_day
    r['left_warn'] = left_warn
    r['free'] = paygoods['free']

    return r

@cache()
def get_member_info(cid):
    spec = json.dumps({"user_id":cid})
    try:
        r = thrift_callex(config.OPENUSER_SERVER, OpenUser,
            'get_profiles', config.OPENUSER_APPID, spec)
        log.debug('r:%s' % r)
        return r[0].__dict__
    except:
        log.warn('get openuser_info error:%s' % traceback.format_exc())

def generate_image(bgimage, text, font_size, fill_color,
                    text_location, font_name="SimHei.ttf"):
    """
    生成图片
    bgimgage: 背景图片地址
    text: 需要添加的文字
    font_size: 文字大小
    fill_color: 字体颜色
    text_location: 文字放置的位置
    font_name: 字体名称
    """

    im = Image.open(bgimage)
    font_path = config.RESOURCE_PATH+font_name
    font = ImageFont.truetype(font_path, font_size)
    draw = ImageDraw.Draw(im)

    if isinstance(text, str):
        text = unicode(text, 'utf-8')
    text = text.replace(u'（', u'(').replace(u'）', u')')
    if len(text) > 15:
        text = text[:15]+u'...'

    font_size_w, font_size_h = font.getsize(text)

    text_location_y = text_location[1]
    text_location_x = text_location[0] + (text_location[2] - font_size_w) / 2
    text_location = (text_location_x, text_location_y)
    log.info("FILL COLOR:{}".format(fill_color))
    simg = StringIO()
    try:
        draw.text(text_location, text, font=font, fill=fill_color)
        im.save(simg, "jpeg")
    except:
        log.warn("GENERATE PIC ERR:{}".format(traceback.format_exc()))
    finally:
        im.close()
        del im

    simg.seek(0)
    img_name = str(uuid.uuid1())+".jpg"

    try:
        url = qiniu_upload(simg.read(), 'near', img_name)
        if not url:
            log.warn("UPLOAD TO QINIU ERR: URL IS None")
        return url
    except:
        log.warn("UPLOAD TO QINIU ERR:{}".format(traceback.format_exc()))
        return None

class BaseHandler(Handler):

    def initial(self):
        self.set_headers({'Content-Type': 'application/json; charset=UTF-8'})

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

    def get_groupid(self, **kw):
        '''获取商户的groupid'''
        groupid = None
        try:
            groupid = self.user.ses.data['groupid']
        except:
            userid = (self.user.userid
                      if (hasattr(self, 'user') and
                          self.user.userid)
                      else kw.get('userid'))
            if userid:
                user = apcli.user_by_id(userid)
                if user:
                    try:
                        self.user.ses.data['groupid'] = user['groupid']
                    except:
                        pass
                    groupid = user['groupid']

        return groupid

def convert_date_to_timestamp(dt):
    return int(time.mktime(dt.timetuple()))

def get_next_month(dt):
    if isinstance(dt, datetime.datetime):
        dt = dt.date()
        pass


    x = dt.replace(day=1)
    x = x + datetime.timedelta(days=33)
    x = x.replace(day=1)
    return x

def format_datetime(dt):
    if isinstance(dt, datetime.datetime):
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(dt, datetime.date):
        return dt.strftime('%Y-%m-%d')

    raise TypeError('parameter dt type should be date or datetime')

# 增强型json编码器
class ExtendedEncoder(json.JSONEncoder):
    def default(self, o):
        try:
            if type(o) == datetime.date:
                return o.strftime(DATE_FMT)
            elif type(o) == datetime.datetime:
                return o.strftime(DATETIME_FMT)
            else:
                return json.JSONEncoder(self, o)
        except:
            return str(o)

@cache()
def get_bigmchntid():
    with get_connection('qf_core') as db:
        bigmchnt = db.select('bigmerchant', fields = 'mchntid, termid',
                              where = {'available' : 1})
        return ['{}_{}'.format(i['mchntid'], i['termid']) for i in bigmchnt ]

def get_hexdigest(algorithm, salt, raw_password):
    if algorithm == 'crypt':
        try:
            import crypt
        except ImportError:
            raise ValueError('"crypt" password algorithm not supported in this environment')
        return crypt.crypt(raw_password, salt)

    if algorithm == 'md5':
        return hashlib.md5(salt + raw_password).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(salt + raw_password).hexdigest()
    raise ValueError("Got unknown password algorithm type in password.")

def constant_time_compare(val1, val2):
    if len(val1) != len(val2):
        return False
    result = 0
    for x, y in zip(val1, val2):
        result |= ord(x) ^ ord(y)
    return result == 0

def enc_password(raw_password, algo = 'sha1'):
    salt = uuid.uuid4().get_hex()[:5]
    enc_password = '%s$%s$%s' % (algo, salt, get_hexdigest(algo, salt, raw_password))
    return enc_password

def check_password(raw_password, enc_password):
    try:
        algo, salt, hsh = enc_password.split('$')
        return constant_time_compare(hsh, get_hexdigest(algo, salt, raw_password))
    except:
        log.warn(traceback.format_exc())
        return False

def load_qd_conf(qd_conf=None):
    qdconfs = None
    with get_connection('qf_mis') as db:
        qdconfs = db.select(
                table= 'qd_conf',
                where= {'status' : 1},
                fields= ('qd_uid, name, wx_pub, protocol, qrcode,'
                         'csinfo, promotion_url, service, ext'))

    if not qdconfs:
        return

    ret = {}
    load_fields = ['protocol', 'qrcode', 'csinfo', 'promotion_url', 'service', 'ext']
    for conf in qdconfs:
        t = {i:conf[i] for i in ('name', 'qd_uid', 'wx_pub') }
        for field in load_fields:
            try:
                t[field] = json.loads(conf[field])
            except:
                t[field] = None
        ret[conf['qd_uid']] = t

    return ret
qfcache.set_value('qd_conf', None, load_qd_conf, 3600)

def get_qd_conf():
    return qfcache.get_data('qd_conf')

def get_qd_conf_value(userid=None, mode='coupon', key='promotion_url', **kw):
    '''获取物料的链接

    会区分渠道id返回url

    Args:
        userid: 商户userid.
        mode: coupon,红包的物料链接; card,集点的物料链接.
        key: qd_conf的key值
    '''
    def _get_default():
        '''获取默认值'''
        if 'default' in kw:
            return kw['default']
        try:
            default_key = kw.get('default_key', 0)
            if mode:
                return (qd_confs[default_key].get(key) or {}).get(mode) or ''
            else:
                return qd_confs[default_key].get(key)
        except:
            return None

    # qdconfs
    if 'qd_confs' in kw:
        qd_confs = kw['qd_confs']
    else:
        qd_confs = get_qd_conf()

    # 渠道id
    if 'groupid' in kw:
        groupid = kw['groupid']
    else:
        user = apcli.user_by_id(int(userid))
        groupid = user['groupid'] if user else 0

    default = _get_default()
    if mode:
        if (groupid in qd_confs and key in qd_confs[groupid] and
            qd_confs[groupid][key]):
            return qd_confs[groupid][key].get(mode, default)
    else:
        if groupid in qd_confs:
            return qd_confs[groupid].get(key) or default

    return default

def get_qd_conf_value_ex(userid=None, mode=None, key=None, groupid=None, **kw):
    '''
    根据是否是直营返回值
    '''
    orig_kw = deepcopy(kw)
    kw['default'] = None
    value = get_qd_conf_value(userid, mode, key,
                              groupid=groupid, **kw)
    if value is not None:
        return value

    # 非直营
    if groupid not in config.QF_GROUPIDS:
        value = get_qd_conf_value(userid, mode, key, groupid=groupid,
                                  default_key=1, **orig_kw)
    if value is not None:
        return value

    return get_qd_conf_value(userid, mode, key,
                             groupid=groupid,  **orig_kw)




#检测是否为业务员
def slsm_is_enable(userid):
    userid = int(userid)

    slsm_users = get_qd_salesman(userid)
    if not slsm_users:
        raise ParamError('业务员不存在')

    slsm_user = slsm_users[0]

    if slsm_user.status == qudao_ttypes.SlsmStatus.ENABLE:
        return True
    else:
        return False
