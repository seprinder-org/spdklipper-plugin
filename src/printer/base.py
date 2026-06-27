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
        
        Now tracks real-time progress from Klipper's print_stats and virtual_sdcard:
        - print_duration (elapsed time)
        - filament_used
        - progress (0.0 to 1.0 from virtual_sdcard)
        - state (printing -> complete)
        - current_layer / total_layer (from print_stats.info)
        - speed (from gcode_move.speed_factor)
        - flow (from gcode_move.extrude_factor)
        - filename (from print_stats.filename)
        
        Calls progress_callback (if provided in kwargs) periodically with:
        {
            'print_duration': float,  # seconds
            'filament_used': float,   # mm
            'progress': float,        # 0.0 to 1.0 from virtual_sdcard
            'state': str,             # printing/complete/error
            'total_duration': float,  # total time including non-printing
            'current_layer': int,     # current layer number
            'total_layer': int,       # total layer count
            'speed': float,           # speed factor (0.0-1.0) or actual mm/s
            'flow': float,            # flow factor (0.0-1.0) or actual mm³/s
            'filename': str,          # current printing filename
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
                # Use the detailed stats query that includes gcode_move and toolhead
                detail_data = {}
                try:
                    detail_data = await self.getPrintStatsDetail()
                except Exception:
                    pass  # detailed endpoint may not be available on older Klipper versions
                
                # Fallback to individual queries if detail fails
                if not detail_data or 'result' not in detail_data:
                    print_stat = await self.getPrintStat()
                    progress_data = {}
                    try:
                        progress_data = await self.getPrintProgress()
                    except Exception:
                        pass
                    detail_data = print_stat if print_stat else {}
                    if progress_data and 'result' in progress_data:
                        if 'result' not in detail_data:
                            detail_data['result'] = {'status': {}}
                        if 'status' not in detail_data['result']:
                            detail_data['result']['status'] = {}
                        if 'virtual_sdcard' in progress_data['result'].get('status', {}):
                            detail_data['result']['status']['virtual_sdcard'] = progress_data['result']['status']['virtual_sdcard']
                
                if detail_data and 'result' in detail_data and 'status' in detail_data['result']:
                    status_data = detail_data['result']['status']
                    stats = status_data.get('print_stats', {})
                    state = stats.get('state', '')
                    print_duration = stats.get('print_duration', 0)
                    filament_used = stats.get('filament_used', 0)
                    total_duration = stats.get('total_duration', 0)
                    
                    # Extract progress from virtual_sdcard (0.0 to 1.0)
                    progress = None
                    v_sdcard = status_data.get('virtual_sdcard', {})
                    if v_sdcard:
                        progress = v_sdcard.get('progress')
                    
                    # Extract layer info from print_stats.info
                    current_layer = None
                    total_layer = None
                    stats_info = stats.get('info', {})
                    if stats_info:
                        current_layer = stats_info.get('current_layer')
                        total_layer = stats_info.get('total_layer')
                    
                    # Extract speed and flow from gcode_move
                    speed = None
                    flow = None
                    gcode_move = status_data.get('gcode_move', {})
                    if gcode_move:
                        # speed_factor: 1.0 = 100%, extrude_factor: 1.0 = 100%
                        speed_factor = gcode_move.get('speed_factor')
                        extrude_factor = gcode_move.get('extrude_factor')
                        if speed_factor is not None:
                            speed = speed_factor  # ratio 0.0-1.0
                        if extrude_factor is not None:
                            flow = extrude_factor  # ratio 0.0-1.0
                    
                    # Get filename from print_stats
                    klipper_filename = stats.get('filename', '')
                    
                    # Send progress update periodically
                    now = asyncio.get_event_loop().time()
                    if progress_callback and (now - last_notify_time >= notify_interval):
                        last_notify_time = now
                        await progress_callback({
                            'print_duration': print_duration,
                            'filament_used': filament_used,
                            'progress': progress,
                            'state': state,
                            'total_duration': total_duration,
                            'current_layer': current_layer,
                            'total_layer': total_layer,
                            'speed': speed,
                            'flow': flow,
                            'filename': klipper_filename,
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
                                'progress': 1.0,  # Force 100% on completion
                                'state': 'complete',
                                'total_duration': total_duration,
                                'current_layer': current_layer,
                                'total_layer': total_layer,
                                'speed': speed,
                                'flow': flow,
                                'filename': klipper_filename,
                            })
                    elif state == 'error':
                        print(f'[doJob] Print error: {stats.get("message", "")}')
                        isCompleted = True
                        rslt = False
                        if progress_callback:
                            await progress_callback({
                                'print_duration': print_duration,
                                'filament_used': filament_used,
                                'progress': progress,
                                'state': 'error',
                                'total_duration': total_duration,
                                'current_layer': current_layer,
                                'total_layer': total_layer,
                                'speed': speed,
                                'flow': flow,
                                'filename': klipper_filename,
                            })
                    elif state == 'cancelled':
                        print('[doJob] Print was cancelled.')
                        isCompleted = True
                        rslt = False
                        if progress_callback:
                            await progress_callback({
                                'print_duration': print_duration,
                                'filament_used': filament_used,
                                'progress': progress,
                                'state': 'cancelled',
                                'total_duration': total_duration,
                                'current_layer': current_layer,
                                'total_layer': total_layer,
                                'speed': speed,
                                'flow': flow,
                                'filename': klipper_filename,
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
