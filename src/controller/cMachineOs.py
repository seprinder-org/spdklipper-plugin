import os
from src.library import handler as hdl
import json

# Start load env.
from dotenv import load_dotenv
import sys
from pathlib import Path
from constants import HOST_SERVER as hostServer

if getattr(sys, 'frozen', False):
    # Đang chạy từ file .exe/.bin đã được PyInstaller build
    base_path = Path(sys._MEIPASS)
else:
    # Dùng __file__ để lấy project root, bất kể working directory là gì
    base_path = Path(__file__).resolve().parent.parent.parent

load_dotenv(dotenv_path=base_path / ".env", override=True) # Load environment variables at the very beginning, overriding existing ones
# End load env.


async def readOne(*args):
    [id, filterOwner] = args
    jsData = {
      'target': 'machineos',
      'action': 'readOne',
      'id': id,
      'filterOwner': filterOwner,
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt