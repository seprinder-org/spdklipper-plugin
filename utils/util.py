from libs.socket_manager import manager, _connect_to_socketio
from constants.constant import HOST_CONNECT as hostConnect, PATH as path
from src.library import handler as hdl
import json
import socketio
import asyncio
import sys
import os
from pathlib import Path


async def connect_socket():
    """Tạo và duy trì kết nối socket."""
    if manager.is_connecting:
        print('Socket connection is already in progress...')
        return

    # Luôn tạo một instance client mới nếu không có hoặc đã bị ngắt kết nối
    if manager.client is None or not manager.client.connected:
        manager.is_connecting = True
        try:
            await manager.create_client()
            # print(f'Attempting to connect to {hostConnect}{path}...')
            # _connect_to_socketio handles its own printing/logging
            await _connect_to_socketio(manager.client)
        finally:
            manager.is_connecting = False
    else:
        print('Socket client already connected.')

async def close_socket_connection():
    """Đóng kết nối socket hiện tại."""
    if manager.client and manager.client.connected:
        print('Closing socket connection...')
        await manager.client.disconnect()
        print('Socket connection closed.')
        manager.client = None # Đặt client về None sau khi ngắt kết nối
    else:
        print('No active socket connection to close.')