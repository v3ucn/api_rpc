# encoding: utf-8

import os
import sys
import uuid
import time
import random
import traceback
import types
import datetime
import urllib
import httplib
import logging
import json
import socket

from StringIO import StringIO
import xlwt
from qiniu import Auth, put_data
from PIL import ImageDraw
from PIL import ImageFont
from PIL import Image
import argparse


HOME = os.path.dirname(os.path.abspath(__file__))
PA_HOME = os.path.dirname(HOME)
sys.path.append(HOME)
sys.path.append(os.path.dirname(HOME))
sys.path.append(os.path.join(os.path.dirname(HOME), 'conf'))
sys.path.append(os.path.join(os.path.dirname(PA_HOME), 'conf'))

import config
import constants
from qfcommon.library import mail
from qfcommon.base import dbpool
from qfcommon.base import logger
from qfcommon.thriftclient.tool import Tool
from qfcommon.base.tools import thrift_callex
import util

dbpool.install(config.DATABASE)

def qiniu_upload(file_bytes, save_path):
    """七牛上传文件
    save_path 直接包含文件名，故此字段请在外部生成
    返回七牛云的存储路径 url
    """
    q = Auth(config.QINIU_ACCESS_KEY, config.QINIU_SECRET_KEY)
    token = q.upload_token('near', save_path)
    ret, info = put_data(token, save_path, file_bytes, check_crc=True)
    if not ret:
        log.warn("qiniu_upload method, ret is None")
        return None
    if info.exception:
        raise info.exception
    return 'http://near.m1img.com/' + ret['key']

def shorten_url(url, host="192.20.10.5:8028"):
    """
    获取短链
    外部访问需要host 为 qmm.la
    内网 10.4, 10.5, 10.6, 10.7 访问需要 192.20.10.5:8028
    """
    httpClient = None
    try:
        params = urllib.urlencode({'url': url})
        headers = {"Content-type": "application/x-www-form-urlencoded","Accept": "text/plain"}
        if host != "qmm.la":
            headers.update({"Host": "qmm.la"})
        httpClient = httplib.HTTPConnection("%s" % host, timeout=2)
        httpClient.request("POST", "/", params, headers)
        response = httpClient.getresponse()
        if response.status == 200:
            ret = response.read()
            retdata = json.loads(ret)
            respcd = retdata.get('respcd', '')
            if respcd != '0000':
                log.warn("GENSHORTURL ERROR, qmm.la respcd={0}, msg={1}".format(respcd, ret))
                return url
            shortcode = retdata.get('data', {}).get('shortcode', '')
            if not shortcode:
                log.warn("GENSHORTURL ERROR, return content='{}'".format(ret))
                return url
            short_url = 'http://qmm.la/' + shortcode
            return short_url
        else:
            log.warn("GENSHORTURL ERROR, response status={0}".format(response.status))
            return url
    except Exception, e:
        log.warn('获取短链服务失败,错误码：%s', e)
        return url
    finally:
        if httpClient:
            httpClient.close()

def real_genpic_upload(actv_id, shop_name):
    """
    生成大图并上传七牛云
    """
    with dbpool.get_connection_exception('qf_mchnt') as db:
        actv_info = db.select_one("mchnt_activity", where={"activityid": actv_id})
        # 如果有预览的图， 则直接返回
        location = json.loads(actv_info.get('bigimg_location'))
        preview_image_url = location.get('preview_image_url', None)
        log.info('get preview_image_url: %s', preview_image_url)
        return preview_image_url

    pic_url = ''
    if actv_info:
        if actv_info.get('end_time') < datetime.datetime.now():  # 过期数据不生成图片
            return
        config_data = json.loads(actv_info.get('bigimg_location'))
        bgimg_name = config_data.get('image_name')
        font_size = config_data.get('font_size')
        fill_color = config_data.get('fill_color')
        offset_x = int(config_data.get('offset_x'))
        offset_y = int(config_data.get('offset_y'))
        max_text_width = int(config_data.get('max_text_width'))

        text_location = (offset_x, offset_y, max_text_width)

        if bgimg_name and font_size and fill_color:
            bgimg_path = config.RESOURCE_PATH+bgimg_name

            pic_url = util.generate_image(bgimg_path, shop_name, font_size,
                                          fill_color, text_location)
            if pic_url:
                try:
                    #short_url = shorten_url(pic_url, host='qmm.la')
                    short_url = shorten_url(pic_url)
                    pic_url = short_url
                except:
                    log.warn("GEN SHORT URL ERR:{}".format(traceback.format_exc()))
    return pic_url

def real_sendmail(pic_url, from_email, to_email, actv_id, send_id):
    '''
    发送邮件
    '''
    send_ret = 0
    if not pic_url:
        return

    sendmail_list = [('post_noreply@qfpay.com', 'QFpost123')]
    send_mail_info = random.choice(sendmail_list)

    with dbpool.get_connection_exception('qf_mchnt') as db:
        actv_info = db.select_one("mchnt_activity", where={"activityid": actv_id})

    if actv_info:
        if actv_info.get('end_time') < datetime.datetime.now(): # 过期的活动不用发数据
            return
        email_content = actv_info.get('email_content').format(pic_url=pic_url)

        try:
            m = mail.MailMessage(actv_info.get('email_title'),from_email, to_email, email_content)
            sender = mail.MailSender('smtp.exmail.qq.com', send_mail_info[0], send_mail_info[1])
            send_status = sender.send(m)
            if send_status:
                send_ret = constants.SEND_MAIL_OK
            else:
                send_ret = constants.SEND_MAIL_FAIL
        except:
            send_ret = constants.SEND_MAIL_FAIL
            log.warn('send mail error, errmsg:{}'.format(traceback.format_exc()))
        time.sleep(1)
        if send_ret:
            update_value = {"status": send_ret}
            update_where = {"id": send_id}
            with dbpool.get_connection_exception('qf_mchnt') as db:
                db.update('mchnt_sendrecord', update_value, update_where)

def SendMail():
    from_email = "post_noreply@qfpay.com"

    with dbpool.get_connection_exception('qf_mchnt') as db:
        where = {"status": ('in', [0, 2])}
        datas = db.select('mchnt_sendrecord', where=where)
    log.info("will send data is: {}".format(datas))

    for d in datas:
        mchnt_id = d.get('mchntid')
        actv_id = d.get('activityid')
        send_where = {"mchntid": mchnt_id, "activityid": actv_id}
        with dbpool.get_connection_exception('qf_mchnt') as db:
            send_info = db.select_one('mchnt_activityrecord', where=send_where)

        if send_info:
            pic_url_bigger = send_info.get('pic_url_bigger')
            to_email = d.get('email', '')
            send_ret = real_sendmail(pic_url_bigger, from_email, to_email, actv_id, d.get('id'))
            log.info("send info = {0}, send_ret:{1}".format(send_info, send_ret))

def GenPic():
    with dbpool.get_connection_exception('qf_mchnt') as db:
        where = {"status":"1", "pic_url_bigger": ""}
        datas = db.select('mchnt_activityrecord', where=where)

    if not datas:
        log.info('no datas need gen pic')
        return

    activity_info = {}
    log.info("need gen pics data is = {}".format(datas))

    for d in datas:
        shop_name = d.get('shop_name', '')
        activity_id = d.get('activityid')

        if not shop_name:
            log.info('NOTGENPIC: data={0}'.format(d))
            continue

        try:
            pic_url = real_genpic_upload(activity_id, shop_name)
        except:
            log.info("GENPIC ERROR:{}".format(traceback.format_exc()))
            pic_url = ''
        if pic_url:
            update_value = {"pic_url_bigger": pic_url}
            update_where = {"mchntid": d.get('mchntid'), 'activityid':d.get('activityid')}
            with dbpool.get_connection_exception('qf_mchnt') as db:
                db.update('mchnt_activityrecord', update_value, where=update_where)

def set_style(name,height,bold=False):
    style = xlwt.XFStyle() # 初始化样式
    font = xlwt.Font() # 为样式创建字体
    font.name = name
    font.bold = bold
    font.color_index = 4
    font.height = height
    style.font = font
    return style

def SendStatistics():
    """
    发送统计邮件到相关人员
    """
    # 获取活动数据
    cur_time = int(time.time())
    where = {"end_time":(">=", cur_time), "status": 1}
    fields = ["activityid", "name", "email_title"]
    with dbpool.get_connection_exception('qf_mchnt') as db:
        actv_data = db.select('mchnt_activity', where=where, fields=fields)

    actv_dict = {}
    for actv in actv_data:
        actv_id = actv.get("activityid")
        actv_dict[actv_id] = actv

    if not actv_dict:
        return

    # 获取参与活动的商户信息
    mchnt_record_where = {"activityid":("in", actv_dict.keys())}
    mchnt_record_fields = ["mchntid", "shop_name", "pic_url_bigger", "activityid"]
    with dbpool.get_connection_exception("qf_mchnt") as db:
        record_data = db.select("mchnt_activityrecord", where=mchnt_record_where,
                                fields=mchnt_record_fields)

    if not record_data:
        return

    record_dict = {}
    for rec in record_data:
        actv_id = rec.get("activityid")
        mchnt_id = rec.get("mchntid")
        key = str(actv_id)+str(mchnt_id)
        record_dict[key] = rec

    # 获取邮件发送信息
    send_where = {"activityid":("in", actv_dict.keys())}
    send_fields = ["mchntid", "activityid", "utime"]
    with dbpool.get_connection_exception("qf_mchnt") as db:
        send_data = db.select("mchnt_sendrecord", where=send_where,
                              fields=send_fields)
    if not send_data:
        return

    send_dict = {}
    for s in send_data:
        actv_id = s.get("activityid")
        mchnt_id = s.get("mchntid")
        key = str(actv_id) + str(mchnt_id)
        record_info = record_dict.get(key)
        if not record_info:
            continue
        s["shop_name"] = record_info.get("shop_name", "")
        s["pic_url"] = record_info.get("pic_url_bigger", "")
        s["activity_name"] = actv_dict.get(actv_id).get("email_title")
        if key not in send_dict:
            send_dict[key] = s
            s["send_count"] = 1
        else:
            if s.get("utime") > send_dict[key]["utime"]:
                send_dict[key]["utime"] = s.get("utime")
            send_dict[key]["send_count"] += 1
    # 生成excel
    excel = _make_excel(send_dict, actv_data)
    content = '''
    hi all，
    附件是营销活动的海报发送数据统计
    请查收
    '''
    to_email = ["karen@qfpay.com", "xiaojinyi@qfpay.com", "shuqin@qfpay.com",
                "wunengbo@qfpay.com", "yuanyuan@qfpay.com"]
    for email in to_email:
        excel.seek(0)
        m = mail.MailMessage("营销活动海报发送数据统计", 'post_noreply@qfpay.com', email, content)
        file_name = time.strftime("%Y%m%d", time.localtime(time.time()))+".xls"
        m.append_data(excel.read(), attachname=file_name)
        sender = mail.MailSender('smtp.exmail.qq.com', 'post_noreply@qfpay.com', 'QFpost123')
        sender.send(m)
        time.sleep(1)


def _make_excel(email_data, actv_data):
    first_row = ["活动ID", "活动名称", "商户ID", "商户名称", "海报短连接", "发送次数", "最后一次发送时间"]
    header_style = set_style("Arial", 200, False)
    xls_file = xlwt.Workbook(encoding="utf-8")
    sheet_name_dict = {}
    idx = 0
    for actv in actv_data:
        actv_name = actv.get("email_title")
        sheet = xls_file.add_sheet(actv_name, cell_overwrite_ok=True)
        for i in xrange(len(first_row)):
            sheet.write(0, i, first_row[i], header_style)
        sheet_name_dict[actv_name] = {"idx": idx, "rows": 1}
        idx += 1

    for v in email_data.itervalues():
        shop_name = v.get("shop_name")
        actv_name = v.get("activity_name")
        idx = sheet_name_dict.get(actv_name, {}).get("idx")
        if idx is None:
            log.info("IDX ERROR, {0} NOT IN {1}".format(actv_name, sheet_name_dict))
            continue

        sheet = xls_file.get_sheet(idx)
        nrows = sheet_name_dict.get(actv_name, {}).get("rows")
        if not nrows:
            log.info("ROWS ERROR, {0} NOT IN {1}".format(actv_name, sheet_name_dict))
            continue

        sheet.write(nrows, 0, v.get("activityid", ""))
        sheet.write(nrows, 1, v.get("activity_name", ""))
        sheet.write(nrows, 2, v.get("mchntid", ""))
        sheet.write(nrows, 3, v.get("shop_name", ""))
        sheet.write(nrows, 4, v.get("pic_url", ""))
        sheet.write(nrows, 5, v.get("send_count", ""))
        last_send_time = v.get("utime").strftime("%Y-%m-%d %H:%M:%S")
        sheet.write(nrows, 6, last_send_time)
        sheet_name_dict[actv_name]["rows"] += 1

    xls_so = StringIO()
    xls_file.save(xls_so)
    return xls_so

def ConvertUrl():
    """
    将大图转换为qmm.la下的短链
    """
    with dbpool.get_connection_exception('qf_mchnt') as db:
        mchnt_fields = ['id', 'pic_url_bigger']
        activity_datas = db.select('mchnt_activityrecord', fields=mchnt_fields)

    update_list = []
    for d in activity_datas:
        url = d.get('pic_url_bigger')
        act_id = d.get('id')
        if 'qmm.la' in url:
            continue
        else:
            #short_url = shorten_url(url, host="qmm.la")
            short_url = shorten_url(url)
            if "qmm.la" in short_url:
                update_list.append({'url': short_url, 'id': act_id})

    if update_list:  # 更新数据
        log.warn("starting update url..., datas={}".format(update_list))
        with dbpool.get_connection_exception('qf_mchnt') as db2:
            for data in update_list:
                update_v = {"pic_url_bigger": data.get('url')}
                where = {"id": data.get('id')}
                db2.update('mchnt_activityrecord', update_v, where)
    else:
        log.info("no url need update")

def GeneratePicLocation(name="big"):
    if name == "big":
        config_data = {"offset_x": 1188,
                       "offset_y": 985,
                       "max_text_width": 3130,
                       "image_name": "big_shujia.jpg",
                       "font_name": "SimHei.ttf",
                       "font_size": 155,
                       "fill_color": '#faf7e6'}
        values = {"bigimg_location": json.dumps(config_data)}
    else:
        config_data = {"offset_x": 169,
                       "offset_y": 138,
                       "max_text_width": 437,
                       "image_name": "small_shujia.jpg",
                       "font_name": "SimHei.ttf",
                       "font_size": 26,
                       "fill_color": '#faf7e6'}
        values = {"smallimg_location": json.dumps(config_data)}

    with dbpool.get_connection_exception('qf_mchnt') as db:
        db.update('mchnt_activity', values, where={"activityid": 3})

if __name__ == '__main__':
    log = logger.install(config.LOGFILE)
    parser = argparse.ArgumentParser()

    parser.add_argument('-tg', '--target', help=u'操作类型',
                        choices=['genpic', 'sendmail', 'sendstatistics', 'converturl', 'generate'],
                        required=True)
    args = parser.parse_args()

    if args.target == 'genpic':  # 生成图片
        GenPic()
    elif args.target == 'sendmail':  # 发送邮件
        SendMail()
    elif args.target == 'sendstatistics':  # 发送统计信息
        SendStatistics()
    elif args.target == 'converturl':
        ConvertUrl()
    else:
        GeneratePicLocation('big')
        GeneratePicLocation("small")
