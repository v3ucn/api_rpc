# encoding:utf-8

import logging
import traceback
import config
import time

from utils.base import BaseHandler
from utils.decorator import check
from util import hids
from excepts import ParamError

from qfcommon.base.dbpool import (
    with_database, get_connection, get_connection_exception
)
from qfcommon.base.qfresponse import QFRET, error, success

from qfcommon.web.validator import Field, T_REG, T_INT, T_STR, T_FLOAT
from utils.decorator import with_customer
from util import (hids, get_qd_conf_value)

log = logging.getLogger()


class AddInvoice(BaseHandler):
    '''
    添加发票信息
    '''

    _validator_fields = [
        Field('userid', isnull=False),
        Field('title', isnull=False),
        Field('taxNumber', isnull=False),
        Field('companyAddress', isnull=False),
        Field('telephone', isnull=False),
        Field('bankName', isnull=False),
        Field('bankAccount', isnull=False),
    ]

    # @check('validator')
    @with_customer
    def POST(self):
        try:

            if not self.customer.is_login():
                return self.write(error(QFRET.LOGINERR, resperr="user not login", respmsg="用户未登陆"))
            params = self.req.input()
            userid = params.get('userid', '')
            try:
                userid = hids.decode(userid)[0]
            except:
                raise ParamError("商户id错误")
            customer_id = self.customer.customer_id
            title = params.get('title', '')
            tax_no = params.get('taxNumber', '')

            address = params.get('companyAddress', '')
            phone = params.get('telephone', '')
            bank_name = params.get('bankName', '')
            bank_num = params.get('bankAccount', '')

            now = int(time.time())
            values = {'utime': now, 'ctime': now}

            values['userid'] = userid
            values['customer_id'] = customer_id
            values['title'] = title
            values['tax_no'] = tax_no
            values['address'] = address
            values['telephone'] = phone
            values['bank_name'] = bank_name
            values['bank_num'] = bank_num
            with get_connection('qf_mchnt') as db:
                db.insert('invoices', values=values)

            return self.write(success({}))

        except:
            log.warn('error :%s' % traceback.format_exc())
            return self.write(error(QFRET.SERVERERR, respmsg='内部错误'))


class InvoiceList(BaseHandler):
    '''
    发票信息
    '''

    @check('login')
    def GET(self):
        try:

            userid = int(self.user.userid)
            results = []
            with get_connection('qf_mchnt') as db:
                invoices = db.select(table='invoices', where={'userid': userid},
                                     other='order by ctime desc limit 5') or []

            for i in invoices:
                tmp = {}
                tmp['title'] = i.get('title', '')
                tmp['tax_no'] = i.get('tax_no', '')
                tmp['address'] = i.get('address', '')
                tmp['telephone'] = i.get('telephone', '')
                tmp['bank_name'] = i.get('bank_name', '')
                tmp['bank_num'] = i.get('bank_num', '')
                results.append(tmp)

            return self.write(success(data=results))

        except:
            log.warn('error :%s' % traceback.format_exc())
            return self.write(error(QFRET.SERVERERR, respmsg='内部错误'))


class GetInvoiceQrcode(BaseHandler):
    '''
    获取用户发票二维码
    返回二维码字符串
    '''

    _base_err = '获取用户二维码失败'

    @check('login')
    def GET(self):

        userid = int(self.user.userid)
        groupid = self.get_groupid(userid)
        # 获取图片信息
        img_conf_qrcode = get_qd_conf_value(
            mode=None, key='qrcode', groupid=groupid
        ) or {}
        invoice_img = img_conf_qrcode.get('invoice_img', {})
        qrcode = img_conf_qrcode.get('invoice_qrcode', '')
        if invoice_img and qrcode:
            img_conf = invoice_img.get('img_conf', {})
            url = qrcode % hids.encode(userid)
        else:
            if groupid in config.BAIPAI_GROUPIDS:
                img_conf = config.BAIPAI_INVOICE_IMG_DEFAULT.get('img_conf')
                url = config.BAIPAI_INVOICE_QRCODE_URL % hids.encode(userid)
            else:
                img_conf = config.INVOICE_IMG_DEFAULT.get('img_conf')
                url = config.INVOICE_QRCODE_URL % hids.encode(userid)
        ret = {}
        ret['img_conf'] = img_conf
        ret['qrcode'] = url

        return self.write(success(data=ret))

