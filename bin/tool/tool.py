# coding:utf-8

import logging
import traceback
import time

from config import CITY_CONF as CCONF

from constants import DATETIME_FMT
from decorator import check_login, raise_excp
from excepts import ParamError

from utils.base import BaseHandler
from utils.valid import is_valid_int
from utils.decorator import check

from base import get_head_banks, get_area_cities

from qfcommon.qfpay.defines import card_type
from qfcommon.base.dbpool import get_connection_exception, get_connection
from qfcommon.base.qfresponse import QFRET,error,success
from qfcommon.web.core import Handler

log = logging.getLogger()


class CityList(BaseHandler):
    '''传省code返回市列表'''

    @raise_excp('获取市列表失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        if 'area_no' not in d:
            raise ParamError('参数错误')

        r, area_no =  [], d['area_no'][:2]
        with get_connection_exception('qf_mis') as db:
            # 取出地区id
            area = db.select_one('tools_area', where={'area_no':area_no}, fields='id, area_name')
            if not area:
                raise ParamError('该省不存在')

            # 取出城市列表
            fields = 'city_no, city_name'
            where = {'area_id' : int(area['id']), 'city_display' : 1}
            r = db.select('tools_areacity', where=where, fields=fields) or []

        cities = [{'city_no':i['city_no'], 'city_name':i['city_name']} for i in r]
        return self.write(success({'cities' : cities, 'area_id':area_no, 'area_name':area['area_name']}))

class AreaCities(BaseHandler):
    '''
    获取城市列表
    '''

    def _regioncities(self, records):
        ret, areacities = [], records.get('records', [])
        try:
            for area_no, city_noes in CCONF.get('region_areas', {}).iteritems():
                meet_area = next((i for i in areacities if i['areaid'] == area_no), None)
                if meet_area:
                    meet_cities = [i for i in meet_area['cities'] if i['cityid'] in city_noes]
                    meet_area['cities'] = meet_cities
                    ret.append(meet_area)
            log.debug('ret:%s' % ret)
        except:
            log.warn('get regioncities fail, %s' % traceback.format_exc())
            return self.write(error(QFRET.THIRDERR, respmsg='获取商圈城市列表失败'))

        return self.write(success({'records' : ret}))

    @raise_excp('获取城市列表失败')
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        area_cities =  get_area_cities() or {}
        records = {'records': area_cities.values()}

        if CCONF.get('is_filte', False) and d.get('query_type', '') == '1':
            return self._regioncities(records)
        else:
            return self.write(success(records))

class BranchBanks(BaseHandler):
    '''
    获取支行列表
    '''

    @raise_excp('获取支行列表失败')
    def GET(self):
        # 访问qiantai_util 获取数据
        d = self.req.input()

        records = []
        if d.get('areaid'):
            with get_connection('qf_mis') as db:
                records = db.select_join(
                        'tools_brchbank tbb', 'tools_bank tb',
                        on= {'tbb.bank_id': 'tb.id'},
                        where= {
                            'tbb.areaid': d['areaid'],
                            'tb.bank_display': 1,
                            'tbb.brchbank_status': 0
                        },
                        other= 'order by bank_no')

        elif ('cityid' in d and 'headbankid' in d and
              is_valid_int(d['cityid']) and
              is_valid_int(d['headbankid'])):
            with get_connection('qf_mis') as db:
                keyword = d.get('keyword', '').strip()
                keyword= (u" and locate('{}',brchbank_name)".format(db.escape(keyword))
                          if keyword else '')
                sql = (u'select brchbank_name name, brchbank_code code '
                       'from tools_brchbank,tools_bank b,tools_areacity c '
                       'where brchbank_status=0 and bank_id=b.id and '
                       'areacity_id=c.id and bank_no={bankid} and '
                       'city_no={cityid} {keyword} order by brchbank_no'.format(
                       bankid= int(d['headbankid']),
                       cityid= int(d['cityid']),
                       keyword= keyword))
                records = db.query(sql)

        return self.write(success({'records': records or []}))

class CardsInfo(BaseHandler):
    '''
    获取银行卡信息
    '''
    @raise_excp('获取银行卡信息失败')
    def GET(self):
        d = self.req.input()
        q = d.get('q', '')
        if len(q) < 5:
            return  self.write(success({'records': []}))
        elif len(q) > 9:
            q = q[:6]

        cardbins = None
        with get_connection('qf_core') as db:
            cardbins = db.select(
                     table= 'cardbin',
                     where= {'cardbin': ('like', '{}%'.format(q))},
                     fields= ('distinct cardbin, bankid headbankid,'
                              ' bankname headbankname, cardtp'))
        if not cardbins:
            return self.write(success({'records': []}))

        hdbanks = get_head_banks()
        tags = set()
        records = []
        for cardbin in cardbins:
            tag = '%s%s' % (cardbin['headbankname'], cardbin['cardtp'])
            if tag in tags:
                continue
            tags.add(tag)

            for hdbank in hdbanks:
                if cardbin['headbankname'] in hdbank['headbankname']:
                    records.append({
                        'headbankname': hdbank['headbankname'],
                        'headbankid': hdbank['headbankid'],
                        'cardtype': card_type.get(int(cardbin['cardtp']),
                                                  '未识别的卡种'),
                        'csphone': hdbank['csphone'] or '',
                        'iscommon': hdbank['iscommon']
                     })
        return self.write(success({'records': records}))

class Headbanks(BaseHandler):
    '''
    获取银行总行列表
    '''

    @raise_excp('获取银行总行列表失败')
    def GET(self):
        records = get_head_banks()
        return self.write(success({'records': records}))


class SystemDT(Handler):
    '''
    获取系统时间
    '''
    @check_login
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}

        try:
            fmt = d.get('fmt', DATETIME_FMT)
            ret = time.strftime(fmt)
        except:
            log.warn('[fmt:%s] fmt is not legal, %s' % (fmt, traceback.format_exc()))
            return self.write(error(QFRET.PARAMERR, respmsg='获取系统时间失败'))

        return self.write(success({'sysdt':ret}))


class Check(BaseHandler):
    '''
    验证手机号码
    '''

    _base_err = '获取信息失败'

    @check()
    def GET(self):
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        if d.get('mobile'):
            user = None
            with get_connection('qf_core') as db:
                user = db.select_join_one(
                    table1 = 'auth_user', table2 = 'profile',
                    on = {'auth_user.id': 'profile.userid'},
                    where = {
                        'auth_user.username' : d['mobile']
                    },
                    fields = 'profile.mobile, profile.nickname shopname, profile.name'
                )
            if not user:
                raise ParamError('商户不存在')
            ret = user

        elif d.get('email'):
            user = None
            with get_connection('qf_core') as db:
                user = db.select_one(
                    'auth_user',
                    where = {
                        'email' : d.get('email')
                    }
                )
            if not user:
                raise ParamError('商户不存在')

            ret = {}

        else:
            raise ParamError('参数错误')


        return success(ret)
