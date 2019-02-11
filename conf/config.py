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
PORT = 2002

# 调试模式: True/False
# 生产环境必须为False
DEBUG = False

# 日志文件配置
LOGFILE = 'stdout'
#LOGFILE = '/Users/yyk/log/mchnt_api/mchnt_api.log'
LOGFILE = 'stdout'

# 数据库配置
DATABASE = {
    'qf_mchnt': {
        'engine':'mysql',
        'db': 'qf_mchnt',
        'host': '172.100.101.156',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qf_core': {
        'engine':'mysql',
        'db': 'qf_core',
        'host': '172.100.101.156',
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
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qf_marketing': {
        'engine':'mysql',
        'db': 'qf_marketing',
        'host': '172.100.101.106',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qf_mis': {
        'engine':'mysql',
        'db': 'qf_mis',
        'host': '172.100.101.155',
        'host': '172.100.101.156',
        'port': 3306,
        'user': 'qf',
        'passwd': '123456',
        'charset': 'utf8',
        'conn': 16,
    },
    'qmm_wx': {
        'engine':'mysql',
        'db': 'qmm_wx',
        'host': '172.100.102.152',
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
        'host': '172.100.111.45',
        'port': 3306,
        'user': 'yyk',
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
    'max_age' : 100,
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
APOLLO_SERVERS = [{'addr': ('172.100.111.45', 6900), 'timeout': 2000}, ]
# captcah server 验证码服务
#CAPTCHA_SERVERS = [{'addr':('172.100.101.156', 6900), 'timeout':50000}]
CAPTCHA_SERVERS = [{'addr':('127.0.0.1', 6000), 'timeout':50000}]
# 短信服务
#PRESMS_SERVERS = [{'addr': ('172.100.101.171', 4444), 'timeout': 2000},]
PRESMS_SERVERS = [{'addr': ('127.0.0.1', 4444), 'timeout': 2000},]
# kuma服务
#KUMA_SERVERS = [{'addr': ('172.100.102.101', 7621), 'timeout': 5000},]
KUMA_SERVERS = [{'addr': ('127.0.0.1', 9300), 'timeout': 5000},]
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
        'host' : '127.0.0.1',
        'port' : 6379,
        'password' : '',
        'default_expire' : 2 * 24 * 60 * 60
    },
    'default': {
        'duration': 3 * 60 * 60,
        'times': 10000
    },
    'get_member_info_conf': {
        'duration': 10 * 60,
        'times': 10000
    },
    'get_all_apply_act_conf': {
        'duration': 60,
        'times': 10000
    },
    'get_all_buyers' : {
        'times' : 1
    }
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
QF_MARKETING_SERVERS = [{'addr': ('127.0.0.1', 6730), 'timeout': 2000}, ]
# 物料的url
PROMOTION_URL = 'http://near.m1img.com/op_upload/62/145819972792.png'
# openuser servers
OPENUSER_SERVER = [{'addr':('172.100.111.45', 7700), 'timeout' : 2000}, ]
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

# 充值付费商品
PAYING_GOODS = {
    'goods': [{   # 好近会员服务
        'services':[{
            'code': 'card_actv',
            'title': '会员集点 有趣的会员玩法',
            'desc': '一周增加3倍回头客',
        }, {
            'code': 'coupon',
            'title': '会员红包 你的营销神器',
             'desc': '流水提升两成以上',
        }, {
             'code': 'member_manage',
             'title': '会员管理 支付即会员',
             'desc': '优惠活动直达顾客'
        }, {
            'code': 'member_note',
            'title': '经营分析 更懂你的店',
            'desc': '经营走势，一目了然'
        }],
        'price': [{
            'code': '12month',
            'amt': 249900,
            'origin_amt': 249900,
            'desc': '每月208元',
            'alidity': {'unit':'months','key': 12},
            'goods_name': '12个月会员服务',
            'note': '推荐',
            'promo_code': 4,
            'promo_amt': 109900,
        }, {
            'code': '6month',
            'amt': 149900,
            'origin_amt': 149900,
            'desc': '每月249元',
            'alidity': {'unit':'months', 'key': 6},
            'goods_name': '6个月会员服务',
            'note':'',
            'promo_code': 3,
            'promo_amt': 57000,
        }, {
            'code': '3month',
            'amt': 79900,
            'origin_amt': 79900,
            'desc': '每月266元',
            'alidity': {'unit':'months', 'key': 3},
            'goods_name': '3个月会员服务',
            'note':'',
            'promo_code': 2,
            'promo_amt': 30000,
        }, {
            'code': 'month',
            'amt': 29900,
            'origin_amt':29900,
            'desc': '',
            'alidity': {'unit':'months', 'key': 1},
            'goods_name': '1个月会员服务',
            'note': '',
            'promo_code': 1,
            'promo_amt': 13000,
        }],
        'code': 'card',
        'priority': 1,
        'name': '会员服务',
        'desc': '每天不到3元'
    }, { # 好近点餐服务
        'services': [{
            'code': 'diancan',
            'title': '点餐功能',
            'desc': '智能餐厅',
        }],
        'priority': 2,
        'price': [{
            'code': '12month',
            'amt': 249900,
            'origin_amt': 249900,
            'desc': '每月208元',
            'alidity': {'unit':'months','key': 12},
            'goods_name': '12个月点餐服务',
            'note': '推荐',
            'promo_code': 4,
            'promo_amt': 109900,
        }, {
            'code': '6month',
            'amt': 149900,
            'origin_amt': 149900,
            'desc': '每月249元',
            'alidity': {'unit':'months', 'key': 6},
            'goods_name': '6个月点餐服务',
            'note':'',
            'promo_code': 3,
            'promo_amt': 57000,
        }, {
            'code': '3month',
            'amt': 79900,
            'origin_amt': 79900,
            'desc': '每月266元',
            'alidity': {'unit':'months', 'key': 3},
            'goods_name': '3个月点餐服务',
            'note':'',
            'promo_code': 2,
            'promo_amt': 30000,
        }, {
            'code': 'month',
            'amt': 29900,
            'origin_amt':29900,
            'desc': '',
            'alidity': {'unit':'months', 'key': 1},
            'goods_name': '1个月点餐服务',
            'note': '',
            'promo_code': 1,
            'promo_amt': 13000,
        }],
        'code' : 'diancan',
        'desc' : '点餐服务',
        'name' : '点餐服务'
    }, { # 储值服务
        'services': [{
            'code': 'diancan',
            'title': '点餐功能',
            'desc': '智能餐厅',
        }],
        'priority': 2,
        'price': [{
            'code': '12month',
            'amt': 249900,
            'origin_amt': 249900,
            'desc': '每月208元',
            'alidity': {'unit':'months','key': 12},
            'goods_name': '12个月点餐服务',
            'note': '推荐',
            'promo_code': 4,
            'promo_amt': 109900,
        }, {
            'code': '6month',
            'amt': 149900,
            'origin_amt': 149900,
            'desc': '每月249元',
            'alidity': {'unit':'months', 'key': 6},
            'goods_name': '6个月点餐服务',
            'note':'',
            'promo_code': 3,
            'promo_amt': 57000,
        }, {
            'code': '3month',
            'amt': 79900,
            'origin_amt': 79900,
            'desc': '每月266元',
            'alidity': {'unit':'months', 'key': 3},
            'goods_name': '3个月点餐服务',
            'note':'',
            'promo_code': 2,
            'promo_amt': 30000,
        }, {
            'code': 'month',
            'amt': 29900,
            'origin_amt':29900,
            'desc': '',
            'alidity': {'unit':'months', 'key': 1},
            'goods_name': '1个月点餐服务',
            'note': '',
            'promo_code': 1,
            'promo_amt': 13000,
        }],
        'code' : 'prepaid',
        'desc' : '储值服务',
        'name' : '储值服务'
    }],
    'free': 7, # 免费体验的天数
    'free_code': 'card', # 免费体验的产品的code
}

# 卡卷活动物料的url
CARD_PROMOTION_URL = 'http://near.m1img.com/op_upload/62/145819972792.png'

# 卡卷活动的最长时间
CARD_ACTV_MAX_EXPIRE = 180
# 集点活动最长开始时间
CARD_ACTV_MAX_START= 30

# qiantai2
QT2_APP_CODE = 123456
QT2_APP_KEY  = 123456
QT2_SERVER = [{'addr': ('yushijun.qfpay.net', 5600), 'timeout': 5000},]

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
}

# 短信服务的参数
PRESMS_FMT = {
    'signup' : ('欢迎注册好近商户，您的验证码{code}，'
                   '五分钟内有效，遇到问题可咨询微信客服{wx_pub}.'),
    'reset_pwd' : ('{name}商户提醒您，您的重置密码'
                   '的验证码为：{code}，5分钟内有效且只能输入一次。'),
}

# 渠道服务
QUDAO_SERVERS = [{'addr': ('101.204.228.105', 17201), 'timeout': 2000},]

#新审核服务
AUDIT_SERVERS = [{'addr': ('172.100.101.110',7100), 'timeout': 6000},]

# 直营渠道id
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

# 储值服务地址
PREPAID_SERVERS = [{'addr':('172.100.111.45', 27013), 'timeout' : 2000}, ]

# D1通道
D1_CHNLIDS = []

# 好近字样的背景
DEFAULT_HJ_HEAD_IMG = 'http://near.m1img.com/op_upload/21/144706478392.png'
# 默认的背景图
DEFAULT_SHOP_HEAD_IMG = 'http://near.m1img.com/op_upload/155/149432051742.png'
# 默认的商户logo
DEFAULT_SHOP_LOGO_URL = 'http://near.m1img.com/op_upload/155/149432051742.png'

#新审核接口渠道id列表
NEW_AUDIT_GROUP = [1587456]


