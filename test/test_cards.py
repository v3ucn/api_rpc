# encoding:utf-8

import time
import fire
from requests import post,get

from base import Base, hids

class Card(Base):

    def create(self, **kw):
        data = {
            'obtain_amt': '100',
            'goods_name': '可乐一瓶',
            'goods_amt': '300',
            'start_time' : '2017-06-27',
            'expire_time' : '2019-03-29',
            'exchange_pt': 3,
            'obtain_limit': 0,
        }
        #data['mchnt_id_list'] = ','.join(hids.encode(i) for i in (20, ))
        data.update(**kw)
        return post(self.host+'/mchnt/card/v1/actv_create',
                data=data, cookies={'sessionid': self._get_sid()})

    def change(self, **kw):
        data = {
            #'obtain_amt': '3000',
            #'goods_name': '可乐两瓶',
            #'goods_amt': '600',
            #'start_time' : '2017-03-29',
            #'expire_time' : '2018-03-29',
            'obtain_limit': 12,
            'id': '6283674417935220740'
        }
        data['mchnt_id_list'] = ','.join(hids.encode(i) for i in (10, 21010853))
        data.update(**kw)
        return post(self.host+'/mchnt/card/v1/actv_change',
                data=data, cookies={'sessionid': self._get_sid()})

    def close(self, **kw):
        data = {
            'expire_time' : '2017-03-29',
            'statement': 'yyk测试',
            'id': '6283674417935220740'
        }
        #data['mchnt_id_list'] = ','.join(hids.encode(i) for i in (20,))
        data.update(**kw)
        return post(self.host+'/mchnt/card/v1/actv_close',
                data=data, cookies={'sessionid': self._get_sid()})


    def index(self):
        return get(self.host+'/mchnt/card/v1/actv_index',
                cookies={'sessionid': self._get_sid()})

    def info(self):
        data = {'id': 6283679098149339141}
        return get(self.host+'/mchnt/card/v1/actv_info',
                data, cookies={'sessionid': self._get_sid()})

    def list(self):
        data = {}
        return get(self.host+'/mchnt/card/v1/actv_list',
                data, cookies={'sessionid': self._get_sid()})

    def customer_list(self):
        data = {'id': 6125528459451876948}
        data = {'id': 6283690645038891016}
        data = {
            'id': 6283679098149339141,
            'order_type': ''
        }
        return get(self.host+'/mchnt/card/v1/customer_list',
                data, cookies={'sessionid': self._get_sid()})

    def exchange_list(self):
        data = {'id': 6125528459451876948}
        data = {'id': 6283690645038891016}
        data = {'id': 6283679098149339141}
        return get(self.host+'/mchnt/card/v1/exchange_list',
                data, cookies={'sessionid': self._get_sid()})

    def tip(self, **kw):
        data = {
            'userid': 12,
        }
        data.update(kw)
        return get(self.host+'/mchnt/card/v1/tips', data)

    def query(self, **kw):
        data = {
            'userid': 20,
            'cid': 24,
            'out_sn': int(time.time()),
            'txamt': 40000,
            'total_amt': 40000,
        }
        data.update(kw)
        code = self.hids.encode(*[int(data[i]) for i in ('userid', 'cid',
                'out_sn', 'txamt', 'total_amt')])
        return post(self.host+'/mchnt/card/v1/query', {'code': code})

    def query_code(self, **kw):
        data = {
            'activity_id': '6283679098149339141',
            #'customer_id': self.hids.encode(24)
            'customer_id': self.hids.encode(1103395)
        }
        data.update(kw)
        return get(self.host+'/mchnt/card/v1/exchange_code', data)

    def exchange(self, **kw):
        data = {
            #'code': '1914',
            'code': '8431',
            'id': 6283679098149339141
        }
        data.update(kw)
        return post(self.host+'/mchnt/card/v1/exchange_goods', data,
                cookies={'sessionid': self._get_sid()})

    def cancel(self, **kw):
        data = {
            'userid': 20,
            'cid': 24,
            'out_sn': int(time.time()),
            'txamt': 40000,
            'total_amt': 40000,
            'orig_out_sn': 1498207629,
        }
        data.update(kw)
        code = self.hids.encode(*[int(data[i]) for i in ('userid', 'cid',
                'out_sn', 'txamt', 'total_amt', 'orig_out_sn')])
        return post(self.host+'/mchnt/card/v1/cancel', {'code': code})


    def cardinfo(self, **kw):
        data = {
            'id': 6283938251556061227,
        }
        data.update(kw)
        return get(self.host+'/mchnt/card/v1/card_info', data,
                cookies={'csid': self._get_csid()})

    def cardlist(self, **kw):
        data = {
            # 'mchnt_id': 11751,
            'customer_id': hids.encode(1103833),
        }
        data.update(kw)
        return get(self.host+'/mchnt/card/v1/card_list', data,
                )
                #cookies={'csid': self._get_csid()})

if __name__ == '__main__':
    fire.Fire(Card)
