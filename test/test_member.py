# encoding:utf-8

import time
import fire
from requests import post,get

from base import Base, hids

class Member(Base):

    def actv_create(self,**kw):
        data = {
            'content': '更多详细信息',
            'start_time': '2016-04-12',
            'expire_time' : '2018-05-13',
        }
        data.update(kw)
        return post(self.host+'/mchnt/member/actv_create',
                data=data, cookies={'sessionid':self._get_sid()})

    def list(self):
        return get(self.host+'/mchnt/member/list',
                cookies={'sessionid':self._get_sid()})

    def head(self, **kw):
        data = {'filter_key': 'lose'}
        data.update(kw)
        return get(self.host+'/mchnt/member/v1/head', data, cookies= {'sessionid':self._get_sid()})

    def list_v1(self, **kw):
        data = {'filter_key': 'lose', 'sort_key': 'txamt'}
        data = kw
        return get(self.host+'/mchnt/member/v1/list', data, cookies= {'sessionid':self._get_sid()})

    def info(self, **kw):
        data = {'customer_id': self.hids.encode(10088)}
        data.update(kw)
        return get(self.host+'/mchnt/member/v1/info', data, cookies= {'sessionid':self._get_sid()})

    def member_info(self, **kw):
        data = {
            'customer_id': self.hids.encode(10088),
            'busicd': '700001'
            }
        data.update(kw)
        return get(self.host+'/mchnt/member/info', data, cookies= {'sessionid':self._get_sid()})

    def txmore(self, **kw):
        data = {'customer_id': self.hids.encode(24)}
        data.update(kw)
        return get(self.host+'/mchnt/member/txmore', data, cookies= {'sessionid':self._get_sid()})

    def privilege_display(self, **kw):
        data = {'mode': 'rule'}
        data.update(kw)
        return get(self.host+'/mchnt/member/privilege/display', data, cookies= {'sessionid':self._get_sid()})

    def privilege_create(self, **kw):
        data = {'content': 'yyk'}
        data.update(kw)
        return post(self.host+'/mchnt/member/privilege/create', data, cookies= {'sessionid':self._get_sid()})

    def privilege_index(self, **kw):
        return get(self.host+'/mchnt/member/privilege/index', cookies= {'sessionid':self._get_sid()})

    def privilege_edit(self, **kw):
        data = {'status': 1, 'id': 6265428757280785691, 'content': 'yyk测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试测试'}
        data.update(kw)
        return post(self.host+'/mchnt/member/privilege/edit', data, cookies= {'sessionid':self._get_sid()})

    def centre(self, **kw):
        data = {
            'userid': self.hids.encode(12),
        }
        data.update(**kw)
        return get(self.host+'/mchnt/member/centre/centre', data, cookies= {'csid':self._get_csid()})

    def cardinfo(self, **kw):
        data = {
            #'userid': self.hids.encode(1492009),
            'userid': self.hids.encode(12),
        }
        return get(self.host+'/mchnt/member/centre/cardinfo', data, cookies= {'csid':self._get_csid()})

    def profile(self, **kw):
        return get(self.host+'/mchnt/member/centre/profile', {'userid': hids.encode(20)}, cookies= {'csid':self._get_csid()})

    def update_profile(self, **kw):
        data = {
            'nickname': 'yyk',
            #'cname': '袁跃江123',
            #'birthday': '2009-01-02'
            #'mobile': 17000000000,
            #'code': '108849',
            #'mode': 'submit',
            'userid': hids.encode(20)
        }
        return post(self.host+'/mchnt/member/centre/update_profile', data,  cookies= {'csid':self._get_csid()})

    def qrcode(self, **kw):
        return get(self.host+'/mchnt/member/centre/qrcode', cookies= {'csid':self._get_csid()})

    def cards(self, **kw):
        data = {'page': 1}
        data.update(**kw)
        return get(self.host+'/mchnt/member/centre/cards', data, cookies= {'csid':self._get_csid()})

    def check_member(self, **kw):
        return post(self.host+'/mchnt/member/check_member', {'encid': self.hids.encode(24, int(time.time()))},
                cookies= {'sessionid':self._get_sid()})

    def shops(self, **kw):
        return get(self.host+'/mchnt/member/centre/shops', {'userid': self.hids.encode(12, int(time.time()))})

    def promotion_effect(self):
        return get(self.host+'/mchnt/notify/promotion_effect/list',
                cookies={'sessionid': self._get_sid()})

    def promotion_list(self, **kw):
        data = {'mode': 'list'}
        data.update(**kw)
        return get(self.host+'/mchnt/member/promotion',data,
                cookies={'csid': self._get_csid()})
    def add_tag(self):
        return post(self.host+'/mchnt/member/v1/add_tag',
                {'userid': 20, 'customer_id': 100, 'tag': 'prepaid'})

if __name__ == '__main__':
    fire.Fire(Member)
