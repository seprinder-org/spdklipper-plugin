from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent.parent

PATH = '/socket'
AGENT_DOMAIN = 'seprinder.com'
AGENT_DEVICE = 'browser'
PORT = 1122 # Fixed port for the FastAPI server.
PATH_DB = str(BASE_PATH / 'db.sqlite3')
SPD_SECRET_KEY = '' # Optional: master key

# Production SPD servers
HOST_CONNECT = 'wss://connect.seprinder.com'
HOST_SERVER = 'https://seprinder.com'

# # local
# HOST_SERVER = 'http://localhost:3000'
# HOST_CONNECT = 'ws://localhost:3030'