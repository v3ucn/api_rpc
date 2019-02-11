# encoding:utf-8

from cache import cache

from qfcommon.base.dbpool import get_connection


@cache(redis_key='_mchnt_api_head_banks_')
def get_head_banks():
    records = None
    with get_connection('qf_mis') as db:
        records = db.select(
                'tools_bank',
                where= {'bank_display': 1},
                fields= ('bank_no headbankid, bank_name headbankname,'
                         'iscommon, csphone'))

    records = records or []
    for record in records:
        record['csphone'] = record['csphone'] or ''

    return records

@cache(redis_key='_mchnt_api_area_cities_')
def get_area_cities():
    records = None
    with get_connection('qf_mis') as db:
        records = db.select_join(
                'tools_areacity tac', 'tools_area ta',
                on= {'tac.area_id': 'ta.id'},
                where= {'area_display': 1, 'city_display': 1},
                fields= ('city_no cityid, city_name cityname, '
                        'area_no areaid, area_name areaname'),
                other= 'order by city_no')

    rtn_val = {}
    for r in records or []:
        if r['areaid'] not in rtn_val:
            rtn_val[r['areaid']] = {
                'areaid': r['areaid'],
                'areaname': r['areaname'],
                'cities': []
            }
        rtn_val[r['areaid']]['cities'].append({
                'cityid': r['cityid'],
                'cityname': r['cityname']
        })

    return rtn_val
