# encoding:utf-8

import fire
from requests import post

from base import Base

class WdApp(Base):

    def ios_bind(self):
        return  post(
            self.host + '/qmm/wd/app/near/ios_bind',
            data = {
                'device_token' : 'efe11ccbe2b3b7a0695fa1c34d144df3d351d7a35068e1ef94003020d60bfbd7',
                'badge' : '0',
                'appver' : '4.6.5',
                'app_type' : '402',
                'deviceid' : '1234',
            },
            cookies={'sessionid' : self._get_sid()}
        )

    def ios_token_set(self):
        return  post(
            self.host + '/qmm/wd/app/near/ios_token_set',
            data = {
                'device_token' : 'efe11ccbe2b3b7a0695fa1c34d144df3d351d7a35068e1ef94003020d60bfbd7',
                'badge' : '0',
                'appver' : '4.6.5',
                'app_type' : '402',
                'deviceid' : '1234',
                'is_logout': 1
            },
            cookies={'sessionid' : self._get_sid()}
        )

    def and_bind(self):
        return  post(
            self.host + '/qmm/wd/app/near/android_bind',
            data = {
                'deviceid' : '1234',
                'clientid' : '5678',
                'appver' : '4.6.5',
                'app_type' : '402',
                'deviceid' : '1234',
            },
            cookies={'sessionid' : self._get_sid()}
        )

    def and_token_set(self):
        return  post(
            self.host + '/qmm/wd/app/near/android_token_set',
            data = {
                'app_type' : '402',
                'deviceid' : '1234',
                'is_logout': 1
            },
            cookies={'sessionid' : self._get_sid()}
        )

if __name__ == '__main__':
    fire.Fire(WdApp)
