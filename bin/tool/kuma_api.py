# coding:utf-8

'''
kuma服务的部分接口
'''

import config
import logging

from runtime import qfcache
from excepts import ParamError

from utils.decorator import check
from utils.base import BaseHandler
from utils.valid import is_valid_int
from utils.tools import unicode_to_utf8

from qfcommon.qfpay.qfresponse import success
from qfcommon.base.dbpool import get_connection
from qfcommon.server.client import ThriftClient
from qfcommon.thriftclient.qudao import QudaoServer
from qfcommon.thriftclient.qudao.ttypes import (
    RegionQueryArg, QueryMeta
)


log = logging.getLogger()


def load_shop_cates(data=None):
    cates = None
    with get_connection('qf_mchnt') as db:
        cates = db.select(
            'shop_category',
            where = {'status' : 1, 'create_time' : '2016-05-18 06:59:59'},
            fields = 'id, parent_id, name, weight',
            other = 'order by weight desc'
        )

    return cates

qfcache.set_value(
    'kuma_shop_cates', None, load_shop_cates,
    getattr(config, 'KUMA_SHOP_CATE_CACHE', 3600)
)

def analysis_list(cates, pid=0):
    '''
    递归, 讲店铺类型分类
    '''
    r = [i for i in cates[::] if i['parent_id'] == pid]
    for i in r:
        i['shoptypes'] = analysis_list(cates, i['id'])

    return r


def get_shop_cates(pid=0):
    all_cates = qfcache.get_data('kuma_shop_cates') or []

    return analysis_list(all_cates, pid)


class ShopTypes(BaseHandler):
    '''获取店铺类型'''

    _base_err = '获取商户类型列表失败'

    @check()
    def GET(self):
        pid = self.req.input().get('pid', '0').strip()
        if not is_valid_int(pid):
            raise ParamError('param error')
        pid = int(pid)

        return success({'shop_types': get_shop_cates(pid)})


def get_regions(city, province, adcode):
    '''通过qudao_api获取商圈'''
    client = ThriftClient(config.QUDAO_SERVERS, QudaoServer, framed=True)
    req_data = RegionQueryArg(
        status = [0, ], audit_status = [2, ],
        query_meta = QueryMeta(offset=0, count=10000),
    )

    if city:
        req_data.city = city

    elif province:
        req_data.province = province

    elif adcode:
        area = None
        area_no = adcode[:2]
        with get_connection('qf_mis') as db:
            area = db.select_one(
                'tools_area', where={'area_no' : area_no}
            )
        if area:
            req_data.province = unicode_to_utf8(area['area_name'])

    region_ids = client.region_query(req_data)
    if not region_ids:
        return []

    return client.region_get(region_ids)

class Regions(BaseHandler):
    '''
    获取商圈列表

    TODO: 后面会根据距离商圈的距离进行排序

    city_name: 市名
    province_name: 省名
    city_no: 地址编码(全国统一)

    '''

    _base_err = '获取商圈列表失败'

    def GET(self):
        params = self.req.input()

        adcode = params.get('city_no', '').strip()
        city = params.get('city_name', '').strip()
        province = params.get('province_name', '').strip()

        regions = get_regions(city, province, adcode)

        # 整理商圈数据
        # 如果没有其他商圈，加上其他商圈
        other_region = config.OTHER_REGION
        add_other_region = True
        ret = []
        for i in regions:
            ret.append({'id': str(i.id), 'name': i.name, 'weight': 1})

            if i.id == int(other_region['id']):
                add_other_region = False
        if add_other_region:
            ret.insert(0, other_region)


        return success({
            'locate_region' : {},
            'regions' : ret
        })
