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


async def verify(*args):
    userId, machineIdentifyNumber = args
    machineId = ''
    condition = {
            'v_possessor_id': userId
            }
    structure = {
                'limit': 8,
                'page': 1,
                'orderBy': 'v_created_timestamp',
                'orderType': 'DESC',
                'lstColumn': [],
                'searchKeyword': '',
            }
    lstMachine = await readCondition(condition, structure)

    if 'error' in lstMachine:
        print(f"Lỗi khi xác minh thiết bị: {lstMachine['error']}")
        return ''

    if 'data' not in lstMachine:
        print(f"Lỗi khi xác minh thiết bị: Không tìm thấy dữ liệu thiết bị.")
        return ''

    for machine in lstMachine['data']:
        if machine['o_identify_number'] == machineIdentifyNumber:
            # Start store current machine.
            tempProfileMachine = json.dumps(machine)
            await hdl.setSecret('profile_machine', tempProfileMachine, 'session')

            # End store current machine.
            machineId = machine['v_id']

    return machineId

async def readOne():
    pass

async def readAll():
    pass

async def readCondition(*args):
    [condition, structure] = args
    jsData = {
        'target': 'machine',
        'action': 'readCondition',
        'condition': condition,
        'structure': structure
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

def createOne():
    pass

def updateOne():
    pass

def deleteOne():
    pass

def restoreOne():
    pass


