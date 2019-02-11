# encoding:utf-8

import json

data = {
    '系统繁忙': json.dumps({
       'zh-cn': '系统繁忙',
       'zh-hk': '系統繁忙',
       'ja-jp': 'システムに忙しい',
       'en-us': 'The system is busy',
    }),

    '获取菜单失败': json.dumps({
       'zh-cn': '获取菜单失败',
       'zh-hk': '獲取菜單失敗',
       'ja-jp': 'データを取得できません',
       'en-us': 'Failed to get the data',
    }),
    '修改密码': json.dumps({
       'zh-cn': '修改密码',
       'zh-hk': '修改密碼',
       'ja-jp': 'パスワード変更',
       'en-us': 'Change password',
    }),
    '交易提示': json.dumps({
       'zh-cn': '交易提示',
       'zh-hk': '交易提示',
       'ja-jp': '取引提示',
       'en-us': 'Transaction hint',
    }),
    '自动打印小票': json.dumps({
       'zh-cn': '自动打印小票',
       'zh-hk': '自動打印小票',
       'ja-jp': '自動的にレシピ―を印刷',
       'en-us': 'Print the receipt automatically',
    }),
    '软件授权': json.dumps({
       'zh-cn': '软件授权',
       'zh-hk': '軟件授權',
       'ja-jp': 'ソフトウェアの授権',
       'en-us': 'Software agreement',
    }),
    '常见问题': json.dumps({
       'zh-cn': '常见问题',
       'zh-hk': '常見問題',
       'ja-jp': 'よくあるご質問',
       'en-us': 'FAQ',
    }),
    '检查更新': json.dumps({
       'zh-cn': '检查更新',
       'zh-hk': '檢查更新',
       'ja-jp': '更新のチェック',
       'en-us': 'Check for updates',
    }),
    '设置屏幕常亮': json.dumps({
       'zh-cn': '设置屏幕常亮',
       'zh-hk': '設置螢幕長亮',
       'ja-jp': '画面を常時点灯させ',
       'en-us': 'Keep screen always on',
    }),
    '店铺签约信息': json.dumps({
       'zh-cn': '店铺签约信息',
       'zh-hk': '店鋪簽約信息',
       'ja-jp': '店舗契約情報',
       'en-us': 'Shop subscription information',
    }),
    '店铺收款码': json.dumps({
       'zh-cn': '店铺收款码',
       'zh-hk': '店鋪收款嗎',
       'ja-jp': '店舗集金コード',
       'en-us': 'QR code',
    }),
    '我的银行卡': json.dumps({
       'zh-cn': '我的银行卡',
       'zh-hk': '我的銀行卡',
       'ja-jp': 'マイ銀行カード',
       'en-us': 'My bank card',
    }),
    '我的服务': json.dumps({
       'zh-cn': '我的服务',
       'zh-hk': '我的服務',
       'ja-jp': 'マイサービス',
       'en-us': 'My service',
    }),
    '推荐给好友': json.dumps({
       'zh-cn': '推荐给好友',
       'zh-hk': '推薦給好友',
       'ja-jp': '友達にシェア',
       'en-us': 'Share to friends',
    }),
    '联系客服': json.dumps({
       'zh-cn': '联系客服',
       'zh-hk': '聯繫客服',
       'ja-jp': 'お問い合わせ',
       'en-us': 'Customer service',
    }),
    '设置': json.dumps({
       'zh-cn': '设置',
       'zh-hk': '設置',
       'ja-jp': '設定',
       'en-us': 'Settings',
    }),
    '多语言': json.dumps({
       'zh-cn': '多语言',
       'zh-hk': '多語言',
       'ja-jp': '言語',
       'en-us': 'Language',
    }),
    '交易提示音': json.dumps({
       'zh-cn': '交易提示音',
       'zh-hk': '交易提示音',
       'ja-jp': '取引効果音',
       'en-us': 'Notice',
    }),

    ## 首页数据接口 /mchnt/user/v1/home_page
    '获取首页数据失败': json.dumps({
       'zh-cn': '获取首页数据失败',
       'zh-hk': '獲取首頁數據失敗',
       'ja-jp': 'データが読み取れませんでした',
       'en-us': 'Fail to get data',
    }),
    '外卖管理': json.dumps({
       'zh-cn': '外卖管理',
       'zh-hk': '外賣管理',
       'ja-jp': 'テイクアウト管理',
       'en-us': 'Takeout',
    }),
    '外卖订单': json.dumps({
       'zh-cn': '外卖订单',
       'zh-hk': '外賣訂單',
       'ja-jp': 'テイクアウト注文書',
       'en-us': 'Takeout order',
    }),
    '折扣买单': json.dumps({
       'zh-cn': '折扣买单',
       'zh-hk': '折扣買單',
       'ja-jp': '日语-折扣买单',
       'en-us': 'zhekou maidan',
    }),
    '特卖验证': json.dumps({
       'zh-cn': '特卖验证',
       'zh-hk': '特賣驗證',
       'ja-jp': 'セール検証',
       'en-us': 'Sale verification',
    }),
    '设计服务': json.dumps({
       'zh-cn': '设计服务',
       'zh-hk': '設計服務',
       'ja-jp': '設計サービス',
       'en-us': 'Design service',
    }),
    '到账记录': json.dumps({
       'zh-cn': '到账记录',
       'zh-hk': '到賬記錄',
       'ja-jp': '入金記録',
       'en-us': 'Transfers',
    }),
    '会员红包': json.dumps({
       'zh-cn': '会员红包',
       'zh-hk': '會員紅包',
       'ja-jp': '会員紅包',
       'en-us': 'Red packet',
    }),
    '物料商城': json.dumps({
       'zh-cn': '物料商城',
       'zh-hk': '物料商城',
       'ja-jp': '材料市場',
       'en-us': 'Materials mall',
    }),
    '会员管理': json.dumps({
       'zh-cn': '会员管理',
       'zh-hk': '會員管理',
       'ja-jp': '会員管理',
       'en-us': 'Member management',
    }),
    '官方活动': json.dumps({
       'zh-cn': '官方活动',
       'zh-hk': '官方轟動',
       'ja-jp': '公式活動',
       'en-us': 'Official event',
    }),
    '商户贷款': json.dumps({
       'zh-cn': '商户贷款',
       'zh-hk': '商戶貸款',
       'ja-jp': '商店ローン',
       'en-us': 'Merchant loan',
    }),
    '经营分析': json.dumps({
       'zh-cn': '经营分析',
       'zh-hk': '經營分析',
       'ja-jp': '経営分析',
       'en-us': 'Operation analysis',
    }),
    '活动营销': json.dumps({
       'zh-cn': '活动营销',
       'zh-hk': '活動營銷',
       'ja-jp': '日语-活动营销',
       'en-us': '活动营销',
    }),
    '会员集点': json.dumps({
       'zh-cn': '会员集点',
       'zh-hk': '會員集點',
       'ja-jp': '会員ポイント集め',
       'en-us': 'Member point collection',
    }),
    '点餐订单': json.dumps({
       'zh-cn': '点餐订单',
       'zh-hk': '點餐訂單',
       'ja-jp': '注文書',
       'en-us': 'Order sheet',
    }),
    '商品管理': json.dumps({
       'zh-cn': '商品管理',
       'zh-hk': '商品管理',
       'ja-jp': '商品管理',
       'en-us': 'Products',
    }),
    '点餐打印': json.dumps({
       'zh-cn': '点餐打印',
       'zh-hk': '點餐打印',
       'ja-jp': 'オーダー印刷',
       'en-us': 'Print order',
    }),
    '会员通知': json.dumps({
       'zh-cn': '会员通知',
       'zh-hk': '會員通知',
       'ja-jp': '会員通知',
       'en-us': 'Member notification',
    }),
    '特卖': json.dumps({
       'zh-cn': '特卖',
       'zh-hk': '特賣',
       'ja-jp': 'セール',
       'en-us': 'Sale',
    }),
    '点餐': json.dumps({
       'zh-cn': '点餐',
       'zh-hk': '點餐',
       'ja-jp': 'オーダー',
       'en-us': 'Order',
    }),
    '会员储值': json.dumps({
       'zh-cn': '会员储值',
       'zh-hk': '會員儲值',
       'ja-jp': '会員プリペイド',
       'en-us': 'Member prepaid',
    }),
    '店铺公告': json.dumps({
       'zh-cn': '店铺公告',
       'zh-hk': '店鋪公告',
       'ja-jp': '店舗公示',
       'en-us': 'Shop announcement',
    }),
    '金融理财': json.dumps({
       'zh-cn': '金融理财',
       'zh-hk': '金融理財',
       'ja-jp': '金融理財',
       'en-us': 'Financial planning',
    }),
    '会员分析': json.dumps({
       'zh-cn': '会员分析',
       'zh-hk': '會員分析',
       'ja-jp': '会員分析',
       'en-us': 'Member analysis',
    }),
    '会员特权': json.dumps({
       'zh-cn': '会员特权',
       'zh-hk': '會員特權',
       'ja-jp': '会員特権',
       'en-us': 'Member privilege',
    }),
    '立即收款': json.dumps({
       'zh-cn': '立即收款',
       'zh-hk': '立即收款',
       'ja-jp': '今すぐ集金',
       'en-us': 'Collect money',
    }),
    '查看流水': json.dumps({
       'zh-cn': '查看流水',
       'zh-hk': '查看流水',
       'ja-jp': '売上一覧',
       'en-us': 'Transactions',
    }),
    '更多': json.dumps({
       'zh-cn': '更多',
       'zh-hk': '更多',
       'ja-jp': '更に',
       'en-us': 'More',
    }),
    '会员功能': json.dumps({
       'zh-cn': '会员功能',
       'zh-hk': '會員功能',
       'ja-jp': '会員機能',
       'en-us': 'Member Management',
    }),
    '营销功能': json.dumps({
       'zh-cn': '营销功能',
       'zh-hk': '營銷功能',
       'ja-jp': 'マーケティング機能',
       'en-us': 'Marketing',
    }),
    '智慧餐厅': json.dumps({
       'zh-cn': '智慧餐厅',
       'zh-hk': '智慧餐廳',
       'ja-jp': 'スマートレストラン',
       'en-us': 'Smart Restaurant',
    }),
    '其他功能': json.dumps({
       'zh-cn': '其他功能',
       'zh-hk': '其他功能',
       'ja-jp': 'その他の機能',
       'en-us': 'Others',
    }),
    '获取功能模块失败': json.dumps({
       'zh-cn': '获取功能模块失败',
       'zh-hk': '獲取功能模塊失敗',
       'ja-jp': 'データが読み取れませんでした',
       'en-us': 'Failed to get the data',
    }),


    # 审核相关
    '审核通过': json.dumps({
       'zh-cn': '审核通过',
       'zh-hk': '審核通過',
       'ja-jp': '監査を通じて',
       'en-us': 'Audit succeed',
    }),
    '审核中': json.dumps({
       'zh-cn': '审核中',
       'zh-hk': '審核中',
       'ja-jp': '監査中',
       'en-us': 'Auditing',
    }),
    '审核驳回': json.dumps({
       'zh-cn': '审核驳回',
       'zh-hk': '審核駁回',
       'ja-jp': '監査差し戻し ',
       'en-us': 'Audit failed',
    }),


    # 登录相关
    '账号或密码有误,请重新输入': json.dumps({
       'zh-cn': '账号或密码有误,请重新输入',
       'zh-hk': '賬號或密碼有誤,請重新輸入',
       'ja-jp': 'アカウント又はパスワードが間違っています。もう一度入力してください',
       'en-us': 'Account or password is wrong, please try again',
    }),
    '商户角色错误': json.dumps({
       'zh-cn': '商户角色错误',
       'zh-hk': '商戶角色錯誤',
       'ja-jp': '間違い商店類別',
       'en-us': 'Incorrect merchant type ',
    }),
    '您的账号未注册，请先注册一下吧': json.dumps({
       'zh-cn': '您的账号未注册，请先注册一下吧',
       'zh-hk': '您的賬號未註冊，請先註冊一下吧',
       'ja-jp': 'このアカウントは未登録です。今すぐ登録しますか。',
       'en-us': 'The account has not been registered yet, register now?',
    }),
    '该操作员不存在': json.dumps({
       'zh-cn': '该操作员不存在',
       'zh-hk': '該操作員不存在',
       'ja-jp': '当該オペレータは存在していません',
       'en-us': 'This operator does not exist',
    }),
    '账号状态有问题哟，联系客服问问吧。电话': json.dumps({
       'zh-cn': '账号状态有问题哟，联系客服问问吧。电话',
       'zh-hk': '賬號狀態有問題喲,聯繫客服問問吧。電話》',
       'ja-jp': 'カウントの状態に問題がありますよ。お問い合わせください。電話番号：',
       'en-us': 'There are some problems with your account, try to call this number:',
    }),

    # 退出登录
    '用户退出登录失败': json.dumps({
       'zh-cn': '用户退出登录失败',
       'zh-hk': '用戶登出失敗',
       'ja-jp': 'ユーザはログアウトできませんでした',
       'en-us': 'Logout fail',
    }),


    # 流水筛选
    '全部': json.dumps({
       'zh-cn': '全部',
       'zh-hk': '全部',
       'ja-jp': '全部',
       'en-us': 'all',
    }),
    '刷卡收款': json.dumps({
       'zh-cn': '刷卡收款',
       'zh-hk': '刷卡收款',
       'ja-jp': 'カード',
       'en-us': 'Card',
    }),
    '刷卡用户': json.dumps({
       'zh-cn': '刷卡用户',
       'zh-hk': '刷卡用户',
       'ja-jp': 'カード',
       'en-us': 'Card',
    }),
    '支付宝收款': json.dumps({
       'zh-cn': '支付宝收款',
       'zh-hk': '支付寶收款',
       'ja-jp': 'Alipay',
       'en-us': 'Alipay',
    }),
    '收款码收款': json.dumps({
       'zh-cn': '收款码收款',
       'zh-hk': '收款碼收款',
       'ja-jp': 'QRコード',
       'en-us': 'QRcode',
    }),
    '支付宝用户': json.dumps({
       'zh-cn': '支付宝用户',
       'zh-hk': '支付寶用戶',
       'ja-jp': 'Alipay',
       'en-us': 'Alipay',
    }),
    '微信收款': json.dumps({
       'zh-cn': '微信收款',
       'zh-hk': '微信收款',
       'ja-jp': 'Wechat',
       'en-us': 'Wechat',
    }),
    '微信用户': json.dumps({
       'zh-cn': '微信用户',
       'zh-hk': '微信用戶',
       'ja-jp': 'Wechat',
       'en-us': 'Wechat',
    }),
    '百度收款': json.dumps({
       'zh-cn': '百度收款',
       'zh-hk': '百度收款',
       'ja-jp': 'baidu pay',
       'en-us': 'baidu pay',
    }),
    '百度钱包用户': json.dumps({
       'zh-cn': '百度钱包用户',
       'zh-hk': '百度錢包用戶',
       'ja-jp': 'baidu',
       'en-us': 'baidu',
    }),
    '京东收款': json.dumps({
       'zh-cn': '京东收款',
       'zh-hk': '京東收款',
       'ja-jp': 'JDPAY',
       'en-us': 'JDPAY',
    }),
    '京东用户': json.dumps({
       'zh-cn': '京东用户',
       'zh-hk': '京東',
       'ja-jp': 'JD',
       'en-us': 'JDpay',
    }),
    'QQ钱包收款': json.dumps({
       'zh-cn': 'QQ钱包收款',
       'zh-hk': 'QQ錢包收款',
       'ja-jp': 'QQpay',
       'en-us': 'QQpay',
    }),
    'QQ钱包用户': json.dumps({
       'zh-cn': 'QQ钱包用户',
       'zh-hk': 'QQ錢包',
       'ja-jp': 'QQpay',
       'en-us': 'QQpay',
    }),
    '储值反扫': json.dumps({
       'zh-cn': '储值反扫',
       'zh-hk': '儲值反掃',
       'ja-jp': 'jp-储值反扫',
       'en-us': 'en-储值反扫',
    }),
    '储值消费': json.dumps({
       'zh-cn': '储值消费',
       'zh-hk': '儲值消費',
       'ja-jp': 'プリペイドで消費',
       'en-us': 'Prepaid',
    }),
    '储值用户': json.dumps({
       'zh-cn': '储值用户',
       'zh-hk': '儲值用戶',
       'ja-jp': 'プリペイドユーザー ',
       'en-us': 'Prepaid',
    }),
    '首页':json.dumps({
       'zh-cn': '首页',
       'zh-hk': '首頁',
       'ja-jp': 'トップ',
       'en-us': 'Homepage',
    }),
    '更多':json.dumps({
       'zh-cn': '更多',
       'zh-hk': '更多',
       'ja-jp': 'サービス',
       'en-us': 'More',
    }),
    '消息':json.dumps({
       'zh-cn': '消息',
       'zh-hk': '消息',
       'ja-jp': 'メッセージ',
       'en-us': 'Message',
    }),
    '我的': json.dumps({
       'zh-cn': '我的',
       'zh-hk': '我的',
       'ja-jp': 'マイページ',
       'en-us': 'My',
    })
}
