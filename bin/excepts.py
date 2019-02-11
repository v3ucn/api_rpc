# encoding:utf-8

from qfcommon.qfpay.qfresponse import QFRET

class MchntException(Exception):

    def __init__(self, errmsg, resperr=None, errcode=QFRET.PARAMERR):
        self.errmsg  = errmsg
        self.errcode = getattr(self, 'errcode', errcode)
        self.resperr = resperr or errmsg

    def __str__(self):
        return '[code:%s] errormsg:%s' % (self.errcode, self.errmsg)


class SessionError(MchntException):
    errcode = QFRET.SESSIONERR

class ParamError(MchntException):
    errcode = QFRET.PARAMERR

class ThirdError(MchntException):
    errcode = QFRET.THIRDERR

class DBError(MchntException):
    errcode = QFRET.DBERR

class CacheError(MchntException):
    errcode = QFRET.DATAERR

class ReqError(MchntException):
    errcode = QFRET.REQERR

class UserError(MchntException):
    errcode = QFRET.USERERR

class RoleError(MchntException):
    errcode = QFRET.ROLEERR

class MacError(MchntException):
    errcode = QFRET.MACERR
