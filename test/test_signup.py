# encoding:utf-8

import fire
from requests import post, get

from base import Base

class User(Base):

    def bigmchnt_signup(self, **kw):
    	data =  {
    	    'username': '14114101109',
            'password': '123456',
    	    'code': '920412',
    	    'shopname': 'yyk的小店',
            'saleman_mobile': '17000000000'
            # 'salema_mobile': '14000000007'

    	}
        return post(self.host+'/mchnt/user/bigmchnt_signup', data)

    def pre_signup(self, **kw):
    	data =  {
            'src': 'salesman',
            'mode': 'bigmchnt',
            'big_uid': 12
    	}
        return post(
            self.host+'/mchnt/user/pre_signup', data,
            headers = {
                'user-agent': 'QYB NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; Language:En-us)'
                #'user-agent': 'NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; Language:En-us)'
            },
            cookies = {'sessionid': self._get_sid()}
        )

    def signup(self, **kw):
    	data =  {
            #'mode': 'bigmchnt',
            #'username': '9000000121000',
    	    'username': '9000000121015',
            'mode': 'mchnt',
    	    'province': '',
    	    'bankprovince': '',
            #'code': '000000',
    	    'shopname': u'yyk的小店',
    	    'sign_lat': '39.996439',
    	    'idcardback': 'f428af2ac7525a2790fecc30a1a1b8e3.jpg',
    	    'bankaccount': '6222024402040259743',
    	    'city': '',
    	    'bankname': '中国工商银行股份有限公司北京通州支行新华分理处',
    	    'shopphoto': 'caea13ddde575356b88f1f28af51a95a.jpg',
    	    'sign_lng': '116.480240',
    	    'saleman_mobile': '',
    	    'idcardinhand': 'c61b003b98dd548a9b7c353251eeef43.jpg',
    	    'location': '朝阳区阜通西大街483号',
    	    'bankmobile': '18513504945',
    	    'shoptype_id': '238',
    	    'bankcity': '北京市',
    	    'bankuser': '袁跃江',
    	    'address': '',
            'password': '123456',
    	    'headbankname': '中国工商银行',
    	    'idnumber': '51231213121312133X',
    	    'idcardfront': '6e28483925d95917a38c2fd9fbfe5bbc.jpg',
    	    'goodsphoto': '932829b3505a51c2afdb1689eddf4035.jpg',
    	    'bankcode': '102100000021',
    	    'provinceid': '110005',
            'head_img': 'http://near.m1img.com/op_upload/137/148040326588.png',
            'logo_url': 'http://near.m1img.com/op_upload/137/148040326588.png',
            'tenpay_ratio': '0.49',
            'alipay_ratio': '0.59',
            'big_uid': 12
    	}
        return post(self.host+'/mchnt/user/signup', data,
            headers = {
                #'user-agent': 'QYB NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; Language:En-us)'
                'user-agent': 'NearMerchant/060985 (iPhone; iOS 9.3.1; Scale/3.00; Language:En-us)'
            },
            cookies={'sessionid': self._get_sid()})

if __name__ == '__main__':
    fire.Fire(User)
