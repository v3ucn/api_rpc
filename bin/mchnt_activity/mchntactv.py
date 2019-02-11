#coding:utf-8


import os, sys
import json
import uuid
import traceback
import config
import logging
from StringIO import StringIO
import time
import datetime
import random

from PIL import ImageDraw
from PIL import ImageFont
from PIL import Image

from decorator import check_login
from qfcommon.qfpay.apolloclient import Apollo
from qfcommon.base.qfresponse import QFRET, error, success
from qfcommon.base.dbpool import with_database, get_connection
from qfcommon.library import mail
import util
from util import get_app_info, get_services
from qfcommon.base.qfresponse import success
from qfcommon.web import core
import constants

log = logging.getLogger()

ACTV_NO = 1 # 无活动
ACTV_NOACTVID = 2 # 未传入活动ID
ACTV_NODATA = 3 # 无活动数据
ACTV_GENPICERR = 4 # 生成缩略图失败
ACTV_NOTJOIN = 5 # 未参加活动
ACTV_INSERTERR = 6  # 参加活动失败
ACTV_NOEMAIL = 7  # 邮箱为空

def GenPic(ori_pic_path, text, font_name, font_size):
    '''
    ori_pic_path: 背景图片地址
    text: 写入图片的文字
    font_name: 字体名称
    font_size: 字体大小
    '''
    im = Image.open(ori_pic_path)

    # 使用字体路径加载字体,
    font_path = config.RESOURCE_PATH+"SimHei.ttf"
    font = ImageFont.truetype(font_path, 30)
    draw = ImageDraw.Draw(im)

    if isinstance(text, str):
        text = unicode(text, 'utf-8')
    text = text.replace(u'（', u'(').replace(u"）", u')')

    if len(text) > 15:
        text = text[:15]+u'...'  #取15个字符
    real_font_size = font.getsize(text)
    img_size = im.size

    font_location_x = img_size[0]/2 - real_font_size[0]/2
    font_location = (font_location_x, 105)
    simg = StringIO()

    try:
        draw.text(font_location, text, font=font, fill="#141c39")
        im.save(simg, "jpeg")
        try:
            im.close()
        except:
            log.warn("image close error, {}".format(traceback.format_exc()))
        del im
    except:
        log.warn("draw pic error:{}".format(traceback.format_exc()))
        return
    simg.seek(0)
    filename = str(uuid.uuid1())+".jpg"
    try:
        url = util.qiniu_upload(simg.read(), 'near', filename)
        if not url:
            log.warn("upload error")
        return url
    except:
        log.warn("upload pic error:{}".format(traceback.format_exc()))

class MchntList(core.Handler):
    @check_login
    def GET(self):
        params = self.req.input()
        with get_connection('qf_mchnt') as db:
            where = {"status": 1}
            other = "order by activityid"
            db_data = db.select('mchnt_activity', where=where, other=other)

        if not db_data:
            return self.write(error(ACTV_NO, respmsg="无活动"))

        actv_list = []
        for actv in db_data:
            actv_info = {}
            try:
                default_count = int(json.loads(actv.get('config_info')).get('default_count') or '663')
            except:
                default_count = 663
            end_time = actv.get('end_time')
            if end_time < datetime.datetime.now():
                actv_info['is_end'] = constants.ACTV_OVERDUE
            else:
                actv_info['is_end'] = constants.ACTV_AVAILABLE
            actv_info['joined_count'] = default_count
            actv_info['activity_id'] = actv.get('activityid')
            actv_info['start_time'] = actv['start_time']
            actv_info['end_time'] = actv['end_time']            
            actv_list.append(actv_info)

        with get_connection('qf_mchnt') as db:
            sql = "select count(id) as cnt, activityid from mchnt_sendrecord group by activityid"
            joined_data = db.query(sql)

        joined_dict = {}
        for tmp in joined_data:
            activity_id = tmp.get('activityid')
            joined_dict[activity_id] =  tmp.get('cnt')

        for actv in actv_list:
            activity_id = actv.get('activity_id')
            actv['joined_count'] += joined_dict.get(activity_id, 0)
        ret_data = {'actv_list': actv_list}
        ret_data['current_datetime'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return self.write(success(data=ret_data))

class ActvInfo(core.Handler):
    @check_login
    def GET(self):
        params = self.req.input()
        actv_id = params.get('activity_id', '')
        if not actv_id:
            return self.write(error(ACTV_NOACTVID, respmsg="请传入活动id"))

        with get_connection('qf_mchnt') as db:
            where = {'activityid': actv_id, 'status': 1}
            db_data = db.select_one('mchnt_activity',where=where)
        ret_data = {}
        if not db_data:
            return self.write(error(ACTV_NODATA, respmsg="活动数据不存在"))
        ret_data['pic_url'] = db_data.get('bg_url_small', '')
        end_time = db_data.get('end_time', 0)
        if end_time < datetime.datetime.now():
            ret_data['is_end'] = constants.ACTV_OVERDUE
        else:
            ret_data['is_end'] = constants.ACTV_AVAILABLE
        return self.write(success(data=ret_data))

class PrevSee(core.Handler):
    def _make_small_image(self, actv_id, shop_name):
        with get_connection('qf_mchnt') as db:
            actv_info = db.select_one("mchnt_activity", where={"activityid": actv_id})
            # 如果有预览的图， 则直接返回
            location = json.loads(actv_info.get('smallimg_location'))
            preview_image_url = location.get('preview_image_url', None)
            log.info('get preview_image_url: %s', preview_image_url)
            return preview_image_url
                
            
        pic_url = ''
        if actv_info:
            config_data = json.loads(actv_info.get('smallimg_location'))
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
        return pic_url

    @check_login
    def POST(self):
        self.set_headers({'Access-Control-Allow-Origin':'http://wx.qfpay.com'})
        self.set_headers({'Access-Control-Allow-Credentials':'true'})
        params = self.req.input()
        actv_id = params.get('activity_id', '')

        if not actv_id:
            return self.write(error(ACTV_NOACTVID, respmsg="请传入活动ID"))

        try:
            userinfo = Apollo(config.APOLLO_SERVERS).user_by_id(self.user.userid)
            log.warn("CALL Apollo RET:".format(userinfo))
            if not userinfo:
                return self.write(error(QFRET.DATAERR, respmsg="获取用户信息失败"))
        except:
            return self.write(error(QFRET.DATAERR, respmsg="获取用户信息失败"))

        mchnt_id = userinfo.get('uid', 0)
        if not mchnt_id:
            log.warn("GET mchnt_id None")
            return self.write(error(QFRET.DATAERR, respmsg="获取用户ID失败"))

        shop_name = userinfo.get('shopname', '')

        with get_connection('qf_mchnt') as db:
            actv_data = db.select_one('mchnt_activity', where={"activityid": actv_id})

        if not actv_data:
            return self.write(error(ACTV_NODATA, respmsg="活动数据不存在"))
        is_end = 1 if actv_data.get('end_time', 0) < datetime.datetime.now() else 0

        with get_connection('qf_mchnt') as db:
            where = {"mchntid": mchnt_id, "activityid": actv_id, "status": 1}
            db_data = db.select_one('mchnt_activityrecord', where=where)

        if not db_data:  # 未参加活动, 插入数据库
            values={"mchntid": mchnt_id, "activityid": actv_id, 'ctime': int(time.time()),
                    "pic_url_bigger":"", "pic_url_middle": "", "status": 1,
                    "shop_name": shop_name}
            ret = db.insert('mchnt_activityrecord', values)
            if ret < 1:  # 插入失败
                return self.write(error(ACTV_INSERTERR, respmsg="参见活动时插入数据失败"))
            log.info("insert to database result={ret}, value={value}".format(ret=ret, value=values))
        with get_connection('qf_mchnt') as db:
            db_data = db.select_one('mchnt_activityrecord', where=where)
        # 已经有数据
        pic_url = db_data.get('pic_url_middle', '')
        if not pic_url:  # 上传图片
            pic_url = self._make_small_image(actv_id, shop_name)

        with get_connection('qf_mchnt') as db:
            value={"pic_url_middle": pic_url}
            update_ret = db.update("mchnt_activityrecord",value, where=where)
            log.info("update result={ret}, value={value}".format(ret=update_ret, value=value))
        ret_data = {'pic_url': pic_url, 'is_end': is_end}
        return self.write(success(data=ret_data))

class Sendmail(core.Handler):
    @check_login
    def POST(self):
        self.set_headers({'Access-Control-Allow-Origin':'http://wx.qfpay.com'})
        self.set_headers({'Access-Control-Allow-Credentials':'true'})
        params = self.req.input()
        actv_id = params.get('activity_id', '')
        to_email = params.get('email', '')

        if not actv_id:
            return self.write(error(ACTV_NOACTVID, respmsg="请传入活动ID"))

        if not to_email:
            return self.write(error(ACTV_NOEMAIL, respmsg="请输入邮件地址"))

        try:
            userinfo = Apollo(config.APOLLO_SERVERS).user_by_id(self.user.userid)
            if not userinfo:
                return self.write(error(QFRET.DATAERR, respmsg="获取用户信息失败"))
        except:
            return self.write(error(QFRET.DATAERR, respmsg="获取用户信息失败"))

        mchnt_id = userinfo.get('uid', 0)
        if not mchnt_id:
            log.error("无法获取到商户的id")
            return self.write(error(QFRET.DATAERR, respmsg="获取用户ID失败"))

        with get_connection("qf_mchnt") as db:
            where = {'mchntid': mchnt_id, 'status': 1, 'activityid': actv_id}
            joined_data = db.select_one('mchnt_activityrecord', where=where)
        if not joined_data:
            return self.write(error(ACTV_NOTJOIN, respmsg="还未参加活动"))
        pic_url_bigger = joined_data.get('pic_url_bigger', '')
        send_status = 0
        if pic_url_bigger:
            with get_connection("qf_mchnt") as db:
                where = {"activityid": actv_id}
                actv_info = db.select_one('mchnt_activity', where)
            if actv_info:
                email_content = actv_info.get('email_content')
                email_title = actv_info.get('email_title')
                send_status = self._sendmail(pic_url_bigger, 'post_noreply@qfpay.com',to_email, email_title, email_content)
        values = {"mchntid": mchnt_id, "email": to_email, 'status': send_status, 'content':'',
                  "ctime":int(time.time()), "activityid": actv_id}
        with get_connection('qf_mchnt') as db:
            ret = db.insert('mchnt_sendrecord', values)
        return self.write(success(data={}))

    def _sendmail(self, pic_url, from_email, to_email, email_title, email_content):
        email_content = email_content.format(pic_url=pic_url)
        sendmail_list = [('post_noreply@qfpay.com', 'QFpost123')]
        send_mail_info = random.choice(sendmail_list)
        send_ret = 0
        try:
            m = mail.MailMessage(email_title,from_email, to_email, email_content)
            sender = mail.MailSender('smtp.exmail.qq.com', send_mail_info[0], send_mail_info[1])
            send_status = sender.send(m)
            if send_status:
                send_ret = constants.SEND_MAIL_OK
            else:
                send_ret = constants.SEND_MAIL_FAIL
        except:
            send_ret = constants.SEND_MAIL_FAIL
            log.warn('send mail error, errmsg:{}'.format(traceback.extract_stack()))
        return send_ret
