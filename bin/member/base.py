# coding:utf-8

import types
import time
import traceback
import logging
import config

from collections import defaultdict

from runtime import redis_pool, hids
from constants import DATETIME_FMT, MulType

from utils.base import BaseHandler
from utils.tools import (
    constants_cache, getid, get_relations, apcli_ex, userid_cache
)
from utils.valid import is_valid_int

from qfcommon.base.dbpool import get_connection, get_connection_exception
from qfcommon.thriftclient.prepaid import prepaid
from qfcommon.server.client import ThriftClient

log = logging.getLogger()


class MemDefine(object):
    '''会员相关定义'''

    # 店铺公告状态
    ACTV_STATUS_ON = 1 # 启用
    ACTV_STATUS_REFUSE = 2 # 审核失败
    ACTV_STATUS_OFF = 3 # 终止

    # 店铺公告返回状态
    ACTV_STATE_ON = 1 # 启用
    ACTV_STATE_REFUSE = 2 # 审核失败
    ACTV_STATE_OFF = 3 # 终止

    # 店铺活动类型
    ACTV_TYPE_PROMO = 1 # 店铺公告
    ACTV_TYPE_PRIVI = 2 # 会员特权

    # 消费者来源
    MEMBER_SRC_PAY = 1 # 支付
    MEMBER_SRC_WX = 2  # 关注公众号
    MEMBER_SRC_QRCODE = 3   # 扫码
    MEMBER_SRC_PREPAID = 4  # 储值
    MEMBER_SRC_SUBMIT = 5  # 提交信息
    MEMBER_SRC_CARD = 6  # 获取会员卡信息


class MemberUtil(object):
    '''会员相关方法'''

    @staticmethod
    def get_actv_state(actv):
        '''
        根据活动信息获取活动的状态
        '''
        now = time.strftime(DATETIME_FMT)
        if actv['status'] == 1:
            return 0 if now < str(actv['expire_time']) else 1
        else:
            return actv['status']

    @staticmethod
    def get_actv_pv(ids):
        '''获取活动的pv'''
        if not isinstance(ids, (types.ListType, types.TupleType)):
            ids = [ids]
        r = {}
        try:
            for i in ids:
                r[i] = redis_pool.get('__member_actv_customer_%s_pv__' % i) or 0
        except:
            log.warn('get pv error:%s' % traceback.format_exc())
        return r

    @staticmethod
    def add_actv_pv(ids):
        '''增加活动的pv'''
        if not isinstance(ids, (types.ListType, types.TupleType)):
            ids = [ids]
        r = {}
        try:
            for i in ids:
                redis_pool.incr('__member_actv_customer_%s_pv__' % i)
        except:
            log.warn('incr pv error:%s' % traceback.format_exc())
        return r

class MemBase(BaseHandler):
    '''
    会员base
    '''

    MEMBER_PRE_CODE = 'QF01:'

    def get_tags(self, customer_id, userid=None):
        if isinstance(customer_id, MulType):
            multype = True
            customer_ids = customer_id
        else:
            multype = False
            customer_ids = [customer_id]

        ret = {}
        # 集点标记
        tags = None
        with get_connection('qf_mchnt') as db:
            tags = db.select('member_tag',
                    where= {
                        'customer_id': ('in', customer_ids),
                        'userid': userid or self.user.userid
                    },
                    fields= ('customer_id, card, prepaid,'
                             'diancan, submit, sale'))
        tags = {tag['customer_id']:tag for tag in tags or []}

        ret = defaultdict(list)
        tag_fields = ['card', 'prepaid', 'diancan', 'submit', 'sale']
        for cid in customer_ids:
            tag = tags.get(cid)
            if not tag:
                continue
            for i in tag_fields:
                if tag.get(i) > 0:
                    ret[cid].append(i)

        return ret if multype else ret[customer_id]

    def add_tag(self, userid, customer_id, tag, src):
        '''
        如果是在连锁店认证, 将会对所有连锁店进行授权
        '''
        userids = [int(userid), ]
        big_uid = self.get_big_uid(userid) or userid
        userids = self.get_link_ids(big_uid) or []
        userids.append(int(big_uid))

        with get_connection('qf_mchnt') as db:
            now = int(time.time())
            exist_user = db.select(
                table = 'member_tag',
                where = {
                    'userid': ('in', userids),
                    'customer_id': customer_id,
                },
                fields = 'userid') or []
            exist_userids = [i['userid'] for i in exist_user]
            log.debug(exist_userids)
            # 更新已有的
            if exist_userids:
                db.update(
                    table = 'member_tag',
                    values = {
                        tag : 1,
                        'utime': now,
                    },
                    where = {
                        tag : 0,
                        'userid' : ('in', exist_userids),
                        'customer_id': customer_id,
                    })

            insert_data = []
            for i in userids:
                if i not in exist_userids:
                    insert_data.append({
                        'id': getid(),
                        'userid': userid,
                        'customer_id': customer_id,
                        'src': src,
                        'ctime': now,
                        'utime': now,
                        tag: 1
                    })
            if insert_data:
                db.insert_list(
                    'member_tag', values_list = insert_data,
                    other = 'ON DUPLICATE KEY UPDATE %s=1' % tag
                )

            return True

        return False


    def get_balance(self, userid, customer_id):
        try:
            client = ThriftClient(config.TPREPAID_SERVERS, prepaid,
                    framed=True, raise_except=True)
            infos = client.m_balance(userid, [int(customer_id)])
            info = next((i for i in infos or []
                    if i.userid == int(userid)), None)
            if info:
                return info.balance
        except:
            log.warn(traceback.format_exc())

        return None

    def get_actv_card(self, userid, customer_id):
        actv = {'desc':'暂无集点活动进行' ,
                'title': '集点状态', 'link': ''}

        # 大商户的子商户userid
        relates =  apcli_ex('getUserRelation',
                userid, 'merchant') or []
        userids = [i.userid for i in relates]
        userids.append(userid)

        infos = pt = None
        with get_connection('qf_mchnt') as db:
            actvs = db.select(
                    'card_actv',
                    where = {
                        'start_time': ('<=', int(time.time())),
                        'expire_time': ('>', int(time.time())),
                        'userid': ('in', userids)
                    },
                    fields = 'exchange_pt, id') or []
            infos = {i['id']:i['exchange_pt'] for i in actvs}
            if infos:
                pt = db.select(
                        'member_pt',
                        where = {
                            'customer_id': customer_id,
                            'activity_id': ('in', infos.keys())
                        },
                        fields = 'cur_pt, activity_id, id') or []

        if infos:
            actv['link'] = getattr(config, 'MEMBER_CARD_LINK', '').format(
                    hids.encode(int(customer_id)))

            # 若仅有一张集点卡
            if len(pt) == 1:
                cur_pt = pt[0]['cur_pt']
                exc_pt = infos[pt[0]['activity_id']]
                actv['desc'] = (
                        '已集点{}/{}'.format(cur_pt, exc_pt)
                        if cur_pt < exc_pt
                        else '有{}个礼品可兑换'.format(cur_pt / exc_pt))

                # 如果返回mp_id, 前端将自己跳转至详细页
                actv['activity_id'] = str(pt[0]['activity_id'])
                actv['mp_id'] = str(pt[0]['id'])

            # 若有多张集点卡
            elif len(pt) > 1:
                actv['desc'] = '有{}张集点卡'.format(len(pt))

            else:
                actv['desc'] = '有0张集点卡'
                if len(actvs) == 1:
                    exc_pt = actvs[0]['exchange_pt']
                    actv['desc'] = '已集点0/{}'.format(exc_pt)

        return actv

    def be_member(self, userid, customer_id, src=MemDefine.MEMBER_SRC_WX):
        ''' 成为会员

        如果是新会员将返回1, 否则返回0

        '''
        now = int(time.time())
        try:
            with get_connection_exception('qf_mchnt') as db:
                cardno = getid()
                db.insert('member',
                        values= {
                            'id': cardno,
                            'userid': userid,
                            'customer_id': customer_id,
                            'num': 0,
                            'txamt': 0,
                            'last_txdtm': 0,
                            'ctime': now,
                            'utime': now
                        })
                self._cardno = cardno

                db.insert('member_tag',
                        values= {
                            'id': getid(),
                            'userid': userid,
                            'customer_id': customer_id,
                            'src': src,
                            'ctime': now,
                            'utime': now
                        })
        except:
            return 0
        return 1

    def get_cards(self, customer_id, groupid=None, offset=0, limit=10):
        '''获取会员卡'''
        self._cards_total_num = 0
        mems = None
        with get_connection('qf_mchnt') as db:
            mems = db.select('member',
                    where= {'customer_id': customer_id},
                    fields= 'userid',
                    other= 'order by ctime desc')
        if not mems: return []

        # 获取关系列表
        # 子商户全转化为大商户userid
        relations = get_relations() or {}
        userids = []
        for mem in mems:
            userid = relations.get(mem['userid'], mem['userid'])
            if userid not in userids:
                userids.append(userid)
        if is_valid_int(groupid):
            userid_cache_list = userid_cache[groupid]
            userids = list(set(userids) & set(userid_cache_list))
        self._cards_total_num = len(userids)

        userids = userids[offset:offset+limit]
        if not userids: return []

        user_exts = apcli_ex('getUserExts', userids)
        user_exts = {i.uid:i for i in user_exts}

        apollo_shops = apcli_ex('findUserBriefsByIds', userids) or {}
        if apollo_shops:
            apollo_shops = {shop.uid:shop for shop in apollo_shops}

        bg_urls =  config.CARDS_BG_URLS
        cards = []
        for userid in userids:
            card = {
                'userid': hids.encode(int(userid)),
                'nickname': '',
                'bg_url': bg_urls[userid % 10 % len(bg_urls)],
            }
            user = apollo_shops.get(userid)
            if user:
                card['nickname'] = user.shopname
            user_ext = user_exts.get(userid)
            if user_ext:
                card['logo_url'] = user_ext.logo_url
                card['head_img'] = user_ext.head_img

            if (not card.get('head_img') or
                card['head_img'] == config.DEFAULT_HJ_HEAD_IMG):
                card['head_img'] = config.DEFAULT_SHOP_HEAD_IMG

            if not card.get('logo_url'):
                card['logo_url'] = config.DEFAULT_SHOP_LOGO_URL

            cards.append(card)

        return cards

    def get_shops(self, userid, offset=0, limit=5):
        '''
        获取门店列表
        '''
        self._shop_num = 0
        relations = get_relations() or {}
        relations_re = defaultdict(list)
        for linkid, uid in relations.iteritems():
            relations_re[uid].append(linkid)

        if userid not in relations_re:return []

        self._shop_num = len(relations_re[userid])
        userids = relations_re[userid][offset:limit]
        if not userids: return []

        user_exts = apcli_ex('getUserExts', userids)
        user_exts = {i.uid:i for i in user_exts}

        apollo_shops = apcli_ex('findUserBriefsByIds', userids) or {}
        if apollo_shops:
            apollo_shops = {shop.uid:shop for shop in apollo_shops}
        # 店铺信息
        shops = []
        for uid in userids:
            shopinfo = {}
            shopinfo['userid'] = hids.encode(int(uid))
            user = apollo_shops.get(uid)
            if user:
                shopinfo['address'] = user.address
                shopinfo['mobile'] = user.mobile
                shopinfo['shopname'] = user.shopname

            user_ext = user_exts.get(uid)
            if user_ext:
                shopinfo['head_img'] = user_ext.head_img
                shopinfo['logo_url'] = user_ext.logo_url
                shopinfo['mobile'] = user_ext.contact

            if (not shopinfo.get('head_img') or
                shopinfo['head_img'] == config.DEFAULT_HJ_HEAD_IMG):
                shopinfo['head_img'] = config.DEFAULT_SHOP_HEAD_IMG

            if not shopinfo.get('logo_url'):
                shopinfo['logo_url'] = config.DEFAULT_SHOP_LOGO_URL

            shops.append(shopinfo)
        return shops

    def get_query_groupid(self, params):
        if 'groupid' not in params or not is_valid_int(params['groupid']):
            return None

        groupid = int(params['groupid'])

        member_groupids = constants_cache['_mchnt_api_member_groupid'] or []

        return groupid if groupid in member_groupids else None
