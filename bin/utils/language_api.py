# encoding:utf-8
'''
语言常量
'''

import types
import logging
import json
import config
import traceback

from runtime import qfcache
from .tools import decode_from_utf8

from qfcommon.base.dbpool import get_connection

log = logging.getLogger()


## 获取常量
def load_constants(constants=None):
    cons = None
    with get_connection('qf_mchnt') as db:
        cons = db.select(
            table= 'language_constant',
            where= {
                'status' : 1,
                'src': getattr(config, 'CONSTANTS_SRC', 'mchnt_api'
            )},
            fields= 'code, value'
        )
    if not cons: return

    ret = {}
    for con in cons:
        try:
            ret[con['code']] = json.loads(con['value'])
        except:
            ret[con['code']] = con['value']
    return ret

qfcache.set_value(
    'language_constant', None, load_constants,
    getattr(config, 'CONSTANTS_CACHE', 3600)
)

def get_constant(code=None, language=None, default_self=True):
    ''' 返回常量

    如果code为空, 返回所有的常量,
    否则返回指定的常量

    '''
    default = code if default_self else None

    cons = qfcache.get_data('language_constant')
    if not code:
        return cons

    try:
        code = decode_from_utf8(code)
        if not cons or code not in cons:
            return default
        else:
            if isinstance(cons[code], types.DictType) and language:
                return cons[code].get(language, default)
            else:
                return cons[code]
    except:
        log.warn(traceback.format_exc())
        return default
