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
        
        Now tracks real-time progress from Klipper's print_stats:
        - print_duration (elapsed time)
        - filament_used
        - state (printing -> complete)
        
        Calls progress_callback (if provided in kwargs) periodically with:
        {
            'print_duration': float,  # seconds
            'filament_used': float,   # mm
            'state': str,             # printing/complete/error
            'total_duration': float   # total time including non-printing
        }
        """
        rslt = False
        progress_callback = kwargs.get('progress_callback', None)
        
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
            
            # Get real-time print stats from Klipper
            try:
                print_stat = await self.getPrintStat()
                if print_stat and 'result' in print_stat and 'status' in print_stat['result']:
                    stats = print_stat['result']['status'].get('print_stats', {})
                    state = stats.get('state', '')
                    print_duration = stats.get('print_duration', 0)
                    filament_used = stats.get('filament_used', 0)
                    total_duration = stats.get('total_duration', 0)
                    
                    # Send progress update periodically
                    now = asyncio.get_event_loop().time()
                    if progress_callback and (now - last_notify_time >= notify_interval):
                        last_notify_time = now
                        await progress_callback({
                            'print_duration': print_duration,
                            'filament_used': filament_used,
                            'state': state,
                            'total_duration': total_duration
                        })
                    
                    # Check if print is complete
                    if state == 'complete':
                        isCompleted = True
                        rslt = True
                        # Send final progress update with completed state
                        if progress_callback:
                            await progress_callback({
                                'print_duration': print_duration,
                                'filament_used': filament_used,
                                'state': 'complete',
                                'total_duration': total_duration
                            })
                    elif state == 'error':
                        print(f'[doJob] Print error: {stats.get("message", "")}')
                        isCompleted = True
                        rslt = False
                        if progress_callback:
                            await progress_callback({
                                'print_duration': print_duration,
                                'filament_used': filament_used,
                                'state': 'error',
                                'total_duration': total_duration
                            })
                    elif state == 'cancelled':
                        print('[doJob] Print was cancelled.')
                        isCompleted = True
                        rslt = False
                        if progress_callback:
                            await progress_callback({
                                'print_duration': print_duration,
                                'filament_used': filament_used,
                                'state': 'cancelled',
                                'total_duration': total_duration
                            })
                    # If 'printing', continue loop
                else:
                    # Fallback to isReadyState if print_stats not available
                    if await self.isReadyState():
                        isCompleted = True
                        rslt = True
            except Exception as e:
                print(f'[doJob] Error checking print status: {e}')
                # Fallback to isReadyState on error
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
