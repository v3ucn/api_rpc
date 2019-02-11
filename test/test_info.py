# encoding:utf-8

import fire
from requests import get

from base import Base

class User(Base):

    def baseinfo(self, **kw):
    	data =  {
            'userid': 21010850,
            'opuid': 0
    	}
        return get(
            self.host+'/mchnt/user/baseinfo', data,
            headers = {
                'user-agent': 'QYB NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; Language:En-us)'
                #'user-agent': 'NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; Language:En-us)'
            },
            cookies = {'sessionid': self._get_sid()}
        )

if __name__ == '__main__':
    fire.Fire(User)
