# coding:utf-8
'''会员中心相关接口

消费者会员中心
b端扫码查看消费者信息
微信c端会员中心相关接口

'''

import time
import json
import config
import logging
import traceback

from excepts import ParamError, SessionError
from decorator import raise_excp, with_validator

from runtime import hids
from utils.base import BaseHandler
from utils.tools import apcli_ex, userid_cache
from utils.decorator import check

from base import MemBase, MemDefine

from qfcommon.base.dbpool import (
    get_connection, get_connection_exception
)
from qfcommon.base.qfresponse import success
from qfcommon.base.tools import thrift_callex, thrift_call
from qfcommon.thriftclient.qf_customer import QFCustomer
from qfcommon.thriftclient.qf_wxmp import QFMP
from qfcommon.thriftclient.qf_customer.ttypes import Profile as tcProfile, CustomerError
from qfcommon.web.validator import Field, T_INT
from qfcommon.server.client import ThriftClient
from qfcommon.thriftclient.wxcard import WXCard
from qfcommon.thriftclient.wxcard.ttypes import(
    CardtplQueryArg, QueryMeta, CardtplStatus, WXCardError
)

log = logging.getLogger()


def get_profile(customer_id):
    '''获取消费者信息'''
    spec = json.dumps({'id': customer_id})
    profiles = thrift_callex(config.OPENUSER_SERVER, QFCustomer,
            'get_profiles', config.OPENUSER_APPID, spec)
    if not profiles:
        raise ParamError('获取消费者信息失败')

    profile = profiles[0].__dict__

    return profile


class Centre(MemBase):
    '''
    会员中心入口
    '''

    _base_err = '获取消费者信息失败'

    def get_actv_info(self, customer_id, groupid):
        '''获取红包个数'''
        userids = None
        if groupid:
            userids = userid_cache[groupid] or []
            userids = map(str, userids)

        # 获取红包的数量
        coupon_num = 0
        with get_connection('qf_marketing') as db:
            coupon_where = {
                'customer_id' : str(customer_id),
                'expire_time' :  ('>', int(time.time())),
                'status' :  ('in', (1, 2))
            }
            if userids is not None:
                userids.append('0')
                coupon_where['mchnt_id'] = ('in', userids)

            coupon_num = db.select_one(
                'coupon_bind', where = coupon_where,
                fields = 'count(1) as num'
            )['num']

        # 获取集点数量
        card_num = 0
        with get_connection('qf_mchnt') as db:
            card_where = {
                'mp.customer_id': int(customer_id),
                'ca.expire_time': ('>', int(time.time()))
            }
            if userids is not None:
                userids.append(0)
                card_where['mp.userid']  = ('in', userids)

            card_num = db.select_join_one(
                'member_pt mp', 'card_actv ca',
                on = {'mp.activity_id' : 'ca.id'},
                where = card_where, fields='count(1) as num'
            )['num']

        return {'card_total_num' : card_num, 'coupon_total_num' : coupon_num}


    @raise_excp(_base_err)
    def GET(self):
        customer_id = self.get_cid()

        groupid = self.get_query_groupid(self.req.input())

        ret = {}
        profile = get_profile(customer_id)
        ret['profile'] = {i:profile[i] for i in ('nickname', 'gender', 'avatar') }
        ret['profile']['customer_id'] = hids.encode(customer_id)
        ret['cards'] = self.get_cards(customer_id, groupid, 0, 2)

        # 会员卡数量
        ret['cards_total_num'] = self._cards_total_num

        # 活动信息
        ret['actv_info'] = self.get_actv_info(customer_id, groupid)

        return self.write(success(ret))


class CardInfo(MemBase):
    '''
    会员卡详细
    '''

    _base_err = '获取详细信息失败'

    def get_privilege(self, userid):
        privilege = None
        with get_connection('qf_mchnt') as db:
            privilege = db.select_one(
                    'member_actv',
                    where= {
                        'userid': userid,
                        'type': MemDefine.ACTV_TYPE_PRIVI,
                        'status': MemDefine.ACTV_STATUS_ON
                    },
                    fields= 'content')
        if not privilege:
            return ''

        return privilege.get('content') or ''

    def get_wxcard(self, userid, customer_id):
        '''获取微信卡包信息'''
        big_uid = self.get_big_uid(userid)
        try:
            q_userid = int(big_uid or userid)
            client = ThriftClient(config.WXCARD_SERVERS, WXCard)
            ret = client.cardtpl_query(
                CardtplQueryArg(
                    query_meta= QueryMeta(),
                    userids= [q_userid, ],
                    status= CardtplStatus.PASS,
                )
            )
            for i in ret or []:
                if i.userid == q_userid:
                    if not getattr(self, '_cardno', ''):
                        with get_connection_exception('qf_mchnt') as db:
                            member = db.select_one(
                                'member',
                                where={
                                    'userid': userid,
                                    'customer_id': customer_id
                                })
                        cardno = member['id']
                    else:
                        cardno = self._cardno

                    appid = i.wx_appid
                    if not appid:  # 如果wx_appid为空,去merchant表找appid

                        model = "normal"
                        ret = client.merchant_get(
                            merchant_ids=[i.merchant_id]
                        )
                        for i in ret:
                            if str(i.userid) == str(q_userid):
                                appid = i.app_id
                    else:
                        model = "third"

                    return {
                        'card_id': i.card_id,
                        'cardno': str(cardno or ''),
                        'appid': appid,
                        "model": model
                    }
        except:
            log.warn(traceback.format_exc())

    def get_submit_info(self, userid, customer_id):
        '''
        获取消费者在商户的认证情况
        '''
        member_tag = None
        with get_connection('qf_mchnt') as db:
            member_tag =  db.select_one('member_tag',
                where = {'userid': userid, 'customer_id': customer_id})

        return (member_tag or {}).get('submit', 0)


    @raise_excp(_base_err)
    def GET(self):
        customer_id = self.get_cid()

        userid = hids.decode(self.req.input().get('userid'))
        if not userid:
            raise ParamError('商户userid为空')
        userid = userid[0]

        openid = self.req.input().get('openid', '')
        ret = dict()

        # 消费者信息
        ret['profile'] =  {}
        profile = get_profile(customer_id)
        ret['profile']['avatar'] = profile['avatar']
        ret['profile']['is_new'] = self.be_member(userid, customer_id)
        ret['profile']['customer_id'] = hids.encode(customer_id)
        ret['profile']['is_submit'] = self.get_submit_info(userid, customer_id)

        # 活动信息
        ret['actvs'] = {}
        ret['actvs']['privilege'] = self.get_privilege(userid)
        ret['actvs']['balance'] = self.get_balance(userid, customer_id) or 0
        card = self.get_actv_card(userid, customer_id) or {}
        ret['actvs']['card'] = card.get('desc')
        ret['actvs']['card_actv_id'] = card.get('mp_id')

        # 店铺信息
        bg_urls = config.CARDS_INFO_BG_URLS
        ret['shopinfo'] = {}
        ret['shopinfo']['mchnt_id'] = userid
        ret['shopinfo']['userid'] = hids.encode(int(userid))
        ret['shopinfo']['bg_url'] = bg_urls[userid % 10 % len(bg_urls)]
        user = apcli_ex('findUserBriefById', userid)
        if user:
            ret['shopinfo']['address'] = user.address
            ret['shopinfo']['mobile'] = user.mobile
            ret['shopinfo']['shopname'] = user.shopname

        user_ext = apcli_ex('getUserExt', int(userid))
        if user_ext:
            ret['shopinfo']['head_img'] = user_ext.head_img or ''
            ret['shopinfo']['logo_url'] = user_ext.logo_url or ''
            ret['shopinfo']['mobile'] = user_ext.contact or user.mobile

        # 实用门店
        ret['shops'] = self.get_shops(userid)
        ret['shop_num'] = self._shop_num

        # 是否卡包信息
        ret['wxcard'] = self.get_wxcard(userid, customer_id) or {}

        # 从weixin_card获取此openid,appid对应的卡包里的所有的卡券列表
        # 如果cardid在里面则返回1, 不然异常情况或者不在都返回0

        appid, card_id = '', ''
        if ret['wxcard']:
            appid = ret['wxcard']['appid']
            card_id = ret['wxcard']['card_id']
        if not appid:
            is_added = 0
            card_code = ''
        else:

            # 如果前端没有给传openid,则先获取openid
            if not openid:
                try:
                    openid = thrift_callex(config.OPENUSER_SERVER, QFCustomer,
                                'get_openid_by_wxappid_and_customid', wx_appid=appid, customid=customer_id)
                except CustomerError:
                    is_added = 0
                    log.debug(traceback.format_exc())

            if not openid:
                is_added = 0
                card_code = ''
            else:
                client = ThriftClient(config.WXCARD_SERVERS, WXCard)

                card_code = client.call("get_cardcode_by_openid", openid=openid, card_id=card_id)
                try:
                    card_list = client.call("get_card_list", openid, appid)
                    if card_id:
                        if card_id in card_list:
                            is_added = 1
                        else:
                            is_added = 0
                    else:
                        is_added = 0

                except WXCardError:
                    log.debug(traceback.format_exc())
                    is_added = 0
        ret['wxcard']['is_added'] = is_added

        # 获取用户领卡时候的code
        ret['wxcard']['code'] = card_code
        return self.write(success(ret))


class Shops(MemBase):
    '''
    获取适用的门店列表
    '''

    _base_err = '获取门店列表失败'

    _validator_fields = [
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
    ]

    @with_validator()
    @raise_excp(_base_err)
    def GET(self):
        userid = hids.decode(self.req.input().get('userid'))
        if not userid:
            raise ParamError('商户userid为空')
        userid = userid[0]

        data = self.validator.data

        limit = data['pagesize']
        offset = data['page'] * data['pagesize']

        ret = {}
        ret['shops'] = self.get_shops(userid, offset, limit)
        ret['shop_num'] = self._shop_num

        return self.write(success(ret))

class Profile(MemBase):
    '''
    消费者信息
    '''

    _base_err = '获取详细信息失败'


    def get_submit_profile(self, customer_id):
        profile = get_profile(customer_id)
        ret = {}
        for field in ('nickname', 'cname', 'mobile', 'birthday'):
            ret[field] = profile[field] or ''

        tags = []
        data = self.req.inputjson()
        userids = hids.decode(data.get('userid'))
        if userids:
            tags = self.get_tags(customer_id, userids[0])
        ret['submit'] = int('submit' in tags)

        return success(ret)

    def get_base_profile(self, customer_id):
        profile = get_profile(customer_id)
        ret = {}
        for field in ('nickname', 'cname', 'mobile', 'birthday', 'gender', 'avatar'):
            ret[field] = profile[field] or ''

        return success(ret)

    @raise_excp(_base_err)
    def GET(self):
        params = self.req.inputjson()

        mode = params.get('mode', 'submit')
        customer_id = self.get_cid()

        if mode == 'base':
            return self.get_base_profile(customer_id)

        else:
            return self.get_submit_profile(customer_id)


class UpdateProfile(MemBase):
    '''
    更新消费者信息
    '''

    _base_err = '更新信息失败'

    @check()
    def POST(self):
        params = self.req.inputjson()

        # 获取customer_id
        customer_id = None
        try:
            customer_id = self.get_cid()
        except:
            if self.check_ip():
                cid = hids.decode(params.get('cid'))
                customer_id = cid[0] if cid else None
        if not customer_id:
            raise SessionError('用户未登录')

        # 消费者进行认证
        # 将更新商户member_tag
        if params.get('mode') == 'submit':
            userids = hids.decode(params.get('userid'))
            if userids:
                self.add_tag(userids[0], customer_id,
                        'submit', MemDefine.MEMBER_SRC_SUBMIT)

        fields = ['nickname', 'cname', 'mobile', 'birthday']
        update_data = {i:params[i]for i in fields if params.get(i)}
        if 'birthday' in update_data:
            profile = get_profile(customer_id)
            if profile['birthday']:
                raise ParamError('已经设置了生日信息')

        # 更新消费者信息
        if update_data:
            thrift_callex(
                config.OPENUSER_SERVER, QFCustomer, 'profile_update',
                customer_id, tcProfile(**update_data)
            )

        return success({})


class Cards(MemBase):
    '''
    会员卡列表
    '''

    _base_err = '获取数据失败'

    _validator_fields = [
        Field('page', T_INT, default=0),
        Field('pagesize', T_INT, default=10),
    ]

    @with_validator()
    @raise_excp(_base_err)
    def GET(self):
        data = self.validator.data
        groupid = self.req.input().get('groupid')

        customer_id = self.get_cid()
        limit = data['pagesize']
        offset = data['page'] * data['pagesize']

        return self.write(success(
            self.get_cards(customer_id, groupid, offset, limit)))


class Qrcode(MemBase):
    '''
    消费者二维码
    '''

    _base_err = '获取数据失败'

    @raise_excp(_base_err)
    def GET(self):
        encode = (
            self.MEMBER_PRE_CODE +
            hids.encode(int(self.get_cid()), int(time.time()))
        )

        return success({'encid': encode})


class CardExt(BaseHandler):
    '''获取签名'''

    _base_err = '获取签名失败'

    @check()
    def GET(self):
        params = self.req.input()

        data = {}
        for i in ('appid', 'card_id', 'code'):
            if not params.get(i):
                raise ParamError('参数不完整')
            data[i] = params[i]

        try:
            card_ext = json.loads(thrift_call(
                QFMP, 'card_ext', config.QFMP_SERVERS,
                data['appid'], data['card_id'], data['code']
            ))
        except:
            raise ParamError('获取签名错误')
            card_ext = {}

        return self.write(success({'card_ext': card_ext}))
