# coding:utf-8

import re
import time
import json
import datetime

from functools import partial

from constants import DATE_FMT, DATETIME_FMT, MOBILE_PATTERN

re_mobile = re.compile(MOBILE_PATTERN)

def is_valid(s, func):
    try:
        func(s)
        return True
    except:
        return False

# 判断是否是日期
is_valid_date = partial(is_valid, func=lambda s: time.strptime(s, DATE_FMT))

# 判断是否是时间
is_valid_datetime = partial(is_valid, func=lambda s: time.strptime(s, DATETIME_FMT))

# 判断是否是数字
is_valid_num= partial(is_valid, func=float)

# 判断是否是整形
is_valid_int= partial(is_valid, func=int)

# 判断是否能json.dumps
is_valid_json= partial(is_valid, func=json.dumps)

# 判断是否datetime
def is_date_type(v):
    return isinstance(v, (datetime.date, datetime.time))

# 判断是否是手机号
def is_valid_mobile(v):
    return re_mobile.match(v)
