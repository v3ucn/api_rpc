# encoding:utf-8

import time
import datetime
import calendar

from valid import is_date_type
from excepts import ParamError
from constants import DT_FMT, DTM_FMT

# 两个日期相隔多少天
def str_diffdays(sDate, eDate, fmt='%Y-%m-%d'):
    return (datetime.datetime.strptime(eDate, fmt) -
            datetime.datetime.strptime(sDate, fmt)).days

# 将时间戳转化为字符串
def tstamp_to_str(stamp, fmt=DTM_FMT):
    return time.strftime(fmt, time.localtime(stamp))

# 将字符串的时间转换为时间戳
def str_to_tstamp(s, fmt=DTM_FMT):
    return int(time.mktime(time.strptime(s, fmt)))

def date_to_tstamp(dt):
    return int(time.mktime(dt.timetuple()))

def get_day_begin_ts():
    '''
    method: 获取当日0点时间戳
    '''
    return int(time.mktime(datetime.date.today().timetuple()))


# 获取相对时间
def future(st=None, years=0, months=0, weeks=0,
           days=0, hours=0, minutes=0, seconds=0,
           milliseconds=0, microseconds=0, fmt_type='date',
           fmt=DT_FMT):
    ''' 相对时间

    Params:
        st: 起始时间, datetime或者date类型
        years, months...: 时间, 负的为向前推算
        fmt_type: str,返回fmt字符串
                  timestamp,返回时间戳
                  date,返回datetime或者date类型
    '''
    st = st or datetime.datetime.now()
    if not is_date_type(st):
        raise ParamError('时间格式不正确')

    if seconds or minutes or hours or days or weeks:
        delta = datetime.timedelta(weeks=weeks, days=days, hours=hours,
                                   minutes=minutes, seconds=seconds,
                                   milliseconds=milliseconds,
                                   microseconds=microseconds)
        st += delta

    if months:
        addyears, months = divmod(months, 12)
        years += addyears
        if not (1 <= months + st.month <= 12):
            addyears, months = divmod(months + st.month, 12)
            months -= st.month
            years += addyears
    if months or years:
        year = st.year + years
        month = st.month + months
        try:
            st = st.replace(year=year, month=month)
        except ValueError:
            _, destination_days = calendar.monthrange(year, month)
            st = st.replace(year=year, month=month, day=destination_days)

    if fmt_type == 'str':
        return st.strftime(fmt)
    elif fmt_type == 'timestamp':
        return time.mktime(st.timetuple())
    else:
        return st

    return st
