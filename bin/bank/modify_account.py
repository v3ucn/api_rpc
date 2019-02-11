# encoding:utf-8

import json
import logging
import traceback
import config
import time
from datetime import datetime
from runtime import redis_pool

from utils.base import BaseHandler
from utils.decorator import check
from utils.date_api import str_to_tstamp

from excepts import (
    ParamError, ThirdError, SessionError, UserError,
    DBError
)
from user.base import UserUtil, UserDefine, APPLY_STATE
from runtime import apcli, ms_redis_pool

from qfcommon.base.dbpool import (
    with_database, get_connection, get_connection_exception
)
from qfcommon.base.qfresponse import QFRET, error, success

from qfcommon.web.validator import Field, T_REG, T_INT, T_STR, T_FLOAT
from tool.base import get_head_banks, get_area_cities
from utils.verify_bank_account import verify_account


log = logging.getLogger()


class AccountTypeHandler(BaseHandler):
    '''
    获取账户类型信息
    '''

    @check('login')
    def GET(self):
        try:
            userid = int(self.user.userid)
            r = apcli.userprofile_by_id(userid)
            if not r:
                raise ParamError('未获取到账户类型')
            else:
                bankinfo = r.get('bankInfo', {})
                return self.write(success(
                    {
                    'banktype': bankinfo.get('banktype', ''),
                    'name': bankinfo.get('bankuser', '')
                    }))
        except:
            log.warn('error :%s' % traceback.format_exc())
            return self.write(error(QFRET.SERVERERR, respmsg=u"服务错误"))


class ChangeItemsHandler(BaseHandler):
    '''
    变更条款
    '''

    @check('login')
    def GET(self):

        return self.write(success({'items': config.ITEMS}))


class BankCardQuestionHandler(BaseHandler):
    '''
    银行卡说明
    '''

    @check('login')
    def GET(self):

        return self.write(success(config.QUESTIONS))


class VerifyAccountHandler(BaseHandler):
    '''
    鉴权账户接口
    '''

    _base_err = '鉴权银行卡失败'

    @check('login')
    def POST(self):

        info = {'code': '', 'codeDesc': ''}
        params = self.req.inputjson()
        banktype = params.get('banktype', '1')

        if banktype == '1':
            userid = int(self.user.userid)
            key = 'verify_account_{}'.format(str(userid))
            if redis_pool.exists(key):
                count = int(redis_pool.get(key))
                if count >= config.CHANGE_BANK_LIMIT:
                    info['codeDesc'] = config.CHANGE_LIMIT_TIP
                    return self.write(success(info))
                else:
                    redis_pool.incr(key)
            else:
                redis_pool.incr(key)
                start_time_stmp = int(time.time())
                end_time = datetime.now().strftime('%Y-%m-%d') + " 23:59:59"
                end_time_stmp = str_to_tstamp(end_time)
                expire_time = end_time_stmp - start_time_stmp
                redis_pool.expire(key, expire_time)

            bankuser = params.get('bankuser', '')
            bankaccount = params.get('bankaccount', '')
            r = apcli.userprofile_by_id(userid)
            if not r:
                raise ParamError('获取用户信息失败')
            else:
                idCard = r.get('user', {}).get('idnumber', '')
                result = verify_account(config.PATH, config.APPKEY, userCode="CITI20170912174935",
                                        sysCode="CITIAPP20170912175227", bankuser=bankuser, bankaccount=bankaccount,
                                        idCard=idCard)
                return self.write(success(result))
        else:
            return self.write(success(info))


class ChangeAccountHandler(BaseHandler):
    '''
    更改账户接口
    '''
    fields = [
        Field('banktype', isnull=False),
        Field('bankuser', isnull=False),
        Field('bankaccount', isnull=False),
        Field('headbankname', isnull=False),
        Field('bankname', isnull=False),
        Field('bankprovince', isnull=False),
        Field('bankcity', isnull=False)
    ]

    @check('login')
    def POST(self):
        try:
            params = self.req.inputjson()
            banktype = params.get('banktype', '')
            bankuser = params.get('bankuser', '')
            bankaccount = params.get('bankaccount', '')
            headbankname = params.get('headbankname', '')
            bankname = params.get('bankname', '')
            brchbank_code = params.get('brchbank_code', '')
            bankprovince = params.get('bankprovince', '')
            bankcity = params.get('bankcity', '')
            img_name = params.get('img_name', '')
            img_type = params.get('img_type', '')
            userid = int(self.user.userid)
            value = {'userid':userid, 'banktype': banktype, 'bankuser': bankuser,
                      'bankaccount': bankaccount, 'headbankname': headbankname, 'brchbank_code':brchbank_code, 'bankname': bankname,
                      'bankprovince': bankprovince, 'bankcity': bankcity, 'applyuser': userid,
                      'applytype': 5, 'modifytime': datetime.now(), 'create_time': datetime.now(), 'status': UserDefine.BANK_APPLY_WAIT,
                      'sync_tl_status': UserDefine.BANK_SYNC_NO}
            value['operatorgroup'] = json.dumps(config.OPERATE_GROUP)

            with get_connection('qf_mis') as db:
                db.insert('bankchange_apply', value)
                where = {'userid': userid}
                if img_name:
                    apy = db.select_one('bankchange_apply', where=where,
                            other='order by modifytime desc') or {}
                    id = apy.get('id', 0)
                    if img_type == '1':
                        img_type = 'BANK_CARD'
                    if img_type == '2':
                        img_type = 'OPEN_LICENSE'
                    db.insert('bankchange_apply_img',
                                   values={'change_apply_id': int(id), 'img': img_name,
                                    'img_type': img_type, 'created': datetime.now(), 'updated': datetime.now()})

            return self.write(success({'message': '申请提交成功，请耐心等待审核结果'}))
        except:
            log.warn('error :%s' % traceback.format_exc())
            return self.write(error(QFRET.SERVERERR, respmsg=u"服务错误"))


class BankInfoHandler(BaseHandler):
    '''
    获取用户银行卡信息
    '''

    def del_cardno(self, cardno):
        len_cardno = len(cardno)
        if len_cardno < 4:
            return cardno[-4:]
        elif len_cardno < 10:
            return '*' * (len_cardno-4)+cardno[-4:]
        else:
            return cardno[:6]+ '*'*(len_cardno-10) + cardno[-4:]

    def _resolve(self, bankinfo):
        b = {k: v or '' for k, v in bankinfo.iteritems()}
        return {
            'cardno': self.del_cardno(b['bankaccount']),
            'name': b['bankuser'],
            'bank_name': b['headbankname'],
            'icon': config.BANK_ICONS.get(bankinfo['headbankname'], config.DEFAULT_BANK_ICON)
        }

    def _get_audit_info(self, userid):
        def get_audit_memo(memo):
            try:
                data = json.loads(memo)['data']
                ret = sorted(data, key=lambda d:d['time'])[-1]['memo']
            except:
                return None
            return ret

        result = {}
        show_button = True
        with get_connection('qf_mis') as db:
            where = {'userid' : userid, 'modifytime' : ('>=', config.BANK_APPLY_ONLINE_TIME)}
            apy = db.select_one('bankchange_apply', where=where,
                        other='order by id desc') or {}
        with get_connection('qf_settle') as db:
            debit_pay = db.select_one('debit_paychnl', where={'userid': userid},
                        other='order by id desc') or {}

        tips = config.BANK_UPDATE_TIPS
        # 获取审核信息
        with get_connection('qf_mis') as db:
            audit_state = db.select_one('apply', where={'user': userid}, fields='user, state') or {}
        if audit_state:
            state = audit_state.get('state', '')
            if state != APPLY_STATE.get("pass"):
                result['show_button'] = False
                return result
        # 未提交过信息
        if not apy:
            result['show_button'] = show_button
            #退票处理
            if debit_pay.get('status', '') == 3:
                result['title'] = tips['debit_back']['title']
                result['subtitle'] = tips['debit_back']['subtitle']
                result['remit_back'] = 1
            return result

        if (apy['status'] == UserDefine.BANK_APPLY_SUCC and
            apy['sync_tl_status'] == UserDefine.BANK_SYNC_SUCC):
            # 审核通过
            result['state'] = UserDefine.BANK_APPLY_STATE_SUCC
            success = {
                'title': tips['success']['title'],
                'subtitle': tips['success']['subtitle'].format(
                    apy['modifytime'].strftime('%Y年%m月%d日'))

            }
            result.update(success)
            result['content'] = []
            result['show_button'] = show_button
            return result

        apy['bankaccount'] = apy['bankaccount'][-4:]
        # 审核关闭 或者 银行反馈失败
        if (apy['status'] == UserDefine.BANK_APPLY_CLOSED or
                apy['sync_tl_status'] == UserDefine.BANK_SYNC_FAIL):
            result['state'] = UserDefine.BANK_APPLY_STATE_FAIL
            result['show_button'] = show_button
            memo = get_audit_memo(apy['operatorinfo'])
            sync_memo = apy.get('sync_memo', '')
            result['title'] = tips['auditing']['title'].format(**apy)
            result['subtitle'] = tips['auditing']['subtitle']
            info = [{'name': tips['submit'], 'time': apy['create_time'].strftime('%Y年%m月%d日 %H:%M:%S') if apy['create_time'] else ''}]
            #state 1.审核中 2.审核成功 3.审核失败
            #风控审核失败
            if apy['status'] == UserDefine.BANK_APPLY_CLOSED:
                info.append({'name': tips['risk_audit'], 'time': '', 'state': 3, 'memo': memo, 'st_title': tips['audit_fail']})
                info.append({'name': tips['bank_change'], 'time': '',  'memo': tips['audit_memo2']})
                result['process'] = 2

            #风控审核通过
            if apy['status'] == UserDefine.BANK_APPLY_SUCC:
                info.append({'name': tips['risk_audit'], 'time': '', 'state': 2, 'memo': '', 'st_title': tips['audit_success']})
                result['process'] = 3
                #银行变更中， 银行卡未同步
                if apy['sync_tl_status'] == UserDefine.BANK_SYNC_NO:
                    #银行信息同步中，时间和memo无法获取
                    info.append({'name': tips['bank_change'], 'time': '', 'state': 1, 'memo': tips['audit_memo1'], 'st_title': tips['sync_ing']})
                #银行同步失败
                else:
                    info.append({'name': tips['bank_change'], 'time': '', 'state': 3, 'memo': sync_memo, 'st_title': tips['sync_fail']})

            result['content'] = info

        # 审核中
        else:
            result['state'] = UserDefine.BANK_APPLY_STATE_ING
            result['title'] = tips['auditing']['title'].format(**apy)
            result['subtitle'] = tips['auditing']['subtitle']
            result['show_button'] = False
            info = [{'name': tips['submit'], 'time': apy['create_time'].strftime('%Y年%m月%d日 %H:%M:%S') if apy['create_time'] else ''}]
            #风控审核成功
            if apy['status'] == UserDefine.BANK_APPLY_SUCC:
                info.append({'name': tips['risk_audit'], 'time': '', 'state': 2, 'memo': '', 'st_title': tips['audit_success']})
                info.append({'name': tips['bank_change'], 'time': '', 'state': 1, 'memo': tips['audit_memo1'], 'st_title': tips['sync_ing']})
                result['process'] = 3
            #风控审核中
            else:
                info.append({'name': tips['risk_audit'], 'time': '', 'state': 1, 'memo': tips['audit_memo1'], 'st_title': tips['audit_ing']})
                info.append({'name': tips['bank_change'], 'time': '', 'memo': tips['audit_memo2']})
                result['process'] = 2

            result['content'] = info
        #商户提交了申请,且被银行退票时,优先展示审核状态
        if not result:
            result['show_button'] = show_button
            #退票处理
            if debit_pay.get('status', '') == 3:
                result['title'] = tips['debit_back']['title']
                result['subtitle'] = tips['debit_back']['subtitle']
                result['remit_back'] = 1

        return result

    _base_err = '获取银行卡信息失败'

    @check('login')
    def GET(self):
        userid = int(self.user.userid)
        r = apcli.userprofile_by_id(userid)
        if not r:
            raise ParamError('未获取到银行卡信息')

        return self.write(success({
            'bankinfo': self._resolve(r['bankInfo']),
            'audit_info': self._get_audit_info(userid)}))


class ProvinceCityHandler(BaseHandler):
    '''
    省市接口，部分渠道不可更改省
    '''

    @check('login')
    def GET(self):

        userid = int(self.user.userid)
        groupid = self.get_groupid()
        r = apcli.userprofile_by_id(userid)
        if not r:
            raise ParamError('未获取到店铺所在省')
        user_province = r.get('user', {}).get('province', '')

        if groupid in config.FORBID_MODIFY_PROVINCE_GROUP:
            with get_connection_exception('qf_mis') as db:
                # 取出地区id
                area = db.select_one('tools_area', where={'area_name': user_province}, fields='id, area_no')
                if not area:
                    raise ParamError('该省不存在')

            # 取出城市列表
            fields = 'city_no, city_name'
            where = {'area_id': int(area['id']), 'city_display': 1}
            r = db.select('tools_areacity', where=where, fields=fields) or []

            cities = [{'cityid': i['city_no'], 'cityname':i['city_name']} for i in r]
            return self.write(success({'records': [{'cities': cities, 'areaid': area['area_no'], 'areaname': user_province}]}))
        else:
            area_cities = get_area_cities() or {}
            records = area_cities.values()
            records.sort(key=lambda k: (k.get('areaid', 0)))
            return self.write(success({'records': records}))
