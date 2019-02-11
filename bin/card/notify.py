# coding:utf-8

'''
交易通知处理
'''


import sys
import traceback
import time
import logging
import gevent

from copy import deepcopy

from runtime import hids
from excepts import ParamError
from base import CardBase, PT_RECORD_GET, PT_RECORD_CANCEL

from utils.decorator import check
from utils.tools import getid
from utils.payinfo import adjust_payinfo_ex
from utils.date_api import str_to_tstamp

from qfcommon.base.qfresponse import success
from qfcommon.base.dbpool import (
    get_connection_exception, get_connection, DBFunc
)

log = logging.getLogger()


class Cancel(CardBase):
    '''
    交易撤销后 （通知服务器调用，会验证ip)
    '''

    def _cancel(self, d):
        now = int(time.time())
        with get_connection('qf_mchnt') as db:
            # 获取集点记录
            pt = db.select_one(
                table='pt_record',
                where={'out_sn': d['orig_out_sn'], 'type': PT_RECORD_GET}
            )
            if not pt:
                return
            actv_id = pt['activity_id']

            where = {'activity_id': actv_id, 'customer_id': d['customer_id']}

            # 获取消费者信息
            member = db.select_one('member_pt', where=where)
            if not member:
                raise ParamError('消费者信息不存在')

            # 撤销集点
            cancel_pt = min(pt['pts'], member['cur_pt'])

            # 插入pt_record
            try:
                pidata = deepcopy(d)
                pidata['id'] = getid()
                pidata['ctime'] = pidata['utime'] = now
                pidata['activity_id'] = actv_id
                pidata['type'] = PT_RECORD_CANCEL
                pidata['pts'] = cancel_pt
                db.insert('pt_record', pidata)
            except:
                log.warn('insert error: %s' % traceback.format_exc())
                return

            card_id = member['id']
            if not cancel_pt:
                return {'cancel_pt': cancel_pt,
                        'activity_id': actv_id, 'card_id': card_id}

            # 更新消费者的集点
            try:
                mem_updata = {
                    'txamt': DBFunc('txamt-%s' % d['txamt']),
                    'total_amt': DBFunc('total_amt-%s' % d['total_amt']),
                    'total_pt': DBFunc('total_pt-%d' % cancel_pt),
                    'cur_pt': DBFunc('cur_pt-%d' % cancel_pt),
                    'utime': now
                    }
                db.update('member_pt', mem_updata, where)
            except:
                log.debug('更新消费者集点信息失败, %s' % traceback.format_exc())
            else:
                # 更新活动信息
                try:
                    ucwhere = {
                        'id': actv_id,
                        'total_pt': ('>=', cancel_pt)
                    }
                    ucdata = {
                        'total_pt': DBFunc('total_pt-%d' % cancel_pt),
                        'utime': now
                    }
                    db.update('card_actv', ucdata, ucwhere)
                except:
                    log.debug('%s' % traceback.format_exc())

                return {
                    'cancel_pt': cancel_pt,
                    'activity_id': actv_id,
                    'card_id': card_id
                }

    _base_err = '撤销集点失败'

    @check('check_ip')
    def POST(self):
        # 获取参数
        d = {k: v.strip() for k, v in self.req.input().iteritems()}
        code = d.get('code') or ''
        try:
            data = {}
            data['userid'], data['customer_id'], data['out_sn'], data['txamt'], data['total_amt'], data['orig_out_sn'] = hids.decode(code)
        except:
            raise ParamError('参数错误')
        data['out_sn'] = str(data['out_sn'])
        data['orig_out_sn'] = str(data['orig_out_sn'])

        # cancel
        r = (self._cancel(data) or
             {'cancel_pt': 0, 'activity_id': '0', 'card_id': 0})

        return success(r)


class Query(CardBase):
    '''
    会员集点活动查询 (c端服务器调用， 会验证ip)
    '''

    def update(self, userid, customer_id):
        try:
            with get_connection_exception('qf_mchnt') as db:
                # 会员来源(支付)
                PAY_SRC = 1
                data = {'card': 1}
                data['utime'] = int(time.time())
                update_result = db.update(
                    'member_tag',
                    values= data,
                    where= {
                        'userid': userid,
                        'customer_id': customer_id,
                    })

                if not update_result:
                    data['id'] = getid()
                    data['ctime'] = int(time.time())
                    data['src'] = PAY_SRC
                    data['userid'] = userid
                    data['customer_id'] = customer_id
                    db.insert('member_tag', values= data)
        except:
            pass

    def _query(self, d):
        rcard, rcustomer, overdue = {}, {}, 0
        now = int(time.time())
        # 获取生效的集点活动
        with get_connection('qf_mchnt') as db:
            rcard = db.select_one(
                    'card_actv',
                    where= {
                        'userid': self.get_userid_condition(d['userid']),
                        'expire_time': ('>=', now),
                        'start_time': ('<', now)
                    },
                    fields= (
                        'id, start_time, expire_time, status, goods_name,'
                        'goods_amt, exchange_pt, obtain_amt, obtain_limit,'
                        'statement'
                    ),
                    other= 'order by ctime desc')
            # 暂无生效的集点活动
            if not rcard:
                return None, None, 0

        # 商户过期信息
        overdue = adjust_payinfo_ex(
                userid= d['userid'],
                service_code= 'card_actv',
                groupid= self.get_groupid(userid=d['userid'])
            )['overdue']

        with get_connection('qf_mchnt') as db:
            # 消费者信息
            customer_info = db.select_one('member_pt',
                    where= {
                        'activity_id': rcard['id'],
                        'customer_id': d['customer_id']
                    }) or {}

            # 若商户过期
            if overdue:
                # 若是新消费者或者老商户且已经兑换过礼品，
                # 则不能继续集点活动了
                if (not customer_info or
                        (not customer_info['cur_pt'] and
                         customer_info['total_pt'])):
                    return None, None, overdue

            # 返回的消费者信息
            rcustomer['cur_pt'] = customer_info.get('cur_pt') or 0
            rcustomer['is_new'] = CardBase.is_new_card(
                    d['userid'], d['customer_id'], d['src'])
            rcustomer['diff_obtain_amt'] = max(rcard['obtain_amt']-d['txamt'],  0)
            rcustomer['card_id'] = customer_info.get('id')
            obtain_pts = min(d['txamt']/rcard['obtain_amt'],
                             rcard['obtain_limit'] or sys.maxint)
            rcustomer['obtain_pts'] = obtain_pts
            rcustomer['exchange'] = rcustomer['cur_pt'] / rcard['exchange_pt']

            # 插入pt_record
            # 插入失败即代表已领取过集点
            is_obtain = False
            try:
                # 若满足条件
                if not rcustomer['diff_obtain_amt']:
                    fields = [
                        'userid', 'customer_id', 'out_sn',
                        'txamt', 'total_amt'
                    ]
                    pt_indata = {field:d[field] for field in fields}
                    pt_indata['ctime'] = pt_indata['utime'] = now
                    pt_indata['activity_id'] = rcard['id']
                    pt_indata['type'] = PT_RECORD_GET
                    pt_indata['id'] = getid()
                    pt_indata['pts'] = obtain_pts

                    db.insert('pt_record', pt_indata)
            except:
                is_obtain= True

            # 若未领取集点
            if not is_obtain:
                try:
                    # 新集点卡消费者
                    if not customer_info:
                        m = {field:d[field] for field in
                            ['userid', 'customer_id', 'txamt', 'total_amt']}
                        if not obtain_pts:
                            m['txamt'] = m['total_amt'] = 0

                        rcustomer['card_id'] = m['id'] = getid()
                        m['activity_id'] = rcard['id']
                        m['ctime'] = m['utime'] = now
                        m['cur_pt'] = m['total_pt'] = obtain_pts

                        db.insert('member_pt',  m)

                    # 有集点的老客户
                    elif obtain_pts:
                        umwhere = {
                            'activity_id': rcard['id'],
                            'customer_id': d['customer_id']
                        }
                        umdata  = {
                            'txamt': DBFunc('txamt+%s'%d['txamt']),
                            'total_amt': DBFunc('total_amt+%s'%d['total_amt']),
                            'total_pt': DBFunc('total_pt+%d'%obtain_pts),
                            'cur_pt': DBFunc('cur_pt+%d'%obtain_pts),
                            'utime': now
                        }
                        db.update('member_pt', umdata, umwhere)

                except:
                    log.debug('更新消费者集点信息失败, %s' % traceback.format_exc())
                else:
                    rcustomer['cur_pt'] += obtain_pts
                    # 获取到集点, 更新活动统计信息
                    if obtain_pts:
                        try:
                            ucwhere = {'id': rcard['id']}
                            ucdata  = {
                                'total_pt':
                                    DBFunc('total_pt+%d'%obtain_pts),
                                'utime': now
                            }
                            db.update('card_actv', ucdata, ucwhere)
                        except:
                            log.debug(traceback.format_exc())

                    # 延后跟新member_tag
                    gevent.spawn(self.update, d['userid'], d['customer_id'])


            # 活动信息
            rcard['id'] = str(rcard['id'])
            rcard['start_time'] = str_to_tstamp(str(rcard['start_time']))
            rcard['expire_time'] = str_to_tstamp(str(rcard['expire_time']))

            # 消费者
            org_pt, now_pt = rcustomer['cur_pt']-obtain_pts, rcustomer['cur_pt']
            rcustomer['add_exchange'] = (now_pt/rcard['exchange_pt'] -
                                         org_pt/rcard['exchange_pt'])
            rcustomer['diff_exchange'] = max(
                rcard['exchange_pt'] - rcustomer['cur_pt']%rcard['exchange_pt'],
                0)

        return rcard, rcustomer, overdue

    _base_err = '获取集点失败'

    @check('check_ip')
    def POST(self):
        # 转化input参数
        d = {k:v.strip() for k, v in self.req.input().iteritems()}
        code = d.get('code') or ''
        try:
            data  = {}
            data['userid'], data['customer_id'], data['out_sn'], data['txamt'], data['total_amt'] = hids.decode(code)
            data['src'] = d.get('src') or 'query'
        except:
            raise ParamError('参数错误')

        data['out_sn'] = str(data['out_sn'])

        # query
        actv, customer, overdue = self._query(data)

        return success({
            'actv': actv or {},
            'customer_info': customer or {},
            'overdue': overdue
        })
