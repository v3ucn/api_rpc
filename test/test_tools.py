# encoding:utf-8

import fire
from requests import post,get

from base import Base

class Tools(Base):

    def code_send(self, **kw):
        data = {
            'mode': 'reset_pwd',
            #'mode': 'signup',
            'mobile': '17000000000',
            #'mobile': '14700002007',
            #'saleman_mobile': '18513504945',
        }
        data.update(kw)

        return get(self.host+'/mchnt/smscode/send', data,)
                #cookies= {'sessionid':self._get_sid()})

    def code_check(self, **kw):
        data = {
            'mobile': '17000000000',
            'code': '870660'
        }
        data.update(kw)

        return post(self.host+'/mchnt/smscode/check', data)

    def is_baipai(self, **kw):
        data = {
            'userid': 12
        }
        return get(self.host+'/mchnt/is_baipai', data)

    def set_cookie(self, **kw):
        return get(self.host+'/mchnt/set_cookie')

if __name__ == '__main__':
    fire.Fire(Tools)
