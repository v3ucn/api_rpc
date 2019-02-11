# encoding:utf-8

import fire
from requests import post

from base import Base


class Recharge(Base):

    def recharge(self, **kw):
        data = {
            'price_code' : 'month',
            'goods_code' : 'diancan,prepaid',
            'mobile' : 'yuanyuejiang@qfpay.com',
            'promo_code' : 'GP6BRZTR'
        }
        return post(self.host+'/mchnt/recharge/promo/recharge', data)


if __name__ == '__main__':
    fire.Fire(Recharge)
    #fire.Fire(Tabs_data)
