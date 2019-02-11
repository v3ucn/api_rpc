# encoding:utf-8

import json

import config
from runtime import qfcache

from .tools import apcli_ex

from qfcommon.base.dbpool import get_connection

def load_qd_conf(qd_conf=None):
    qdconfs = None
    with get_connection('qf_mis') as db:
        qdconfs = db.select(
                table= 'qd_conf',
                where= {'status' : 1},
                fields= (
                    'qd_uid, name, wx_pub, protocol, qrcode,'
                    'csinfo, promotion_url, service, push, ext, '
                    'push'))

    if not qdconfs:
        return

    ret = {}
    load_fields = [
        'protocol', 'qrcode', 'csinfo', 'promotion_url',
        'service', 'ext', 'push'
    ]
    for conf in qdconfs:
        t = {i:conf[i] for i in ('name', 'qd_uid', 'wx_pub') }
        for field in load_fields:
            try:
                t[field] = json.loads(conf[field])
            except:
                t[field] = None
        ret[conf['qd_uid']] = t

    return ret
qfcache.set_value('qd_conf', None, load_qd_conf, 3600)

def get_qd_conf():
    return qfcache.get_data('qd_conf')

def get_qd_conf_value(userid=None, mode='coupon', key='promotion_url', **kw):
    '''获取物料的链接

    会区分渠道id返回url

    Args:
        userid: 商户userid.
        mode: coupon,红包的物料链接; card,集点的物料链接.
        key: qd_conf的key值
    '''
    def _get_default():
        '''获取默认值'''
        if 'default' in kw:
            return kw['default']
        try:
            default_key = kw.get('default_key', 0)
            if mode:
                return ((qd_confs[default_key].get(key) or {}).get(mode) or
                         kw.get('default_val', ''))
            else:
                return qd_confs[default_key].get(key)
        except:
            return None

    # qdconfs
    if 'qd_confs' in kw:
        qd_confs = kw['qd_confs']
    else:
        qd_confs = get_qd_conf()

    # 渠道id
    if 'groupid' in kw:
        groupid = kw['groupid']
    else:
        user = apcli_ex('findUserBriefById', int(userid))
        groupid = user.groupid if user else 0

    default = _get_default()
    if mode:
        if (groupid in qd_confs and key in qd_confs[groupid] and
            qd_confs[groupid][key]):
            return qd_confs[groupid][key].get(mode, default)
    else:
        if groupid in qd_confs:
            return qd_confs[groupid].get(key) or default

    return default

def get_qd_conf_value_ex(
        userid=None, mode=None, key=None, groupid=None,
        default=None):
    '''根据是否是直营返回值

    优先取渠道单独配置, 若渠道未配置:
    直营会取qd_conf中qd_uid为0的配置,
    非直营取qd_conf中qd_uid为1的配置
    '''
    return get_qd_conf_value(
            userid= userid, mode= mode,
            key= key, groupid= groupid,
            default_key= int(groupid not in config.QF_GROUPIDS),
            default_val= default)
