# encoding:utf-8

import config
import logging
log = logging.getLogger()
import traceback

from utils.base import BaseHandler

from qfcommon.base.tools import ThriftClient
from qfcommon.thriftclient.wxcard import WXCard
from qfcommon.thriftclient.wxcard.ttypes import CardInterfaceActiveInfo, WXCardError
from qfcommon.base.qfresponse import error, success, QFRET


class InterfaceActive(BaseHandler):

    def POST(self):
        params = {k: str(v).strip() for k, v in self.req.input().iteritems()}
        card_id = params.get("card_id")
        encrypt_code = params.get("encrypt_code")
        openid = params.get("openid")

        client = ThriftClient(config.WXCARD_SERVERS, WXCard)
        client.raise_except = True
        info = CardInterfaceActiveInfo(
            card_id=card_id,
            encrypt_code=encrypt_code,
            openid=openid
        )
        try:
            client.call("card_interface_active", info, 0)
            return self.write(success(data={}))
        except WXCardError as e:
            log.debug(traceback.format_exc())
            return self.write(error(QFRET.THIRDERR, respmsg=e.respmsg))
