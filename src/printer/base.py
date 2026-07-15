import asyncio
import aiohttp
import sys
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod


class BasePrinter(ABC):
    def __init__(self, address_control: str, **kwargs):
        self.address_control = address_control
        self.kwargs = kwargs

    # Default - Start.
    @abstractmethod
    async def runHome(self):
        pass

    @abstractmethod
    async def getTemperature(self):
        pass

    @abstractmethod
    async def getPrintStat(self):
        pass

    @abstractmethod
    async def isReadyState(self):
        pass
    
    # Trả response về server để cập nhật job này đã xong.
    async def doJob(self, filename: str, **kwargs):
        """
        Default implementation for basic job execution loop.
        Chạy trong background task (create_task) để không block các sự kiện socket khác.
        
        Trong mỗi vòng lặp kiểm tra, thu thập nhiệt độ đầu in và bàn in,
        sau đó gọi progress_callback (nếu có) để gửi dữ liệu về server.
        """
        rslt = False
        progress_callback = kwargs.get('progress_callback')
        
        # Start the print job
        started = await self.printModel(filename, **kwargs)
        # We assume truthy return means started successfully or returned valid JSON
        if started == False:
            return False

        # Wait a moment for Klipper to register the print state
        await asyncio.sleep(3)

        # Loop to check for completion with real-time progress tracking
        isCompleted = False
        last_notify_time = 0
        notify_interval = 10  # seconds between progress notifications
        
        while not isCompleted:
            # Check status every 5 seconds for more responsive progress tracking
            await asyncio.sleep(5)
            
            # Thu thập nhiệt độ hiện tại và gửi qua callback
            if progress_callback:
                try:
                    temp_data = await self.getTemperature()
                    print_stat = await self.getPrintStat()
                    
                    # Trích xuất thông tin từ print_stat
                    print_stats_status = {}
                    try:
                        print_stats_status = print_stat['result']['status']['print_stats']
                    except (KeyError, TypeError):
                        pass
                    
                    progress = {
                        'temperature': temp_data,
                        'print_duration': print_stats_status.get('print_duration', 0),
                        'filament_used': print_stats_status.get('filament_used', 0),
                        'state': print_stats_status.get('state', ''),
                    }
                    await progress_callback(progress)
                except Exception as e:
                    print(f'[doJob] Error collecting progress data: {e}')
            
            # Check if printer is ready (meaning job finished)
            if await self.isReadyState():
                isCompleted = True
                rslt = True
                
        return rslt

    # async def doJobWithFailureDetection(self, filename: str, targetJobId: str, addressCamera: str, **kwargs):
    #     """
    #     Reserved for future use with camera-based failure detection.
    #     """
    #     pass

    @abstractmethod
    async def runCancel(self):
        pass

    @abstractmethod
    async def removeFile(self, filename: str):
        pass

    @abstractmethod
    async def uploadFile(self, filename: str, file_stream):
        pass

    # Default - End.

    # # # Additional function.
    async def getInfoMachine(self):
        pass

    async def runPause(self):
        pass

    async def runResume(self):
        pass

    async def runShutdown(self):
        pass

    async def runRestart(self):
        pass

    async def runScript(self):
        pass
        
    # Helpers for subclasses to implement
    @abstractmethod
    async def printModel(self, filename: str, **kwargs):
        """
        Implementation specific to starting a print job.
        Should return True/dict on success.
        """
        pass
