# encoding:utf-8

import json

from qfcommon.qfpay import msgpassclient
from qfcommon.base import logger
log = logger.install('stdout')

data = json.dumps({
    "profile": {
        "nickname": "759\u963f\u4fe1\u5c4b"
    },
    "orig_trade": {
    },
    "channel": {
        "mchntnm": "wx370e5f2f9001f90b", "key3": "wx087a3fc3f3757766", "key2": "4a60e60111715e5942341860e54173f0", "key1": "", "termid": "1298257101", "mchntid": "10028073"
    },
    "trade": {
        "note": {
            "openid": "oMGYCj8pUA4nBk4oAx9-7iYDdFds",
            "trade_type": "NATIVE",
            "prepay_id": "wx201604151800380af5dc2f2c0059107670",
            "time_end": "20160415180109",
            "bank_type": "CFT",
            "sub_openid": "oYkCztztAhQhfP9X3DEHz0X9q5Jk",
            "cash_fee": "1",
            "transaction_id": "4000152001201604154872515237"
        },
        "sysdtm": "2016-04-15 18:00:36", "coupon_amt": "",
        "cardcd": "oYkCztztAhQhfP9X3DEHz0X9q5Jk",
        "cardcd": "test",
        "userid": "11", "opuid": "",
        "retcd": "0000", "longitude": "123.7869",
        "txamt": "1", "busicd": "800201",
        "coupon_code": "", "out_trade_no": "",
        "activity_id": "", "syssn": "20160415124500020003833746",
        "txcurrcd": "156", "latitude": "21.017927",
        "customer_id": "",
        "groupid": "10016"
    }
})

msgpassclient.publish('paycore.succ_trade', data)
