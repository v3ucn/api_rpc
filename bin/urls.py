# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import tool
import app
import user
import coupon
import member
import bigmchnt
import card
import recharge
import notify
import zhongqiu_activity
import qudao
import bk
import mis
import bank
import trade
import third
import invoice
import mchnt_commission
from mchnt_activity import mchntactv
import sales

urls = (
    # ping
    ('^/mchnt/ping$', tool.index.Ping),
    # 验证csid
    ('^/mchnt/check_csid$', tool.index.CheckCsid),
    # setcookie
    ('^/mchnt/set_cookie$', tool.index.SetCookie),
    # 商户是否是白牌
    ('^/mchnt/is_baipai$', tool.index.IsBaiPai),

    ## init
    # app初始化
    ('^/mchnt/init$', app.app.Init),
    # app(v1版)初始化
    ('^/mchnt/app/v1/conf$', app.v1.Conf),

    ## 验证码相关接口
    # 验证码获取
    ('^/mchnt/smscode/send$', tool.smscode.Send),
    # 验证码检验
    ('^/mchnt/smscode/check$', tool.smscode.Check),
    # 邮政验证码获取
    ('^/mchnt/emailcode/send$', tool.smscode.EmailCodeSend),
    # 邮政验证码验证
    ('^/mchnt/code/check$', tool.smscode.Check),


    ## 商户相关接口
    # 用户登出
    ('^/mchnt/user/logout$', user.login.Logout),
    # 用户登录
    ('^/mchnt/user/login$', user.login.Login),
    # 用户预注册
    ('^/mchnt/user/pre_signup$', user.signup.PreSignup),
    # 用户注册
    ('^/mchnt/user/signup$', user.signup.Signup),
    # 用户修改密码
    ('^/mchnt/user/reset_pwd$', user.user.ResetPwd),
    # 检验用户是否注册
    ('^/mchnt/user/check$', user.user.Check),
    # 获取用户信息
    ('^/mchnt/user/info$', user.user.Info),
    # 获取用户信息 v1
    ('^/mchnt/user/v1/info$', user.v1.Info),
    # 获取首页信息
    ('^/mchnt/user/v1/home_page$', user.v1.HomePage),
    # 获取用户功能模块
    ('^/mchnt/user/v1/service$', user.v1.Service),
    # 获取用户数据
    ('^/mchnt/user/v1/data$', user.v1.Data),
    # 好近建议
    ('^/mchnt/user/v1/advice$', user.v1.Advice),
    # 获取用户统计信息
    ('^/mchnt/user/v1/stats$', user.v1.Stats),
    # 获取用户付费信息
    ('^/mchnt/user/v1/pay_info$', user.v1.PayInfo),
    # 创建店铺(补充商圈信息)
    ('^/mchnt/user/shop_create$', user.user.ShopCreate),
    # 获取用户二维码
    ('^/mchnt/user/qrcode$', user.user.GetQrcode),
    # 获取用户银行卡
    ('^/mchnt/user/bankinfo$', user.user.BankInfoHandler),
    # 修改用户信息
    ('^/mchnt/user/change$', user.user.Change),
    # 修改商户名称
    ('^/mchnt/user/v1/change$', user.user.Change_v1),
    # 修改用户账号
    ('^/mchnt/user/change_username$', user.user.ChangeUsername),
    # 获取商户审核状态
    ('^/mchnt/user/apply_info$', user.user.Apply_info),
    # 获取商户基本信息接口
    ('^/mchnt/user/mchnt_info$', user.user.MchntInfo),
    # 获取用户凭证信息
    ('^/mchnt/user/voucher$', user.user.VoucherInfo),
    # 获取商户费率
    ('^/mchnt/user/v1/ratio$', user.signup.Ratio),
    # audit 获取审核信息
    ('^/mchnt/user/v1/audit$', user.signup.Audit),
    # tab标记
    ('^/mchnt/user/tab_badge$', user.user.TabBadge),
    # 商户protocol
    ('^/mchnt/user/protocol$', user.user.Protocol),
    # 商户客服信息
    ('^/mchnt/user/csinfo$', user.user.CSInfo),
    # 用户我的菜单列表
    ('^/mchnt/user/v1/menu$', user.v1.Menu),
    ### 用户活动相关
    # 允许创建活动列表
    ('^/mchnt/user/allow_actvs$', user.actv.AllowActv),
    # 活动结案报告
    ('^/mchnt/user/actv_effect$', user.actv.ActvEffect),
    # 活动结案报告列表
    ('^/mchnt/user/data_list$', user.actv.DataList),
    ### 到账接口
    # settle 获取划款列表头部信息
    ('^/mchnt/user/v1/settle_head$', user.settle_v1.Head),
    # settle 获取到账记录列表
    ('^/mchnt/user/v1/settles$', user.settle_v1.List),
    # settle 获取到账记录详细信息总结
    ('^/mchnt/user/v1/settle_summary$', user.settle_v1.Summary),
    # settle 获取到账记录详细信息列表
    ('^/mchnt/user/v1/settle_details$', user.settle_v1.Details),
    # settle 获取到账记录列表
    ('^/mchnt/user/v1/settle_list$', user.settle.List),
    # settle 获取到账记录详细信息
    ('^/mchnt/user/v1/settle_info$', user.settle.Info),
    # 用户配置
    ('^/mchnt/user/v1/conf$', user.conf.Conf),
    ### 操作员配置
    # 操作员列表
    ('^/mchnt/opuser/list$', user.opuser.List),
    # 操作员信息
    ('^/mchnt/opuser/info$', user.opuser.Info),
    # 管理操作员状态
    ('^/mchnt/opuser/change$', user.opuser.Change),
    # 添加操作员
    ('^/mchnt/opuser/add$', user.opuser.AddOpuser),
    # 获取下一个操作员id
    ('^/mchnt/opuser/opuid$', user.opuser.Opuid),

    # 辅助类接口
    # 获取用户信息 (流水详细页获取店铺名和操作员名)
    ('^/mchnt/user/baseinfo$', user.info.BaseInfo),
    # 验证用户信息
    ('^/mchnt/user/valid$', user.info.Valid),
    # 打印结算单 (获取部分流水数据)
    ('^/mchnt/user/receipt$', user.trade.Receipt),
    # 上传打印信息 (打印结算单)
    ('^/mchnt/user/up_receipt_info$', user.trade.UpReceiptInfo),

    ## tool
    # 城市列表
    ('^/mchnt/tool/areacities$', tool.tool.AreaCities),
    # 城市列表
    ('^/mchnt/tool/cities$', tool.tool.CityList),
    # 商圈列表 (Kuma)
    ('^/mchnt/tool/get_regions$', tool.kuma_api.Regions),
    # 总行列表
    ('^/mchnt/tool/headbanks$', tool.tool.Headbanks),
    # 支行列表
    ('^/mchnt/tool/branchbanks$', tool.tool.BranchBanks),
    # 银行卡信息
    ('^/mchnt/tool/cardsinfo$', tool.tool.CardsInfo),
    # 店铺类型列表(通过kuma获取的店铺类型)
    ('^/mchnt/tool/shoptypes$', tool.kuma_api.ShopTypes),
    # 获取系统时间
    ('^/mchnt/tool/sysdt$', tool.tool.SystemDT),

    # 验证手机号
    ('^/mchnt/tool/check_mobile$', tool.tool.Check),
    # 验证账号
    ('^/mchnt/tool/check$', tool.tool.Check),


    ## 红包活动接口
    # 获取红包
    ('^/mchnt/activity/template$', coupon.actv.Template),
    # 创建活动
    ('^/mchnt/activity/create$', coupon.actv.Create),
    # 活动详细信息
    ('^/mchnt/activity/info$', coupon.actv.Info),
    # 活动列表
    ('^/mchnt/activity/list$', coupon.actv.List),
    # 修改活动状态
    ('^/mchnt/activity/change$', coupon.actv.Change),
    # 获取消费者信息
    ('^/mchnt/activity/customer$', coupon.actv.Customer),

    # 获取活动报名列表
    ('^/mchnt/activity/apply_entrance$', coupon.official.Entrance),
    # 获取活动报名列表
    ('^/mchnt/activity/apply_list$', coupon.official.List),
    # 获取活动报名详细信息
    ('^/mchnt/activity/apply_info$', coupon.official.Info),


    # 大湾区相关红包接口
    ('^/mchnt/coupon/dw/verify$', coupon.dw.Verify),
    ('^/mchnt/coupon/dw/verify_list$', coupon.dw.VerifyList),

    # 会员相关接口
    # 获取会员列表
    ('^/mchnt/member/list$', member.member.List),
    # 获取会员信息
    ('^/mchnt/member/info$', member.member.Info),
    # 创建会员活动
    ('^/mchnt/member/actv_create$', member.actv.Create),
    # 获取会员活动列表
    ('^/mchnt/member/actv_list$', member.actv.List),
    # 获取会员详细信息
    ('^/mchnt/member/actv_info$', member.actv.Info),
    # 管理会员活动
    ('^/mchnt/member/actv_manage$', member.actv.Manage),
    # 会员的促销信息列表 (c端)
    ('^/mchnt/member/promotion$', member.operate.Promotion),
    # 会员的促销详细信息 (c端)
    ('^/mchnt/member/promotion_info$', member.operate.PromotionInfo),

    # 会员v1接口
    # 会员头部信息
    ('^/mchnt/member/v1/head$', member.v1.Head),
    # 会员列表
    ('^/mchnt/member/v1/list$', member.v1.List),
    # 会员详细信息
    ('^/mchnt/member/v1/info$', member.v1.Info),
    # 交易更多信息
    ('^/mchnt/member/txmore$', member.member.Txmore),
    # 检验会员
    ('^/mchnt/member/check_member$', member.v1.CheckMember),
    # 获取会员列表
    ('^/mchnt/member/v1/add_tag$', member.v1.AddTag),

    # 会员特权
    # 获取会员特权
    ('^/mchnt/member/v1/privilege$', member.v1.Privilege),
    # 获取会员卡号
    ('^/mchnt/member/v1/cardno$', member.v1.Cardno),
    # 会员特权展示
    ('^/mchnt/member/privilege/display$', member.privilege.Display),
    # 会员特权创建
    ('^/mchnt/member/privilege/create$', member.privilege.Create),
    # 会员特权首页
    ('^/mchnt/member/privilege/index$', member.privilege.Index),
    # 会员特权修改
    ('^/mchnt/member/privilege/(?P<mode>(edit))$', member.privilege.Manage),

    ## 会员中心接口
    # 会员卡中心
    ('^/mchnt/member/centre/centre$', member.centre.Centre),
    # 会员卡详细
    ('^/mchnt/member/centre/cardinfo$', member.centre.CardInfo),
    # 消费者详细
    ('^/mchnt/member/centre/profile$', member.centre.Profile),
    # 更新消费者详细
    ('^/mchnt/member/centre/update_profile$', member.centre.UpdateProfile),
    # 获取二维码
    ('^/mchnt/member/centre/qrcode$', member.centre.Qrcode),
    # 会员卡列表
    ('^/mchnt/member/centre/cards$', member.centre.Cards),
    # 会员卡店铺列表
    ('^/mchnt/member/centre/shops$', member.centre.Shops),
    # 获取大商户签名
    ('^/mchnt/member/centre/card_ext$', member.centre.CardExt),
    # 优惠商家列表 - c端
    ('^/mchnt/member/shop/list$', member.shop.List),
    # 商户详细信息 - c端
    ('^/mchnt/member/shop/info$', member.shop.Info),
    # 消费者红包列表 - c端
    ('^/mchnt/member/coupon/list$', member.c_coupon.List),

    # bigchnt
    # 升级成为大商户
    ('^/mchnt/v1/bigmchnt/signup$', bigmchnt.ToBigMchnt),
    # 绑定子商户
    ('^/mchnt/v1/bigmchnt/bind$', bigmchnt.BindMchnt),

    # 热点营销活动
    ('^/mchntactv/list', mchntactv.MchntList),
    ('^/mchntactv/actvinfo', mchntactv.ActvInfo),
    ('^/mchntactv/prevsee', mchntactv.PrevSee),
    ('^/mchntactv/sendmail', mchntactv.Sendmail),


    #### 集点活动 ####

    ## 集点活动相关
    # 创建卡卷活动
    ('^/mchnt/card/v1/actv_create$', card.actv.Create),
    # 修改卡卷活动
    ('^/mchnt/card/v1/actv_change$', card.actv.Change),
    # 停止卡卷活动
    ('^/mchnt/card/v1/actv_close$', card.actv.Close),
    # 卡卷活动首页
    ('^/mchnt/card/v1/actv_index$', card.actv.Index),
    # 卡卷活动列表
    ('^/mchnt/card/v1/actv_list$', card.actv.List),
    # 卡卷活动信息
    ('^/mchnt/card/v1/actv_info$', card.actv.Info),
    # mis修改活动
    ('^/mchnt/card_mis/v1/change$', card.mis.Change),

    # customer
    # 会员集点活动会员集点信息
    ('^/mchnt/card/v1/customer_list$', card.customer.List),
    # 会员集点活动会员兑换信息
    ('^/mchnt/card/v1/exchange_list$', card.customer.ExchangeList),
    # 会员集点活动会员兑换
    ('^/mchnt/card/v1/exchange_goods$', card.customer.Exchange),

    ##  通知消息处理
    # 撤销集点
    ('^/mchnt/card/v1/cancel$', card.notify.Cancel),
    # 获取满足条件的集点活动
    ('^/mchnt/card/v1/query$', card.notify.Query),

    ## c端接口
    # 获取兑换码
    ('^/mchnt/card/v1/exchange_code$', card.operate.ExchangeCode),
    # 查询兑换码是否被兑换
    ('^/mchnt/card/v1/exchange_query$', card.operate.ExchangeQuery),
    # 我的卡包-列表
    ('^/mchnt/card/v1/card_list$', card.operate.CardList),
    # 我的卡包-详细信息
    ('^/mchnt/card/v1/card_info$', card.operate.CardInfo),
    # 会员集点 获取tips
    ('^/mchnt/card/v1/tips$', card.operate.Tips),

    ##################


    # 服务付费
    # 获取服务免费体验
    ('^/mchnt/recharge/v1/free$', recharge.recharge.Free),
    # 获取商品信息
    ('^/mchnt/recharge/v1/goods_info$', recharge.recharge.Info),
    # 查询优惠码
    ('^/mchnt/recharge/v1/promo_code$', recharge.recharge.PromoCode),
    # 商品下单
    ('^/mchnt/recharge/v1/create_order$', recharge.order.Create),
    # 查询订单
    ('^/mchnt/recharge/v1/query$', recharge.order.Query),
    # 获取qt2异步通知 (qt2回调)
    ('^/mchnt/recharge/v1/notify$', recharge.order.Notify),
    # 获取购买记录
    ('^/mchnt/recharge/v1/record$', recharge.record.List),
    #### 渠道相关
    # 推广的价格列表
    ('^/mchnt/recharge/promo/price_list$', recharge.promo.PriceList),
    # 推广的充值
    ('^/mchnt/recharge/promo/recharge$', recharge.promo.Recharge),
    # mis充值
    ('^/mchnt/recharge/mis/recharge$', recharge.mis.Recharge),
    # 获取商品列表
    ('^/mchnt/recharge/mis/goods_list$', recharge.mis.GoodsList),
    # 添加渠道
    ('^/mchnt/recharge/mis/add_promo$', recharge.mis.AddPromo),
    # 修改渠道
    ('^/mchnt/recharge/mis/change_promo$', recharge.mis.ChangePromo),
    # 添加渠道推广码
    ('^/mchnt/recharge/mis/add_promo_code$', recharge.mis.AddPromoCode),
    # 修改渠道推广码
    ('^/mchnt/recharge/mis/change_promo_code$', recharge.mis.ChangePromoCode),

    # 用户商品信息
    ('^/mchnt/recharge/v2/goods_info$', recharge.v2.Goods),
    # 支付预览
    ('^/mchnt/recharge/v2/preview$', recharge.v2.Preview),
    # 查询优惠码
    ('^/mchnt/recharge/v2/promo_code$', recharge.v2.PromoCode),
    # 商品下单
    ('^/mchnt/recharge/v2/create_order$', recharge.v2.OrderCreate),

    ## 商户通知
    # 通知类型
    ('^/mchnt/notify/type_list/?$', notify.notify_base.TypeList),
    # 运营汇总
    ('^/mchnt/notify/summary', notify.notify_base.Summary),
    # 红包效果汇总
    ('^/mchnt/notify/coupon/summary', notify.coupon.Summary),
    # 红包效果列表
    ('^/mchnt/notify/coupon_effect/list', notify.coupon.EffectList),
    # 红包详情
    ('^/mchnt/notify/coupon/verbose', notify.coupon.Verbose),
    # 红包设置规则
    ('^/mchnt/notify/coupon/rule', notify.coupon.Rule),
    # 创建红包
    ('^/mchnt/notify/coupon/create', notify.coupon.Create),
    # 预览
    ('^/mchnt/notify/coupon/preview', notify.coupon.Preview),
    # 废弃
    ('^/mchnt/notify/coupon/remove', notify.coupon.Remove),
    # 推广总体效果
    ('^/mchnt/notify/promotion/summary', notify.promotion.Summary),
    # 推广预览
    ('^/mchnt/notify/promotion/preview', notify.promotion.Preview),
    # 推广效果列表
    ('^/mchnt/notify/promotion_effect/list', notify.promotion.EffectList),
    # 推广效果列表
    ('^/mchnt/notify/promotion/rule', notify.promotion.Rule),

    ## 特卖
    # 特卖列表
    ('^/mchnt/notify/sale/list', notify.sale.List),
    # 特卖规则
    ('^/mchnt/notify/sale/rule', notify.sale.Rule),
    # 特卖删除
    ('^/mchnt/notify/sale/remove', notify.sale.Remove),
    # 特卖统计
    ('^/mchnt/notify/sale/summary', notify.sale.Summary),
    # 特卖修改
    ('^/mchnt/notify/sale/change', notify.sale.Change),
    # 特卖创建
    ('^/mchnt/notify/sale/create', notify.sale.Create),
    # 特卖规则
    ('^/mchnt/notify/sale/rule', notify.sale.Rule),
    # 特卖列表 (c端)
    ('^/mchnt/notify/sale/notify_list', notify.sale.NotifyList),
    # 附近特卖列表 (c端)
    ('^/mchnt/notify/sale/near_list', notify.sale.NearSaleList),
    # 订单列表
    ('^/mchnt/notify/sale/order_list', notify.sale.OrderList),
    # 特卖列表 (c端)
    ('^/mchnt/notify/sale/all_sale', notify.sale.AllSale),
    # 获取最近的特卖订单
    ('^/mchnt/notify/sale/latest_orders$', notify.sale.LatestOrders),
    # 完成页特卖
    ('^/mchnt/notify/sale/tips$', notify.sale.Tips),
    # 本店其他特卖
    ('^/mchnt/notify/sale/other$', notify.sale.Other),

    # 中秋活动效果排行榜
    ('^/mchnt/zhongqiu_activity/rank_list', zhongqiu_activity.RankList),

    ## qudao 调的接口
    ('^/mchnt/qd/audit_stat', qudao.qudao.AuditStat),
    # 获取商户结算类型T1/D1
    ('^/mchnt/qd/settle_type', qudao.qudao.SettleType),

    ## 生意王接口
    # 获取数据
    ('^/mchnt/bk/stat', bk.mchnt.Stat),
    # 生意王意向
    ('^/mchnt/bk/apply', bk.mchnt.Apply),

    # mis用到的接口
    ('^/mchnt/mis/service_list', mis.service.List),
    # mis获取服务列表
    ('^/mchnt/mis/module_service', mis.service.ServiceList),
    # 大商户注册
    ('^/mchnt/user/bigmchnt_signup$', user.signup.ToBigMchnt),

    # 意锐小票数据
    ('^/mchnt/receipt/info$', tool.receipt_data.ReceiptInfo),

    # 推送绑定
    ('^/qmm/wd/app/near/ios_bind$', user.token.IosSet),
    ('^/qmm/wd/app/near/ios_token_set$', user.token.IosSet),
    ('^/qmm/wd/app/near/android_bind$', user.token.AndSet),
    ('^/qmm/wd/app/near/android_token_set$', user.token.AndSet),

    # 获取tabs
    ('^/mchnt/user/v1/tabs$', user.v1.Tabs),
    # 获取账户类型信息
    ('^/mchnt/account/type$', bank.modify_account.AccountTypeHandler),
    # 获取银行卡及审核信息
    ('^/mchnt/user/v2/bankinfo$', bank.modify_account.BankInfoHandler),
    # 获取银行卡变更条款
    ('^/mchnt/change_account/items$', bank.modify_account.ChangeItemsHandler),
    # 银行卡三要素验证
    ('^/mchnt/validate_account$', bank.modify_account.VerifyAccountHandler),
    # 银行卡变更信息
    ('^/mchnt/bank/change$', bank.modify_account.ChangeAccountHandler),
    # 省市信息
    ('^/mchnt/tool/province/cities', bank.modify_account.ProvinceCityHandler),
    # 获取银行卡常见问题
    ('^/mchnt/bank/modify_account/introductions$', bank.modify_account.BankCardQuestionHandler),
    # 获取连锁店常见问题
    ('^/mchnt/user/shop/introductions$', user.shops.ShopQuestionHandler),

    # 消费券
    # 兑换
    ('^/mchnt/goods_coupon/exchange$', coupon.goods_coupon.Exchange),
    # 兑换记录
    ('^/mchnt/goods_coupon/record$', coupon.goods_coupon.RecordList),
    # 兑换券状态
    ('^/mchnt/goods_coupon/status$', coupon.goods_coupon.Status),

    # 我的商户列表
    ('^/mchnt/user/shops', user.shops.Shops),
    # 商户详情
    ('^/mchnt/user/shop/detail', user.shops.Detail),
    # 解绑子店
    ('^/mchnt/user/shop/delete', user.shops.Delete),
    # 验证密码是否正确
    ('^/mchnt/user/validate_password', user.shops.ValidatePassword),

    # 获取最新创建的商户的信息
    ('^/mchnt/latestshop/info', user.shops.GetLatestShopInfo),

    # 操作员退款权限列表
    ('^/mchnt/opuser/perm/list$', user.opuser.DebitBackList),
    # 变更操作员权限
    ('^/mchnt/opuser/perm/change$', user.opuser.ChangePerm),
    # 获取操作员权限
    ('^/mchnt/opuser/perms$', user.opuser.UserPerm),

    # 修改门店密码
    ('^/mchnt/user/shop/modify_password', user.shops.ModifyShopPassword),

    # 门店账户是否接收收银员播报
    ('^/mchnt/user/shop/is_receive_push', user.shops.IsReceivePush),

    # 开启接收收银员交易播报
    ('^/mchnt/user/shop/set_receive_push', user.shops.SetReceivePush),

    # 添加意向合作商户
    ('^/mchnt/intentcoopman/add', user.intent_coopman.AddIntentMchnt),

    ('^/mchnt/intentcoopman/query_count', user.intent_coopman.QueryCount),

    # 微信会员卡激活
    ('^/mchnt/wxcard/interface_active', member.wxcard.InterfaceActive),

    # 获取当前商户是否开启会员实名认证， 和会员总数，实名总数信息
    ('^/mchnt/member/real_auth_info', member.real_auth.GetInfo),

    # 设置商户的实名认证状态
    ('^/mchnt/member/onoroff_real_auth', member.real_auth.SetMemberAuth),

    # 获取商户实名认证的文本和图片
    ('^/mchnt/member/real_auth_desc', member.real_auth.GetDocAndImg),

    # 合规商户补件的相关接口
    # 查询当前商户补件的信息
    ('^/mchnt/user/supplied_info', user.supply_mchinfo.SuppliedInfo),
    ('^/mchnt/user/supply_info', user.supply_mchinfo.SupplyInfo),
    ('^/mchnt/user/query_supplied_userid', user.supply_mchinfo.QuerySuppliedUserid),

    # 短信营销创建
    ('^/mchnt/member/message/info$', member.message.InfoMessages),
    # 短信下单
    ('^/mchnt/member/message/create_order$', member.message.Create),
    # 短信列表
    ('^/mchnt/member/message/list$', member.message.List),

    # 短信营销常见问题
    ('^/mchnt/member/message/introductions$', member.message.MessageQuestionHandler),
    # 给商户设置管理密码
    ('^/mchnt/user/set_manage_password', user.user.SetManagePassword),
    # 给商户重置管理密码
    ('^/mchnt/user/reset_manage_password', user.user.ResetManagePassword),

    # qiantai2接口
    ('^/mchnt/qt/v1/payment', trade.trade.Payment),
    ('^/mchnt/qt/v1/query', trade.trade.Query),
    # 零售通
    ('^/mchnt/oauth/authorize', third.lst.Code),
    ('^/mchnt/oauth/token', third.lst.AccessToken),
    ('^/mchnt/oauth/get_user', third.lst.GetUser),

    # 语音播报锦囊
    ('^/mchnt/voice/broadcast', member.message.VOICEBROADHandler),

    ('^/mchnt/oauth/supplied', third.lst.SuppliedInfo),
    ('^/mchnt/oauth/supplyinfo', third.lst.SupplyInfo),
    ('^/mchnt/oauth/get_area', third.lst.GetArea),

    # 收银员交易统计
    ('^/mchnt/opuser/trade$', trade.trade.TradeTotal),

    # 添加发票
    ('^/mchnt/invoice/add$', invoice.mchnt_invoice.AddInvoice),
    # 获取发票信息
    ('^/mchnt/invoice/list$', invoice.mchnt_invoice.InvoiceList),

    # 佣金汇总
    ('^/mchnt/commission/summary', mchnt_commission.commission.CommissionSummary),
    # 佣金明细
    ('^/mchnt/commission/detail', mchnt_commission.commission.CommissionDetail),
    # 获取用户二维码
    ('^/mchnt/invoice/qrcode$', invoice.mchnt_invoice.GetInvoiceQrcode),

    #签约宝活动获取审核状态
    ('^/mchnt/salesman/v1/status$', sales.sales.GetStatus),
    #签约宝活动上传参数和图片
    ('^/mchnt/salesman/v1/upload$', sales.sales.Upload),
    #签约宝活动返回商户图片地址和字段
    ('^/mchnt/salesman/v1/return$', sales.sales.Return),

)
