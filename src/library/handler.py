from io import BytesIO
import shutil
import json
import zipfile
import xml.etree.ElementTree as ET
import asyncio
import aiohttp
import threading
import re
import base64
import os # Thêm import os
import hashlib
import ssl
try:
    import certifi
except ImportError:
    certifi = None

from sqlmodel import Session, select
from src.database.sqlite3 import Secret, engine
from libs import socket_manager as soc
from src.library import exception as exp
from src.controller import cUser
from cryptography.fernet import Fernet

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

# SPD_SECRET_KEY is OPTIONAL in .env for security.
# If not set, the system auto-generates a key on first run and stores it
# in the database (see loadKey()). This means even if .env is leaked,
# the master encryption key remains protected inside the SQLite DB.
# On Raspberry Pi, both .env and db.sqlite3 should have chmod 600.
spdSecretKey = os.getenv('SPD_SECRET_KEY') or ''  # Optional: master key from env
pathDb = os.getenv('PATH_DB')

secretKey = None

# This function is run inside a normal function and cannot use prefix await.
def runAsyncTaskWithoutAwait(_rtrn, _func , *args):
    def asyncRun():
        asyncio.run(_func(*args))
    rslt = False
    if _rtrn == False:
        threading.Thread(target=asyncRun).start()
        rslt = True
    else:
        rslt = asyncio.run(runAsyncTaskWithAwait(True, _func, *args))
    return rslt

# This function is run insde an async function as usual.
async def runAsyncTaskWithAwait(_rtrn, _func , *args):
    rslt = False
    task = asyncio.get_event_loop().create_task(_func(*args))
    if _rtrn == False:
        rslt = True
    else:
        await task
        rslt = task.result()
        if not rslt:
            rslt = True
    return rslt

async def asyncRequestWithAccess(targetUrl, targetData):
    # thread_sensitive makes the task run in another thread since the main thread is already blocked by websocket.
    accessToken = await getSecret('access_token', 'local')
    refreshToken = await getSecret('refresh_token', 'local')
    try:
        if accessToken == '' and refreshToken == '' and targetData['action'] == 'getProfile':
            raise exp.AuthTokenOffline()
            # raise Exception('Offline')
        configurationAgent = await getSecret('configuration_agent', 'session')
        if configurationAgent == '': # Bookmark, this is a temporary solution.
            configurationAgent = '{"v_domain": "seprinder.com"}'
        lstHeader={'Authorization': f'Bearer {accessToken}', 'X-Agent': configurationAgent}
        
        ssl_context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
        async with aiohttp.ClientSession(headers=lstHeader, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:

            async with session.post(url=targetUrl, json=targetData) as res: # Json as data.
                if res.status == 401:
                    # remove accessToken.
                    await setSecret('access_token', '', 'local')
                    raise exp.AuthAccessTokenExpired()
                    # raise Exception('Try to refresh token.')
                jsRes = await res.json()
                rslt = jsRes['result']

    except Exception as ex:
        msg = str(ex)
        if msg == 'Try to renew an access token.':
            rslt = await cUser.refreshToken(refreshToken)
        else:
            rslt = {'error': msg}
    return rslt

async def asyncRequestWithToken(targetUrl, targetData, token):
    try:
        if token:
            configurationAgent = await getSecret('configuration_agent', 'session')
            if configurationAgent == '': # Bookmark, this is a temporary solution.
                configurationAgent = '{"v_domain": "seprinder.com"}'
            lstHeader={'Authorization': f'Bearer {token}', 'X-Agent': configurationAgent}
            
            ssl_context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
            async with aiohttp.ClientSession(headers=lstHeader, connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:

                async with session.post(url=targetUrl, json=targetData) as res: # Json as data.
                    jsRes = await res.json()
                    rslt = jsRes['result']
                    if 'accessToken' in rslt:
                        accessToken = rslt['accessToken']
                        # set accessToken.
                        await setSecret('access_token', accessToken, 'local')
                        # Instead of raising, return the result indicating success
                        return rslt
                    else:
                        return {'error': 'Logout'}
        else:
            return {'error': 'Offline'}
    except Exception as ex:
        msg = str(ex)
        rslt = {'error': msg}
    return rslt


def getLocale(request):
    pattern = r'(?<=\/)\w{2}'
    pathName = request.path
    find = re.search(pattern, pathName)
    locale = 'en'
    if find:
        locale = find[0]
    rslt = {'locale': locale }
    return rslt

# Encrypt and Decrypt.
def generateKey():
    """
    Generates a key and save it into a file
    """
    key = Fernet.generate_key()
    return key.decode()

async def setSecretKey(name: str, value: str, type: str):
    rslt = False
    with Session(engine) as session:
        try:
            oSecret = session.exec(select(Secret).where(Secret.name == name, Secret.type == type)).first()
        except Exception as ex:
            print(ex)
            oSecret = None

        if oSecret: # If having values then get it.
            oSecret.value = value
        else: # If not having values set a new value.
            oSecret = Secret(name=name, value=value, type=type)
        session.add(oSecret)
        session.commit()
        session.refresh(oSecret)
        rslt = True
    return rslt

async def getSecretKey(name: str, type: str):
    rslt = ''
    with Session(engine) as session:
        try:
            oSecret = session.exec(select(Secret).where(Secret.name == name, Secret.type == type)).first()
        except Exception as ex:
            print(ex)
            oSecret = None

        if oSecret:
            value = oSecret.value
            rslt = value
    return rslt

async def setSecret(name: str, value: str, type: str):
    rslt = False
    with Session(engine) as session:
        encryptName = base64Encode(name)
        encryptValue = await encrypt(value)

        try:
            oSecret = session.exec(select(Secret).where(Secret.name == encryptName, Secret.type == type)).first()
        except Exception as ex:
            print(ex)
            oSecret = None

        if oSecret: # If having values then get it.
            oSecret.value = encryptValue
        else: # If not having values set a new value.
            oSecret = Secret(name=encryptName, value=encryptValue, type=type)
        session.add(oSecret)
        session.commit()
        session.refresh(oSecret)
        rslt = True
    return rslt

async def getSecret(name: str, type: str):
    rslt = ''
    with Session(engine) as session:
        encryptName = base64Encode(name)

        try:
            oSecret = session.exec(select(Secret).where(Secret.name == encryptName, Secret.type == type)).first()
        except Exception as ex:
            print(ex)
            oSecret = None

        if oSecret:
            value = oSecret.value
            rslt = await decrypt(value)
    return rslt

def resetSecret(type: str):
    rslt = False
    with Session(engine) as session:
        try:
            lstSecret = session.exec(select(Secret).where(Secret.type == type)).all()
            if lstSecret:
                for oSecret in lstSecret:
                    session.delete(oSecret)
                session.commit()
            rslt = True
        except Exception as ex:
            print(f"Lỗi khi reset secret: {ex}")
    return rslt

async def encrypt(message):
    """
    Encrypts a message
    """
    rslt = ''
    try:
        encoded_message = message.encode()
        tempKey = (await loadKey()).encode() # Encode the key to bytes
        f = Fernet(tempKey)
        encrypted_message = f.encrypt(encoded_message)
        rslt = encrypted_message.decode()
    except Exception as ex:
        print(ex)
    return rslt

async def decrypt(encrypted_message):
    """
    Decrypts an encrypted message
    """
    rslt = ''
    try:
        encoded = encrypted_message.encode()
        tempKey = (await loadKey()).encode() # Encode the key to bytes
        f = Fernet(tempKey)
        decrypted_message = f.decrypt(encoded)
        rslt = decrypted_message.decode()
    except Exception as ex:
        print(ex)
    return rslt

def base64Encode(txt):
    rslt = ''
    msgBytes = txt.encode('utf-8')
    b64Bytes = base64.b64encode(msgBytes)
    rslt = b64Bytes.decode()
    return rslt

def base64Decode(b64):
    rslt = ''
    b64Bytes = b64.encode('utf-8')
    msgBytes = base64.b64decode(b64Bytes)
    rslt = msgBytes.decode()
    return rslt

async def loadKey():
    """
    Load the master encryption key with the following priority:
    1. From in-memory cache (secretKey global)
    2. From database (Secret table, name='secret_key', type='local')
    3. Auto-generate a new key and persist it to database
    4. Fallback to SPD_SECRET_KEY from .env (if explicitly set)

    SECURITY: The master key is stored in the SQLite database (chmod 600)
    rather than requiring it in .env. This means even if .env is leaked,
    the encryption key remains protected inside the DB.
    """
    global secretKey
    if secretKey is not None:
        return secretKey

    key_name = 'secret_key'
    key_type = 'local'

    # Try to load from database first
    db_value = await getSecretKey(key_name, key_type)
    if db_value:
        secretKey = db_value
        return secretKey

    # If SPD_SECRET_KEY is explicitly set in .env, use it and persist to DB
    if spdSecretKey:
        secretKey = spdSecretKey
        await setSecretKey(key_name, secretKey, key_type)
        return secretKey

    # Auto-generate a new key and persist to database
    secretKey = generateKey()
    await setSecretKey(key_name, secretKey, key_type)
    return secretKey

async def download_file_async(url: str, id: str, machineOsName: str = ''):
    """
    Tải file từ URL và trả về StreamReader cùng với ClientSession.
    Người gọi có trách nhiệm đóng session.
    """
    # Regex để tách tên file từ URL (phần cuối của path trước query parameters)
    # Ví dụ: .../filename.gcode?params... -> filename.gcode
    match = re.search(r'\/([^\/\?]+)(?:\?|$)', url)
    if match:
        filename = match.group(1)
        if filename.endswith('.gcode'):
            filename = id + ".gcode"
        elif filename.endswith('.3mf'):
            filename = id + ".3mf"
    else:
        # Fallback nếu không tách được
        filename = id + (".3mf" if machineOsName == 'Bambu lab' else ".gcode")

    ssl_context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context))
    try:
        response = await session.get(url)
        if response.status != 200:
            await session.close()
            raise Exception(f"Download lỗi: {response.status}")
        
        # Luôn trả về BytesIO để hỗ trợ xử lý file (zip/unzip) dễ dàng hơn cho mọi loại máy in
        return filename, BytesIO(await response.read()), session
            
    except Exception as e:
        await session.close()
        raise e
            
async def delete_file_async(filepath: str):
    """
    Async wrapper để xoá file mà không block event loop.
    Trả về True nếu xoá thành công, False nếu không tồn tại hoặc lỗi.
    Tương thích với Python 3.7 bằng cách dùng run_in_executor thay vì to_thread.
    """
    if not os.path.isfile(filepath):
        print(f"File không tồn tại: {filepath}")
        return False

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, os.remove, filepath)
        return True
    except Exception as e:
        print(f"Lỗi khi xoá file {filepath}: {e}")
        return False

# def deleteDataset():
#     capture_path = Path("detection/spd_dataset/capture")
#     if capture_path.exists() and capture_path.is_dir():
#         try:
#             shutil.rmtree(capture_path)
#             print(f"Đã xoá thư mục: {capture_path}")
#         except Exception as e:
#             print(f"Lỗi khi xoá thư mục {capture_path}: {e}")

# def createDataset():
#     dataset_path = Path("detection/spd_dataset")
#     capture_path = dataset_path / "capture"
#     failure_path = dataset_path / "failure"
#     success_path = dataset_path / "success"

#     # 1. Tạo cấu trúc thư mục bên ngoài nếu chưa có
#     if not dataset_path.exists():
#         try:
#             dataset_path.mkdir()
#             print(f"Đã tạo thư mục: {dataset_path}")
#         except Exception as e:
#             print(f"Lỗi khi tạo thư mục {dataset_path}: {e}")
    
#     for path in [capture_path, failure_path, success_path]:
#         if not path.exists():
#             try:
#                 path.mkdir()
#                 print(f"Đã tạo thư mục: {path}")
#             except Exception as e:
#                 print(f"Lỗi khi tạo thư mục {path}: {e}")

#     # 2. Nếu đang chạy từ file exe (frozen), copy dữ liệu mẫu từ template ra ngoài
#     if getattr(sys, 'frozen', False):
#         # Đường dẫn tới thư mục template nằm trong file exe
#         template_root = Path(sys._MEIPASS) / "dataset_template"
        
#         # Danh sách các thư mục cần copy dữ liệu mẫu
#         sub_dirs = ["failure", "success"]
        
#         for sub in sub_dirs:
#             src_dir = template_root / sub
#             dst_dir = dataset_path / sub
            
#             if src_dir.exists() and dst_dir.exists():
#                 # Lấy danh sách file trong đích để kiểm tra xem đã có file chưa
#                 # Nếu thư mục đích trống hoặc ít file, ta có thể quyết định copy đè hoặc bổ sung.
#                 # Ở đây logic đơn giản: Nếu thư mục đích TRỐNG thì mới copy mẫu ra.
#                 if not any(dst_dir.iterdir()):
#                     print(f"Đang khởi tạo dữ liệu mẫu cho {sub}...")
#                     try:
#                         for item in src_dir.iterdir():
#                             if item.is_file():
#                                 shutil.copy2(item, dst_dir)
#                         print(f"Đã copy xong dữ liệu mẫu cho {sub}")
#                     except Exception as e:
#                         print(f"Lỗi khi copy dữ liệu mẫu cho {sub}: {e}")

def get_3mf_plate_number(file_input) -> int:
    """
    Extracts the active plate number from a .3mf file.
    Accepts a filename (str), bytes, or a file-like object (e.g. BytesIO).
    Default returns 1 if no specific plate is found or on error.
    """
    plate_number = 1
    
    try:
        # If input is bytes, wrap it in BytesIO
        if isinstance(file_input, bytes):
            file_obj = BytesIO(file_input)
        # If input is a string (filename), verify it exists and open it? 
        # Actually ZipFile can handle filename string directly.
        elif isinstance(file_input, str):
            if not os.path.exists(file_input) or not file_input.endswith('.3mf'):
                return 1
            file_obj = file_input
        else:
            # Assume it's a file-like object
            file_obj = file_input
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
                
        if zipfile.is_zipfile(file_obj):
             with zipfile.ZipFile(file_obj, 'r') as z:
                found_in_config = False
                # Method 1: Check Metadata/model_settings.config
                try:
                    if 'Metadata/model_settings.config' in z.namelist():
                        with z.open('Metadata/model_settings.config') as f:
                            tree = ET.parse(f)
                            root = tree.getroot()
                            for plate in root.findall('plate'):
                                gcode_file = None
                                plater_id = None
                                for metadata in plate.findall('metadata'):
                                    key = metadata.get('key')
                                    val = metadata.get('value')
                                    if key == 'gcode_file':
                                        gcode_file = val
                                    elif key == 'plater_id':
                                        plater_id = val
                                
                                # If this plate has a gcode file associated with it, it's the one we want.
                                if gcode_file and len(gcode_file.strip()) > 0 and plater_id:
                                    plate_number = int(plater_id)
                                    found_in_config = True
                                    break
                except Exception as e:
                    print(f"Error parsing model_settings.config: {e}")

                # Method 2: Fallback to file listing if not found in config
                if not found_in_config:
                    files = z.namelist()
                    for f in files:
                        # Look for Metadata/plate_*.gcode
                        match = re.search(r'Metadata/plate_(\d+)\.gcode', f)
                        if match:
                            plate_number = int(match.group(1))
                            break
                            
        # Reset cursor if it's a file object so subsequent reads work
        if hasattr(file_input, 'seek'):
             file_input.seek(0)

    except Exception as e:
        print(f"Error inspecting 3mf file: {e}")
            
    return plate_number

async def ensure_onnx_compatibility(file_path):
    """
    Checks the ONNX Opset and IR version and downgrades them if they exceed 
    max supported versions by older onnxruntime.
    """
    try:
        def _patch_onnx(path):
            try:
                model = onnx.load(str(path))
                modified = False

                # Handle IR Version (Error: Unsupported model IR version: 10, max: 8)
                if model.ir_version > 8:
                    print(f"[ONNX Patch] Detected IR version {model.ir_version} in {path.name}. Downgrading to 8.")
                    model.ir_version = 8
                    modified = True

                # Handle Opset Version
                for imp in model.opset_import:
                    if (imp.domain == '' or imp.domain == 'ai.onnx') and imp.version > 18:
                        print(f"[ONNX Patch] Detected Opset {imp.version} in {path.name}. Downgrading to 18.")
                        imp.version = 18
                        modified = True
                
                if modified:
                    onnx.save(model, str(path))
                    print(f"[ONNX Patch] Model {path.name} saved with updated compatibility.")
            except Exception as e:
                 print(f"[ONNX Patch Internal Error] {e}")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _patch_onnx, file_path)
    except Exception as e:
        print(f"[ONNX Patch Error] {e}")

# async def createModel():
#     model_path = Path("detection/model")
#     if not model_path.exists():
#         try:
#             model_path.mkdir(parents=True, exist_ok=True)
#             print(f"Đã tạo thư mục: {model_path}")
#         except Exception as e:
#             print(f"Lỗi khi tạo thư mục {model_path}: {e}")
#             return

#     api_url = "https://api.github.com/repos/seprinder-org/failure-ai-detection-in-3d-printing/contents/model"
    
#     try:
#         ssl_context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
#         async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
#             async with session.get(api_url) as resp:
#                 if resp.status == 200:
#                     files = await resp.json()
                    
#                     # Helper function to calculate Git SHA of a local file
#                     def calculate_git_sha(filepath):
#                         try:
#                             filesize = os.path.getsize(filepath)
#                             sha1 = hashlib.sha1()
#                             # Git blob header: "blob <content_length>\0"
#                             sha1.update(f"blob {filesize}\0".encode())
#                             with open(filepath, 'rb') as f:
#                                 while True:
#                                     chunk = f.read(65536)
#                                     if not chunk:
#                                         break
#                                     sha1.update(chunk)
#                             return sha1.hexdigest()
#                         except Exception as e:
#                             print(f"Lỗi tính hash file {filepath}: {e}")
#                             return None

#                     for file in files:
#                         name = file['name']
#                         download_url = file['download_url']
#                         remote_sha = file.get('sha')
                        
#                         target_name = None
#                         if name.endswith('.onnx'):
#                             target_name = "best.onnx"
#                         elif name.endswith('.cfg'):
#                             target_name = "settings.cfg"
                        
#                         if target_name:
#                             target_file = model_path / target_name
#                             should_download = True
                            
#                             if target_name == 'settings.cfg' and target_file.exists():
#                                 print(f"File {target_name} đã tồn tại. Bỏ qua cập nhật để giữ cấu hình riêng.")
#                                 should_download = False
#                             elif target_file.exists():
#                                 local_sha = calculate_git_sha(target_file)
#                                 if local_sha and local_sha == remote_sha:
#                                     print(f"File {target_name} đã tồn tại và giống server (SHA: {local_sha}). Bỏ qua.")
#                                     should_download = False
#                                 else:
#                                     print(f"File {target_name} khác server (Local: {local_sha} != Remote: {remote_sha}). Cập nhật...")
#                             else:
#                                 print(f"File {target_name} chưa có. Tải về...")

#                             if should_download:
#                                 print(f"Đang tải {name} về thành {target_name}...")
#                                 async with session.get(download_url) as file_resp:
#                                     if file_resp.status == 200:
#                                         content = await file_resp.read()
#                                         # Sử dụng run_in_executor cho thao tác ghi file để không block event loop
#                                         loop = asyncio.get_event_loop()
#                                         await loop.run_in_executor(None, lambda: target_file.write_bytes(content))
#                                         print(f"Đã tải xong {target_name}")

#                                     else:
#                                         print(f"Lỗi khi tải {name}: Status {file_resp.status}")

#                             # Check and patch ONNX version for both new and existing files
#                             if target_name.endswith('.onnx'):
#                                 await ensure_onnx_compatibility(target_file)
#                 else:
#                     print(f"Không thể lấy danh sách file từ Github. Status: {resp.status}")
#     except Exception as e:
#         print(f"Lỗi trong quá trình tạo model: {e}")