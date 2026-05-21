from src.library import handler as hdl
import os
import json
from constants import HOST_SERVER as hostServer

# Start load env.
from dotenv import load_dotenv
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Đang chạy từ file .exe/.bin đã được PyInstaller build
    base_path = Path(sys._MEIPASS)
else:
    # Dùng __file__ để lấy project root, bất kể working directory là gì
    base_path = Path(__file__).resolve().parent.parent.parent

load_dotenv(dotenv_path=base_path / ".env", override=True) # Load environment variables at the very beginning, overriding existing ones
# End load env.


async def getConfiguration(*args):
    domain, device = args
    jsData = {
        'target': 'agent',
        'action': 'getConfiguration',
        'domain': domain,
        'device': device
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

async def verify(*args):
    domain, device = args
    configurationAgent = await getConfiguration(domain, device)
    if 'error' not in configurationAgent and 'data' in configurationAgent:
        tempConfigurationAgent = json.dumps(configurationAgent['data'])
        valid = await hdl.setSecret('configuration_agent', tempConfigurationAgent, 'session')
        return configurationAgent['data']['v_id']

    if 'error' in configurationAgent:
        print(f"Lỗi khi xác minh đại lý: {configurationAgent['error']}")
    else:
        print(f"Lỗi khi xác minh đại lý: Không tìm thấy dữ liệu cấu hình.")
    return ''