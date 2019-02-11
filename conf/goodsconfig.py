# encoding:utf-8

### 老版本兼容问题
### 不得不保留
# 优惠码的key
# 充值付费商品
PAYING_GOODS = {
    'goods': [{
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
    },
    {
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
    }],
    'free': 7, # 免费体验的天数
    'free_code': 'card', # 免费体验的产品的code
}

# 优惠码的key
PROMO_KEYS = {
    'card' : ['qf&20160707'], # 会员服务
    'v1' : ['qf2017v1'], # 基本服务
    'v2' : ['qf2017v2'], # 高级服务
}

# 充值付费商品
GOODS = [{ # 免费服务
    'services':[{
        'code': 'pay',
        'title': '支付收款',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }],
    'is_gratis': True,
    'code': 'card',
    'name': '免费服务',
    'logo_url': 'http://near.m1img.com/op_upload/137/148109872579.png',
    'color': '#f4d32e',
    'vip': 0,
    'desc': ''
}, { # 基本服务
    'services': [{
        'code': 'pay',
        'title': '支付收款',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png',
        'info_url': 'http://www.baidu.com',
    }, {
        'code': ['card_actv', 'coupon', 'member_manage', 'member_note'],
        'title': '会员基础功能',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }, {
        'code': 'prepaid',
        'title': '会员储值',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }, {
        'code': 'wx_pub',
        'title': '关注公众号',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }],
    'price': {
        'code': '12month',
        'amt': 149900,
        'alidity': {'unit':'months','key': 12},
        'goods_name': '12个月基本服务',
        'promo_code': 1,
    },
    'code': 'v1',
    'name': '基本服务',
    'logo_url': 'http://near.m1img.com/op_upload/137/148109872579.png',
    'color': '#f4d32e',
    'per_price': 100,
    'is_gratis': True,
    'vip': 1,
    'desc': '',
}, { # 高级服务
    'services': [{
        'code': 'pay',
        'title': '支付收款',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }, {
        'code': ['card_actv', 'coupon', 'member_manage', 'member_note'],
        'title': '会员基础功能',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }, {
        'code': 'prepaid',
        'title': '会员储值',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }, {
        'code': 'wx_pub',
        'title': '关注公众号',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }, {
        'code': 'push',
        'title': '消息推送',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }, {
        'code': 'business_king',
        'title': '生意王',
        'icon_url': 'http://near.m1img.com/op_upload/137/148040326588.png'
    }],
    'price': {
        'code': '12month',
        'amt': 999900,
        'alidity': {'unit':'months','key': 12},
        'goods_name': '12个月高级服务',
        'promo_code': 1,
    },
    'code': 'v2',
    'name': '高级服务',
    'logo_url': 'http://near.m1img.com/op_upload/137/148109872579.png',
    'color': '#f4d32e',
    'vip': 2,
    'desc': ''
}]

# 推广列表
# 1渠道， 2直营
PROMO_GOODS_DICT = {
    'prepaid' : ['v1', 'v1'],
    'card' : ['v1', 'card'],
    'diancan' : ['diancan', 'diancan'],
}
