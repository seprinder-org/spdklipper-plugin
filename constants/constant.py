from pathlib import Path
from typing import Optional

BASE_PATH = Path(__file__).resolve().parent.parent

HOST_CONNECT = 'wss://connect.seprinder.com'
PATH = '/socket'
# DATASET_ROOT = "detection/spd_dataset"
HOST_SERVER = 'https://seprinder.com'
AGENT_DOMAIN = 'seprinder.com'
AGENT_DEVICE = 'browser'
PORT = 1122 # Fixed port for the FastAPI server.
PATH_DB = str(BASE_PATH / 'db.sqlite3')
SPD_SECRET_KEY = '' # Optional: master key


# HOST_CONNECT = 'http://192.168.1.108:3030'
# HOST_SERVER = 'http://192.168.1.108:3000'

# HOST_CONNECT = 'http://localhost:3030'
# HOST_SERVER = 'http://localhost:3000'


def override_from_config(config_path: Optional[Path] = None) -> None:
    """
    Override HOST_SERVER and HOST_CONNECT from spdklipper.conf [server] section.
    Call this once at startup, after resolving the config path.
    """
    from src.library.config_reader import read_server_config

    server_cfg = read_server_config(config_path)

    global HOST_SERVER, HOST_CONNECT

    if server_cfg.get('host_server'):
        old = HOST_SERVER
        HOST_SERVER = server_cfg['host_server']
        print(f"[Config] HOST_SERVER overridden: {old} -> {HOST_SERVER}")

    if server_cfg.get('host_connect'):
        old = HOST_CONNECT
        HOST_CONNECT = server_cfg['host_connect']
        print(f"[Config] HOST_CONNECT overridden: {old} -> {HOST_CONNECT}")