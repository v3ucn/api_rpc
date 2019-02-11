# encoding:utf-8

import fire
from requests import post,get

from base import Base

class Coupon(Base):

    def apply_list(self, **kw):
        return get(self.host+'/mchnt/activity/apply_list', cookies={'sessionid':self._get_sid()})

    def list(self, **kw):
        data = {'state':1}
        data.update(kw)
        return get(self.host+'/mchnt/activity/list',data, cookies={'sessionid':self._get_sid()})

    def create(self, **kw):
        data = {
            'title': 'yyk测试',
            'amt_min': 0,
            'amt_max': 150,
            'total_amt': 100000,
            'obtain_limit_amt' : 123,
            'use_limit_amt' : 150,
            'coupon_lifetime' : 7,
            'start_time' : '2017-04-01',
            'expire_time' : '2017-07-22',
            #'type': 20, # 消费返劵
            'type': 21, # 消费分享劵

        }
        data.update(kw)
        return post(self.host+'/mchnt/activity/create', data=data,
                cookies={'sessionid': self._get_sid()})

    def change(self, **kw):
        data = {'id' : 6253519909410731855}
        data.update(kw)
        return post(self.host+'/mchnt/activity/change',
                data=data, cookies={'sessionid':self._get_sid()})

    def notify_list(self, **kw):
        return get(self.host+'/mchnt/notify/coupon_effect/list',
                cookies={'sessionid':self._get_sid()})

if __name__ == '__main__':
    fire.Fire(Coupon)
