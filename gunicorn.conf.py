"""Conservative initial sizing; shared Redis is required in production."""
import os

bind = '0.0.0.0:' + os.getenv('PORT', '5000')
workers = 2
timeout = 120
accesslog = '-'
errorlog = '-'
# Do not log query strings, cookies or authorization headers.
access_log_format = '%(h)s %(m)s %(U)s %(s)s %(L)s'
# Do not trust arbitrary X-Forwarded-* headers; HTTPS cookies are explicit.
forwarded_allow_ips = ''
