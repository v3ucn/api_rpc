# coding:utf-8

import config
import json
import logging
import traceback
import datetime

from collections import defaultdict

from runtime import hids
from excepts import ParamError, ThirdError

from utils.defines import CodeDef
from utils.base import BaseHandler
from utils.decorator import check

from qfcommon.thriftclient.qf_marketing import QFMarketing
from qfcommon.base.qfresponse import success
from qfcommon.base.dbpool import get_connection_exception
from qfcommon.base.tools import thrift_callex

log = logging.getLogger()


class Verify(BaseHandler):
    '''兑换红包'''

    _base_err = '核销失败'

    def get_code_info(self, code):
        code_info = hids.decode(code)
        if len(code_info) < 2:
            raise ParamError('核销失败,兑换码不存在!')

        code_type, code_id = code_info[:2]
        if code_type != CodeDef.DW_CODE:
            raise ParamError('核销失败,兑换码不存在!')

        with get_connection_exception('qf_marketing') as db:
            code_info = db.select_one(
                'verify_coupon', where = {'id' : code_id}
            )
            if not code_info:
                raise ParamError('核销失败,兑换码不存在!')

            if (code_info['status'] not in
                    (CodeDef.DW_STATUS_CREATE, CodeDef.DW_STATUS_BIND)):
                raise ParamError('核销失败,兑换码已被使用')

            actv_info = db.select_one(
                'activity_verify',
                where = {'id' : code_info['activity_id']}
            )
            try:
                mchnt_id_list = json.loads(actv_info['mchnt_id_list'])
                mchnt_ids = set(map(int, mchnt_id_list))
            except:
                mchnt_ids = []

            now = datetime.datetime.now()
            if now > actv_info['expire_time']:
                raise ParamError('核销失败, 兑换码已过期')

            if now < actv_info['start_time']:
                raise ParamError('核销失败, 请在{}至{}兑换'.format(
                    str(actv_info['start_time']),
                    str(actv_info['expire_time'])
                ))

            if int(self.user.userid) not in mchnt_ids:
                raise ParamError('核销失败, 该兑换码不能在该店核销')

        return code_info


    @check('login')
    def POST(self):
        params = self.req.input()

        code_info = self.get_code_info(params.get('code'))
        req_args = json.dumps({
            'verify_id' : code_info['id'],
            'userid' : int(self.user.userid)
        })

        try:
            thrift_callex(
                config.QF_MARKETING_SERVERS, QFMarketing,
                'verify_actv_verify', req_args
            )
        except:
            log.warn(traceback.format_exc())
            raise ThirdError('核销失败')

        return success({})


class VerifyList(BaseHandler):
    '''兑换列表'''

    _base_err = '获取数据失败'

    @check('login')
    def GET(self):
        userid = int(self.user.userid)
        with get_connection_exception('qf_marketing') as db:
            records = db.select(
                'verify_record',
                where = {'userid' : userid},
                other = self.get_other(fields = ('ctime', )),
                fields = 'src, verify_id, activity_id, ctime'
            )
            if not records:
                return success({'records' : []})

            actv_ids = [i['activity_id'] for i in records]
            actvs = db.select(
                'activity_verify', where = {'id' : ('in', actv_ids)},
                fields = 'id, name, img, src'
            ) or []
            actv_dict = {i['id']:i for i in actvs}

            # 补充活动信息
            tidy_records = defaultdict(list)
            for i in records:
                actv_id = i.pop('activity_id')
                i['name'] = '优惠'
                i['img'] = ''
                if actv_id in actv_dict:
                    actv = actv_dict[actv_id]
                    i['name'] = actv['name']
                    i['img'] =  actv['img']
                i['code'] = hids.encode(CodeDef.DW_CODE, i.pop('verify_id'))

                t = str(i['ctime'])[:10]
                tidy_records[t].append(i)

            # 获取头部信息
            last_day = str(records[-1]['ctime'])[:10]
            first_day = str(records[0]['ctime'])[:10]
            sql = (
                'select DATE_FORMAT(ctime, "%%Y-%%m-%%d") as date, '
                'count(1) as num from verify_record '
                'where userid=%d and ctime>="%s 00:00:00" and ctime <= "%s 23:59:59" '
                'group by DATE_FORMAT(ctime, "%%Y%%m%%d") order by ctime desc'
                % (userid, last_day, first_day)
            )
            diff_days = db.query(sql) or []

        ret = []
        for i in diff_days:
            t = {}
            t['date'] = i['date']
            t['total_num'] = i['num']
            t['records'] = tidy_records.get(i['date']) or []
            ret.append(t)

        return success({'records': ret})
