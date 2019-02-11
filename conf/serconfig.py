# encoding:utf-8

# 用户默认返回的服务列表
DEFAULT_SERVICES = [
    'HJ0005', 'HJ0006', 'HJ0007', 'HJ0008', 'HJ0009', 'HJ0010', 'HJ0011',
    'HJ0012', 'HJ0014', 'HJ0016', 'HJ0020', 'HJ0021', 'HJ0022',
    'HJ0026', 'HJ1111', 'HJ0029', 'HJ1001', 'HJ1002', 'HJ1003',
    'HJ0030',
]

# 用户默认开通的服务列表
SIGNUP_DEFAULT_SERVICES = ['HJ0006', 'HJ0008',  'HJ0009']

# 功能模块
MODULES = [
    {'module':'member', 'name':'会员功能', 'color':'#8883f4'},
    {'module':'special', 'name':'营销功能', 'color':'#ff3d1f'},
    {'module':'diancan', 'name':'智慧餐厅', 'color':'#4dcfba'},
    {'module':'default', 'name':'其他功能', 'color':'#ff8100'},
]

# 系统服务列表配置
SYSTEM_SERVICES = [
    {
        'code':'HJ0001', 'weight':100, 'name':'商品管理', 'status': 0,
        'icon':'http://near.m1img.com/op_upload/70/145724476608.png',
        'link': {'default': 'nearmcht://view-goods-list'},
    },
    {
        'code':'HJ0002', 'weight':98, 'name':'外卖管理', 'status': 0,
        'icon':'http://near.m1img.com/op_upload/62/145744271435.png',
        'link': {'default': 'nearmcht://view-takeout-list'},
    },
    {
        'code':'HJ0003', 'weight':99, 'name':'外卖订单', 'status': 0,
        'icon':'http://near.m1img.com/op_upload/62/145744268838.png',
        'link': {'default': 'http://wx.qfpay.com/near/takeout.html'}
    },
    {
        'code':'HJ0004',
        'weight': {
            'default': 97,
            'app-021000': 13,
            'app-040000': 90,
        },
        'name':'折扣买单', 'status': 1,
        'icon':'http://near.m1img.com/op_upload/62/145744279122.png',
        'link': {'default': 'http://wx.qfpay.com/near/consuming.html'}
    },
    {
        'code':'HJ0005',
        'weight':{
            'default': 96,
            'app-021000': 58,
            'app-030800': 90,
        },
        'name':'特卖验证', 'status': 1,
        'icon':{
            'default' : 'http://near.m1img.com/op_upload/70/145724489414.png',
            'app-030800': 'http://near.m1img.com/op_upload/137/148040320292.png',
        },
        'link': {
            'default': 'http://wx.qfpay.com/near/redeem.html',
            'app-030400': 'nearmcht://view-special-redeem',
        },
        'module' : {
            'app-030800' : 'special'
        }
    },
    {
        'code':'HJ0006', 'name':'联系客服', 'status':1,
        'weight': {
            'default': 95,
            'app-020000': 14,
            'app-030800' : 90,
        },
        'icon':{
            'default' : 'http://near.m1img.com/op_upload/70/145724492026.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040225912.png',
        },
        'link': {'default': 'http://qmm.la/wkY5uG'}
    },
    {
        'code':'HJ0007', 'name':'设计服务', 'status': 1,
        'weight': {
            'default': 93,
            'app-020000': 15,
            'app-030800': 80,
        },
        'icon':{
            'default' : 'http://near.m1img.com/op_upload/70/145724498064.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040227508.png',
        },
        'link': {'default': ''},
        'condition' : ['group_dis'],
    },
    {
        'code':'HJ0008', 'weight':102, 'name':'到账记录', 'status': 1,
        'icon':'http://near.m1img.com/op_upload/70/145724494803.png',
        'link': {
            'and-000000~019999': 'http://wx.qfpay.com/near/arrival-record.html',
            'ios-000000~020999': 'http://wx.qfpay.com/near/arrival-record.html'
        }
    },
    {
        'code':'HJ0009', 'name':'会员红包', 'status': 1,
        'icon': {
            'default': 'http://near.m1img.com/op_upload/70/145707292202.png',
            'app-020000': 'http://near.m1img.com/op_upload/137/147686355218.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040317063.png',
        },
        'weight': {
            'default': 101,
            'app-020000': 9,
            'app-030800': 190,
        },
        'link': {
            'default': 'http://wx.qfpay.com/near/coming-soon.html',
            'middle': 'nearmcht://view-coupon-activity',
        },
        'module': 'member',
        'note': '拉新留旧必备神器',
        'stats_note': '今日使用红包<font color="#FF3B49">{num}</font>个',
        'pos' : ['home_page', 'all']
    },
    {
        'code':'HJ0010', 'name':'物料商城', 'status': 1,
        'weight': {
            'default': 90,
            'app-020000': 16,
            'app-030800': 70,
        },
        'icon':{
            'default' : 'http://near.m1img.com/op_upload/12/14613221182.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040309021.png'
        },
        'link': {'default': 'http://mmwd.me/shop/204758'},
        'condition' : ['group_dis'],
    },
    {
        'code':'HJ0011', 'name':'会员管理','status': 1,
        'icon': {
            'default': 'http://near.m1img.com/op_upload/12/146132210088.png',
            'app-021000': 'http://near.m1img.com/op_upload/137/147686352185.png',
            'app-030800': 'http://near.m1img.com/op_upload/137/148040174114.png',
        },
        'weight': {
            'default': 89,
            'app-020000': 11,
            'app-030800': 201,
        },
        'link': {
            'ios-020502': 'nearmcht://view-member-activity',
            'and-010700': 'nearmcht://view-member-activity',
        },
        'module': 'member',
        'note': '支付即本店会员',
        'stats_note': '今日新增<font color="#7696FB">{num}</font>会员',
        'pos' : ['home_page', 'all']
    },
    {
        'code':'HJ0012','name':'官方活动','status': 1,
        'weight': {
            'default': 88,
            'app-021000': 49,
            'app-030800': 70,
        },
        'icon':{
            'default' : 'http://near.m1img.com/op_upload/12/146132207764.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040166954.png',
        },
        'link': {
            'ios-020502': '/templates/activity.html',
            'and-010700': '/templates/activity.html'
        },
        'module' : {
            'app-030800' : 'special',
        }
    },
    {
        'code':'HJ0013', 'name':'商户贷款', 'status': 1,
        'weight': {
            'default': 87,
            'ios-021000': 17,
            'and-020000': 17,
            'app-030800': 100,
        },
        'icon':{
            'default' : 'http://near.m1img.com/op_upload/12/146494320841.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040302975.png',
        },
        'link': {'default': 'http://ximu.qfpay.com/ximuindex',}
    },
    {
        'code':'HJ0014', 'name':'经营分析', 'status': 0,
        'weight': {
            'default': 86,
            'ios-021000~030299': 7,
            'and-020000~030299': 7,
            'app-030300': 59,
        },
        'icon': {
            'default': 'http://near.m1img.com/op_upload/12/146494314053.png',
            'ios-021000~030299': 'http://near.m1img.com/op_upload/28/146762769468.png',
            'and-020000~030299': 'http://near.m1img.com/op_upload/28/146762769468.png',
            'app-030800': 'http://near.m1img.com/op_upload/137/148040222978.png',
        },
        'link': {'default':'https://tp.maxfun.co/qf/mobile_data?page=1&module=1,2&style=1',},
        'module': {
            'default': 'member',
            'app-030300': 'default',
            'app-030800': 'diancan',
        },
        'note': '清晰把脉经营情况',
        'stats_note': '',
    },
    {
        'code':'HJ0015', 'name':'活动营销', 'status': 1,
        'weight': {
            'default': 85,
            'ios-021000': 60,
            'and-020000': 60,
            'app-030800': 80,
        },
        'icon':{
            'default' : 'http://near.m1img.com/op_upload/12/146494316139.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040306206.png',
        },
        'link': {
            'ios-020502': 'http://wx.qfpay.com/near-v2/hot-marketing.html',
            'and-010700': 'http://wx.qfpay.com/near-v2/hot-marketing.html',
        },
        'module' : {
            'app-030800' : 'special'
        }
    },
    {
        'code':'HJ0016', 'name':'会员集点', 'status': 1,
        'weight': {
            'default': 84,
            'ios-021000': 8,
            'and-020000': 8,
            'app-030800': 200,
        },
        'icon': {
            'default': 'http://near.m1img.com/op_upload/12/146494376393.png',
            'ios-021000': 'http://near.m1img.com/op_upload/137/147686357859.png',
            'and-020000': 'http://near.m1img.com/op_upload/137/147686357859.png',
            'app-030800': 'http://near.m1img.com/op_upload/137/148040326588.png',
        },
        'link': {
            'ios-020700~020799': 'nearmcht://view-member-card',
            'ios-020900': 'nearmcht://view-member-card',
            'and-010900~010999': 'nearmcht://view-member-card',
            'and-020000': 'nearmcht://view-member-card',
        },
        'module': 'member',
        'note': '有趣的会员玩法',
        'stats_note': '今日集点<font color="#9100E6">{num}</font>个',
        'pos' : ['home_page', 'all']
    },
    {
        'code':'HJ0017', 'weight':83, 'name':'点餐订单', 'status': 1,
        'weight': {
            'default': 83,
            'ios-021000': 47,
            'and-020000': 47,
        },
        'icon':'http://near.m1img.com/op_upload/8/146716911399.png',
        'link': {
            'ios-020700~030799': 'http://wx.qfpay.com/near-v2/restaurant-order-list.html',
            'and-000000~030799': 'http://wx.qfpay.com/near-v2/restaurant-order-list.html'
        },
    },
    {
        'code':'HJ0018', 'name':'商品管理', 'status': 1,
        'weight': {
            'default': 82,
            'ios-021000': 48,
            'and-020000': 48,
        },
        'icon':'http://near.m1img.com/op_upload/8/14689205674.png',
        'link': {
            'ios-020700~030199': 'http://wx.qfpay.com/near-v2/diancan-manage.html',
            'and-000000~030199': 'http://wx.qfpay.com/near-v2/diancan-manage.html',
            'app-030200~030799': 'nearmcht://view-goods-manage',
        },
    },
    {
        'code':'HJ0019', 'name':'点餐打印', 'status': 1,
        'weight': {
            'default': 81,
            'ios-021000': 46,
            'and-020000': 46,
        },
        'icon':'http://near.m1img.com/op_upload/8/147148686008.png',
        'link': {
            'and-030106': 'nearmcht://view-order-print'
        },
    },
    {
        'code':'HJ0020', 'name':'会员通知', 'status': 1,
        'weight': {
            'default': 86,
            'app-030300': 10,
            'app-030800': 180,
        },
        'icon': {
            'default': 'http://near.m1img.com/op_upload/137/147686363148.png',
            'app-030800': 'http://near.m1img.com/op_upload/137/148040312068.png',
        },
        'link': {
            'app-030300':'nearmcht://view-member-notify?userid={mobile}',
        },
        'module':  'member',
        'note': '特卖通知重磅上线',
        'stats_note': '',
        'pos' : ['home_page', 'all']
    },
    {
        'code':'HJ0021', 'name':'特卖', 'status': 1,
        'weight': {
            'default' : 100,
            'app-030800': 160,
        },
        'icon': {
            'default' : 'http://near.m1img.com/op_upload/137/147686360592.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040269019.png',
        },
        'link': {
            'app-030500':'nearmcht://view-special-sale',
        },
        'module': 'special',
        'note': '打造爆品聚人气',
        'pos': {
            'app-000000~040200': ['home_page', 'all'],
        }
    },
    {
        'code':'HJ0022', 'name': '点餐', 'status': 1,
        'weight': {
            'default' : 50,
            'app-030800': 150,
        },
        'icon':  {
            'default' : 'http://near.m1img.com/op_upload/137/147686349458.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040314435.png',
        },
        'link': {
            'app-030500':'http://wx.qfpay.com/near-v2/diancan-intro.html',
        },
        'recharge_link' : 'nearmcht://view-diancan-management',
        'group_link' : 'http://wx.qfpay.com/near-v2/wx-diancan-intro.html',
        'module':  'diancan',
        'note': '自助点餐效率高',
        'condition' : ['group_link', 'diancan_service'],
        'pos' : ['home_page', 'all']
    },
    {
        'code':'HJ0025','name':'会员储值', 'status': 1,
        'weight': {
            'default' : 78,
            'app-030800': 160,
        },
        'icon': {
            'default' : 'http://near.m1img.com/op_upload/8/148006543493.png',
            'app-030800' : 'http://near.m1img.com/op_upload/137/148040324045.png'
        },
        'link': {
            'app-020700~040200': 'https://o2.qfpay.com/prepaid/v1/page/b/index.html',
        },
        'module': {
            'default': 'default',
            'app-030800': 'member',
        },
    },
    {
        'code':'HJ0026','name':'店铺公告', 'status': 1, 'weight': 70,
        'icon': 'http://near.m1img.com/op_upload/137/148040232687.png',
        'link': {
            'app-030800': 'nearmcht://view-shop-notice',
        },
        'module': 'special',
        'pos' : ['all']
    },
    {
        'code':'HJ0027','name':'金融理财', 'status': 1, 'weight': 110,
        'icon': 'http://near.m1img.com/op_upload/127/148273830874.png',
        'link': {
            'app-030800': 'http://qmm.la/JP46UB',
        },
    },
    {
        'code':'HJ0028','name':'会员分析', 'status': 1, 'weight': 210,
        'icon': 'http://near.m1img.com/op_upload/115/148913687193.png',
        'link': 'http://wx.qfpay.com/near-v2/business-king-intro.html',
        'pos': ['all'],
        'module': 'member',
        'condition' : ['group_control'],
    },
    {
        'code':'HJ0029','name':'会员储值', 'status': 1,
        'weight': 160,
        'icon': 'http://near.m1img.com/op_upload/137/148040324045.png',
        'link': {
            'app-040204': 'https://o2.qfpay.com/prepaid/v1/page/b/index.html',
        },
        'module': 'member',
	    'pos' : ['home_page', 'all']
    },
    {
        'code':'HJ0030','name':'会员特权', 'status': 1,
        'weight': 150,
        'icon': 'http://near.m1img.com/op_upload/137/149300361542.png',
        'link': {
            'app-040400': 'nearmcht://view-member-privilege',
        },
        'module': 'member',
        'condition' : ['group_control'],
        'pos' : ['home_page', 'all'],
        'tip' : {
          'default': {  # 脚标
             'title': 'NEW',
             'id': 10
          }
        }
    },
    {
        'code': 'HJ1001',
        'status': 1, 'weight': 100,
        'icon': 'http://near.m1img.com/op_upload/8/14897353539.png',
        'link': 'nearmcht://view-collection-service',
        'name': '立即收款',
        'pos': ['head'],
        'condition': ['cate_control'],
        'show_cates': ['merchant', 'submerchant', 'opuser']
    },
    {
        'code': 'HJ1002',
        'status': 1, 'weight': 90,
        'icon': 'http://near.m1img.com/op_upload/8/148973534267.png',
        'link': 'nearmcht://view-trade-list',
        'name': '查看流水',
        'pos': ['head']
    },
    {
        'code': 'HJ1003',
        'status': 1, 'weight': 80,
        'icon': 'http://near.m1img.com/op_upload/8/148973532957.png',
        'link': 'http://wx.qfpay.com/near/arrival-record.html',
        'name': '到账记录',
        'condition': ['dis_service'],
        'dis_service': 'balance',
        'pos': ['head']
    },
    {
        'code': 'balance',
        'status': 1, 'weight': 80,
        'icon': 'http://near.m1img.com/op_upload/8/148973532957.png',
        'link': 'http://wx.qfpay.com/near/arrival-record.html',
        'name': '余额提现',
        'pos': ['head']
    },
    {
        'code':'HJ1111', 'name': '更多', 'status': 1, 'weight': 0,
        'icon':  'http://near.m1img.com/op_upload/137/148109825521.png',
        'link': {'app-030800':'nearmcht://tab_all_service'},
        'module':  'all',
        'note': '自助点餐效率高',
        'pos' : ['home_page']
    },
]


