# encoding:utf-8

import logging
import time
import re
import traceback
log = logging.getLogger()

from qfcommon.base.dbpool import with_database
from qfcommon.base.qfresponse import success

from utils.base import BaseHandler
from decorator import raise_excp
from excepts import ParamError, DBError
from constants import DTM_FMT, INTENT_COOP_TYPE, MOBILE_PATTERN
from util import getid


class AddIntentMchnt(BaseHandler):

    @with_database("qf_mchnt")
    @raise_excp("添加合作商户失败")
    def POST(self):

        params = {k.strip(): str(v).strip() for k, v in self.req.inputjson().items()}
        name = params.get("name", '')
        contact_mobile = params.get("contact_mobile", '')
        city = params.get("city", '')
        company = params.get('company', '')
        coop_type = params.get("coop_type", '1')  # 合作方式

        medium = params.get("medium", "")
        campaign = params.get("campaign", "")
        source = params.get("source", "")
        content = params.get("content", "")
        term = params.get("term", "")

        if not name or not contact_mobile or not city or not coop_type:
            raise ParamError("参数不能为空")
        try:
            coop_type = int(coop_type)
            if coop_type not in INTENT_COOP_TYPE:
                raise ParamError("coop_type参数错误")
        except:
            raise ParamError("coop_type参数错误")

        if not re.match(MOBILE_PATTERN, contact_mobile):
            raise ParamError("手机格式错误")

        curr_time = time.strftime(DTM_FMT)
        if self.db.select("intent_coopman", where={"contact_mobile": contact_mobile}, fields="id"):
            raise ParamError("此手机号已提交过")
        else:
            pri_id = getid()
            try:
                self.db.insert("intent_coopman", values={"id": pri_id,
                                                         "name": name,
                                                         "contact_mobile": contact_mobile,
                                                         "city": city,
                                                         "coop_type": coop_type,
                                                         "source": source,
                                                         "medium": medium,
                                                         "campaign": campaign,
                                                         "content": content,
                                                         "term": term,
                                                         "company": company,
                                                         "ctime": curr_time})
                return self.write(success(data={}))
            except:
                log.warning(traceback.format_exc())
                raise DBError("操作失败")


class QueryCount(BaseHandler):

    @with_database("qf_mchnt")
    @raise_excp("查询合作伙伴总数失败")
    def GET(self):

        try:
            r = self.db.select_one("intent_coopman", fields="count(contact_mobile) as count")
            count = r['count']
            return self.write(success(data={"count": count}))
        except:
            raise DBError("数据库查询出错")
