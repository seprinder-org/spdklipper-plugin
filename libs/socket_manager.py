import json
import platform
import asyncio
import logging
import os
import socketio
import sys
import tracemalloc
import ssl
try:
    import certifi
except ImportError:
    certifi = None
from pathlib import Path
from urllib import parse
from dotenv import load_dotenv
from sqlmodel import Session, select
from src.database.sqlite3 import getSession, SocketStatus # Import getSession and SocketStatus
from datetime import datetime
from src.library import handler as hdl
import aiofiles

from src.library import exception as exp
from src.controller import cJob, cStorage, cSlicer, cMachineOs

from constants.constant import HOST_CONNECT, PATH

from src.printer import klipper as klp # Kliper.
# from src.printer import bambulab as bbl # Bambu lab.
# from src.printer import octoprint as octo # Octoprint.
# from src.printer import ender5maxchinese as efmc # Ender 5 Max Chinese.
# from src.printer import kobraoscloud as koc # KobraOs cloud.
# from src.printer import saturn4ultra as s4u # Saturn 4 Ultra.

# Track memory
tracemalloc.start()

# Global variables (không chứa socket client)
lstWsClient = {}
lstScServer = {}
profileUser = {}
accessToken = ''
refreshToken = ''
addressControl = ''
addressCamera = ''
isAmsUsed = False

# Load .env
if getattr(sys, 'frozen', False):
    base_path = Path(sys._MEIPASS)
else:
    base_path = Path(os.getcwd())
load_dotenv(dotenv_path=base_path / ".env", override=True)
if certifi:
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()



# Define the namespace
class scClient(socketio.AsyncClientNamespace):
    authen = {}
    printers = {}

    def on_disconnect(self):
        print(f'Disconnected from Socket.IO server.')
        asyncio.create_task(update_socket_status_in_db(False))

    async def on_confirm(self, msg):
        global addressControl, addressCamera, isAmsUsed

        currentPlatform = self.client.connection_headers['x-current-platform']
        currentUserId = self.client.connection_headers['x-current-user-id']
        targetUserId = self.client.connection_headers['x-target-user-id']
        targetMachineId = self.client.connection_headers['x-target-machine-id']

        connectionId = f'{currentPlatform}@{currentUserId}=>{targetUserId}:{targetMachineId}'
        lstScServer[connectionId] = self
        self.authen = {
            'currentPlatform': currentPlatform,
            'currentUserId': currentUserId,
            'targetUserId': targetUserId,
            'targetMachineId': targetMachineId,
        }

        profileMachine = json.loads(await hdl.getSecret('profile_machine', 'session'))
        addressControl = profileMachine.get('o_address_control', '')
        addressCamera = profileMachine.get('o_address_camera', '')

        if profileMachine['v_id'] != targetMachineId:
            hdl.resetSecret('local')
            hdl.resetSecret('session')
            print('Machine id mismatch. Resetting secrets and exiting.')
            sys.exit(1)

        tempProfileUser = await hdl.getSecret('profile_user', 'session')
        profileUser = json.loads(tempProfileUser)
        if profileUser['v_id'] != targetUserId:
            hdl.resetSecret('local')
            hdl.resetSecret('session')
            print('User id mismatch. Resetting secrets and exiting.')
            sys.exit(1)

        print('BackServer: Connected successfully')
        asyncio.create_task(update_socket_status_in_db(True))

    # Các hàm xử lý các sự kiện socket khác (rút gọn giữ nguyên logic)
    async def _reply(self, action, res, msg):
        data = {'msg': json.loads(msg), 'res': res}
        answer = json.dumps({'action': action, 'data': data})
        await self.emit('replyMessage', answer)

    async def _get_printer(self, profileMachine):
        machineOsId = profileMachine.get('v_machine_os_id')
        if not machineOsId: return None, None
        
        tempMachineOs = await cMachineOs.readOne(machineOsId, '')
        machineOsName = tempMachineOs['data']['v_name']
        
        machineAuthentication = profileMachine.get('o_machine_authentication', '{}')
        auth = json.loads(machineAuthentication)
        
        machineIdentifyNumber = profileMachine.get('o_identify_number', 'default')
        if machineIdentifyNumber in self.printers:
            return self.printers[machineIdentifyNumber], machineOsName

        printer = None
        if machineOsName == 'Klipper':
            printer = klp.KlipperPrinter(addressControl)
            # printer = klp.KlipperPrinter(addressControl, mock=True)
        # elif machineOsName == 'Bambu lab':
        #     printer = bbl.BambulabPrinter(addressControl, auth.get('accessCode'), auth.get('serialCode'), auth.get('isAmsUsed'))
        #     # printer = bbl.BambulabPrinter(addressControl, auth.get('accessCode'), auth.get('serialCode'), auth.get('isAmsUsed'), mock=True)
        # elif machineOsName == 'Octoprint':
        #     printer = octo.OctoprintPrinter(addressControl, auth.get('apiKey'))
        #     # printer = octo.OctoprintPrinter(addressControl, auth.get('apiKey'), mock=True) # For mocking if there is no real printers.
        # elif machineOsName == 'Ender 5 Max Chinese':
        #     printer = efmc.Ender5MaxChinesePrinter(addressControl)
        #     # printer = efmc.Ender5MaxChinesePrinter(addressControl, mock=True)
        # elif machineOsName == 'KobraOs cloud':
        #     printer_code = auth.get('printer_code')
        #     printer_token = auth.get('printer_token')
        #     printer = koc.KobraOsCloudPrinter(printer_code, printer_token)
        #     # printer = koc.KobraOsCloudPrinter(printer_code, printer_token, mock=True)
        # elif machineOsName == 'Saturn 4 Ultra':
        #     mainboard_id = auth.get('mainboard_id')
        #     # # Use ipAddress from auth if global addressControl is not set
        #     # effective_address = addressControl or auth.get('ipAddress', '')
        #     printer = s4u.Saturn4UltraPrinter(addressControl, mainboard_id=mainboard_id)
        
        if printer:
            self.printers[machineIdentifyNumber] = printer
        
        return printer, machineOsName

    async def _send_busy_reply(self, action, msg):
        jsTemp = {
            'action': action,
            'data': {
                'msg': json.loads(msg),
                'res': {'error': 'Machine is busy.'}
            }
        }
        await self.emit('replyMessage', json.dumps(jsTemp))

    async def _handle_machine_action(self, action_name, msg, *args):
        tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
        if tempProfileMachine:
            profileMachine = json.loads(tempProfileMachine)
            printer, _ = await self._get_printer(profileMachine)
            if printer:
                func = getattr(printer, action_name, None)
                if func:
                    res = await func(*args)
                    await self._reply(action_name, res, msg)

    async def on_getPrintStat(self, msg):
        await self._handle_machine_action('getPrintStat', msg)

    async def on_getTemperature(self, msg):
        await self._handle_machine_action('getTemperature', msg)

    async def on_runHome(self, msg):
        tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
        if tempProfileMachine:
            profileMachine = json.loads(tempProfileMachine)
            printer, _ = await self._get_printer(profileMachine)
            if printer:
                if not await printer.isReadyState():
                    await self._send_busy_reply('runHome', msg)
                else:
                    await self._handle_machine_action('runHome', msg)

    async def on_doJob(self, msg):
        tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
        if tempProfileMachine:
            profileMachine = json.loads(tempProfileMachine)
            printer, machineOsName = await self._get_printer(profileMachine)
            if printer:
                if not await printer.isReadyState():
                    await self._send_busy_reply('doJob', msg)
                else:
                    jsMsg = json.loads(msg)
                    targetJobId = jsMsg['message']['detail']
                    targetMachineId = jsMsg['message']['machineId']

                    condition = {
                        'v_id': targetJobId,
                        'v_status': 'Printing',
                        'v_sender_id': targetMachineId,
                        'a_result': 'Active'
                    }
                    structure = {
                            'limit': 1,
                            'page': 1,
                            'orderBy': 'v_created_timestamp',
                            'orderType': 'DESC',
                            'lstColumn': [],
                            'searchKeyword': '',
                        }
                    lstJob = await cJob.readCondition(condition, structure)
                    targetJob = lstJob['data'][0]
                    orderDetailId = targetJob['o_order_detail_id']
                    
                    # (Slicer and storage logic kept as is but slightly cleaned up)
                    condition = {'v_order_detail_id': orderDetailId, 'a_result': 'Active'}
                    lstSlicer = await cSlicer.readCondition(condition, structure)
                    if len(lstSlicer['data']) == 0:
                        condition = {'v_possessor_id': orderDetailId, 'a_result': 'Active'}
                        lstStorage = await cStorage.readCondition(condition, structure)
                        targetStorage = lstStorage['data'][0]
                        targetId, targetCloudPath = targetStorage['v_id'], targetStorage['o_cloud_path']
                    else:
                        targetSlicer = lstSlicer['data'][0]
                        targetId, targetCloudPath = targetSlicer['v_id'], targetSlicer['o_cloud_path']

                    print('Printing job:', targetJobId)
                    filename, file_stream, session = await hdl.download_file_async(targetCloudPath, targetId, machineOsName)
                    try:
                        await asyncio.sleep(5)
                        fullpath = await printer.uploadFile(filename, file_stream)
                        await asyncio.sleep(5)
                        if fullpath is None:
                            await cJob.notify(targetJob['v_id'], 'Failed')
                            return

                        # is_win64 = sys.platform == 'win32' and platform.machine().endswith('64')
                        # is_ai_supported = is_win64

                        if profileMachine.get('o_is_camera_in_used'):
                            rslt = await printer.doJobWithFailureDetection(filename, targetJobId, addressCamera, job_id=targetJobId)
                        else:
                            rslt = await printer.doJob(filename, job_id=targetJobId)

                        await asyncio.sleep(5)
                        if rslt:
                            await cJob.notify(targetJob['v_id'], 'Completed')
                            await asyncio.sleep(5)
                            await printer.removeFile(filename)
                            print('File is removed.')
                    finally:
                        await session.close()

    async def on_cancelCurrentJob(self, msg):
        tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
        if tempProfileMachine:
            profileMachine = json.loads(tempProfileMachine)
            printer, _ = await self._get_printer(profileMachine)
            if printer:
                if not await printer.isReadyState():
                    resCancel = await printer.runCancel()
                    await asyncio.sleep(5)
                else:
                    resCancel = True
                
                if resCancel: 
                    jsMsg = json.loads(msg)
                    currentJobId = jsMsg['message']['detail']
                    await cJob.notify(currentJobId, 'Cancelled')

    # async def on_doLabel(self, msg):
    #     jsMsg = json.loads(msg)
    #     targetDetail = jsMsg['message']['detail']
    #     label, filename = targetDetail.split(' - ')[0], targetDetail.split(' - ')[1]
    #     filepath = os.path.join(dataset_root, 'capture', filename)
    #     # If label is fail then it detected failure wrong.
    #     if label == 'fail': # => Success
    #         # Move file to fail folder.
    #         os.rename(filepath, os.path.join(dataset_root, 'success', filename))
    #     elif label == 'pass': # => Failure
    #         # Move file to success folder.
    #         os.rename(filepath, os.path.join(dataset_root, 'failure', filename))
        
    #     # Combine 2 prints.
    #     print('Label result:', label, ' - ', 'Filename:', filename)

    async def on_checkConnection(self, msg):
        tempProfileUser = hdl.getSecret('profile_user', 'session')
        if tempProfileUser:
            profileUser = json.loads(tempProfileUser)
        
        tempProfileMachine = hdl.getSecret('profile_machine', 'session')
        if tempProfileMachine:
            profileMachine = json.loads(tempProfileMachine)
        currentPlatform = 'BackBridge'
        currentUserId = profileUser['v_id']
        targetUserId = profileUser['v_id']
        targetMachineId = profileMachine['v_id']
        
        tempMsg = {
                "message": {
                    "machineId": targetMachineId,
                    "userId": currentUserId,
                    "action": "checkConnection",
                    "detail": "",
                    "sender": "BackBridge",
                    "receiver": "BackServer"
                },
                "authen": {
                    'currentPlatform': currentPlatform,
                    'currentUserId': currentUserId,
                    'targetUserId': targetUserId,
                    'targetMachineId': targetMachineId,
                }
                }

        print('Received checkConnection message:', msg)
        await self._reply('checkConnection', {'status': 'success', 'message': 'Connection is active.'}, msg)
    
    async def on_replyMessage(self, msg):
        print('Received reply message:', msg)

    # async def on_getInfoMachine(self, msg):
    #     await self._handle_machine_action('getInfoMachine', msg)

    # async def on_runEjectBed(self, msg):
    #     await self._handle_machine_action('runEjectBed', msg)

    # async def on_runShutdown(self, msg):
    #     await self._handle_machine_action('runShutdown', msg)

    # async def on_runRestart(self, msg):
    #     await self._handle_machine_action('runRestart', msg)

    # async def on_runPause(self, msg):
    #     await self._handle_machine_action('runPause', msg)

    # async def on_runResume(self, msg):
    #     await self._handle_machine_action('runResume', msg)

    # async def on_runCancel(self, msg):
    #     await self._handle_machine_action('runCancel', msg)


class SocketClientManager:
    def __init__(self):
        self.client = None
        self.is_connecting = False

    async def create_client(self):
        if self.client:
            try:
                await self.client.disconnect()
            except:
                pass
        # Disable SSL verify directly in constructor for NUC compatibility
        self.client = socketio.AsyncClient(logger=True, engineio_logger=True, ssl_verify=False)
        self.client.register_namespace(scClient('/'))
        return self.client

    # async def send_image(self, file_path: str, image_name: str, event_name: str = 'stream-image'):
    #     if self.client and self.client.connected:
    #         if os.path.exists(file_path):
    #             async with aiofiles.open(file_path, 'rb') as f:
    #                 image_data = await f.read()
    #                 # Cannot send binary mixed with JSON easily in a single emit unless using a specific structure or multiple args.
    #                 # Socket.IO supports emitting multiple arguments.
    #                 # arg1: metadata (JSON), arg2: binary data
    #                 metadata = {'imageName': image_name}
    #                 await self.client.emit(event_name, (metadata, image_data))
    #                 print(f"Sent image {file_path} with name {image_name} via socket event '{event_name}'")
    #         else:
    #             print(f"Image file not found: {file_path}")
    #     else:
    #         print("Socket not connected, cannot send image.")

manager = SocketClientManager()

async def update_socket_status_in_db(is_connected: bool):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _perform_socket_status_db_operations, is_connected)

def _perform_socket_status_db_operations(is_connected: bool):
    session_generator_obj = getSession()
    with next(session_generator_obj) as session:
        # Always update the single status entry or create it if it doesn't exist
        socket_status_entry = session.exec(select(SocketStatus).limit(1)).first()
        if socket_status_entry:
            socket_status_entry.is_connected = is_connected
            socket_status_entry.timestamp = datetime.now()
        else:
            socket_status_entry = SocketStatus(is_connected=is_connected)
        session.add(socket_status_entry)
        session.commit()
        session.refresh(socket_status_entry)

# Entry point
async def _connect_to_socketio(client):
    global profileUser
    retry_count = 0
    max_retries = 5
    retry_delay = 5  # seconds

    while retry_count < max_retries:
        try:
            tempProfileUser = await hdl.getSecret('profile_user', 'session')
            tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
            if tempProfileUser and tempProfileMachine:
                profileUser = json.loads(tempProfileUser)
                profileMachine = json.loads(tempProfileMachine)
                currentPlatform = 'BackBridge'
                currentUserId = profileUser['v_id']
                targetMachineId = profileMachine['v_id']
                
                # Normalize URL: python-socketio handles upgrade internally,
                # using https:// is often more reliable than wss:// in some environments.
                url = HOST_CONNECT
                if not url:
                    print('HOST_CONNECT environment variable is not set.')
                    return False
                    
                if url.startswith('wss://'):
                    url = url.replace('wss://', 'https://')
                elif url.startswith('ws://'):
                    url = url.replace('ws://', 'http://')

                print(f'Attempting to connect to {url}{PATH} (Attempt {retry_count + 1}/{max_retries})...')
                
                await client.connect(
                    url,
                    headers={
                        'x-current-platform': currentPlatform,
                        'x-current-user-id': currentUserId,
                        'x-target-user-id': currentUserId,
                        'x-target-machine-id': targetMachineId
                    },
                    socketio_path = PATH,
                    transports=['websocket']  # Force websocket to avoid polling issues
                )
                print('Connected to Socket.IO server.')
                await client.wait()
                return True
            else:
                print('User or machine profile not found. Please login to bridge.')
                return False
        except socketio.exceptions.ConnectionError as e:
            retry_count += 1
            print(f"Connection failed (Attempt {retry_count}/{max_retries}): {e}")
            if retry_count < max_retries:
                print(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                print("Max retries reached. Connection failed.")
                return False
        except Exception as ex:
            print(f"An error occurred during connection attempt: {str(ex)}")
            return False
    return False