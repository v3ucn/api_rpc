# coding:utf-8


class ActvUnionDef(object):
    '''联盟活动常量定义'''

    STATUS_WAIT = 1 # 未启用
    STATUS_ON = 2 # 未启用
    STATUS_CLOSE = 3 # 关闭

    TYPE_CONSUME_BACK = 1 # 消费返


class CouponDef(object):
    '''红包相关定义'''

    ACTIVITY_TYPE_PAYMENT = 2 # 消费返劵/分享劵


class CodeDef(object):
    '''兑换码相关定义'''

    DW_CODE = 0 # 大湾区红包


    DW_STATUS_CREATE = 1 # 创建
    DW_STATUS_BIND = 2 # 绑定
    DW_STATUS_USED = 3 # 已使用
    DW_STATUS_DROP = 4 # 作废
