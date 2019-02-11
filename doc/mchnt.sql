CREATE TABLE `qd_conf` (
  `id` BIGINT(20) unsigned NOT NULL,
  `qd_uid` BIGINT NOT NULL COMMENT '渠道ID(0是默认配置)',
  `status` SMALLINT DEFAULT 1 COMMENT '配置状态 1:启用 2:关闭',
  `name` char(20) DEFAULT '' COMMENT '渠道名称',
  `wx_pub` char(30) DEFAULT '' COMMENT '渠道微信公众号',
  `protocol` varchar(2048) DEFAULT '' COMMENT '渠道协议配置',
  `qrcode` varchar(512) DEFAULT '' COMMENT '二维码相关配置',
  `csinfo` varchar(512) DEFAULT '' COMMENT '客服信息配置',
  `push` varchar(1024) DEFAULT '' COMMENT '推送相关配置',
  `ext` varchar(2048) DEFAULT '' COMMENT '其他',
  `ctime` int(11) NOT NULL COMMENT '创建时间',
  `utime` int(11) NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY (`qd_uid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='渠道配置表';

alter table qd_conf add `promotion_url` varchar(1024) DEFAULT '' COMMENT '活动物料url(集点,红包等活动)' AFTER `push`;
alter table qd_conf add `service` longtext NOT NULL COMMENT '渠道九宫格配置' AFTER promotion_url;

alter table apply add `ratio` varchar(1024) DEFAULT '' COMMENT '商户费率 tenpay_ratio:微信, alipay_ratio:支付宝, jdpay_ratio:京东, qqpay_ratio:qq'


CREATE TABLE `bk_apply` (
  `id` bigint(20) unsigned NOT NULL,
  `userid` int(11) NOT NULL COMMENT '商户userid',
  `state` smallint(6) DEFAULT 1 COMMENT '申请状态 1:正常',
  `license_state` smallint(6) DEFAULT 1 COMMENT '营业执照状态 1:有 2:正在办理 3:没有,借用 4:没有',
  `wx_pub` varchar(20) DEFAULT '' COMMENT '微信公众号名字',
  `mobile` varchar(20) DEFAULT '' COMMENT '联系电话',
  `ext` varchar(1024) DEFAULT '' COMMENT '其他',
  `ctime` int(11) NOT NULL COMMENT '创建时间',
  `utime` int(11) NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `userid` (`userid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='生意王申请表';

CREATE TABLE `member_tag` (
  `id` bigint(20) NOT NULL COMMENT 'id',
  `userid` bigint(20) NOT NULL COMMENT 'userid',
  `customer_id` bigint(20) NOT NULL COMMENT '消费者id',
  `coupon` smallint(6) DEFAULT 0 COMMENT '红包 0:未使用 1:使用',
  `card` smallint(6) DEFAULT 0 COMMENT '集点',
  `prepaid` smallint(6) DEFAULT 0 COMMENT '储值',
  `sale` smallint(6) DEFAULT 0 COMMENT '特卖',
  `diancan` smallint(6) DEFAULT 0 COMMENT '点餐',
  `src` smallint(6) DEFAULT 1 COMMENT '会员来源 1.支付 2.关注 3.扫码...',
  `ctime` int(11) DEFAULT NULL COMMENT '创建时间',
  `utime` int(11) DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `userid` (`userid`,`customer_id`),
  KEY `customer_id` (`customer_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='会员辅助信息';


alter table member_actv add `type` smallint(6) DEFAULT 1 COMMENT '活动类型: 1.店铺公告 2.会员特权活动' after userid;


CREATE TABLE `test` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT 'id',
  `userid` bigint(20) NOT NULL COMMENT 'userid',
  `customer_id` bigint(20) NOT NULL COMMENT '消费者id',
  `coupon` smallint(6) DEFAULT 0 COMMENT '红包 0:未使用 1:使用',
  `utime` int(11) DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB CHARSET=utf8 COMMENT='test';


alter table member_tag add `submit` smallint(6) DEFAULT '0' COMMENT '点餐' after diancan;

alter table card_actv add  `mchnt_id_list` longtext NOT NULL COMMENT '商户id列表, json list格式, 例: ["xxx", "yyy", "zzz"]';

CREATE TABLE `language_constant` (
  `code` varchar(128) NOT NULL COMMENT '常量key',
  `value` varchar(1024) NOT NULL COMMENT '常量value',
  `src` varchar(64) DEFAULT '' COMMENT '使用的项目，比如bigmchnt, mchnt_api',
  `status` smallint(6) DEFAULT '1' COMMENT '状态 0: 不启用  1: 启用',
  `ctime` int(11) unsigned NOT NULL COMMENT '创建时间',
  `utime` int(11) unsigned NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`code`, `src`)
)ENGINE=InnoDB CHARSET=utf8 COMMENT='国际化常量定义';


CREATE TABLE `push_control` (
  `userid` bigint(20) NOT NULL COMMENT 'userid',
  `push_master` smallint(6) DEFAULT 0 COMMENT '收银员推送是否推给主账号 0 不推送 1 推送',
  `push_opuser` smallint(6) DEFAULT 0 COMMENT '主账号推送是否推送给收银员 0 不推送 1 推送',
  `status` smallint(6) DEFAULT 1 COMMENT '状态 0: 不启用  1: 启用',
  `ctime` datetime NOT NULL COMMENT '记录创建时间',
  `utime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
  PRIMARY KEY (`userid`)
)ENGINE=InnoDB CHARSET=utf8 COMMENT='商户推送控制';
