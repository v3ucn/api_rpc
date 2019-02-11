# -*- coding: utf-8 -*

import json
import config
import logging
from qfcommon.thriftclient.data_activiquer import activiquer
from qfcommon.web import core
from qfcommon.qfpay.qfresponse import success
from qfcommon.base.tools import thrift_callex

log = logging.getLogger()

class RankList(core.Handler):

    @classmethod
    def get_pop_list(cls):
        try:
            _pop_list = thrift_callex(config.DATAS_SERVERS, activiquer,
                                      "activiq",
                                      "actzqj",  "pop")

            pop_list = json.loads(_pop_list)

            log.info('pop_list: %s', pop_list)
            return pop_list
        except:
            log.exception('query datas: %s failure:', config.DATAS_SERVERS)

        return []

    @classmethod
    def get_pot_list(cls):
        try:
            _pot_list = thrift_callex(config.DATAS_SERVERS, activiquer,
                                      "activiq",
                                      "actzqj",  "pot")

            pot_list = json.loads(_pot_list)

            log.info('pot_list: %s', pot_list)
            return pot_list
        except:
            log.exception('query datas %s failure:', config.DATAS_SERVERS)

        return []


    def GET(self):
        result = dict(pop_list=[],
                      pot_list=[])

        result['pop_list'] = self.get_pop_list()
        result['pot_list'] = self.get_pot_list()

        return self.write(success(result))
