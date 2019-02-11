# encoding:utf-8

import config
import logging
import hashlib
import traceback
import time
log = logging.getLogger()
import json

from utils.base import BaseHandler
from qfcommon.base.dbpool import with_database
from utils.tools import unicode_to_utf8


class ReceiptInfo(BaseHandler):
    '''
    获取小票数据
    '''

    @with_database('qf_mchnt')
    def POST(self):
        try:
            params = self.req.inputjson()
            device_id = params.get('device_id', '')
            mchnt_id = params.get('mch_id', '')
            content = params.get('content', '')
            receiptId = params.get('receiptId', '')
            sign = params.get('sign', '')
            filter = ['device_id', 'mch_id', 'content', 'receiptId', 'nonce_str']
            filter_dict = {k: v for k, v in params.items() if k in filter}
            sort_dict = sorted(filter_dict.iteritems(), key=lambda d: d[0])
            string = '&'.join(['{0}={1}'.format(k, unicode_to_utf8(v)) for (k, v) in sort_dict if v not in ['', None]])
            string = string + '&key={key}'.format(key=config.RECEIPT_DATA_KEY)
            sign_string = hashlib.md5(string).hexdigest().upper()
            now = int(time.time())
            if sign_string == sign:
                a = self.db.insert('receipt_data',
                     values={'device_id': device_id, 'mchnt_id': mchnt_id,
                     'content': content, 'receipt_id': receiptId, 'ctime': now, 'utime': now})
                return self.write(json.dumps({'code': 'SUCCESS', 'msg': '成功'}))

            else:
                return self.write(json.dumps({'code': 'FAIL', 'msg': '签名失败'}))

        except Exception,e:
            log.warn('error :%s' % traceback.format_exc())
            return self.write(json.dumps({'code': 'FAIL', 'msg': '服务错误'}))
