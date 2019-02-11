# encoding:utf-8
# 各种提示文案

# 银行卡审核上线时间
BANK_APPLY_ONLINE_TIME = '2016-11-16 00:00:00'

# 用户相关提示
BANK_AUDIT_TIPS = {
    'auditing' : {
        'title' : '新卡{bankaccount}正在审核中',
        'content' : ['银行会在1-3个工作日内进行审核。']
    },
    'fail' : {
        'title' : '审核失败',
    },

}

# 银行对应图片
BANK_ICONS = {
    '北京银行' : 'http://near.m1img.com/op_upload/137/14787778645.png',
    '华夏银行' : 'http://near.m1img.com/op_upload/137/147877793737.png',
    '中国工商银行' : 'http://near.m1img.com/op_upload/137/147877789275.png',
    '中国建设银行' : 'http://near.m1img.com/op_upload/137/147877796246.png',
    '交通银行' : 'http://near.m1img.com/op_upload/137/147877798651.png',
    '中国民生银行' : 'http://near.m1img.com/op_upload/137/147877801427.png',
    '兴业银行' : 'http://near.m1img.com/op_upload/137/147877803862.png',
    '中国招商银行' : 'http://near.m1img.com/op_upload/137/147877806131.png',
    '中国农业银行' : 'http://near.m1img.com/op_upload/137/147877808663.png',
    '中国人民银行' : 'http://near.m1img.com/op_upload/137/147877811245.png',
    '中国银行' : 'http://near.m1img.com/op_upload/137/147877814632.png',
    '中国邮政储蓄银行' : 'http://near.m1img.com/op_upload/137/14787781854.png',
}

DEFAULT_BANK_ICON = 'http://near.m1img.com/op_upload/137/148843587903.png'

# 支付类型列表对应关系
BILL_TYPE_DETAIL = {
    'alipay': '支付宝交易',
    'tenpay': '微信交易',
    'jdpay' : '京东交易',
    'card' : '银行卡交易',
    'qq_pay' : 'QQ钱包',
    'hj_coupon': '好近补贴'
}

# 到账类型
BILL_TYPES = ['alipay', 'tenpay', 'jdpay', 'card', 'qq_pay', 'hj_coupon']

# 本店创建特卖title
CONSUMED_SALE_TITLE = '本店精选超值特卖'

# 附近店铺特卖title
NEAR_SALE_TITLE = '好近推荐附近特卖'

# 首页数据panel
DATA_PANELS = {
    'sale_data' : {
        'color' : '#f4d32e', # 面板颜色
        'title' : '进行中的活动：特卖',
        'dismode' : 'actv', # 展示方式
        'actv_info' : {
            'title' : u'{title}',
            'icon' : 'http://near.m1img.com/op_upload/137/148109875364.png',
            'desc' : '活动已进行{ondays}天'
        },
        'datas' : [
            {'desc':'曝光数', 'count':'{total_query}', 'unit':'次'},
            {'desc':'购买数', 'count':'{sales_count}', 'unit':'次'},
            {'desc':'兑换数', 'count':'{buy_count}', 'unit':'次'},
        ],
        'link' : 'nearmcht://view-special-sale'
    },
    'card_data' : {
        'color' : '#8883f4', # 面板颜色
        'dismode' : 'actv', # 展示方式
        'actv_info' : {
            'title' : u'满{exchange_pt}点可换{goods_name}',
            'icon' : 'http://near.m1img.com/op_upload/137/148109872579.png',
            'desc' : '活动已进行{ondays}天'
        },
        'title' : '进行中的活动：集点', # 展示方式
        'datas' : [
            {'desc':'参与人数', 'count':'{customer_num}', 'unit':'人'},
            {'desc':'会员复购数', 'count':'{rebuy}', 'unit':'次'},
            {'desc':'兑换数', 'count':'{exchange_num}', 'unit':'份'},
        ],
        'link' : 'nearmcht://view-member-card'
    },
    'coupon_data' : {
        'color' : '#ff0000', # 面板颜色
        'dismode' : 'actv', # 展示方式
        'actv_info' : {
            'title' : u'{title}',
            'icon' : 'http://near.m1img.com/op_upload/137/148170401623.png',
            'desc' : u'活动已进行{ondays}天'
        },
        'title' : '会员红包使用情况', # 展示方式
        'datas' : [
            {'desc':'领取数', 'count':'{used_num}', 'unit':'个'},
            {'desc':'使用数', 'count':'{use}', 'unit':'个'},
            {'desc':'刺激消费数', 'count':'{total_amt:.2f}', 'unit':'元'},
        ],
        'link' : 'nearmcht://view-coupon-activity'
    },
    'prepaid_data' : {
        'color' : '#ff0000', # 面板颜色
        'dismode' : 'actv', # 展示方式
        'actv_info' : {
            'title' : u'储值活动',
            'icon' : 'http://near.m1img.com/op_upload/137/148040324045.png',
            'desc' : u'活动已进行{ondays}天'
        },
        'title' : '储值活动情况', # 展示方式
        'datas' : [
            {'desc':'今日储值', 'count':'{today_total_pay_amt:.2f}', 'unit':'元'},
            {'desc':'储值会员', 'count':'{user_num}', 'unit':'位'},
            {'desc':'储值金额', 'count':'{total_pay_amt:.2f}', 'unit':'元'},
        ],
        'link' : 'https://o2.qfpay.com/prepaid/v1/page/b/index.html'
    },
    'today_data' : {
        'color' : '#257ce8', # 面板颜色
        'dismode' : 'census', # 展示方式
        'title' : '今日数据', # 展示方式
        'link' : '',
        'create_time' : {
            'default': 0,
            'and-030400': 90,
            'ios-030400': 100,
        },
        'datas' : [
            {'desc':'交易金额', 'count':'{total_amt:.2f}', 'unit':'元', 'more':'交易金额数据包含今日的微信支付、支付宝支付、京东支付、QQ钱包支付、储值充值、储值消费'},
            {'desc':'交易笔数', 'count':'{total_count}', 'unit':'笔'},
            {'desc':'新增会员', 'count':'{add_num}', 'unit':'个'},
            {'desc':'回头客', 'count':'{old_num}', 'unit' :'个'},
        ],
    }
}

# 好近建议
ADVICES = [{ # 顾客少
        'from' : 'datas',
        'limit' : 'data["newc_7d_rank_p"] >= 24',
        'desc' : ('新客少，近7天新增会员有<font color="#ff8100">{newc_7d_cnt}</font>人，'
                  '落后<font color="#ff8100">{newc_7d_rank_p:.0f}%</font>的本地同行，'
                  '马上创建活动增加客流吸粉。'),
        'link' : 'http://wx.qfpay.com/near-v2/activity-create.html',
        'button_desc' : '创建活动'
    }, { # 回头客少
        'from' : 'datas',
        'limit' : 'data["activec_30d_rank_p"] >= 30',
        'desc' : ('回头客少，近30天有<font color="#ff8100">{activec_30d_cnt}</font>个会员到店消费两次以上，'
                  '低于<font color="#ff8100">{activec_30d_rank_p:.0f}%</font>的本地同行。'),
        'link' : 'http://wx.qfpay.com/near-v2/activity-create.html',
        'button_desc' : '创建活动'
    }, { # 会员流失严重
        'from' : 'datas',
        'limit' : 'data["lossc_60d_rank_p"] >= 70',
        'desc' : ('会员流失严重，近60天有<font color="#ff8100">{lossc_60d_cnt}</font>'
                  '个会员没有再次到店消费，高于<font color="#ff8100">{lossc_60d_rank_p:.0f}%</font>'
                  '的本地同行。'),
        'link' : 'http://wx.qfpay.com/near-v2/activity-create.html',
        'button_desc' : '创建活动'
    }, { # 会员过期
        'from' : 'vip',
        'limit' : 'data["status"] and data["overdue"]',
        'desc' : '会员服务到期提醒，你的会员服务已经到期，赶紧续费吧',
        'link' : 'nearmcht://view-member-pay',
        'button_desc' : '立即续费',
    }, { # 特卖库存
        'from' : 'sale',
        'limit' : 'data["quantity_p"] > 5',
        'desc' : '特卖商品即将售罄提醒，你的{title}特卖商品即将售罄，是否增加库存？',
        'link' : 'nearmcht://view-special-sale',
        'button_desc' : '编辑特卖'
    },
]
# 默认建议
DEFAULT_ADVICE = {
    'title' : '经营贴士',
    'color' : '#ff8100',
}

# 数据tips
DATA_TIPS = {
     'notify_cp_link' : 'nearmcht://view-member-notify',
     'notify_cp_title' : '红包通知活动情况',
     'notify_cp_desc' : '等待通知',
     'back_cp_title' : '消费返红包活动情况',
     'share_cp_title' : '分享红包活动情况',
     'actv_default_desc' : '活动即将开始',
 }

# 活动结案报告返回
ACTV_EFFECT = {
    1 : { # 集点活动
        'datas' : [{
            'title' : '参与会员数',
            'desc' : '{customer_num}位'
        }, {
            'title' : '集点数',
            'desc' : '{total_pt}点'
        }, {
            'title' : '礼品兑换数',
            'desc' : '{exchange_num}份'
        }, {
            'title' : '礼品总价',
            'desc' : '{total_txamt:.2f}元'
        }],
        'effect' : [{
            'title' : '会员复购数',
            'desc' : '{rebuy}位'
        }, {
            'title' : '刺激消费',
            'desc' : '{total_amt:.2f}元'
        }],
        'rank' : '你的活动效果在同城同行业<span>{total_actv_cnt}</span>家商户中排名<span>{rk}</span>名 领先<span>{rk_p:.0f}%</span>的同行',
        'button' : {
            'link' : 'nearmcht://view-member-card',
            'name' : '立即创建新的集点活动'
        },
        '_desc_fmt' : '温馨提示：你的兑换{goods_name}的集点活动已结束，贴心备好数据报告，清晰呈现活动效果！#戳~立即查看#'
    },
    2 : { # 特卖活动
        'datas' : [{
            'title' : '售出数',
            'desc' : '{sales_count}份'
        }, {
            'title' : '兑换数',
            'desc' : '{buy_count}份'
        }, {
            'title' : '让利总计',
            'desc' : '{total_cheap_amt:.2f}元'
        }],
        'effect' : [{
            'title' : '曝光数',
            'desc' : '{total_query}次'
        }, {
            'title' : '特卖收入',
            'desc' : '{total_amt:.2f}元'
        }],
        'rank' : '你的活动效果在同城同行业<span>{total_actv_cnt}</span>家商户中排名<span>{rk}</span>名 领先<span>{rk_p:.0f}%</span>的同行',
        'button' : {
            'link' : 'nearmcht://view-special-sale',
            'name' : '立即创建新的特卖活动'
        }
    },
    3 : { # 消费返红包
        'datas' : [{
            'title' : '红包发放数',
            'desc' : '{used_num}个'
        }, {
            'title' : '红包核销数',
            'desc' : '{cnt}个'
        }, {
            'title' : '活动预算',
            'desc' : '{total_amt:.2f}元'
        }, {
            'title' : '实际花销',
            'desc' : '{t_coupon_amt:.2f}元'
        }],
        'effect' : [{
            'title' : '老会员到店数',
            'desc' : '{c_cnt}位'
        }, {
            'title' : '刺激消费',
            'desc' : '{total_amt:.2f}元'
        }],
        'rank' : '你的活动效果在同城同行业<span>{total_actv_cnt}</span>家商户中排名<span>{rk}</span>名 领先<span>{rk_p:.0f}%</span>的同行',
        'button' : {
            'link' : 'nearmcht://view-coupon-activity',
            'name' : '立即创建新的消费返红包'
        }
    },
}
ACTV_EFFECT[30] = { #  消费分享红包
    'datas' : ACTV_EFFECT[3]['datas'],
    'effect' : [{
        'title' : '会员拉新',
        'desc' : '{c_cnt}位',
    }, {
        'title' : '刺激消费',
        'desc' : '{total_amt:.2f}元',
    }],
    'rank' : '你的活动效果在同城同行业<span>{total_actv_cnt}</span>家商户中排名<span>{rk}</span>名 领先<span>{rk_p:.0f}%</span>的同行',
    'button' : {
        'link' : 'nearmcht://view-coupon-activity',
        'name' : '立即创建新的分享红包'
    }
}
ACTV_EFFECT[31] = { # 红包通知
    'datas' : ACTV_EFFECT[3]['datas'],
    'effect' : [{
        'title' : '召回15天未到店会员',
        'desc' : '{c_cnt}位',
    }, {
        'title' : '刺激消费',
        'desc' : '{total_amt:.2f}元',
    }],
    'rank' : '你的活动效果在同城同行业<span>{total_actv_cnt}</span>家商户中排名<span>{rk}</span>名 领先<span>{rk_p:.0f}%</span>的同行',
    'button' : {
        'link' : 'nearmcht://view-member-notify',
        'name' : '立即创建新的红包通知'
    }
 }
TRADE_STATE_FIELDS = ['alipay', 'weixin', 'jdpay', 'qqpay', 'card', 'prepaid']

# 创建红包, 店铺通告, 特卖的rule
ACTV_TIPS = {
    'coupon': { # 分发红包
        'rule': ['确认提交后，将在次日以公众号的形式将你的店铺红包发给会员；',
                  '红包费用由商户承担，会员收到红包会<font color="#8b62e9">即时生效</font>；'],
        'preview': [{
            'title': '你的所有会员都关注了公众号，红包会通过公众号发送到您的会员，如下图所示：',
            'url': 'http://near.m1img.com/op_upload/148/148706137748.png'
        }, {
            'title': '会员每打开一次公众号，均可收到领取红包的通知。',
            'url': 'http://near.m1img.com/op_upload/137/148878391923.PNG'
        }]
    },
    'sale': { # 创建特卖
        'rule': ['会员购买后，需凭兑换码在有效期内到店兑换',
                 '兑换成功后的商品款项<font color="#8b62e9">于第二个工作日到账</font>',
                 '<font color="#8b62e9">未兑换的商品订单，款项不会到账</font>']
    },
    'promotion': { # 店铺公告
        'preview' : [{
            'title' : '创建店铺公告后，会员扫描店内支付二维码即可查看。',
            'url' : 'http://near.m1img.com/op_upload/137/147038864457.jpg'
        }, {
            'title' : '你的所有会员都关注了公众号，可随时在公众号菜单中查看你的店铺公告。',
            'url' : 'http://near.m1img.com/op_upload/148/148671674279.png'
        }]
    },
    'privilege': { # 特权
        'rule': [
        '会员特权创建成功后会通过公众号的会员中心展示给你的会员，权益表述清晰明确，能吸引更多顾客到店哦',
            '一切活动解释权归本店所有'
        ]
    }
}

# 默认数据列表
DATA_DEFAULT_DESC_FMT = '温馨提示：你的{title}活动已结束，贴心备好数据报告，清晰呈现活动效果！#戳~立即查看#'
# 列表默认图像
DATA_DEFAULT_IMG_URL = 'http://near.m1img.com/op_upload/118/149933500445.png'
# 详细页url
DATA_DEFAULT_INFO_URL = 'http://wx.qfpay.com/near-v2/data-record.html?id={}'

## 会员信息
# 会员列表过滤
MEMBER_FILTERS =  [{
    'all': '全部',
}, {
    'prepaid': '储值会员',
}, {
    'card': '集点会员',
#}, {
    #'active': '活跃会员',
}, {
    'lose': '流失会员',
}]
# 会员排序
MEMBER_SORTS =  [{
    'last_txdtm|desc': '到店时间由近到远',
}, {
    'last_txdtm': '到店时间由远到近',
}, {
    'num|desc': '到店次数由多到少'
}, {
    'num': '到店次数由少到多'
}, {
    'txamt|desc': '消费金额由多到少'
}, {
    'txamt': '消费金额由少到多'
}]
# 会员flag
MEMBER_FLAGS=  [{
    'card': 'http://near.m1img.com/op_upload/137/148040326588.png'
}, {
    'prepaid': 'http://near.m1img.com/op_upload/137/148040324045.png'
}]

# 会员列表bg_url
CARDS_INFO_BG_URLS = [
    'http://near.m1img.com/op_upload/137/149312537901.png',
    'http://near.m1img.com/op_upload/137/149312535791.png',
    'http://near.m1img.com/op_upload/137/149312529708.png',
    'http://near.m1img.com/op_upload/137/149312475077.png'
]

# 会员详细bg_url
CARDS_BG_URLS = [
    'http://near.m1img.com/op_upload/155/149319979482.png',
    'http://near.m1img.com/op_upload/155/149319978551.png',
    'http://near.m1img.com/op_upload/155/149319977648.png',
    'http://near.m1img.com/op_upload/155/149319976605.png',
]


