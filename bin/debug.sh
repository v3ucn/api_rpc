#!/bin/bash
#/home/qfpay/python/bin/python server.py debug $1
python server.py debug $1
#gunicorn -c /Users/yyk/work/mchnt_api/conf/gunicorn_setting.py server:app
#/home/qfpay/python/bin/watchmedo auto-restart -d . -p "*.py" /home/qfpay/python/bin/python server.py debug $1
