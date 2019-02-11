# coding=utf-8

import config
import logging
import traceback
import time

from decorator import check_login, check_login_ex, raise_excp
from constants import DATE_FMT, DATETIME_FMT
from util import (
    is_valid_date, str_len, str_timestamp, remove_emoji, create_id,
    is_valid_int, prelogin_lock, postlogin_lock, BaseHandler
)
from excepts import ParamError, DBError
from base import MemberUtil, MemDefine
from utils.payinfo import get_payinfo_ex
from utils.decorator import check

from qfcommon.base.dbpool import get_connection_exception, get_connection
from qfcommon.base.qfresponse import success

log = logging.getLogger()

class Create(BaseHandler):
    '''
    创建会员活动
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        userid = int(self.user.ses.get('userid', ''))

        # 验证商户付费状态
        check_payinfo = getattr(config, 'MEMBER_CHECK_PAYINFO', True)
        if check_payinfo:
            mchnt = get_payinfo_ex(userid,
                    service_code= 'member_manage',
                    groupid= self.get_groupid())
            if not mchnt:
                raise ParamError('你的会员服务尚未开通，请联系业务员开通后再进行设置。')
            elif str(mchnt['expire_time']) <= time.strftime(DATETIME_FMT):
                raise ParamError('只有续费才能创建哦')

        field = ['title', 'content', 'start_time', 'expire_time', 'bg_url']
        r = {i:remove_emoji(d.get(i, '')) for i in field}

        r['userid'] = userid
        # content
        if not (str_len(r['content']) <= 150):
            raise ParamError('更多信息要小于150位哦')
        # start_time, expire_time
        if not all(map(is_valid_date, [r['start_time'], r['expire_time']])):
            raise ParamError('时间格式不对')
        if r['start_time'] > r['expire_time']:
            raise ParamError('活动开始时间大于截止时间')
        r['start_time'] = str_timestamp(r['start_time'], DATE_FMT)
        r['expire_time'] = str_timestamp(r['expire_time'], DATE_FMT) + (24*60*60-1)

        return r

    def _create(self, p):
        field = ['userid', 'title', 'content', 'start_time', 'expire_time', 'bg_url']
        d = {i:p[i] for i in field}
        d['ctime'] = d['utime'] = int(time.time())
        d['status'] = 1 # 启用
        d['id'] = create_id()
        d['type'] = MemDefine.ACTV_TYPE_PROMO
        try:
            with get_connection_exception('qf_mchnt') as db:
                db.insert('member_actv', d)
        except:
            log.warn('insert member actv error:%s' % traceback.format_exc())
            raise DBError('创建活动失败')
        else:
            with get_connection('qf_mchnt') as db:
                db.update('member_actv',
                        values = {
                            'status' : MemDefine.ACTV_STATUS_OFF
                        },
                        where = {
                            'status' : MemDefine.ACTV_STATUS_ON,
                            'expire_time' : ('>=', int(time.time())),
                            'id' : ('!=', d['id']),
                            'userid' : d['userid'],
                            'type': MemDefine.ACTV_TYPE_PROMO,
                        })
        return d['id']

    @check_login_ex(prelogin_lock, postlogin_lock)
    @raise_excp('创建活动失败')
    @check(['check_perm'])
    def POST(self):
        d = self._trans_input()

        # 创建活动
        return self.write(success({'id': self._create(d)}))

class List(BaseHandler):
    '''
    会员活动列表 b端
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {}
        r['userid'] = int(self.user.ses.get('userid', ''))
        r['state'] = d.get('state', '')

        # 分页信息
        page, pagesize = d.get('page', 0), d.get('pagesize', 10)
        if not all(map(is_valid_int, (pagesize, page))):
            raise ParamError('分页信息错误')
        r['offset'], r['limit'] = int(page)*int(pagesize), int(pagesize)

        return r

    def _actv_list(self, d):
        def _get_where():
            # 活动状态 0: 进行中， 1:已过期 2：审核失败 3：删除
            now = int(time.time())
            r = 'userid=%s and type=1' % d['userid']
            # 进行中
            if d['state'] == '0':
                r += ' and expire_time >= %s and status = 1 ' % now
            # 过期了
            elif d['state'] == '1':
                r += ' and (expire_time < %s or status = 1) ' % now
            # 2:审核失败 3:删除
            elif d['state'] in ('2', '3'):
                r += ' and status=%s ' % d['state']
            # 默认是除去删除的所有数据
            else:
                r += ' and status != 3 '
            return r

        fields = 'id, title, bg_url, content, start_time, expire_time, status, audit_info'
        where  = _get_where()
        sql    = ('select %s from member_actv where %s order by ctime desc limit %s offset %s'
            % (fields, where, d['limit'], d['offset']))

        cnt_sql = 'select count(*) as num from member_actv where %s' % where

        with get_connection_exception('qf_mchnt') as db:
            actvs = db.query(sql) or []
            total_num = db.query(cnt_sql)[0]['num']
            indated_num = db.select_one('member_actv', fields='count(1) as num',
                    where= {
                        'userid': d['userid'],
                        'status': 1,
                        'expire_time': ('>', int(time.time())),
                        'type': MemDefine.ACTV_TYPE_PROMO,
                    })['num']
        pvs = MemberUtil.get_actv_pv([i['id'] for i in actvs])
        for i in actvs:
            i['state'] = MemberUtil.get_actv_state(i)
            i['pv'] = pvs.get(i['id'], 0)

        return actvs, total_num, indated_num

    @check_login
    @raise_excp('获取会员活动列表失败')
    def GET(self):
        d = self._trans_input()

        # get actv list
        r, total_num, indated_num = self._actv_list(d)
        return self.write(success({
            'now': time.strftime(DATETIME_FMT),
            'total_num': total_num,
            'indated_num':  indated_num,
            'activities': r
        }))

class Info(BaseHandler):
    '''
    活动详细信息 - b端
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        # 活动id
        r = {'id' : d.get('id', '')}
        if not is_valid_int(r['id']):
            raise ParamError('活动id不合法')

        r['userid'] = int(self.user.ses.get('userid', ''))

        return r

    @check_login
    @raise_excp('查询活动信息失败')
    def GET(self):
        d = self._trans_input()

        # fields
        fields = ('cast(id as char) as id, status,  title, bg_url,'
            'content, start_time, expire_time, audit_info, userid')
        # where
        where = {'id': d['id'], 'userid': d['userid'], 'type': MemDefine.ACTV_TYPE_PROMO}
        # 获取活动报名详细信息
        with get_connection_exception('qf_mchnt') as db:
            r = db.select_one('member_actv', where = where, fields = fields)
            if not r:
                raise ParamError('该活动不存在')

        r['state'] = MemberUtil.get_actv_state(r)
        r['pv'] = MemberUtil.get_actv_pv(r['id']).get(r['id'], 0)

        return self.write(success(r))

class Manage(BaseHandler):
    '''
    活动详细信息
    '''

    def _trans_input(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        r = {'id' : d.get('id', '')}
        r['userid'] = int(self.user.ses.get('userid', ''))

        r['type'] = d.get('type', 'del')
        if r['type'] not in ('del',):
            raise ParamError('操作类型不对')

        with get_connection_exception('qf_mchnt') as db:
            actv = db.select_one('member_actv', where = {'userid': r['userid'], 'id': r['id']})
        if not actv:
            raise ParamError('该活动不存在')

        return r

    def _del(self, p):
        try:
            with get_connection_exception('qf_mchnt') as db:
                data = {'status': 3, 'utime': int(time.time())}
                db.update('member_actv', data, where={'id':p['id']})
        except:
            log.warn('del member actv error:%s' % traceback.format_exc())
            raise DBError('更新活动失败')
        return self.write(success({'id':p['id']}))

    @check(['login', 'check_perm'])
    @raise_excp('编辑活动失败')
    def POST(self):
        d = self._trans_input()

        # manage
        func = getattr(self, '_'+d['type'])
        return func(d)
