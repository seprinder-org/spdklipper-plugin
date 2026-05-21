from sqlmodel import Field, Session, SQLModel, create_engine
import os
from datetime import datetime

# Start load env.
from dotenv import load_dotenv
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Đang chạy từ file .exe/.bin đã được PyInstaller build
    base_path = Path(sys._MEIPASS)
else:
    base_path = Path(os.getcwd())

load_dotenv(dotenv_path=base_path / ".env", override=True) # Load environment variables at the very beginning, overriding existing ones
# End load env.

pathDb = os.getenv('PATH_DB')
sqliteUrl = f"sqlite:///{pathDb}"

connectArgs = {"check_same_thread": False}
engine = create_engine(sqliteUrl, connect_args=connectArgs)

class Secret(SQLModel, table=True):
    name: str = Field(primary_key=True) # Name of secret. This is also a primary key.
    value: str # Value of secret.
    type: str # Local or Session.

class ServerLog(SQLModel, table=True):
    __mapper_args__ = {"confirm_deleted_rows": False} # Fix warning.
    id: int = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now)
    message: str

class SocketStatus(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    is_connected: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=datetime.now)

def createDbAndTbl():
    SQLModel.metadata.create_all(engine)
    # Ensure database file has restricted permissions (owner-only)
    _restrict_db_permissions()

def _restrict_db_permissions():
    """Restrict database file permissions to owner-only (0600) on Unix systems."""
    try:
        if os.path.exists(pathDb):
            # Set file to owner read/write only
            os.chmod(pathDb, 0o600)
    except Exception:
        pass  # Best-effort on Windows or permission-limited environments

def getSession():
    with Session(engine) as session:
        yield session
