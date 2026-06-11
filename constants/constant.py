from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent.parent

# HOST_CONNECT = 'wss://connect.seprinder.com'
PATH = '/socket'
# DATASET_ROOT = "detection/spd_dataset"
# HOST_SERVER = 'https://seprinder.com'
AGENT_DOMAIN = 'seprinder.com'
AGENT_DEVICE = 'browser'
PORT = 1122 # Fixed port for the FastAPI server.
PATH_DB = str(BASE_PATH / 'db.sqlite3')
SPD_SECRET_KEY = '' # Optional: master key


# HOST_CONNECT = 'http://192.168.1.108:3030'
# HOST_SERVER = 'http://192.168.1.108:3000'

HOST_CONNECT = 'http://localhost:3030'
HOST_SERVER = 'http://localhost:3000'