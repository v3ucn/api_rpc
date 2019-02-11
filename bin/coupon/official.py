# vim: set ts=4 et sw=4 sts=4 fileencoding=utf-8 :

import json
import traceback
import time
import config
import urllib
import datetime

import logging
log = logging.getLogger()

from constants import DATE_FMT
from cache import cache
from util import (
    url_add_query, openid2userid, unicode_to_utf8, unicode_to_utf8_ex
)
from decorator import openid_required, openid_or_login, raise_excp
from excepts import ParamError

from utils.valid import is_valid_int
from utils.base import BaseHandler
from utils.qdconf_api import get_qd_conf_value

from qfcommon.base.dbpool import get_connection
from qfcommon.base.qfresponse import success

@cache()
def get_all_apply_act():
    '''获取商户可参加的报名活动'''
    r = None
    with get_connection('qf_mchnt') as db:
        fields = ['id', '`condition`', 'expire_time']
        r = db.select('official_actv', where={'status' : 1},
            fields=fields, other='order by ctime desc')
    return r

class Entrance(BaseHandler):

    @openid_required
    def GET(self):
        # use openid get userid
        userid = openid2userid(self.openid)

        # skip url
        skip_url = url_add_query(self._d.get('redirect_url', config.DEFAULT_REDIRECT_URL), {'_swx':self.swx})

        # 跳转到绑定页面
        if not userid:
            return self.redirect(config.OP_BIND_URL % urllib.quote(skip_url))

        return self.redirect(unicode_to_utf8(skip_url))

class List(BaseHandler):
    '''
    获取活动详细信息
    '''

    def analyze_condition(self, c):
        try:
            r = {}
            rows = [i for i in c.split('and') if i]
            for i in rows:
               k, op, v= i.split()
               r[k.strip()[10:-2]] = json.loads(v.strip())
        except:
           log.warn('analyze condition error:%s' % traceback.format_exc())
        return r

    def _list(self, mid):
        '''获取商户可参加的报名活动'''
        r = {'ondated':[], 'outdated':[]}
        # 获取用户信息
        userinfo = None
        with get_connection('qf_core') as db:
            userinfo = db.select_one('profile', where={'userid' : mid})
        if not userinfo:
            raise ParamError('用户信息不存在')

        # 对userinfo进行编码处理
        userinfo = {k:unicode_to_utf8_ex(v) for k, v in userinfo.iteritems()}

        # 渠道严格控制
        group_control = get_qd_conf_value(mode='official_actv_control', key='ext',
                        groupid=userinfo['groupid'], default=False) or {}

        # 获取用户的相关活动
        now = int(time.time())
        acts, ids = get_all_apply_act() or [], []
        for act in acts:
            try:
                if not eval(act['condition'] or 'True', {'userinfo':userinfo}):
                    continue
                if group_control:
                    groupids = self.analyze_condition(act['condition']).get('groupid', [])
                    if userinfo['groupid'] not in set(groupids):
                        continue
                ids.append(act['id'])
            except:
                log.warn('error:%s' % traceback.format_exc())

        # 如果列表为空直接返回
        if not ids:
            return r

        actvs = None
        with get_connection('qf_mchnt') as db:
            actvs = db.select(
                    table= 'official_actv',
                    where= {'status': 1, 'id': ('in', ids)},
                    fields= ('cast(id as char) as id,title,bg_url,rule,'
                            'content, start_time, expire_time, poster_url,'
                            'poster_content'),
                    other= 'order by ctime desc') or []
        if not actvs:
            return r

        now = datetime.datetime.now()
        for actv in actvs:
            et = actv['expire_time']
            actv['rule'] = actv['rule'].split('\n')
            actv['poster_content'] = actv['poster_content'].split('\n')
            actv['start_time'] = actv['start_time'].strftime(DATE_FMT)
            actv['expire_time'] = actv['expire_time'].strftime(DATE_FMT)

            if et > now:
                r['ondated'].append(actv)
            else:
                r['outdated'].append(actv)
        return r

    @openid_or_login
    @raise_excp('获取活动列表失败')
    def GET(self):
        mid = self._userid

        # 获取活动列表
        r = self._list(mid)
        return self.write(success(r))

class Info(BaseHandler):
    '''
    获取活动报名详细信息
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {'aid' : d.get('id', '')}
        r['mchnt_id'] = self._userid
        if not is_valid_int(r['aid']):
            raise ParamError('活动id不合法')
        return r

    @openid_or_login
    @raise_excp('查询活动信息失败')
    def GET(self):
        d = self._trans_input()
        # 获取活动报名详细信息
        r = None
        with get_connection('qf_mchnt') as db:
            r = db.select_one(
                    table= 'official_actv',
                    where= {
                        'id' : d['aid'],
                        'status' : 1
                    },
                    fields= ('cast(id as char) as id, title, rule, bg_url, content,'
                             'start_time, expire_time, poster_url, poster_content, ext')
                    )
        if not r:
            raise ParamError('该活动不存在')

        r['rule'] = r['rule'].split('\n')
        r['poster_content'] = r['poster_content'].split('\n')
        r['start_time'] = r['start_time'].strftime(DATE_FMT)
        r['expire_time'] = r['expire_time'].strftime(DATE_FMT)

        return self.write(success(r))
