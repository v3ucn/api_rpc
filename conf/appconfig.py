# encoding:utf-8

import json

# app配置
APP_CONFIG = {
    'zip_conf' : 'ZIP_CONFIG',
    'activity_conf' : 'ACT_CONF',
    'pay_sequence' : 'PAY_SEQUENCE',
    'trade_config' : 'TRADE_LIST_CONFIG'
}

# 新的user_conf
USER_CONF = {
    'zip_conf': 'ZIP_CONFIG',
    'activity_conf': 'ACT_CONF',
    'pay_sequence': {
        'qdmode': 'PAY_SEQUENCE',
    },
    'trade_config': {
        'qdmode': 'TRADE_LIST_CONFIG',
    },
    'show_reset_pwd': {
        'qdmode': 'SHOW_RESET_PWD',
    },
    'show_create_notify': {
        'qdmode': 'SHOW_CREATE_NOTIFY',
    },
    'head_service': {
        'pos': 'head',
        'mode': 'service'
    },
    'start_page': {
        'mode': 'app',
        'qdmode': 'start_page'
    },
    'trade_statistics': {
        'mode': 'app',
        'qdmode': 'trade_statistics'
    },
    'app_share_conf': {
        'mode': 'app',
        'qdmode': 'app_share_conf'
    },
    'home_banner': {
        'mode': 'app',
        'qdmode': 'home_banner',
        'user_jugge': 1,
    },
    'important_notice': {
        'mode': 'app',
        'qdmode': 'important_notice',
        'user_jugge': 1,
    }
}
# app对对应表
APPID_MAP = {
    'and': 13,
    'ios':  14,
}
# 是否显示忘记密码页面
SHOW_RESET_PWD = 1
# 是否展示创建会员通知
SHOW_CREATE_NOTIFY = 1


# zip包配置
ZIP_CONFIG = {
    'tag' : '0.1.0',
    'need_update' : '1',
    'zip_url' : 'http://near.m1img.com/op_upload/155/149388854288.gz',
    'pages': json.dumps({
        '/templates/activity.html': {
            'online': 'http://wx.qfpay.com/near/activity.html',
            'offline': '/templates/activity.html'
        },
        'notify_special_sale_preview': {
            'online': 'https://wx.qa.qfpay.net/near-v2/sale-preview.html',
            'offline': '/templates/sale-preview.html'
        },
        'member_right_preview': {
            'online': 'https://wx.qfpay.com/near-v2/member-detail.html',
            'offline': '/templates/member-detail.html'
        }
    })
}

# 活动配置
ACT_CONF = {
    'limit_share_num' : 5000,   # 创建分享活动的限制数量
    'limit_sponsor_num' : 5000,  # 创建反劵活动的限制数量
    'limit_expire_time' : 90,   # 创建活动限制的截止时间
}

# 支付配置
PAY_SEQUENCE =  ['wx', 'baidu', 'alipay', 'prepaid']

# 交易流水配置
TRADE_LIST_CONFIG = [{
        "ptype": [
            "000000",
            "700000",
            "700003",
            "800101",
            "800107",
            "800108",
            "800201",
            "800207",
            "800208",
            "800401",
            "800407",
            "800408",
            "800501",
            "800507",
            "800508",
            "800601",
            "800607",
            "800608"
        ],
        "ptype_name": [],
        "picon": [],
        "enable_choose": 1,
        "choose_name": "全部",
        "choose_icon": "http://near.m1img.com/op_upload/137/15016550142.png"
    }, {
        "ptype": [
            "000000"
        ],
        "ptype_name": [
            "刷卡收款"
        ],
        "picon": [
            "http://near.m1img.com/op_upload/137/149087351038.png",
            "http://near.m1img.com/op_upload/137/149087366414.png"
        ],
        "user_type": "刷卡用户",
        "pcode": "card",
        "enable_choose": 1,
        "choose_name": "刷卡收款",
        "choose_icon": "http://near.m1img.com/op_upload/137/150165503905.png",
    }, {
        "ptype": [
            "800101",
            "800107",
            "800108"
        ],
        "ptype_name": [
            "支付宝收款",
            "收款码收款",
            "支付宝收款"
        ],
        "picon": [
            "http://near.m1img.com/op_upload/137/149087355543.png",
            "http://near.m1img.com/op_upload/137/149087371217.png"
        ],
        "user_type": "支付宝用户",
        "pcode": "alipay",
        "enable_choose": 1,
        "choose_name": "支付宝收款",
        "choose_icon": "http://near.m1img.com/op_upload/137/150165500111.png",
        "refund": {
            "busicd": "800103",
            "businm": "alipay_refund"
        }
    }, {
        "ptype": [
            "800201",
            "800207",
            "800208"
        ],
        "ptype_name": [
            "微信收款",
            "收款码收款",
            "微信收款"
        ],
        "picon": [
            "http://near.m1img.com/op_upload/137/149087357417.png",
            "http://near.m1img.com/op_upload/137/149087372758.png"
        ],
  		"user_type": "微信用户",
        "pcode": "weixin",
        "enable_choose": 1,
        "choose_name": "微信收款",
        "choose_icon": "http://near.m1img.com/op_upload/137/150165507928.png",
        "refund": {
            "busicd": "800203",
            "businm": "weixin_refund"
        }
    }, {
        "ptype": [
            "800401",
            "800407",
            "800408"
        ],
        "ptype_name": [
            "百度收款",
            "收款码收款",
            "百度收款"
        ],
        "picon": [
            "http://near.m1img.com/op_upload/137/149087352325.png",
            "http://near.m1img.com/op_upload/137/149087367926.png"
        ],
        "user_type": "百度钱包用户",
        "pcode": "baifubao",
        "enable_choose": 0,
        "refund": {
            "busicd": "800403",
            "businm": "baifubao_refund"
        }
    }, {
        "ptype": [
            "800501",
            "800507",
            "800508"
        ],
        "ptype_name": [
            "京东收款",
            "收款码收款",
            "京东收款"
        ],
        "picon": [
            "http://near.m1img.com/op_upload/137/14908735420.png",
            "http://near.m1img.com/op_upload/137/149087369768.png"
        ],
        "user_type": "京东用户",
        "pcode": "jdpay",
        "enable_choose": 1,
        "choose_name": "京东收款",
        "choose_icon": "http://near.m1img.com/op_upload/137/150165505186.png",
        "refund": {
            "busicd": "800503",
            "businm": "jdpay_refund"
        }
    }, {
        "ptype": [
            "800601",
            "800607",
            "800608"
        ],
        "ptype_name": [
            "QQ收款",
            "收款码收款",
            "QQ收款"
        ],
        "picon": [
            "http://near.m1img.com/op_upload/137/149087361057.png",
            "http://near.m1img.com/op_upload/137/149087376772.png"
        ],
  		"user_type": "QQ钱包用户",
        "pcode": "qqpay",
        "enable_choose": 1,
        "choose_name": "QQ钱包收款",
        "choose_icon": "http://near.m1img.com/op_upload/137/15016550634.png",
        "refund": {
            "busicd": "800603",
            "businm": "qqpay_refund"
        }
    }, {
        "ptype": ["700000", "700003"],
        "ptype_name": ["储值消费",  "储值反扫"],
        "picon": [
            "http://near.m1img.com/op_upload/137/149087362931.png",
            "http://near.m1img.com/op_upload/137/149087378211.png"
        ],
  		"user_type": "储值用户",
        "pcode": "prepaid",
        "enable_choose": 1,
        "choose_name": "储值消费",
        "choose_icon": "http://near.m1img.com/op_upload/137/150165502525.png",
        "refund": {
            "busicd": "700002",
            "businm": "prepaid_refund"
        }
    }
]
