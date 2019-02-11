# coding:utf-8
'''会员中心相关接口

消费者会员中心
b端扫码查看消费者信息
微信c端会员中心相关接口

'''

import json
import time
import config
import logging

from excepts import ParamError
from runtime import hids, redis_pool, geo_redis_pool
from base import MemBase

from utils.tools import apcli_ex, big_uid_cache, calcDistance
from utils.decorator import check
from utils.valid import is_valid_int, is_valid_num
from utils.payinfo import adjust_payinfo_ex
from utils.qdconf_api import get_qd_conf_value_ex

from qfcommon.base.qfresponse import success

log = logging.getLogger()


class List(MemBase):
    '''
    获取优惠商家列表
    '''

    _base_err = '获取门店列表失败'

    def get_all_userids(self, params):
        had_geo = lng = lat = False
        if is_valid_num(params.get('lng')) and is_valid_num(params.get('lat')):
            had_geo = True
            lng = float(params['lng'])
            lat = float(params['lat'])

        # 大商户userid
        big_uids = redis_pool.smembers('_mchnt_big_uid_cache_')

        # 若传入groupid
        groupid = self.get_query_groupid(params)
        if groupid:
            rkey = '_mchnt_group_cache_{}_'.format(groupid)
            group = redis_pool.lrange(rkey, 0, -1)
            users = []
            for i in group:
                try:
                    data = json.loads(i)
                    if data['userid'] in big_uids:
                        continue
                    users.append(data)
                except:
                    pass

            # 没有经纬度直接返回
            if not had_geo: return users

            users.sort(key = lambda d: calcDistance(lng, lat, d['lng'], d['lat']))

            return [i['userid'] for i in users]

        # 若未传经纬度
        if not had_geo: return []

        userids = geo_redis_pool.georadius(
            '_mchnt_geo_', lng, lat, 20, 'km', sort = 'ASC',
            count = 10000
        )

        return [int(i) for i in userids if int(i) not in big_uids]

    def sort(self, userids):
        '''
        对商户进行优先级排序
        联盟活动商户 > 普通活动商户 > 普通商户
        '''
        def sort_key(userid):
            if userid in union_userids:
                return 0
            elif userid in normal_userids:
                return 1
            else:
                return 2

        # 普通活动商户
        card_userids = redis_pool.smembers('_mchnt_card_actv_cache_') or set()
        coupon_userids = redis_pool.smembers('_mchnt_coupon_actv_cache_') or set()
        prepaid_userids = redis_pool.smembers('_mchnt_prepaid_actv_cache_') or set()
        normal_userids = card_userids | coupon_userids | prepaid_userids
        log.debug(normal_userids)

        # 联盟活动商户
        union_userids = redis_pool.smembers('_mchnt_coupon_union_actv_cache_') or set()
        log.debug(union_userids)

        return sorted(userids, key = sort_key)

    def get_list(self, params):
        '''
        若传入groupid, 将返回该渠道下所有的商户(无视方圆20公里限制)
        '''
        userids = self.get_all_userids(params)

        if not userids:
            return success({'shops' : []})

        # 对userid进行优先级排序
        userids = self.sort(userids)

        limit, offset = self.get_pageinfo()

        ret_userids = userids[offset:offset+limit]
        if ret_userids:
            users = apcli_ex('findUserBriefsByIds', ret_userids)
            user_dict = {i.uid:i.__dict__ for i in users}

            user_exts = apcli_ex('getUserExts', ret_userids)
            user_ext_dict = {i.uid:i.__dict__ for i in user_exts}


            trade_key = '_paycell_trade_stat_{}_'.format(time.strftime('%Y%m'))
            trade_stats = redis_pool.hmget(trade_key, ret_userids)
            trade_dict = dict(zip(ret_userids, trade_stats))

        ret = []
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        for userid in ret_userids:
            user = user_dict.get(int(userid)) or {}
            tmp = {
                'shopname' : user.get('shopname', ''),
                'mobile' : user.get('mobile', ''),
                'address' : user.get('address', ''),
                'enuserid' : hids.encode(userid)
            }

            # 图片
            user_ext = user_ext_dict.get(userid, {})
            tmp['head_img'] = user_ext.get('head_img', '')
            tmp['logo_url'] = user_ext.get('logo_url', '')

            if not tmp['head_img']:
                tmp['head_img'] = get_qd_conf_value_ex(
                    groupid = user.get('groupid' or 0), mode = 'default_head_img',
                    key = 'ext'
                ) or ''

            if not tmp['logo_url']:
                tmp['logo_url'] = get_qd_conf_value_ex(
                    groupid = user.get('groupid', 0), mode = 'default_logo_url',
                    key = 'ext'
                ) or ''

            # 总的交易
            tmp['trade_num'] = trade_dict.get(userid) or 0


            # 获取活动消息
            rkey = '_mchnt_all_actv_cache_{}_'.format(userid)
            tmp['actv_info'] = {}
            all_actv = redis_pool.hgetall(rkey)

            if 'coupon_actv' in all_actv:
                try:
                    data = json.loads(all_actv['coupon_actv'])

                    if data['expire_time'] > now:
                        tmp['actv_info']['coupon'] = {
                            'amt' : data.get('amt', 0)
                        }
                except:
                    pass

            if 'coupon_union_actv' in all_actv:
                try:
                    data = json.loads(all_actv['coupon_union_actv'])

                    if data['expire_time'] > now:
                        tmp['actv_info']['coupon_union'] = {
                            'amt' : data.get('amt', 0)
                        }
                except:
                    pass

            if 'prepaid_actv' in all_actv:
                try:
                    data = json.loads(all_actv['prepaid_actv'])

                    if data['expire_time'] > now:
                        tmp['actv_info']['prepaid'] = {
                            'max_present_amt' : data.get('max_present', 0)
                        }
                except:
                    pass

            if 'card_actv' in all_actv:
                try:
                    data = json.loads(all_actv['card_actv'])

                    if data['expire_time'] > now:
                        tmp['actv_info']['card'] = data
                except:
                    pass


            ret.append(tmp)

        return success({'shops': ret})

    def get_sub_list(self, params):
        ret = {'shops': [], 'total_num': 0}

        # 大商户userid
        big_uid = hids.decode(params.get('code'))
        if not big_uid:
            return success(ret)
        big_uid = big_uid[0]

        # 子商户userid
        relates = apcli_ex('getUserRelation', int(big_uid), 'merchant') or []
        link_ids = [i.userid for i in relates]
        ret['total_num'] = len(relates)

        limit, offset = self.get_pageinfo()
        link_ids = link_ids[offset:offset+limit]
        if not link_ids:
            return success(ret)

        users = apcli_ex('findUserBriefsByIds', link_ids) or []
        user_dict = {user.uid:user.__dict__ for user in users}
        user_exts = apcli_ex('getUserExts', link_ids) or []
        user_ext_dict = {i.uid:i.__dict__ for i in user_exts}

        shops = []
        for link_id in link_ids:
            tmp = {}
            user = user_dict.get(link_id, {})
            tmp['shopname'] = user.get('shopname', '')
            tmp['mobile'] = user.get('mobile', '')
            tmp['address'] = user.get('address', '')
            tmp['enuserid'] = hids.encode(link_id)

            user_ext = user_ext_dict.get(link_id, {})
            tmp['head_img'] = user_ext.get('head_img', '')
            tmp['logo_url'] = user_ext.get('logo_url', '')

            if not tmp['head_img']:
                tmp['head_img'] = get_qd_conf_value_ex(
                    groupid = user.get('groupid' or 0), mode = 'default_head_img',
                    key = 'ext'
                ) or ''

            if not tmp['logo_url']:
                tmp['logo_url'] = get_qd_conf_value_ex(
                    groupid = user.get('groupid', 0), mode = 'default_logo_url',
                    key = 'ext'
                ) or ''

            shops.append(tmp)
        ret['shops'] = shops

        return success(ret)

    @check()
    def GET(self):
        params = self.req.input()
        mode = params.get('mode')


        if mode == 'sub':
            return self.get_sub_list(params)

        else:
            return self.get_list(params)


class Info(MemBase):
    '''获取商户详细信息'''

    _base_err = '获取商户详细信息失败'


    def get_shopinfo(self, userid):
        user = apcli_ex('findUserBriefById', userid)
        if not user:
            raise ParamError('商户不存在')
        shopinfo = {
            'shopname' : user.shopname,
            'mobile' : user.mobile,
            'addr' : user.address,
            'head_img' : '',
            'logo_url' : '',
            'trade_total_num' : 0
        }

        # 获取交易笔数
        rkey = '_paycell_trade_stat_{}_'.format(time.strftime('%Y%m'))
        shopinfo['trade_total_num'] = int(redis_pool.hget(rkey, userid) or 0)

        user_ext = apcli_ex('getUserExt', userid)
        if user_ext:
            shopinfo['head_img'] = user_ext.head_img
            shopinfo['logo_url'] = user_ext.logo_url

        if not shopinfo['head_img']:
            shopinfo['head_img'] = get_qd_conf_value_ex(
                groupid = user.groupid, mode = 'default_head_img',
                key = 'ext'
            ) or ''

        if not shopinfo['logo_url']:
            shopinfo['logo_url'] = get_qd_conf_value_ex(
                groupid = user.groupid, mode = 'default_logo_url',
                key = 'ext'
            ) or ''

        return shopinfo

    def get_takeout_url(self, userid):
        '''获取外卖链接'''
        payinfo = adjust_payinfo_ex(userid, goods_code = 'diancan') or {}
        if payinfo.get('overdue', True):
            return ''

        data = {
            'userid' : userid,
            'enuserid' : hids.encode(userid)
        }

        return config.TAKEOUT_URL.format(**data)

    def get_userid(self, params):
        userid = None
        if params.get('enuserid'):
            userids = hids.decode(params['enuserid']) or [None, ]
            userid = userids[0]

        elif is_valid_int(params.get('userid')):
            userid = int(params['userid'])

        if not userid:
            raise ParamError('商户不存在')

        return userid

    @check()
    def GET(self):
        params = self.req.input()
        userid = self.get_userid(params)

        # 店铺信息
        shopinfo = self.get_shopinfo(userid)

        # 分店信息
        sub_info = {'sub_code': '', 'total_num': 0}
        big_uid = max(big_uid_cache[userid], 0)
        if big_uid > 0:
            sub_info['sub_code'] = hids.encode(int(big_uid), userid)
            relates = apcli_ex('getUserRelation', int(big_uid), 'merchant') or []
            sub_info['total_num'] = len(relates)

        return success({
            'shopinfo' : shopinfo,
            'pay_url' : config.QRCODE_URL % hids.encode(userid),
            'takeout_url' : self.get_takeout_url(userid),
            'sub_info' : sub_info
       })
