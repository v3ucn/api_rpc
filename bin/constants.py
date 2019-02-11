#coding: utf-8

import types

# ListType, TupleType
MulType = (types.ListType, types.TupleType)

# 邮件正则
# 以字母开头，后跟任意非\n字符。然后@，后跟任意非\n字符
EMAIL_PATTERN  = '^\S+@(?:\S+\.)+\S+'

# 手机号码正则
MOBILE_PATTERN = '^1(0|1|2|3|4|5|6|7|8|9)\d{9}$'

# 简单手机号码验证，长度不超过15
SIMPLE_MOBILE_PATTERN = '^\d{1,15}$'

# 密码正则，6-20位字母数字组合
PASSWORD_PATTERN = r'^[a-zA-Z0-9]{6,20}$'

# 时间格式
DTM_FMT = DATETIME_FMT = '%Y-%m-%d %H:%M:%S'
DT_FMT = DATE_FMT = '%Y-%m-%d'
DTM_PATTERN = r"^\d{4}(-\d\d){2} \d\d(:\d\d){2}"

# 商户付费状态
MCHNT_STATUS = (MCHNT_STATUS_FREE, MCHNT_STATUS_NORMAL) = (1, 2)

# 操作类型
OPERATE_TYPE = (OPERATE_RECHARGE, OPERATE_ADD_PROMO, OPERATE_CHANGE_PROMO, OPERATE_ADD_PROMO_CODE, OPERATE_CHANGE_PROMO_CODE, OPERATE_ADD_NUM_PROMO_CODE) = (1, 2, 3, 4, 5, 41)

# 红包状态
# 1: 领取  2: 绑定  3: 使用  4:  作废
COUPON_STATUS = (COUPON_STATUS_OBTAIN, COUPON_STATUS_BIND, COUPON_STATUS_USE, COUPON_STATUS_DESTROY) = (1, 2, 3, 4)

# 记录状态
# 0: 领取  1: 使用  2: 还原  3:  作废
RECORD_STATUS = (RECORD_STATUS_OBTAIN, RECORD_STATUS_USE, RECORD_STATUS_UNDO, RECORD_STATUS_DESTROY) = (0, 1, 2, 3)

# 活动分享类型
# 1: 红包 2: 积分 3: 实物券
ACTIVITY_SHARE_TYPE = (ACTIVITY_SHARE_TYPE_COUPON, ACTIVITY_SHARE_TYPE_INTEGRAL, ACTIVITY_SHARE_TYPE_GOODS_COUPON) = (1, 2, 3)

# 渠道
CHNLBIND_TYPE_WX = 8 # 微信支付
SETTLE_TYPE_T1 = 1 # t1清算
SETTLE_TYPE_D1 = 2 # d1清算
SETTLE_TYPE_D0 = 3 # d0清算

#获取凭证图片信息
CERT_NAME = {
    'idcardfront': '身份证正面',
    'idcardback': '身份证背面',
    'licensephoto': '营业执照',
    'livingphoto': '近期生活照',
    'groupphoto': '业务员与申请人在收银台合影',
    'goodsphoto': '店铺内景照片',
    'shopphoto': '店铺外景照片',
    'authcertphoto': '授权书照片',
    'idcardinhand': '手持身份证合照',
    'signphoto': '手写签名照',
    'otherphoto': '其他凭证照片',
    'otherphoto1': '其他凭证照片',
    'otherphoto2': '其他凭证照片',
    'otherphoto3': '其他凭证照片',
    'authidcardfront': '授权法人身份证正面',
    'authidcardback': '授权法人身份证背面',
    'authedcardfront': '被授权人身份证正面',
    'authedcardback': '被授权人身份证背面',
    'invoicephoto': '发票',
    'purchaselist': '进货单',
    'taxphoto': '税务登记证',
    'taxproof': '完税证明',
    'paypoint': '收银台照',
    'lobbyphoto': '财务室或者大堂照',
    'authbankcardfront': '银行卡正面',  # 授权法人银行卡正面
    'authbankcardback': '银行卡背面',  # 授权法人银行卡背面
    'rentalagreement': '店铺租赁合同',
    'orgphoto': '组织机构代码证',
    'openlicense': '开户许可证',
    'delegateagreement': '业务代理合同或者协议',
    'iatacert': '航协证',
    'insurancecert': '经营保险代理业务许可证，保险兼业',
    'licensephoto1': '营业执照照片',
    'foodcirculationpermit':  '食品流通许可证',
    'foodhygienelicense': '食品卫生许可证',
    'foodservicelicense': '餐饮服务许可证',
    'subshopdesc': '分店说明',
}

OLD2NEW_CERT = {
    'id_front.jpg': 'idcardfront',  # 身份证正面
    'id_back.jpg': 'idcardback',  # 身份证背面
    'license.jpg': 'licensephoto',  # 营业执照
    'license_page1.jpg': 'licensephoto',  # 营业执照
    'license_page2.jpg': 'licensephoto',  # 营业执照
    'livingphoto.jpg': 'livingphoto',  # 近期生活照
    'gathering_attest.jpg': 'groupphoto',  # 业务员与申请人合影
    'business_attest_srv.jpg': 'goodsphoto',  # 所售商品/经营场所内景照片
    'business_attest_other4.jpg': 'shopphoto',  # 经营场所，商户店面正门照，店铺门面照片/经营场所外景照片
    'idcardinhand.jpg': 'idcardinhand',  # 手持身份证合照
    'photo3.jpg': 'signphoto',  # 手写签名照
    'legal_person_auth.jpg': 'authcertphoto',  # 授权书照片
    'legal_person_auth_front.jpg': 'authidcardfront',  # 被授权人身份证正面
    'legal_person_auth_back.jpg': 'authidcardback',  # 被授权人身份证背面
    'taxphoto.jpg': 'taxphoto',  # 税务登记证
    'paypoint.jpg': 'paypoint',  # 收银台照
    'lobby.jpg': 'lobbyphoto',  # 财务室或者大堂照
    'authbankcardfront.jpg': 'authbankcardfront',  # 授权法人银行卡正面
    'authbankcardback.jpg': 'authbankcardback',  # 授权法人银行卡背面
    'rentalagreement.jpg': 'rentalagreement',  # 租赁协议，产权证明，市场管理方证明/店铺租赁合同
    'orgphoto.jpg': 'orgphoto',  # 组织机构代码证
    'open_licensephoto.jpg': 'openlicense',  # 开户许可证
    'delegateagreement.jpg': 'delegateagreement',  # 业务代理合同或者协议
    'iatacert.jpg': 'iatacert',  # 航协证
    'insurancecert.jpg': 'insurancecert',  # 经营保险代理业务许可证，保险兼业
}

class QTRET:
    OK        = "0000"

    DATAEXIST = "3106"


SEND_MAIL_OK = 1
SEND_MAIL_FAIL = 2
ACTV_OVERDUE = 1
ACTV_AVAILABLE = 0


# 可用收银员的状态
VALID_OPUSER_STATUS = 1

# 是否接收收银员播报的状态 对应qf_mchnt数据库表push_control
RECEIVE_PUSH = 1
NO_RECEIVE_PUSH = 0

# 合伙人提交信息中的合作性质, 1-公司，2-个人, 对应qf_mchnt数据库intent_coopman表的coop_type字段
INTENT_COOP_TYPE = INTENT_COOP_TYPE_COMPANY, INTENT_COOP_TYPE_PERSONAL = 1, 2

# 商户的会员实名认证: 0-未设置 1-启用 2-未启用
MEMBER_AUTH = MEMBER_AUTH_UNSET, MEMBER_AUTH_ON, MEMBER_AUTH_OFF = 0, 1, 2

# 商户的紧急补件状态
NO_SUPPLIED, ALREADY_SUPPLIED = 0, 1

# 图片表里面的转态说明
IMG_WAITE_AUDIT, IMG_AUDIT_PASS, IMG_NOT_PASS, IMG_NOT_UPLOAD = 0, 1, 2, 3

# 活动状态1:未启用 2:启用 3:关闭
ACTIVITY_STATUS = ACT_UN_ENABLED, ACT_ENABLED, ACT_CLOSED = 1, 2, 3
