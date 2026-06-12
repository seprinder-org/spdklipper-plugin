import ipaddress
import os
import shutil
import uvicorn
import socket
import sys
from pathlib import Path

# Add project root to sys.path so that 'src', 'libs', 'constants' packages are found
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi import Depends, FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from src.database.sqlite3 import Secret, ServerLog, SocketStatus, getSession, createDbAndTbl
from src.controller import cUser, cMachine, cAgent
import asyncio
import json
from src.library import handler as hdl
from src.library import config_reader as cfg  # Config reader for spdklipper.conf
from libs import socket_manager as soc
from utils import util as soc_util
from fastapi.responses import JSONResponse
from fastapi import WebSocket, WebSocketDisconnect
from constants import AGENT_DOMAIN as agentDomain, AGENT_DEVICE as agentDevice, PORT as port

import datetime

# print('For deployment')

# Start load env.
base_path = Path(__file__).resolve().parent.parent
exe_path = base_path
# End load env.

# --- Parse CLI arguments for -c (config) and -l (log) ---
_cli_args = cfg.parse_cli_args()
_config_path = cfg.resolve_config_path(_cli_args.get('config_path'))
if _config_path:
    print(f"[Config] Using config file: {_config_path}")
else:
    print("[Config] No config file found. Web login will be used if needed.")

# --- End CLI args ---

# Function to check if a port is in use
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


while is_port_in_use(port):
    port += 1


# Initialize Jinja2Templates
templates = Jinja2Templates(directory=base_path / "src" / "view")

# Custom stdout writer to capture logs and save to DB
class LogWriter:
    def __init__(self, original_stdout, db_session_generator):
        self.original_stdout = original_stdout
        self.db_session_generator = db_session_generator

    def write(self, message):
        self.original_stdout.write(message)
        stripped_message = message.strip()
        if stripped_message: # Only process non-empty lines
            # # Define keywords to filter for
            # important_keywords = ["connection", "establish", "disconnect", "retrying connect", "Lỗi:", "Đang cố gắng đăng nhập", "Đăng nhập thành công", "Người dùng đã đăng xuất"]

            # # Check if any important keyword is in the message (case-insensitive)
            # if any(keyword.lower() in stripped_message.lower() for keyword in important_keywords):
            #     # Run DB operations in a separate thread to avoid blocking the event loop
            #     asyncio.create_task(self._save_log_to_db(stripped_message))

            asyncio.create_task(self._save_log_to_db(stripped_message))

    async def _save_log_to_db(self, message):
        # Use asyncio.to_thread for blocking DB operations
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._perform_db_operations, message)

    def _perform_db_operations(self, message):
        # Call the generator function to get the generator object
        session_generator_obj = self.db_session_generator()
        with next(session_generator_obj) as session:
            new_log = ServerLog(message=message)
            session.add(new_log)
            session.commit()
            session.refresh(new_log)

            # Giới hạn số lượng log là 100. Nếu vượt quá, ghi đè log cũ nhất.
            total_logs = len(session.exec(select(ServerLog)).all())
            if total_logs >= 100:
                # Lấy log cũ nhất để ghi đè
                oldest_log = session.exec(select(ServerLog).order_by(ServerLog.timestamp).limit(1)).first()
                if oldest_log:
                    session.delete(oldest_log)
                    session.commit()

    def flush(self):
        self.original_stdout.flush()

# Bắt đầu khởi tạo database.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # IMPORTANT: Do NOT call deleteDb() here — that would destroy all
    # encrypted secrets (access tokens, refresh tokens) on every restart.
    # The database is persistent and tokens survive across reboots.
    createDbAndTbl()

    # Delete dataset (disabled — detection feature not yet active).
    # hdl.deleteDataset()

    # Create dataset (disabled — detection feature not yet active).
    # hdl.createDataset()

    # Create model (disabled — detection feature not yet active).
    # await hdl.createModel()

    # --- Auto-login from config file (spdklipper.conf) ---
    creds = cfg.read_credentials(_config_path)
    config_has_creds = cfg.has_valid_credentials(creds) and creds['machine_id']

    # Check if machine_id in config has CHANGED since last session.
    # If so, reset the old session so auto-login re-authenticates with the new machine.
    if config_has_creds:
        tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
        if tempProfileMachine:
            try:
                old_machine_data = json.loads(tempProfileMachine)
                old_machine_id = old_machine_data.get('o_identify_number', '')
                if old_machine_id and old_machine_id != creds['machine_id']:
                    print(f"[AutoLogin] Phát hiện machine_id thay đổi: '{old_machine_id}' → '{creds['machine_id']}'")
                    print("[AutoLogin] Đang xóa session cũ để đăng nhập lại với máy mới...")
                    # resetSecret is a sync function, run in executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, hdl.resetSecret, 'session')
                    await loop.run_in_executor(None, hdl.resetSecret, 'local')
                    # Also close any existing socket connection
                    await soc_util.close_socket_connection()
            except Exception as e:
                print(f"[AutoLogin] Lỗi khi kiểm tra machine_id cũ: {e}")

    # Only attempt auto-login if no existing session is found.
    tempProfileUser = await hdl.getSecret('profile_user', 'session')
    if not tempProfileUser:
        if config_has_creds:
            print("[AutoLogin] Phát hiện thông tin đăng nhập trong config. Đang tự động đăng nhập...")
            try:
                # Step 1: Verify agent
                agent_id = await cAgent.verify(agentDomain, agentDevice)
                if not agent_id:
                    print("[AutoLogin] Lỗi: Xác minh đại lý thất bại.")
                else:
                    # Step 2: Login user
                    user_id = await cUser.verify(creds['username'], creds['password'])
                    if not user_id:
                        print("[AutoLogin] Lỗi: Đăng nhập thất bại. Kiểm tra lại username/password.")
                    else:
                        # Step 3: Verify machine with exact Machine ID from config
                        print(f"[AutoLogin] Sử dụng Machine ID từ config: {creds['machine_id']}")
                        machine_id = await cMachine.verify(user_id, creds['machine_id'])
                        if not machine_id:
                            print(f"[AutoLogin] Lỗi: Không tìm thấy máy với ID '{creds['machine_id']}' trong tài khoản.")
                        else:
                            # Step 4: Connect socket
                            print("[AutoLogin] Đăng nhập và xác thực máy in thành công!")
                            asyncio.create_task(soc_util.connect_socket())
            except Exception as e:
                print(f"[AutoLogin] Lỗi trong quá trình tự động đăng nhập: {e}")
        else:
            if not creds['machine_id']:
                print("[AutoLogin] Thiếu machine_id trong config. Cần điền đủ username, password và machine_id.")
            else:
                print("[AutoLogin] Không tìm thấy thông tin đăng nhập trong config. Dùng giao diện web để đăng nhập.")
    else:
        print("[AutoLogin] Đã có phiên làm việc cũ. Bỏ qua tự động đăng nhập.")
    # --- End auto-login ---

    asyncio.create_task(periodic_check_connection())
    asyncio.create_task(periodic_refresh_session())
    asyncio.create_task(periodic_check_machine_id())
    # Redirect stdout to our custom writer
    sys.stdout = LogWriter(sys.stdout, getSession)

    yield

    # Restore original stdout when app shuts down
    sys.stdout = sys.__stdout__
# Kết thúc khởi tạo database.

app = FastAPI(lifespan=lifespan)

public_path = base_path / "src" / "public"

# Fallback if the path is not found directly in the PyInstaller bundle's base_path
if not public_path.is_dir():
    # This might happen if src/public is not directly at base_path/src/public
    # but perhaps at the root of the temporary directory or another location
    # Try to find it relative to the script's current working directory
    public_path = Path(os.getcwd()) / "src" / "public"
    if not public_path.is_dir():
        # As a last resort, try relative to the script's file location
        public_path = Path(os.path.dirname(os.path.abspath(__file__))) / "src" / "public"

app.mount("/public", StaticFiles(directory=public_path), name="public")

static_path = base_path / "static"

# Fallback if the path is not found directly in the PyInstaller bundle's base_path
if not static_path.is_dir():
    # This might happen if src/static is not directly at base_path/src/static
    # but perhaps at the root of the temporary directory or another location
    # Try to find it relative to the script's current working directory
    static_path = Path(os.getcwd()) / "static"
    if not static_path.is_dir():
        # As a last resort, try relative to the script's file location
        static_path = Path(os.path.dirname(os.path.abspath(__file__))) / "static"

app.mount("/static", StaticFiles(directory=static_path), name="static")

capture_path = exe_path / "detection" / "spd_dataset" / "capture"
os.makedirs(capture_path, exist_ok=True)
app.mount("/captures", StaticFiles(directory=capture_path), name="captures")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, session: Session = Depends(getSession)):
    logs = session.exec(select(ServerLog).order_by(ServerLog.timestamp.desc()).limit(10)).all()
    formatted_logs = [f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {log.message}" for log in logs]

    socket_status_entry = session.exec(select(SocketStatus).limit(1)).first()
    is_socket_connected = socket_status_entry.is_connected if socket_status_entry else False

    tempProfileUser = await hdl.getSecret('profile_user', 'session')
    if tempProfileUser:
        profileUser = json.loads(tempProfileUser)
        username = profileUser['v_username']
        if username:
            tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
            if tempProfileMachine:
                profileMachine = json.loads(tempProfileMachine)
                machine_id = profileMachine['o_identify_number']
                if machine_id:
                    return templates.TemplateResponse(
                    "index.html",
                    {
                        "request": request,
                        "username": username,
                        "fullname": profileUser['v_name'],
                        "machine_id": machine_id,
                        "machine_name": profileMachine['v_name'],
                        "machine_description": profileMachine['v_description'],
                        "machine_is_auto_eject": profileMachine['v_is_auto_eject'],
                        "machine_is_private": profileMachine['o_is_private'],
                        "logs": formatted_logs, # Pass current logs to template
                        "is_socket_connected": is_socket_connected # Pass socket status to template
                    }
                )
    return templates.TemplateResponse("login.html", {"request": request, "logs": formatted_logs}) # Pass current logs to template

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request, session: Session = Depends(getSession)):
    logs = session.exec(select(ServerLog).order_by(ServerLog.timestamp.desc()).limit(100)).all()
    formatted_logs = [f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {log.message}" for log in logs]

    tempProfileUser = await hdl.getSecret('profile_user', 'session')
    if tempProfileUser:
        profileUser = json.loads(tempProfileUser)
        username = profileUser['v_username']
        if username:
            tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
            if tempProfileMachine:
                profileMachine = json.loads(tempProfileMachine)
                machine_id = profileMachine['o_identify_number']
                if machine_id:
                    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request, "logs": formatted_logs}) # Pass current logs to template

@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    machineIdentifyNumber: str = Form(...),
    session: Session = Depends(getSession) # Inject session for logging
):
    print(f"Đang cố gắng đăng nhập với Username: {username}, Machine ID: {machineIdentifyNumber}")
    agent_id = await cAgent.verify(agentDomain, agentDevice)
    if agent_id == '':
        print("Lỗi: Xác minh đại lý thất bại. Đang dừng chương trình.")
        logs = session.exec(select(ServerLog).order_by(ServerLog.timestamp.desc()).limit(100)).all()
        formatted_logs = [f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {log.message}" for log in logs]
        return templates.TemplateResponse("login.html", {"request": request, "error": "Xác minh đại lý thất bại.", "logs": formatted_logs})

    user_id = await cUser.verify(username, password)
    if user_id == '':
        print("Lỗi: Xác minh người dùng thất bại. Đang dừng chương trình.")
        logs = session.exec(select(ServerLog).order_by(ServerLog.timestamp.desc()).limit(100)).all()
        formatted_logs = [f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {log.message}" for log in logs]
        return templates.TemplateResponse("login.html", {"request": request, "error": "Xác minh người dùng thất bại.", "logs": formatted_logs})

    machine_id = await cMachine.verify(user_id, machineIdentifyNumber)
    if machine_id == '':
        print("Lỗi: Xác minh thiết bị thất bại. Đang dừng chương trình.")
        logs = session.exec(select(ServerLog).order_by(ServerLog.timestamp.desc()).limit(100)).all()
        formatted_logs = [f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {log.message}" for log in logs]
        return templates.TemplateResponse("login.html", {"request": request, "error": "Xác minh thiết bị thất bại.", "logs": formatted_logs})

    # Chạy hàm init của socket trong một tác vụ nền
    asyncio.create_task(soc_util.connect_socket())

    print(f"Đăng nhập thành công cho Username: {username}, Machine ID: {machineIdentifyNumber}")
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request, session: Session = Depends(getSession)):
     return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@app.post("/logout")
async def logout(request: Request):
    print("Người dùng đã đăng xuất.")
    await cUser.logout(request)

    # Đóng kết nối socket khi đăng xuất
    await soc_util.close_socket_connection()

    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@app.post("/socket/connect")
async def connect_socket_endpoint():
    try:
        asyncio.create_task(soc_util.connect_socket())
        return {"status": "success", "message": "Đang cố gắng kết nối socket."}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi khi kết nối socket: {e}"}

@app.post("/socket/disconnect")
async def disconnect_socket_endpoint():
    try:
        await soc_util.close_socket_connection()
        return {"status": "success", "message": "Đã ngắt kết nối socket."}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi khi ngắt kết nối socket: {e}"}

@app.post("/connection/check")
async def check_connection_endpoint():
    try:
        isConnectFailed = True
        isServerFailed = True
        # Socket.
        if soc.manager.client and soc.manager.client.connected:
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
            checked = {'status': 'error', 'message': ''}
            try:
                checked = await soc.manager.client.call('checkConnection', json.dumps(tempMsg), timeout=2)
            except Exception as e:
                checked['message'] = f'No response from socker server.'

            if checked['status'] == 'success':
                isConnectFailed = False
            elif checked['status'] == 'error':
                await disconnect_socket_endpoint()
                await asyncio.sleep(2)
                await connect_socket_endpoint()
                await asyncio.sleep(2)

            # Check server.
            configurationAgent = await cAgent.getConfiguration(agentDomain, agentDevice)
            if 'error' not in configurationAgent:
                isServerFailed = False
            return {"status": checked['status'], "message": f"Is server failed => {isServerFailed}, Is connect failed => {isConnectFailed}, {checked['message']}"}
        else:
            return {"status": "error", "message": "Socket client chưa được kết nối."}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi khi gửi yêu cầu kiểm tra kết nối socket: {e}"}

async def periodic_check_connection():
    while True:
        try:
            # Nếu socket chưa kết nối, tự động kết nối lại
            if not soc.manager.client or not soc.manager.client.connected:
                print("[CheckConnection] Socket chưa kết nối. Đang thử kết nối lại...")
                asyncio.create_task(soc_util.connect_socket())
                await asyncio.sleep(5)  # Chờ một chút để kết nối
            else:
                result = await check_connection_endpoint()
                print(f"[CheckConnection] {result}")
        except Exception as e:
            print(f"[CheckConnection] Error: {e}")

        await asyncio.sleep(30)

async def periodic_check_machine_id():
    """Kiểm tra định kỳ mỗi 30 giây nếu machine_id trong config thay đổi.
    Nếu phát hiện thay đổi, tự động xóa session cũ và đăng nhập lại với máy mới."""
    last_known_machine_id = None
    while True:
        try:
            await asyncio.sleep(30)

            creds = cfg.read_credentials(_config_path)
            if not cfg.has_valid_credentials(creds) or not creds['machine_id']:
                continue

            new_machine_id = creds['machine_id']

            # Lưu machine_id lần đầu để làm mốc so sánh
            if last_known_machine_id is None:
                last_known_machine_id = new_machine_id
                continue

            # Nếu machine_id thay đổi so với lần kiểm tra trước
            if new_machine_id != last_known_machine_id:
                print(f"[MachineWatch] Phát hiện machine_id thay đổi: '{last_known_machine_id}' → '{new_machine_id}'")
                print("[MachineWatch] Đang xóa session cũ và đăng nhập lại với máy mới...")

                # Reset session
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, hdl.resetSecret, 'session')
                await loop.run_in_executor(None, hdl.resetSecret, 'local')
                await soc_util.close_socket_connection()

                # Cập nhật mốc mới
                last_known_machine_id = new_machine_id

                # Thực hiện auto-login với machine_id mới
                agent_id = await cAgent.verify(agentDomain, agentDevice)
                if not agent_id:
                    print("[MachineWatch] Lỗi: Xác minh đại lý thất bại.")
                    continue

                user_id = await cUser.verify(creds['username'], creds['password'])
                if not user_id:
                    print("[MachineWatch] Lỗi: Đăng nhập thất bại. Kiểm tra lại username/password.")
                    continue

                machine_id = await cMachine.verify(user_id, creds['machine_id'])
                if not machine_id:
                    print(f"[MachineWatch] Lỗi: Không tìm thấy máy với ID '{creds['machine_id']}' trong tài khoản.")
                    continue

                print(f"[MachineWatch] Đăng nhập và xác thực máy in '{creds['machine_id']}' thành công!")
                asyncio.create_task(soc_util.connect_socket())
        except Exception as e:
            print(f"[MachineWatch] Lỗi: {e}")

async def periodic_refresh_session():
    """Làm mới token tự động mỗi 10 phút nếu người dùng đã đăng nhập."""
    while True:
        try:
            # Ngủ 10 phút (600 giây) trước khi bắt đầu chu kỳ tiếp theo
            await asyncio.sleep(600)

            # Chỉ tiến hành nếu đã đăng nhập
            tempProfileUser = await hdl.getSecret('profile_user', 'session')
            if tempProfileUser:
                print(f"[PeriodicRefresh] {datetime.datetime.now()} - Bắt đầu tự động làm mới phiên làm việc...")
                # Gọi refreshSession qua wrapper handle_refresh logic
                result = await perform_refresh_session()
                print(f"[PeriodicRefresh] Kết quả: {result}")
            else:
                print(f"[PeriodicRefresh] {datetime.datetime.now()} - Chưa đăng nhập, bỏ qua làm mới.")
        except Exception as e:
            print(f"[PeriodicRefresh] Lỗi: {e}")

async def perform_refresh_session():
    """Logic cốt lõi để làm mới phiên làm việc, có thể gọi từ API hoặc tác vụ nền."""
    try:
        # 1. Lấy thông tin hiện tại từ secret (nếu có)
        tempProfileUser = await hdl.getSecret('profile_user', 'session')
        tempProfileMachine = await hdl.getSecret('profile_machine', 'session')

        if not tempProfileUser or not tempProfileMachine:
            return {"status": "error", "message": "Không tìm thấy thông tin phiên làm việc cũ."}

        profileUser = json.loads(tempProfileUser)
        profileMachine = json.loads(tempProfileMachine)
        userId = profileUser['v_id']
        machineIdentifyNumber = profileMachine['o_identify_number']

        # 2. Ngắt kết nối socket cũ
        await soc_util.close_socket_connection()

        # 3. Làm mới cấu hình Agent
        agent_id = await cAgent.verify(agentDomain, agentDevice)
        if not agent_id:
            return {"status": "error", "message": "Xác minh đại lý thất bại khi làm mới."}

        # 4. Làm mới Profile User (Handler sẽ tự động dùng refresh token nếu access token hết hạn)
        newProfile = await cUser.getProfile()
        if 'error' in newProfile:
             return {"status": "error", "message": f"Không thể lấy profile mới: {newProfile['error']}"}

        tempProfileUserJson = json.dumps(newProfile['data'])
        await hdl.setSecret('profile_user', tempProfileUserJson, 'session')

        # 5. Làm mới thông tin Machine
        new_machine_id = await cMachine.verify(userId, machineIdentifyNumber)
        if not new_machine_id:
            return {"status": "error", "message": "Xác minh thiết bị thất bại khi làm mới."}

        # 6. Kết nối lại socket
        asyncio.create_task(soc_util.connect_socket())

        return {"status": "success", "message": "Đã làm mới phiên làm việc và kết nối lại thành công."}
    except Exception as e:
        print(f"Lỗi khi thực hiện perform_refresh_session: {e}")
        return {"status": "error", "message": f"Lỗi hệ thống: {e}"}

@app.post("/refresh")
async def refreshSession(request: Request):
    print("Đang tiến hành làm mới phiên làm việc (Refresh Session) theo yêu cầu người dùng...")
    return await perform_refresh_session()

# Additional information.
@app.get("/secrets")
def readAllSecret(
    session: Session = Depends(getSession),
    offset: int = 0,
    limit: int = 100,
):
    secrets = session.exec(select(Secret).offset(offset).limit(limit)).all()
    return secrets


# ============================================================
# Machine Info API endpoint
# ============================================================
@app.get("/machine/info")
async def get_machine_info(request: Request):
    """
    Returns Machine Info as JSON for external consumers (e.g., Moonraker,
    Fluidd/Mainsail dashboard widgets, or custom scripts).

    Response format:
    {
        "machine_id": "PRN-01",
        "machine_name": "My Printer",
        "status": "connected",
        "connected": true,
        "last_seen": "2026-06-12T09:30:15",
        "timestamp": "2026-06-12T09:30:15"
    }
    """
    from src.database.sqlite3 import SocketStatus, engine
    from sqlmodel import select, Session

    # Default response when not logged in
    result = {
        "machine_id": "",
        "machine_name": "",
        "status": "disconnected",
        "connected": False,
        "last_seen": "",
        "timestamp": ""
    }

    # Check if user is logged in
    tempProfileUser = await hdl.getSecret('profile_user', 'session')
    if not tempProfileUser:
        return result

    profileUser = json.loads(tempProfileUser)

    tempProfileMachine = await hdl.getSecret('profile_machine', 'session')
    if not tempProfileMachine:
        return result

    profileMachine = json.loads(tempProfileMachine)

    # Get socket connection status from DB
    socket_status_entry = None
    try:
        with Session(engine) as session:
            socket_status_entry = session.exec(
                select(SocketStatus).limit(1)
            ).first()
    except Exception:
        pass

    is_connected = socket_status_entry.is_connected if socket_status_entry else False
    last_seen = socket_status_entry.timestamp.isoformat() if socket_status_entry and socket_status_entry.timestamp else ""

    result = {
        "machine_id": profileMachine.get('o_identify_number', ''),
        "machine_name": profileMachine.get('v_name', ''),
        "status": "connected" if is_connected else "disconnected",
        "connected": is_connected,
        "last_seen": last_seen,
        "timestamp": datetime.datetime.now().isoformat()
    }

    return result


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False, workers=1)