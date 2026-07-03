import json
import math
import asyncio
import os
import socketio
import sys
import tracemalloc
import base64
from io import BytesIO
try:
    import certifi
except ImportError:
    certifi = None
from pathlib import Path
from urllib import parse
from sqlmodel import Session, select
from src.database.sqlite3 import getSession, SocketStatus # Import getSession and SocketStatus
from datetime import datetime
from src.library import handler as hdl

from src.library import exception as exp
from src.controller import cJob, cStorage, cSlicer, cMachineOs

from constants.constant import HOST_CONNECT, PATH

from src.printer import klipper as klp # Kliper.
# from src.printer import bambulab as bbl # Bambu lab.
# from src.printer import octoprint as octo # Octoprint.
# from src.printer import ender5maxchinese as efmc # Ender 5 Max Chinese.
# from src.printer import kobraoscloud as koc # KobraOs cloud.
# from src.printer import saturn4ultra as s4u # Saturn 4 Ultra.

# --- SPD Status file path (for Moonraker component integration) ---
# This file is read by the Moonraker custom component (spd_status.py)
# to display SPD connection status on Fluidd/Mainsail via M117.
SPD_STATUS_FILE = os.path.expanduser("~/printer_data/config/spd_status.json")

# Track memory
tracemalloc.start()

# Global variables (không chứa socket client)
lstWsClient = {}
lstScServer = {}
profileUser = {}
accessToken = ''
refreshToken = ''
isAmsUsed = False

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
        global isAmsUsed

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
        
        # Lấy địa chỉ control từ profileMachine thay vì biến global
        machineAddressControl = profileMachine.get('o_address_control', '')
        machineAddressCamera = profileMachine.get('o_address_camera', '')
        
        machineIdentifyNumber = profileMachine.get('o_identify_number', 'default')
        if machineIdentifyNumber in self.printers:
            return self.printers[machineIdentifyNumber], machineOsName

        printer = None
        if machineOsName == 'Klipper':
            printer = klp.KlipperPrinter(machineAddressControl)
            # printer = klp.KlipperPrinter(machineAddressControl, mock=True)
        # elif machineOsName == 'Bambu lab':
        #     printer = bbl.BambulabPrinter(machineAddressControl, auth.get('accessCode'), auth.get('serialCode'), auth.get('isAmsUsed'))
        #     # printer = bbl.BambulabPrinter(machineAddressControl, auth.get('accessCode'), auth.get('serialCode'), auth.get('isAmsUsed'), mock=True)
        # elif machineOsName == 'Octoprint':
        #     printer = octo.OctoprintPrinter(machineAddressControl, auth.get('apiKey'))
        #     # printer = octo.OctoprintPrinter(machineAddressControl, auth.get('apiKey'), mock=True) # For mocking if there is no real printers.
        # elif machineOsName == 'Ender 5 Max Chinese':
        #     printer = efmc.Ender5MaxChinesePrinter(machineAddressControl)
        #     # printer = efmc.Ender5MaxChinesePrinter(machineAddressControl, mock=True)
        # elif machineOsName == 'KobraOs cloud':
        #     printer_code = auth.get('printer_code')
        #     printer_token = auth.get('printer_token')
        #     printer = koc.KobraOsCloudPrinter(printer_code, printer_token)
        #     # printer = koc.KobraOsCloudPrinter(printer_code, printer_token, mock=True)
        # elif machineOsName == 'Saturn 4 Ultra':
        #     mainboard_id = auth.get('mainboard_id')
        #     # # Use ipAddress from auth if global addressControl is not set
        #     # effective_address = machineAddressControl or auth.get('ipAddress', '')
        #     printer = s4u.Saturn4UltraPrinter(machineAddressControl, mainboard_id=mainboard_id)
        
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
                    # Lấy thông tin từ message
                    directFileUrl = jsMsg['message'].get('fileUrl', '')
                    directFileName = jsMsg['message'].get('fileName', '')
                    fileBase64 = jsMsg['message'].get('fileBase64', '')

                    # Nếu có fileBase64 trong message, đây là in trực tiếp (Print Now từ editor)
                    # File đã được backend download và gửi dưới dạng base64 qua socket
                    if fileBase64:
                        print(f'Direct print from editor (base64): {targetJobId}, fileName: {directFileName}')
                        file_bytes = base64.b64decode(fileBase64)
                        file_stream = BytesIO(file_bytes)
                        filename = directFileName if directFileName else f'{targetJobId}.gcode'
                        session = None  # Không cần session cho base64, xử lý trong finally
                        targetJob = {'v_id': targetJobId}
                    elif directFileUrl:
                        print(f'Direct print from editor: {targetJobId}, fileUrl: {directFileUrl}')
                        filename, file_stream, session = await hdl.download_file_async(directFileUrl, targetJobId, machineOsName)
                        targetJob = {'v_id': targetJobId}
                    else:
                        # In từ đơn hàng thông thường: tra cứu job trong database
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
                        if not lstJob.get('data') or len(lstJob['data']) == 0:
                            print(f'Job not found in database: {targetJobId}')
                            return
                        targetJob = lstJob['data'][0]
                        orderDetailId = targetJob['o_order_detail_id']

                        # Lấy file từ cloud storage thông qua order_detail_id
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
                            if targetJob:
                                await cJob.notify(targetJob['v_id'], 'Failed')
                            return

                        # Chạy doJob trong một task riêng để không block các sự kiện socket khác
                        # (ví dụ: máy thứ 2 gửi lệnh trong khi máy thứ 1 đang in)
                        asyncio.create_task(self._run_doJob_background(printer, filename, targetJob, targetJobId, session))
                    finally:
                        # session sẽ được đóng trong _run_doJob_background nếu có
                        pass

    async def _run_doJob_background(self, printer, filename, targetJob, targetJobId, session):
        """Chạy doJob trong background task để không block socket event loop.
        
        Now sends real-time progress updates (elapsed time, filament used, temperature) to the server
        by passing a progress_callback to printer.doJob().
        """
        # Track the last notified print_duration to avoid duplicate final updates
        last_notified_duration = 0
        
        async def progress_callback(progress: dict):
            """Callback được gọi từ printer.doJob() mỗi khi có cập nhật tiến trình."""
            nonlocal last_notified_duration
            print_duration = progress.get('print_duration', 0)
            filament_used = progress.get('filament_used', 0)
            state = progress.get('state', '')
            temperature = progress.get('temperature', {})
            
            # Only notify if print_duration has changed (avoid duplicate updates)
            if print_duration != last_notified_duration or state in ('complete', 'error', 'cancelled'):
                last_notified_duration = print_duration
                
                if targetJob:
                    # Map Klipper state to job status
                    if state == 'complete':
                        status = 'Completed'
                    elif state == 'error':
                        status = 'Failed'
                    elif state == 'cancelled':
                        status = 'Cancelled'
                    else:
                        status = 'Printing'  # Still printing
                    
                    # Send progress update to server (bao gồm nhiệt độ)
                    await cJob.notify(
                        targetJob['v_id'],
                        status,
                        targetPrintDuration=print_duration,
                        targetFilamentUsed=filament_used,
                        targetTemperature=temperature  # Thêm nhiệt độ
                    )
                    print(f'[Progress] Job {targetJob["v_id"]}: state={state}, duration={print_duration}s, '
                          f'filament={filament_used}mm, temp={temperature}')

        try:
            rslt = await printer.doJob(
                filename,
                job_id=targetJobId,
                progress_callback=progress_callback
            )

            await asyncio.sleep(5)
            if rslt:
                if targetJob:
                    # Final notification - job is completed
                    await cJob.notify(targetJob['v_id'], 'Completed')
                await asyncio.sleep(5)
                await printer.removeFile(filename)
                print('File is removed.')
            else:
                # Job failed or was cancelled
                if targetJob:
                    await cJob.notify(targetJob['v_id'], 'Failed')
                print(f'Job {targetJobId} finished with failure.')
        finally:
            if session:
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
        tempProfileUser = await hdl.getSecret('profile_user', 'session')
        if tempProfileUser:
            profileUser = json.loads(tempProfileUser)
        
        tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
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

    async def on_getInfoMachine(self, msg):
        await self._handle_machine_action('getInfoMachine', msg)

    async def on_runEjectBed(self, msg):
        await self._handle_machine_action('runEjectBed', msg)

    async def on_runShutdown(self, msg):
        await self._handle_machine_action('runShutdown', msg)

    async def on_runRestart(self, msg):
        await self._handle_machine_action('runRestart', msg)

    async def on_runPause(self, msg):
        await self._handle_machine_action('runPause', msg)

    async def on_runResume(self, msg):
        await self._handle_machine_action('runResume', msg)

    async def on_runCancel(self, msg):
        await self._handle_machine_action('runCancel', msg)

    async def on_controlCommand(self, msg):
        """
        Handle control commands (jog, setExtruderTemp, setBedTemp, emergencyStop, etc.)
        sent from FrontServer via spdconnect.

        Command format in msg.message.detail:
          - 'jog x 10 F1500'       → G91 + G1 X10 F1500
          - 'jog y -5 F3000'       → G91 + G1 Y-5 F3000
          - 'jog z 1 F600'         → G91 + G1 Z1 F600
          - 'setExtruderTemp 200'  → M104 S200
          - 'setBedTemp 60'        → M140 S60
          - 'emergencyStop'        → M112 (emergency stop)
        """
        tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
        if not tempProfileMachine:
            print('[controlCommand] No machine profile found.')
            return

        profileMachine = json.loads(tempProfileMachine)
        printer, machineOsName = await self._get_printer(profileMachine)
        if not printer:
            print('[controlCommand] No printer instance available.')
            return

        jsMsg = json.loads(msg)
        command_str = jsMsg.get('message', {}).get('detail', '').strip()
        if not command_str:
            print('[controlCommand] Empty command string.')
            return

        print(f'[controlCommand] Received: "{command_str}" for {machineOsName}')

        try:
            parts = command_str.split()
            cmd_type = parts[0].lower()

            if cmd_type == 'jog':
                # Format: jog <axis> <distance> F<speed>
                # e.g. 'jog x 10 F1500'
                if len(parts) >= 3:
                    axis = parts[1].lower()
                    distance = parts[2]
                    speed = '1500'
                    for p in parts[3:]:
                        if p.startswith('f'):
                            speed = p[1:]
                    # Relative positioning + move
                    gcode = f'G91\nG1 {axis.upper()}{distance} F{speed}\nG90'
                    await printer.runScript(gcode)
                    print(f'[controlCommand] Jog {axis} {distance} F{speed}')
                else:
                    print(f'[controlCommand] Invalid jog format: {command_str}')

            elif cmd_type == 'setextrudertemp':
                # Format: setExtruderTemp <temp>
                if len(parts) >= 2:
                    temp = parts[1]
                    gcode = f'M104 S{temp}'
                    await printer.runScript(gcode)
                    print(f'[controlCommand] Set extruder temp to {temp}°C')
                else:
                    print(f'[controlCommand] Invalid setExtruderTemp format: {command_str}')

            elif cmd_type == 'setbedtemp':
                # Format: setBedTemp <temp>
                if len(parts) >= 2:
                    temp = parts[1]
                    gcode = f'M140 S{temp}'
                    await printer.runScript(gcode)
                    print(f'[controlCommand] Set bed temp to {temp}°C')
                else:
                    print(f'[controlCommand] Invalid setBedTemp format: {command_str}')

            elif cmd_type == 'emergencystop':
                # M112 - Emergency stop
                await printer.runScript('M112')
                print('[controlCommand] Emergency stop (M112)')

            else:
                # Unknown command - try sending as raw G-code
                print(f'[controlCommand] Unknown command type: "{cmd_type}", sending as raw G-code')
                await printer.runScript(command_str)

            # Reply success
            await self._reply('controlCommand', {'status': 'success', 'command': command_str}, msg)

        except Exception as e:
            print(f'[controlCommand] Error executing command "{command_str}": {e}')
            await self._reply('controlCommand', {'status': 'error', 'error': str(e)}, msg)


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

    # Write status file for Moonraker component integration
    _write_spd_status_file(is_connected)

def _write_spd_status_file(is_connected: bool):
    """
    Write SPD connection status to a JSON file that the Moonraker custom component
    (spd_status.py) reads to display SPD status on Fluidd/Mainsail via M117.
    """
    try:
        # Read profile_machine from DB to get machine_id
        machine_id = ''
        machine_name = ''
        try:
            import asyncio
            # Use synchronous DB access since we're in an executor
            from src.database.sqlite3 import Secret, engine
            from src.library.handler import base64Encode, decrypt

            with Session(engine) as session:
                encrypt_name = base64Encode('profile_machine')
                oSecret = session.exec(
                    select(Secret).where(Secret.name == encrypt_name, Secret.type == 'session')
                ).first()
                if oSecret:
                    decrypted = asyncio.run(decrypt(oSecret.value))
                    profile = json.loads(decrypted)
                    machine_id = profile.get('o_identify_number', '')
                    machine_name = profile.get('v_name', '')
        except Exception:
            pass

        status_data = {
            "machine_id": machine_id,
            "machine_name": machine_name,
            "connected": is_connected,
            "status": "connected" if is_connected else "disconnected",
            "timestamp": datetime.now().isoformat()
        }

        # Ensure directory exists
        status_dir = os.path.dirname(SPD_STATUS_FILE)
        os.makedirs(status_dir, exist_ok=True)

        with open(SPD_STATUS_FILE, 'w') as f:
            json.dump(status_data, f)
    except Exception as e:
        print(f"[SPD Status] Error writing status file: {e}")

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