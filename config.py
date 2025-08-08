import re
from os import environ,getenv

id_pattern = re.compile(r'^.\d+$')
def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default
      
# Telegram API credentials
API_ID = int(environ.get('API_ID', '904789'))
API_HASH = environ.get('API_HASH', '2262ef67ced426b9eea57867b11666a1')
BOT_TOKEN = environ.get('BOT_TOKEN', "")
DATABASE_URI_SESSIONS_F = environ.get('DATABASE_URI_SESSIONS_F', "")
LOG_CHANNEL_SESSIONS_FILES = int(environ.get('LOG_CHANNEL_SESSIONS_FILES', '-1002450886765'))

