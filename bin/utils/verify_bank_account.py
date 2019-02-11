# encoding:utf-8

import config
import random
import logging
import urllib
import urllib2
import time
import json
from utils.date_api import tstamp_to_str
from utils.des import encrypt_3des, decrypt_3des, sign_, verify


def verify_account(path, appkey, userCode='CITI20170912174935', sysCode='CITIAPP20170912175227', **kwargs):

    info = {'code': '', 'codeDesc': ''}
    bankuser = kwargs.get('bankuser', '')
    bankaccount = kwargs.get('bankaccount', '')
    idCard = kwargs.get('idCard', '')

    #userCode 商户编号，即用户编号,唯一编号
    #sysCode 应用编号,唯一编号
    #appkey 平台提供的加密秘钥appkey

    #请求原因
    qryReason="银行卡鉴权认证"

    #用户自己生成的 随机8位数字或者字母
    vector = ''.join(random.choice('ABCDEFGHIJKLMNPQRSTUVWXYZ123456789') for _ in range(8))
    now = int(time.time())
    qryDate = tstamp_to_str(now, fmt='%Y%m%d')
    qryTime = tstamp_to_str(now, fmt='%H%M%S')

    #生成商户批次号：唯一，不超过20位（10位时间戳 + 10位随机数）
    stamp = ''.join(random.choice('ABCDEFGHIJKLMNPQRSTUVWXYZ123456789') for _ in range(10))
    qryBatchNo = str(now) + stamp
    condition = {'realName': bankuser, 'idCard': idCard, 'bankCard': bankaccount}
    header = {'qryBatchNo': qryBatchNo, 'userCode': userCode, 'sysCode': sysCode, 'qryReason': qryReason,
              'qryDate': qryDate, 'qryTime': qryTime, 'version': '2.0'}
    data = json.dumps({'header': header, 'condition': condition})
    logging.debug('请求参数: {0}'.format(data))

    #根据appkey, data, vector加密
    encrData = encrypt_3des(data, appkey, IV=vector)

    #根据请求报文进行签名, encrData signPrivateKey
    signature = sign_(encrData, config.signPrivateKey)

    params = {'condition': encrData, 'userCode': userCode, 'signature': signature,
              'vector': vector}
    params = urllib.urlencode(params)

    msg = '{0}?{1}'.format(path, params)
    logging.debug('[%sAPI]: %s' % ('auth', msg))
    begin_request = time.time()
    try:
        conn = urllib2.Request(path, data=params, headers={'Accept-Charset': 'utf-8'})
        res = urllib2.urlopen(conn).read()
        result = json.loads(res)
    except Exception, e:
        end_time = time.time()
        logging.error('[%sAPI] %s %s request use:%s s, error:%s' % ('auth', 'POST', msg, (end_time - begin_request), e))
        result = {}
        info['code'] = '-1'
        info['codeDesc'] = '鉴权失败'
        return info

    sign = result.get('signature', '')
    datas = result.get('contents', '')

    #验签及解密报文
    #验证加密内容报文的签名
    contents = verify(datas, sign, config.signPublicKey)

    # 先判断contents，如果contents不为空，那就解密，判断里面是否存在msg 或者data，如果data是空的，就直接取明文msg
    if contents:
        # 解密数据
        decrp_data = decrypt_3des(datas, appkey, IV=vector)
        result = json.loads(decrp_data) or {}
        if (result.has_key('data')):
            data = result.get('data', [])[0].get('record', [])[0]
            resCode = data.get('resCode', '')
            resDesc = data.get('resDesc', '')
            info['code'] = resCode
            info['codeDesc'] = resDesc

        else:
            msg = result.get('msg', {})
            resCode = msg.get('code', '')
            resDesc = msg.get('codeDesc', '')
            info['code'] = resCode
            info['codeDesc'] = resDesc
    else:
        msg = result.get('msg', {})
        resCode = msg.get('code', '')
        resDesc = msg.get('codeDesc', '')
        info['code'] = resCode
        info['codeDesc'] = resDesc

    return info
