# encoding:utf-8

import hashlib
import config
import logging
import traceback

from excepts import ParamError

from utils.decorator import check
from utils.base import BaseHandler

from qfcommon.base.tools import smart_utf8
from qfcommon.base.qfresponse import success
from qfcommon.base.dbpool import get_connection
from qfcommon.server.client import HttpClient

log = logging.getLogger()

# 苹果绑定平台
ios_bind_platform = getattr(
    config, 'IOS_PUSH_BIND_PLATFORM', ['msgpush', 'push_entry']
)

# 安卓绑定平台
and_bind_platform = getattr(
    config, 'AND_PUSH_BIND_PLATFORM', ['msgpush', 'push_entry']
)

class TokenBase(BaseHandler):

    def get_bind_id(self):
        userid = int(self.user.userid)

        opuid = int(self.user.ses.get('opuid') or 0)

        if opuid:
            return userid * 10000 + opuid
        else:
            return userid

    def sign(self, data, sign_key):
        '''push_entry 签名'''
        md5 = hashlib.md5()
        try:
            keys = sorted(data.keys())
            values = []
            for key in keys:
                values.append('%s=%s' % (key, smart_utf8(data[key])) )
            str_v = '&'.join(values)
            md5.update(str_v + smart_utf8(sign_key) )
            return md5.hexdigest().upper()
        except:
            log.error(traceback.format_exc())
            raise ParamError('签名错误')


    def push_entry_get_deviceid(self, data):
        '''
        获取deviceid
        ios: device_token
        andriod: clientid
        '''
        ret = ''
        if self.platform == 'ios':
            if data.get('device_token'):
                ret = data['device_token']

            elif self.user.ses.get('push_device_token'):
                ret = self.user.ses.get('push_device_token')

            if ret:
                # 保留device_token
                self.user.ses.data['push_device_token'] = ret

        elif self.platform == 'android':
            if data.get('clientid'):
                ret = data['clientid']

            elif self.user.ses.get('push_clientid'):
                ret = self.user.ses.get('push_clientid')

            elif ('msgpush' in and_bind_platform and
                data.get('deviceid') and
                data.get('apptype')):

                with get_connection('push_data') as db:
                    getui = db.select_one(
                        table= 'getui_bind',
                        where= {
                            'deviceid': data['deviceid'],
                            'apptype': data['apptype']
                        },
                        fields = 'clientid'
                    )
                    if getui:
                        ret = getui['clientid']
            if ret:
                # 保留clientid
                self.user.ses.data['push_clientid'] = ret

        return ret

    def push_entry_bind(self, data):
        params = {
            'userid': data['userid'],
            'apptype': data['apptype'],
            'deviceid': self.push_entry_get_deviceid(data),
            'platform': self.platform,
            'sdk': self.sdk,
        }
        if 'appver' in data:
            params['appversion'] = data['appver']

        if not params['deviceid']:
            log.warn('未找到deviceid')
            return

        if params['apptype'] not in config.SIGN_KEYS:
            log.warn('[apptype:%s]不合法' % params['apptype'])
            return

        params['sign'] = self.sign(params, config.SIGN_KEYS[params['apptype']])

        if data.get('is_logout'):
            url = '/pushapi/v1/dev/unbind'
        else:
            url = '/pushapi/v1/dev/bind'

        HttpClient(config.PUSH_BIND_SERVERS).post_json(
            url, params
        )


class IosSet(TokenBase):
    '''
    ios推送 设置
    '''

    _base_err = '参数错误'

    # 推送平台
    platform = 'ios'

    # 推送sdk
    sdk = 'apns'

    def msgpush_bind(self, data):
        with get_connection('push_data') as db:
            where= {
                'device_token': data['device_token'],
                'apptype': data['apptype']
            }
            if db.select('ios_bind', where = where):
                db.update(
                    table= 'ios_bind',
                    values= {
                        'is_logout': int(data['is_logout']),
                        'userid': data['userid'],
                        'appver': data['appver'],
                        'update_time': 'now()'
                    },
                    where= where
                )
            else:
                db.insert('ios_bind', values = data)


    @check('login')
    def POST(self):
        params = self.req.input()

        data = {}
        data['userid'] = self.get_bind_id()
        data['apptype'] = int(params.get('app_type') or 402)
        data['device_token'] = params.get('device_token', '').strip()
        data['openid'] = params.get('openid', '')
        data['mobile'] = params.get('mobile', 0)
        data['appver'] = params.get('appver', '')
        data['badge'] = int(params.get('badge', '0').strip())
        data['usertag'] = int(params.get('usertag', '0'))
        data['token_status'] = 0
        data['create_time'] = data['update_time'] = 'now()'
        data['is_logout'] = int(params.get('is_logout') or 0)

        if not data['device_token']:
            raise ParamError('参数错误')

        for i in ios_bind_platform:
            try:
                getattr(self, i+'_bind')(data)
            except:
                log.warn(traceback.format_exc())

        return success({})


class AndSet(TokenBase):
    '''
    and推送 设置
    '''

    _base_err = '参数错误'

    # 推送平台
    platform = 'android'

    # 推送sdk
    sdk = 'getui'

    def msgpush_bind(self, data):
        if self.sdk != 'getui':
            return

        with get_connection('push_data') as db:
            where = {
                'deviceid': data['deviceid'],
                'apptype': data['apptype']
            }
            if db.select('getui_bind', where = where):
                update_fields = [
                    'openid', 'mobile', 'appver', 'clientid', 'usertag',
                    'userid', 'update_time'
                ]
                update_data = {i:data[i] for i in update_fields if data[i]}
                update_data['is_logout'] = data['is_logout']
                update_data['token_status'] = data['token_status']
                db.update(
                    table = 'getui_bind', values = update_data,
                    where = where
                )

            else:
                db.insert(
                    table = 'getui_bind', values = data,
                )

    @check('login')
    def POST(self):
        params = self.req.input()

        sdk = params.get('sdk') or 'getui'
        if sdk not in ('xiaomi', 'huawei', 'getui'):
            raise ParamError('sdk not support')
        self.sdk = sdk

        data = {}
        data['userid'] = self.get_bind_id()
        data['apptype'] = int(params.get('app_type') or 402)
        data['deviceid'] = params.get('deviceid', '').strip()
        data['clientid'] = params.get('clientid', '').strip()
        data['openid'] = params.get('openid', '')
        data['mobile'] = params.get('mobile', 0)
        data['appver'] = params.get('appver', '')
        data['usertag'] = int(params.get('usertag', '0'))
        data['is_logout'] = int(params.get('is_logout') or 0)
        data['create_time'] = data['update_time'] = 'now()'
        data['token_status'] = 0

        if not data['deviceid']:
            raise ParamError('参数错误')

        for i in and_bind_platform:
            try:
                getattr(self, i+'_bind')(data)
            except:
                log.warn(traceback.format_exc())

        return success({})
