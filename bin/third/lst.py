# coding:utf-8

import uuid
import logging
import config
import json
import traceback
import time
from collections import _itemgetter

from runtime import redis_pool
from utils.decorator import check
from utils.base import BaseHandler
from utils.tools import url_add_query
from constants import DATETIME_FMT
from user.base import UserDefine

from excepts import ParamError, MacError, DBError

from qfcommon.base.dbpool import get_connection
from qfcommon.base.qfresponse import success

log = logging.getLogger()


class Code(BaseHandler):
    '''获取code'''

    _base_err = '获取code失败'

    @check('login')
    def GET(self):
        params = self.req.input()
        for i in ('client_id', 'redirect_uri'):
            if not params.get(i):
                raise ParamError('%s is must' % i)

        if params['client_id'] != config.LST_CONF['client_id']:
            raise MacError('client_id 错误')

        code = str(uuid.uuid1())

        rkey = config.LST_CONF['code_fmt'].format(code)

        redis_pool.set(
            rkey, self.user.userid, config.LST_CONF['code_expire']
        )

        redirect_url = url_add_query(params['redirect_uri'], {'code': code})
        log.debug('redirect_url:%s' % redirect_url)

        self.redirect(redirect_url)


class AccessToken(BaseHandler):
    '''获取能访问的access_token'''

    def GET(self):
        try:
            params = self.req.input()
            for i in ('client_id', 'code', 'client_secret'):
                if not params.get(i):
                    raise ParamError('%s is must' % i)

            if (params['client_id'] != config.LST_CONF['client_id'] or
                params['client_secret'] != config.LST_CONF['client_secret']
               ):
                raise MacError('client 验证失败')

            # 验证code
            rkey = config.LST_CONF['code_fmt'].format(params['code'])
            userid = redis_pool.get(rkey)
            if not userid:
                raise MacError('code 验证失败')
            redis_pool.delete(rkey)

            # 生成access_token
            access_token = str(uuid.uuid1())
            ak_rkey = config.LST_CONF['access_token_fmt'].format(access_token)
            redis_pool.hmset(ak_rkey, {'cnt': 0, 'userid': userid})

            expire = config.LST_CONF['access_token_expire']
            redis_pool.expire(ak_rkey, expire)

            ret = {
                'access_token': access_token,
                'expire' : expire
            }
        except:
            log.warn(traceback.format_exc())
            ret = {}

        return json.dumps(ret)


class GetUser(BaseHandler):
    '''获取用户信息'''

    def POST(self):
        return self.GET()

    def GET(self):
        try:
            params = self.req.input()

            # 验证access_token
            access_token = params.get('access_token', '')
            ak_rkey = config.LST_CONF['access_token_fmt'].format(access_token)
            ak_info =  redis_pool.hgetall(ak_rkey)
            if (not ak_info or
                int(ak_info.get('cnt') or 1) > config.LST_CONF['access_token_limit']
               ):
                raise MacError('access_token 失效')
            redis_pool.hincrby(ak_rkey, 'cnt')

            userid = int(ak_info['userid'])
            lst_data = None
            with get_connection('qf_core') as db:
                mchinfo = db.select_one(
                    table = 'extra_mchinfo',
                    where = {'userid' : userid},
                    fields = 'lst_data'
                )
                lst_data = json.loads(mchinfo.get('lst_data', ''))
            if not lst_data:
                raise ParamError('没有相关信息')

            fields = ['province', 'city', 'storeName', 'area', 'street', 'detailAddress', 'contactPerson', 'mobile', 'licenseNo', 'storeType']
            ret = {i:lst_data.get(i, '') for i in fields}

            ret['bizId'] = ret['sysId'] = str(userid)
        except:
            log.warn(traceback.format_exc())
            ret = {}

        return json.dumps(ret)


class SuppliedInfo(BaseHandler):
    '''
    用户填写信息
    '''

    @check('login')
    def GET(self):
        userid = self.user.userid
        where = {'userid': userid}
        fields = 'nickname, licensenumber, name, mobile'

        try:
            with get_connection('qf_mchnt') as db:
                lst_auth_row = db.select_one('mchnt_control', fields='is_auth_lst', where={'userid': userid})

            with get_connection('qf_core') as conn:
                row = conn.select_one('profile', fields=fields, where=where)

            is_auth_lst = 1 if lst_auth_row and lst_auth_row['is_auth_lst'] else 0
            ret = dict()
            ret['is_auth_lst'] = is_auth_lst

            if is_auth_lst:
                with get_connection('qf_core') as conn:
                    row = conn.select_one('extra_mchinfo', fields='lst_data', where={'userid': userid})
                tmp = json.loads(row['lst_data'] if row else {})
                pcas = tmp['province'] + tmp['city'] + tmp['area'] + tmp['street']
                try:
                    tmp['detail'] = tmp['detailAddress'].split(pcas)[1]
                except:
                    log.warn(traceback.format_exc())
                    tmp['detail'] = ''
                ret.update(tmp)
                del ret['detailAddress']
                if 'storeType' in ret:
                    del ret['storeType']
                return self.write(success(data=ret))
            else:
                if row:
                    ret['storeName'] = row['nickname'] if row['nickname'] else ''
                    ret['licenseNo'] = row['licensenumber'] if row['licensenumber'] else ''
                    ret['contactPerson'] = row['name'] if row['name'] else ''
                    ret['mobile'] = row['mobile'] if row['mobile'] else ''
                    ret['province'], ret['city'], ret['area'], ret['street'], ret['detail'] = ('',) * 5
                    return self.write(success(data=ret))
                else:
                    raise ParamError('未查询到用户信息')
        except:
            log.warn(traceback.format_exc())
            return self.write(success(data={'ret': {}}))


class SupplyInfo(BaseHandler):

    @check('login')
    def POST(self):
        params = {k: str(v).strip() for k, v in self.req.input().iteritems()}
        storeName = params.get('storeName', '')
        licenseNo = params.get('licenseNo', '')
        contactPerson = params.get('contactPerson', '')
        mobile = params.get('mobile', '')
        province = params.get('province', '')
        city = params.get('city', '')
        area = params.get('area', '')
        street = params.get('street', '')
        detail = params.get('detail', '')

        for i in (('店铺名称', storeName), ('营业执照号', licenseNo), ('联系人姓名', contactPerson),
                  ('联系人手机号', mobile), ('收货所在地区', province), ('街道', street)):
            if not i[1]:
                raise ParamError('%s不能为空' % i[0])

        detailAddress = ''.join((province, city, area, street, detail))
        userid = self.user.userid

        # 先判断licenseNo是否在数据库已经有了 如果有licenseNo必须与数据库一致
        with get_connection('qf_core') as conn:
            row = conn.select_one('profile', fields="licensenumber, mcc", where={"userid": userid})

        if row and row['mcc']:
            storeType = row['mcc']
        else:
            storeType = UserDefine.DEFAULT_MCC

        # 手机号不可重复
        with get_connection("qf_core") as conn:
            row = conn.select_one("extra_mchinfo", where={'lst_data': ('like', '\"mobile\": \"' + str(mobile) + '\"')})
        if row:
            raise ParamError('手机号不可重复')

        lst_data = {
            'province': province,
            'city': city,
            'street': street,
            'storeName': storeName,
            'mobile': mobile,
            'storeType': str(storeType),
            'area': area,
            'detailAddress': detailAddress,
            'licenseNo': licenseNo,
            'contactPerson': contactPerson
        }

        def is_userid_intable(table_name):
            row = conn.select_one(table_name, fields='userid', where={'userid': userid})
            return True if row else False
        try:
            with get_connection('qf_core') as conn:

                now = time.strftime(DATETIME_FMT)
                if is_userid_intable('extra_mchinfo'):
                    conn.update('extra_mchinfo', values={'lst_data': json.dumps(lst_data)}, where={'userid': userid})
                else:
                    conn.insert('extra_mchinfo', values={'userid': userid, 'lst_data': json.dumps(lst_data),
                                                         'ctime': now})

            with get_connection('qf_mchnt') as conn:
                now = time.strftime(DATETIME_FMT)
                if is_userid_intable('mchnt_control'):
                    conn.update('mchnt_control', values={'is_auth_lst': 1}, where={'userid': userid})
                else:
                    conn.insert('mchnt_control', values={'is_auth_lst': 1, 'status': 1,
                                                         'ctime': now, 'utime': now, 'userid': userid})

            return self.write(success(data={}))
        except:
            log.warn(traceback.format_exc())
            raise ParamError('数据库更新失败')


class GetArea(BaseHandler):

    @check('login')
    def GET(self):

        params = self.req.input()
        pid = params.get('pid', '')
        if not pid:
            raise ParamError('pid不能为空')

        try:
            int(pid)
        except:
            raise ParamError('pid格式错误')

        try:
            with get_connection('qf_mis') as conn:
                rows = conn.select('lst_area', fields='area_id, full_name, name', where={'status': 1, 'parent_id': pid})
                rows = sorted(rows, key=_itemgetter('area_id'))
            return self.write(success(data=rows))
        except:
            log.warn(traceback.format_exc())
            raise DBError('查询区域失败')