# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import os
import sys
from webconfig import *
from tipconfig import *
from serconfig import *
from appconfig import *
from goodsconfig import *

# 服务地址
HOST = '0.0.0.0'

# 服务端口
PORT = 6200

# 调试模式: True/False
# 生产环境必须为False
DEBUG = False

# 日志文件配置
LOGFILE = 'stdout'
#LOGFILE = '/Users/yyk/log/mchnt_api/mchnt_api.log'

# 数据库配置
DATABASE = {
    'qf_mchnt': {
        'engine':'mysql',
        'db': 'qf_mchnt',
        # 'host': '172.100.101.156',
        'host': '172.100.101.107',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qf_core': {
        'engine':'mysql',
        'db': 'qf_core',
        # 'host': '172.100.101.156',
        #'host': '172.100.101.155',
        'host': '172.100.101.107',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qf_tools': {
        'engine':'mysql',
        'db': 'qf_tools',
        'host': '172.100.101.156',
        #'host': '172.100.101.107',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qf_marketing': {
        'engine':'mysql',
        'db': 'qf_marketing',
        # 'host': '172.100.101.156',
        'host': '172.100.101.107',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qf_mis': {
        'engine':'mysql',
        'db': 'qf_mis',
        # 'host': '172.100.101.155',
        'host': '172.100.101.107',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qmm_wx': {
        'engine':'mysql',
        'db': 'qmm_wx',
        # 'host': '172.100.102.152',
        'host': '172.100.101.107',
        # 'host': '172.100.101.156',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'app_conf': {
        'engine':'mysql',
        'db': 'app_config',
        'host': '172.100.102.101',
        'port': 3307,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qf_prepaid': {
        'engine':'mysql',
        'db': 'qf_prepaid',
        'host': '172.100.101.107',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },

    'qf_settle': {
        'engine':'mysql',
        'db': 'qf_settle',
        'host': '172.100.101.107',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },

    'qf_trade': {
        'engine':'mysql',
        'db': 'qf_trade',
        'host': '172.100.101.107',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },

    'qf_audit': {
        'engine': 'mysql',
        'db': 'qf_audit',
        'host': '172.100.101.156',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },

}

# cookie配置
COOKIE_CONFIG = {
    'max_age' : 10000000000,
    'domain'  : None,
}

# 用户类型
USER_CATE = 'merchant'

# 钱台app_code
QT_APP_CODE = '123456'
# 钱台server_key
QT_SERVER_KEY = '123456'
# 钱台 out_user(统一一个out_user)
QT_OUT_USER = 'haojin_out_user'

# 钱台api_url
QIANTAI_API = 'http://127.0.0.1:6777'
# 钱台util api_url, 线下测试会用到
QIANTAI_UTIL_API = 'http://127.0.0.1:9494'

# apolloserver
APOLLO_SERVERS = [{'addr': ('172.100.101.156', 6900), 'timeout': 2000}, ]
APOLLO_SERVERS = [{'addr': ('172.100.111.45', 6900), 'timeout': 5000}, ]
APOLLO_SERVERS = [{'addr': ('127.0.0.1', 6900), 'timeout': 5000}, ]
APOLLO_SERVERS = [{'addr': ('172.100.101.107', 6900), 'timeout': 5000}, ]
# captcah server 验证码服务
#CAPTCHA_SERVERS = [{'addr':('172.100.101.156', 6900), 'timeout':50000}]
CAPTCHA_SERVERS = [{'addr':('127.0.0.1', 6000), 'timeout':50000}]
# 短信服务
#PRESMS_SERVERS = [{'addr': ('172.100.101.171', 4444), 'timeout': 2000},]
PRESMS_SERVERS = [{'addr': ('127.0.0.1', 4444), 'timeout': 2000},]
# kuma服务
#KUMA_SERVERS = [{'addr': ('172.100.102.101', 7621), 'timeout': 5000},]
# KUMA_SERVERS = [{'addr': ('172.100.111.45', 9300), 'timeout': 5000},]
KUMA_SERVERS = [{'addr': ('172.100.101.107', 9301), 'timeout': 500},]
KUMA_SERVERS = [{'addr': ('172.100.101.107', 9301), 'timeout': 5000},]
#KUMA_SERVERS = [{'addr': ('172.100.102.103', 9300), 'timeout': 500},]
# 账户服务
ACCOUNT_SERVERS = [{'addr': ('172.100.101.106', 8000), 'timeout': 5000},]
# spring 服务（生成id)
SPING_SERVERS = [{'addr': ('172.100.101.106', 4590), 'timeout': 5000},]
# tempalService url
TEMPlATE_SERVERS = [{'addr': ('172.100.102.101', 4056), 'timeout': 2000},]


AUDIT_SERVERS = [{'addr': ('127.0.0.1', 7100), 'timeout': 6000}, ]

# 验证码服务的src
CAPTCHA_SRC = 'merchant'

# cache缓存的配置
CACHE_CONF = {
    'redis_cache_name': 'mchnt_api_cache',
    'redis_conf':  {
        # 'host' : '127.0.0.1',
        'host' : '172.100.101.107',
        'port' : 6379,
        'password' : '',
        'default_expire' : 2 * 24 * 60 * 60
    },
    # 'default': {
    #     'duration': 3 * 60 * 60,
    #     'times': 10000
    # },
    # 'get_member_info_conf': {
    #     'duration': 10 * 60,
    #     'times': 10000
    # },
    # 'get_all_apply_act_conf': {
    #     'duration': 60,
    #     'times': 10000
    # },
    # 'get_all_buyers' : {
    #     'times' : 1
    # }
}

# 获取城市列表配置文件
CITY_CONF = {
    'is_filte' : False,
    'region_areas' : {
        11 : [1100],  # 北京市: 北京市
        44 : [4401, 4403] # 广东省: 广州市,深圳市
    }
}

# finance服务
FINANCE_SERVERS = [{'addr': ('127.0.0.1', 8033), 'timeout': 5000},]
FINANCE_SERVERS = [{'addr': ('172.100.111.45', 8033), 'timeout': 5000},]



# 注册时渠道id
SIGNUP_GROUPID = 20655

# manage服务
MANAGE_SERVERS = [{'addr': ('172.100.101.156', 4100), 'timeout': 5000},]

# 二维码salt
QRCODE_SALT = 'qfpay'
QRCODE_URL  = 'https://o2.qfpay.com/q/pay?h=%s'

# 风控等级
RISKLEVEL = 118

# 消费分享劵可领次数
OBTAIN_NUM = 10
# 活动servers
QF_MARKETING_SERVERS = [{'addr': ('127.0.0.1', 7000), 'timeout': 2000}, ]
# openuser servers
OPENUSER_SERVER = [{'addr':('172.100.101.107', 7700), 'timeout':2000 }, ]
# openuser appid
OPENUSER_APPID = 10007
# redis配置
REDIS_CONF = {
    'host' : '172.100.101.156',
    'port' : 6379,
    'password' : '',
    'default_expire' : 2 * 24 * 60 * 60
}

# 分享默认配置
SHARE_ACT_DEFAULT_CONF = {
    'title' :  '【{shopname}】正在做活动，快来领取店铺红包啦！',
    'icon_url' : 'http://near.m1img.com/op_upload/28/146759882485.png',
    'desc' : '到店消费可直接抵钱哟！好近全民红包季，每天优惠享不停！'
}
# 好近熊的头像
HJ_AVATAR = 'http://7xry2m.com1.z0.glb.clouddn.com/avatar.png'
MCHNT_AVATAR = 'http://7xry2m.com1.z0.glb.clouddn.com/avatar.png'
APP_DEFAULT_AVATR = 'http://near.m1img.com/op_upload/21/144706478392.png'

# 获取wx openid 配置
WX_CONF = {
    'wx_url' : 'https://open.weixin.qq.com/connect/oauth2/authorize',
    'wx_appid' : 'wx087a3fc3f3757766',
    'wx_redirect_uri' : 'https://qtapi.qa.qfpay.net/trade/wechat/v1/get_weixin_code',
    'wx_appsecret' : '4a60e60111715e5942341860e54173f0',
    'wx_ak_url' : 'https://api.weixin.qq.com/sns/oauth2/access_token'
}

# 跳转获取wx openid
WX_REDIRECT = ('{wx_url}?appid={wx_appid}&redirect_uri={wx_redirect_uri}&response_type=code'
    '&scope=snsapi_userinfo&state=%s#wechat_redirect'.format(**WX_CONF))
# 跳转到openapi页面
OP_BIND_URL = 'https://qtapi.qa.qfpay.net/push/v2/entrance?mode=bind_ex&skip_url=%s'
# SKIP_URL
OP_SKIP_URL = 'https://qtapi.qa.qfpay.net/mchnt/activity/apply_entrance'
# openapi url
OPENAPI_URL = 'https://qtapi.qa.qfpay.net'
# 默认跳转页面
DEFAULT_REDIRECT_URL = 'http://172.100.108.35:8080/html/activity.html'

# 集点活动的最长时间
CARD_ACTV_MAX_EXPIRE = 180
# 集点活动最长开始时间
CARD_ACTV_MAX_START= 30

# qiantai2
# QT2_APP_CODE = 123456
# QT2_APP_KEY  = 123456
# QT2_SERVER = [{'addr': ('yushijun.qfpay.net', 5600), 'timeout': 5000},]

# qiantai2
QT2_APP_CODE = '8085381F5F2F1C726C8232E61C96302D'
QT2_APP_KEY  = '5E37CAD08F0E7387D40825B37524B566'
QT2_SERVER = [{'addr': ('172.100.101.107', 6200), 'timeout': 5000},]

# 开通服务的链接
OPEN_SERVICE_LINK = 'nearmcht://view-member-pay'

# trade_push
TRADE_PUSH_SERVER = [{'addr': ('172.100.111.45', 2003), 'timeout': 1000},]

# 推广红包活动效果
PROMOTION_COUPON_REPORT_SERVERS = [{'addr': ('172.100.102.101', 4067), 'timeout': 2000}, ]
NOTIFY_MAX_COUNT_MONTH = 20

# 收款费率
RATIOS = [{
        'name': '微信收款', 'key': 'tenpay_ratio',
        'url': 'http://7xry2m.com1.z0.glb.clouddn.com/avatar.png'
    }, {
        'name': '支付宝收款', 'key': 'alipay_ratio',
        'url': 'http://7xry2m.com1.z0.glb.clouddn.com/avatar.png'
    }, {
        'name': '京东收款', 'key': 'jdpay_ratio',
        'url': 'http://7xry2m.com1.z0.glb.clouddn.com/avatar.png'
	}]


QINIU_ACCESS_KEY = 'vdc6zqJGZLdU2z_lXXBJ_NLXK-M18XQ2Y7E5cyjb'
QINIU_SECRET_KEY = 'iANjdgatLuHhmXVTE5ibQ5OnIfg8AqKbWzYI-HXr'

#SALE_WEIDIAN_URL = "http://1.wx.qfpay.com/qmm"
SALE_WEIDIAN_URL = "http://127.0.0.1:8080/qmm"
SALE_SERVERS =  [{'addr': ('127.0.0.1', 8080), 'timeout': 2000}, ]

SALE_ACTIVITY_STATUS_INTERNAL_TEST = True # 线上灰度：所有的创建的特卖活动默认的状态为内部测试。 当到线上正式的时候， 该值=False
# 从好近app获取用户的订单
SALE_ORDER_LIST_HAOJIN_URL = 'https://api.haojin.in/trade/api/order/near_orders'

# 微信消息推送, 特卖和红包通知会使用到
QF_WXMP_THRIFT_SERVER = [{'addr': ('172.100.101.106', 6121), 'timeout': 5000},]


COUPON_QF_MARKETING_SERVERS = [{'addr': ('172.100.101.106', 6730), 'timeout': 200000}, ]

#  微信红包列表的url地址
COUPON_WEIXIN_LIST_URL = "https://marketing.qfpay.com/static/show_coupon.html"

#
WEIXIN_APP_ID = 'wx087a3fc3f3757766'
# 微信特卖列表页
SALE_WEIXIN_LIST_URL = 'https://o.qa.qfpay.net/v2/app.html?customer_id={customer_id}#!/sale'


# 微信特卖列表页
SALE_WEIXIN_LIST_URL = 'https://o.qa.qfpay.net/v2/app.html?customer_id={customer_id}#!/sale'

# 特卖和红包微信推送模板消息格式
WECHAT_SALE_COUPON_CONTENT = ''' 11点啦~好近店铺送福利喽！
[\xf0\x9f\x95\x99限时特卖]
你熟悉的店都在，低于7折哦
<a href="http://url.cn/2FN1F2g">戳这抢购，特卖不等人 </a>

[\xf0\x9f\x92\xb0现金红包]
会员专属，感恩回馈
<a href="https://o2.qfpay.com/trade/wechat/v1/get_weixin_code?scope=snsapi_base&redirect_uri=https%3A%2F%2Fmarketing.qfpay.com%2Fv1%2Fmkw%2Fpage_coupons&response_type=code&appid=wxeb6e671f5571abce#wechat_redirect">戳这儿数红包 </a>

'''

# mmwd redis配置
MMWD_REDIS = {
    'host' : '172.100.101.156',
    'port' : 6379,
    'password' : '',
    'db' : 4,
}

# mmwd social配置
MMWD_SOCIAL_REDIS = {
    'host': '172.100.102.101',
    'port': 6379,
    'db': 0,
}

# data engine 参数
DATAENGINE_SERVERS = [{'addr': ('172.100.101.106', 4800), 'timeout': 5000},]

# 数据组接口
DATAS_SERVERS = [{'addr': ('172.100.102.101', 4069), 'timeout': 5000},]
DATAS_SERVERS = [{'addr':('127.0.0.1', 2001), 'timeout':1000}]

# 微信通道id
WX_CHNLID = 20

# fund serviers
#FUND_SERVERS = [{'addr': ('172.100.101.106', 12003), 'timeout': 2000}, ]
FUND_SERVERS = [{'addr': ('127.0.0.1', 12000), 'timeout': 2000}, ]

# openapi_trade
OPENAPI_TRADE_SERVERS = [{'addr': ('127.0.0.1', 2000), 'timeout': 1000}, ]

# 验证码配置
SMS_CODE_RULE = {
    'count_limit' : 5,
    'expire_limit' : 5 * 3600,
	'expires': 5 * 3600,
}

# 短信服务的参数
# 短信服务的参数
PRESMS_FMT = {
    'signup' : ('欢迎注册好近商户，您的验证码{code}，'
                   '五分钟内有效，遇到问题可咨询微信客服{wxh}.'),
    'signup_daling': ('欢迎注册达令商户，您的验证码{code}，'
                      '五分钟内有效，遇到问题可咨询微信客服dalingsh'),
    'signup_vcb': ('欢迎注册V创宝商户，您的验证码{code}，'
                      '五分钟内有效，遇到问题可咨询微信客服VChongPo'),
    'reset_pwd' : ('{name}商户提醒您，您的重置密码'
                   '的验证码为：{code}，5分钟内有效且只能输入一次。'),
    'customer'  : '{code}',
}

# 短信服务tag的参数
PRESMS_TAG = {
    'hjsh': 'hj_mchnt',
    'daling': 'dalingsh',
    1588076: 'dalingsh',
    'vcb': 'vchuangbao',
    1588158: 'vchuangbao',
}

# 渠道服务
QUDAO_SERVERS = [{'addr': ('172.100.101.107', 8000), 'timeout': 2000},]

# 直营渠道id
QF_GROUPIDS = [10001, 10008, 10016, 10046, 20030, 20068, 20126, 20424, 20448, 20458, 20465, 20485, 20486, 20487, 20488, 20489, 20496, 20500, 20501, 20512, 20513, 20514, 20515, 20516, 20520, 20523, 20524, 20525, 20529, 20534, 20535, 20536, 20537, 20538, 20539, 20655, 20693, 20720, 20724, 20725, 20726, 20727, 20728, 20729, 20745, 20774, 20776, 20777, 20778, 20779, 20780, 20782, 20800, 20801, 20825]
QF_GROUPIDS = [20944, ]

# 渠道的费率
DEFAULT_RATIOS = {
    'feeratio': 0.0125,
    'creditratio': 0.0125,
    'tenpay_ratio': 0.006,
    'alipay_ratio': 0.006,
    'jdpay_ratio': 0.006,
    'qqpay_ratio': 0.0038,
    'max': 0.02
}

MEMBER_PREPAID_LINK = 'https://o2.qfpay.com/prepaid/v1/page/b/members/detail.html?c={}'

PREPAID_SERVERS = 'http://172.100.101.107'

# 储值服务地址
TPREPAID_SERVERS = [{'addr':('172.100.101.107', 10011), 'timeout' : 2000}, ]

# 好近字样的背景
DEFAULT_HJ_HEAD_IMG = 'http://near.m1img.com/op_upload/21/144706478392.png'
# 默认的背景图
DEFAULT_SHOP_HEAD_IMG = 'http://near.m1img.com/op_upload/155/149432051742.png'
# 默认的商户logo
DEFAULT_SHOP_LOGO_URL = 'http://near.m1img.com/op_upload/155/149432051742.png'

# 支持刷卡支付的useragent
UA_CARD =  'APOS A8'

# 微信卡包
WXCARD_SERVERS = [{'addr': ('172.100.101.107', 20020), 'timeout': 2000},]

# 微信server服务
QFMP_SERVERS = [{'addr': ('172.100.101.107', 6120), 'timeout': 2000}]

# 直营渠道id
BAIPAI_GROUPIDS = [1622845, 1588076, 1590191, 1625677, 1645189, 1630543, 1588158, 1634275, 1617829, 1617325]


# 小票key
RECEIPT_DATA_KEY = 'b6a8e5669691d5dbfef6da778170f6cc'


# 默认的appid
DEFAULT_APPID = 'wx087a3fc3f3757766'

# d1
D1_CHNLIDS = [36]

QUDAO_MCHNTID_CACHE = 1
#密钥key
RECEIPT_DATA_KEY = 'b6a8e5669691d5dbfef6da778170f6cc'
QPOS_TRADE_FEE = {
    'debit_ratio': 0.005,
    'credit_ratio': 0.006,
    'tenpay_ratio': 0.006,
    'alipay_ratio': 0.006,
    'jdpay_ratio': 0.006,
    'qqpay_ratio': 0.006,
    'debit_maxfee': -1,
    'credit_maxfee': -1,
    'tenpay_maxfee': -1,
    'alipay_maxfee': -1,
}
# 支持刷卡支付的useragent
UA_CARD = 'APOS A8'
# 直营渠道id
BAIPAI_GROUPIDS = [
  1622845, 1588076, 1625677, 1645189, 1630543, 1588158,
  1634275, 1617829, 1617325, 1659955
]
# 渠道配置
RATIO_CONF = {
    'alipay_ratio_extra': [0.0],
    'tenpay_ratio_extra': [0.0],
}
OPERATE_GROUP = {"opgid": [17, 16]}

#签名私钥
signPrivateKey = '''-----BEGIN RSA PRIVATE KEY-----
                 MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEAhQ+tOwfs9I0tmMl5bEjrig6DagmA9houjDnjZgBx+EOQlt8XoTG6QBzZvEUB+9xYS1yqylsWNrFsVUe4rIUMBwIDAQABAkB77Dm9vIfmyoUowpsfSlpzXUjuvKMqkP/BATjTip6aQ4wwwZq0LFsX/uC2q9XGFZ8wWg+NnJxC2XV9/9T2DpqBAiEA9vtXk3XY9CD+zETlfOIM1ZPh9p+wqVELesXEpX3/JNECIQCJ63bTUNBQIKcRN8TvV2bEPUVAsSqGzZDnYRWknQ05VwIhAOQWC7N/ksMpsYUdXz2sWKPo9TXYFcLXuJ1CBK+8oyLxAiAUKSNZiHqq+9rwHWLgSbpv/TTeXAeHZQ1FhV+QjJSeSQIgB9VKnokdTCtQw+K1OHLmHosPIrQfwGCFBM3VhWbMSnE=
                 -----END RSA PRIVATE KEY-----'''
#固定平台签名公钥
signPublicKey = '''-----BEGIN PUBLIC KEY-----
                MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAJJY/kusrKic6XAhHMakIX06nEnMnvceRV5m8dLIKQcz0RNkDXiEQ/EIV0hZQNQlTIyB5f6OzQeDjJlDUGgkyD8CAwEAAQ==
                -----END PUBLIC KEY-----'''

#平台提供的加密秘钥appkey
APPKEY = "DvEQwQ5SvGL9ZPthCFECoq18"

#银行卡三要
PATH = "https://api.hfdatas.com/superapi/super/auth/smrz3"

FORBID_MODIFY_PROVINCE_GROUP = [10003, 10006, 10007, 10009, 10010, 10011, 10013, 10014, 10015, 10018, 10019, 10020, 10032, 10033, 10034, 10035, 10036, 10038,
 10039, 10041, 10042, 10043, 10044, 10045, 10047, 10048, 10070, 10071, 10077, 10078, 10081, 10089, 12038, 12076, 12350, 12409,
 12647, 12849, 12850, 12851, 12852, 12853, 12855, 13006, 13040, 19436, 19555, 19557, 20002, 20004, 20005, 20006, 20007, 20008,
 20009, 20010, 20011, 20012, 20013, 20014, 20018, 20019, 20020, 20022, 20023, 20024, 20025, 20026, 20027, 20028, 20031, 20032,
 20033, 20034, 20035, 20036, 20037, 20038, 20039, 20040, 20041, 20042, 20043, 20044, 20045, 20046, 20047, 20048, 20049, 20050,
 20051, 20052, 20053, 20054, 20055, 20056, 20057, 20058, 20059, 20060, 20062, 20063, 20064, 20065, 20066, 20067, 20069, 20070,
 20071, 20072, 20073, 20074, 20075, 20076, 20078, 20079, 20080, 20082, 20083, 20084, 20085, 20086, 20087, 20088, 20089, 20090,
 20091, 20092, 20093, 20094, 20095, 20096, 20097, 20098, 20099, 20100, 20101, 20102, 20103, 20104, 20105, 20106, 20107, 20108,
 20109, 20110, 20111, 20112, 20113, 20115, 20116, 20117, 20118, 20119, 20120, 20121, 20122, 20123, 20124, 20127, 20128, 20129,
 20131, 20132, 20133, 20134, 20135, 20136, 20137, 20138, 20140, 20141, 20142, 20143, 20144, 20145, 20146, 20147, 20148, 20149,
 20150, 20152, 20153, 20154, 20155, 20156, 20157, 20158, 20159, 20160, 20161, 20162, 20163, 20164, 20165, 20166, 20167, 20168,
 20169, 20170, 20171, 20172, 20173, 20174, 20175, 20177, 20178, 20179, 20180, 20181, 20182, 20184, 20185, 20186, 20187, 20188,
 20189, 20190, 20191, 20192, 20193, 20194, 20195, 20197, 20198, 20199, 20201, 20202, 20203, 20204, 20206, 20207, 20208, 20209,
 20210, 20211, 20212, 20213, 20214, 20215, 20216, 20217, 20218, 20220, 20221, 20222, 20224, 20225, 20226, 20227, 20229, 20230,
 20231, 20232, 20233, 20235, 20236, 20237, 20238, 20240, 20241, 20242, 20243, 20244, 20245, 20246, 20247, 20248, 20250, 20252,
 20253, 20254, 20256, 20257, 20258, 20259, 20263, 20264, 20265, 20266, 20267, 20269, 20270, 20272, 20273, 20274, 20275, 20276,
 20277, 20278, 20279, 20280, 20281, 20282, 20283, 20284, 20285, 20286, 20287, 20288, 20289, 20290, 20291, 20292, 20293, 20294,
 20295, 20296, 20297, 20298, 20299, 20300, 20302, 20303, 20304, 20305, 20306, 20307, 20308, 20309, 20310, 20311, 20312, 20313,
 20314, 20315, 20316, 20317, 20318, 20319, 20320, 20321, 20322, 20323, 20324, 20325, 20327, 20330, 20331, 20332, 20333, 20334,
 20336, 20337, 20338, 20339, 20340, 20342, 20343, 20344, 20345, 20346, 20347, 20348, 20349, 20350, 20351, 20352, 20353, 20354,
 20355, 20356, 20357, 20358, 20359, 20360, 20361, 20362, 20363, 20364, 20365, 20366, 20367, 20368, 20369, 20369, 20370, 20371,
 20372, 20373, 20374, 20375, 20376, 20377, 20378, 20379, 20380, 20381, 20382, 20383, 20384, 20385, 20386, 20387, 20388, 20389,
 20390, 20391, 20392, 20393, 20394, 20395, 20396, 20397, 20398, 20399, 20400, 20401, 20403, 20404, 20405, 20406, 20407, 20408,
 20409, 20410, 20411, 20412, 20413, 20414, 20415, 20416, 20417, 20418, 20419, 20420, 20421, 20422, 20423, 20435, 20436, 20438,
 20441, 20442, 20444, 20445, 20446, 20448, 20449, 20450, 20451, 20452, 20459, 20460, 20461, 20462, 20463, 20464, 20469, 20470,
 20471, 20472, 20473, 20474, 20475, 20477, 20479, 20481, 20482, 20484, 20490, 20492, 20495, 20498, 20502, 20508, 20509, 20522,
 20530, 20531, 20541, 20542, 20543, 20544, 20548, 20549, 20650]

#限制次数及提示
CHANGE_BANK_LIMIT = 3
CHANGE_LIMIT_TIP = '抱歉，已超出今日更改次数上限'

#短信服务测试地址（正式上线需替换）
PRESMS_SERVERS = [{'addr': ('172.100.101.133', 4444), 'timeout': 2000},]
# 短信服务的参数
PRESMS_MARKETING_CONFIG = {
    'source' : 'mchnt_api',
    # 'tag' : 'dahantc',
    'tag' : 'dahantcsfl',
    'target' : '短信营销',
}


EMAIL_CONTENT = '''
Dear {nickname}，<br /><br />

We have received your apply to reset password.<br /><br />

Your verification code is as below：<br />
<font color="#0000ff" size="4">{code}</font><br /><br />

Please enter the code on the page.<br /><br />

The code will be expires in 5 minutes.<br />
 '''

# 邮箱验证码配置
EMAIL_CODE_CONF = {
     'expires' : 5 * 60 * 60, 'length' : 6, 'mode' : 1,
     'limit_time' : 60,
     'server' : 'smtp.exmail.qq.com',
     'frommail' : 'yuanyuejiang@qfpay.com',
     'password' : 'Yuan920412',
     'subject' : '邮箱验证码',
     'content' : EMAIL_CONTENT,
 }


DEFAULT_CLIENT_URL = {
    "pay_url": "https://api.qa.qfpay.net",
    "pay_trade_query_url": "https://o2.qa.qfpay.net"
}
# 根据渠道配置的 渠道有特殊需求这里加
GROUP_CONF_CLIENT_URL = {
    "111111": {
        "pay_url": "https://api.qa.qfpay.net",
        "pay_trade_query_url": "https://o2.qa.qfpay.net"
    }
}

VOICE_BROADCAST_IOS = [
    'http://near.m1img.com/op_upload/115/151514289478.png',
    'http://near.m1img.com/op_upload/115/15154968318.png',
    'http://near.m1img.com/op_upload/115/151514309042.png',
    'http://near.m1img.com/op_upload/115/151514332681.png',
    'http://near.m1img.com/op_upload/115/151514351579.png',
    'http://near.m1img.com/op_upload/115/151514355644.png',
    'http://near.m1img.com/op_upload/115/151514358245.png',
    'http://near.m1img.com/op_upload/115/15151439042.png',
    'http://near.m1img.com/op_upload/115/151549677141.png'
]

VOICE_BROADCAST_ANDROID = [
    'http://near.m1img.com/op_upload/115/151514289478.png',
    'http://near.m1img.com/op_upload/115/151549630915.jpg',
    'http://near.m1img.com/op_upload/115/151514570608.png',
    'http://near.m1img.com/op_upload/115/151514573871.png',
    'http://near.m1img.com/op_upload/115/151514575787.png',
    'http://near.m1img.com/op_upload/115/151514577648.png',
    'http://near.m1img.com/op_upload/115/151514579616.png',
    'http://near.m1img.com/op_upload/115/151514581314.png',

    'http://near.m1img.com/op_upload/115/15154963636.png',
    'http://near.m1img.com/op_upload/115/151549638204.png',
    'http://near.m1img.com/op_upload/115/151549639628.png',
    'http://near.m1img.com/op_upload/115/151549641186.png',
    'http://near.m1img.com/op_upload/115/151549642787.png',
    'http://near.m1img.com/op_upload/115/151549644724.png'

]


# geo redis配置
GEO_REDIS_CONF = {
     'host' : '172.100.101.107',
     'port' : 6379,
     'password' : '',
 }

# 舞象云qiantai2配置
WXY_QT2_CONF = {
   'appcode' : '8085381F5F2F1C726C8232E61C96302D',
     'appkey' : '5E37CAD08F0E7387D40825B37524B566',
     'app_uid' : 11751,
 }

#二维码url
INVOICE_QRCODE_URL = 'https://marketing.qfpay.com/paydone/billcode-page.html?userid=%s'
#二维码图片信息
INVOICE_IMG_DEFAULT = {
        "img_conf": {
            "bg_height": 1961,
            "qr_posy": 600,
            "qr_posx": 364,
            "qr_size": 700,
            "bg_width": 1430,
            "bg_url": "http://near.m1img.com/op_upload/137/152239598253.jpg"
        }
}
#白牌二维码图片信息
BAIPAI_INVOICE_QRCODE_URL = 'https://marketing.qfpay.com/paydone/billcode-page.html?userid=%s&appid=wxeb6e671f5571abce'

BAIPAI_INVOICE_IMG_DEFAULT = {
        "img_conf": {
            "bg_height": 1961,
            "qr_posy": 600,
            "qr_posx": 364,
            "qr_size": 700,
            "bg_width": 1430,
            "bg_url": "https://near.qfpay.com.cn/op_upload/156/152266171721.jpg"
        }
}

SIWEI_INVOICE_QRCODE_URL = 'https://marketing.qfpay.com/paydone/billcode-page.html?userid=%s&appid=wxffa4536644f38cfe',

HK_GROUPID = [1593964, 1951376, 1951391, 2071265]