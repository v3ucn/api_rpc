# encoding:utf-8

import fire
import json
from requests import post,get

from base import Base
from qfcommon.base.dbpool import get_connection


class User(Base):

    def pre_signup(self, **kw):
        data = {
            'username': 14512400011,
            'code': '000000',
            'mode': 'bigmchnt'
        }
        return post(self.host+'/mchnt/user/pre_signup',
                data=data, cookies={'sessionid': self._get_sid()})

    def reset_pwd(self, **kw):
        data = {
            'mobile': 17000000000,
            'password': 123456,
            'code': '000000',
        }
        data.update(kw)
        return post(self.host+'/mchnt/user/reset_pwd', data)

    def big_signup(self, **kw):
        data = {
            'username':'14900000000',
            'password':'123456',
            'code': '000000',
            'shopname': 'yyk测试',
            'saleman_mobile': '17000000000'
        }
        return post(self.host+'/mchnt/user/bigmchnt_signup', data)

    def userLogin(self, **kw):
        data = {
            'username': 17000000000,
            'password': '123456',
            'udid' : '123',
            #'username': 13545454545,
            #'password': '000291',
            #'opuid' : 1,
        }
        data.update(**kw)
        return post(self.host+'/mchnt/user/login',
                data,
                headers = {'user-agent': 'NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; Language:En-us)'},
                )

    def conf(self, **kw):
        headers = {'user-agent': 'NearMerchant/000985 APOS A8 (iPhone; iOS 9.3.1; Scale/3.00; Language:ja-jp)'}
        return get(self.host+'/mchnt/user/v1/conf',
                headers= headers, cookies={'sessionid':self._get_sid()})

    def ratio(self, **kw):
        headers = {'user-agent': 'NearMerchant/000985 APOS A8 (iPhone; iOS 9.3.1; Scale/3.00; Language:ja-jp)'}
        return get(self.host+'/mchnt/user/v1/ratio',
                {'enuserid': self.hids.encode(30)},
                headers= headers, cookies={'sessionid':self._get_sid()})

    def audit(self, **kw):
        headers = {'user-agent': 'NearMerchant/000985 APOS A8 (iPhone; iOS 9.3.1; Scale/3.00; Language:ja-jp)'}
        return get(self.host+'/mchnt/user/v1/audit',
                {'enuserid': self.hids.encode(30)},
                headers= headers, cookies={'sessionid':self._get_sid()})

    def homepage(self, **kw):
        return get(self.host+'/mchnt/user/v1/home_page',
                headers = {'user-agent': 'NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; )'},
                cookies= {'sessionid':self._get_sid()})

    def service(self, **kw):
        #return get(self.host+'/mchnt/user/v1/service',
        return get(self.host+'/mchnt/user/v1/info',
                headers = {'user-agent': 'NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; Language:En-us)'},
                cookies= {'sessionid':self._get_sid()})

    def payinfo(self):
        data = {'userid': 12, 'code': 'coupon'}
        #return get(self.host+'/mchnt/user/v1/pay_info',
                #data = data, cookies= {'sessionid':self._get_sid()})
        return get(self.host+'/mchnt/user/v1/pay_info',
                   data)

    def data(self):
        headers = {'user-agent': 'NearMerchant/030985 APOS A8 (iPhone; iOS 9.3.1; Scale/3.00)'}
        #headers = {'user-agent': 'Near-Merchant-Android;version_name:v6.3.0;version_code:3875;channel:haojin;model:APOS A8;'}
        return get(self.host+'/mchnt/user/v1/data',
                cookies= {'sessionid':self._get_sid()},
                headers= headers)

    def change(self):
        data = {
            'head_img': 'yyk',
            'logo_url': 'http://near.m1img.com/op_upload/137/148040326588.png',
            'logo_url': 'yyk1',
            'location': '测试location',
            'address': '测试address',
            'province': '北京市'
        }
        return post(self.host+'/mchnt/user/change', data, cookies={'sessionid':self._get_sid()})

    def stats(self):
        return get(self.host+'/mchnt/user/v1/stats',
                cookies={'sessionid':self._get_sid()})

    def advice(self):
        return  get(self.host+'/mchnt/user/v1/advice',
                {'mode' : 'normal', 'index' : 3},
                cookies={'sessionid' : self._get_sid()})

    def menu(self):
        return  get(self.host+'/mchnt/user/v1/menu',
                {'mode' : 'main'},
                headers = {'user-agent': 'NearMerchant/040985 (iPhone; iOS 9.3.1; Scale/3.00;)'},
                cookies={'sessionid' : self._get_sid()})

    def tabs(self):
        return  get(self.host+'/mchnt/user/v1/tabs',
                headers = {'user-agent': 'NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00)'},
                cookies={'sessionid' : self._get_sid()})


class Tabs_data(Base):

    def tabs(self):

        values = {"ios_tabs":  [
          {
         "icon": "http://near.m1img.com/op_upload/105/150348111759.png",
         "icon_selected": "http://near.m1img.com/op_upload/105/150348106883.png",
         "link": "nearmcht://view-home-module",
         "name": "首页",
         "color": "#000000",
         "color_selected": "#FF8100",
         },
         {
         "icon": "http://near.m1img.com/op_upload/105/150348115347.png",
         "icon_selected": "http://near.m1img.com/op_upload/105/150348114341.png",
         "link": "nearmcht://view-more-module",
         "name": "更多",
         "color": "#000000",
         "color_selected": "#FF8100",

         },
       {
         "icon": "http://near.m1img.com/op_upload/105/150348117955.png",
         "icon_selected": "http://near.m1img.com/op_upload/105/150348117035.png",
         "link": "nearmcht://view-message-module",
         "name": "消息",
         "color": "#000000",
         "color_selected": "#FF8100",
         },
        {
         "icon": "http://near.m1img.com/op_upload/105/150348120002.png",
         "icon_selected": "http://near.m1img.com/op_upload/105/150348118983.png",
         "link": "nearmcht://view-mine-module",
         "name": "我的",
         "color": "#000000",
         "color_selected": "#FF8100",
         }
      ],
            "and_tabs":  [
          {
         "icon": "http://near.m1img.com/op_upload/105/150348111759.png",
         "icon_selected": "http://near.m1img.com/op_upload/105/150348106883.png",
         "link": "nearmcht://view-home-module",
         "name": "首页",
         "color": "#000000",
         "color_selected": "#FF8100",
         },
         {
         "icon": "http://near.m1img.com/op_upload/105/150348115347.png",
         "icon_selected": "http://near.m1img.com/op_upload/105/150348114341.png",
         "link": "nearmcht://view-more-module",
         "name": "更多",
         "color": "#000000",
         "color_selected": "#FF8100",

         },
       {
         "icon": "http://near.m1img.com/op_upload/105/150348117955.png",
         "icon_selected": "http://near.m1img.com/op_upload/105/150348117035.png",
         "link": "nearmcht://view-message-module",
         "name": "消息",
         "color": "#000000",
         "color_selected": "#FF8100",
         },
        {
         "icon": "http://near.m1img.com/op_upload/105/150348120002.png",
         "icon_selected": "http://near.m1img.com/op_upload/105/150348118983.png",
         "link": "nearmcht://view-mine-module",
         "name": "我的",
         "color": "#000000",
         "color_selected": "#FF8100",
         }
      ]
        }

        with get_connection('qf_mis') as db:
            qdconfs = db.select(
                    table='qd_conf',
                    where={'qd_uid' : 0},
                    fields=('service'))
            vals = json.loads(qdconfs[0]['service'])
            vals.update(values)
            db.update('qd_conf', {'service': json.dumps(vals)}, where={'qd_uid': 0})


        # with get_connection('qf_mis') as db:
        #     db.insert('qd_conf', {'service': json.dumps(values), 'qd_uid': 10, 'id': 12})

if __name__ == '__main__':
    fire.Fire(User)
    #fire.Fire(Tabs_data)
