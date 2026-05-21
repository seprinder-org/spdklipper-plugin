import asyncio
import aiohttp
import sys
import json
import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from datetime import datetime

from src.printer.base import BasePrinter

class KlipperPrinter(BasePrinter):
    def __init__(self, address_control: str, mock: bool = False):
        super().__init__(address_control)
        self.mock = mock
        # self.target_folder = 'spd' # Remove spd folder since Ender 5 Max cannot read it.
        self.gcode_run_home = 'G28'

    def _extract_3mf_archive_in_memory(self, file_stream) -> BytesIO:
        """
        Extract Metadata/plate_1.gcode from .3mf archive in memory.
        """
        try:
            with zipfile.ZipFile(file_stream, 'r') as zip_ref:
                gcode_content = zip_ref.read("Metadata/plate_1.gcode")
                return BytesIO(gcode_content)
        except Exception as e:
            print(f"Error extracting .3mf: {e}")
            return None

    async def getInfoMachine(self):
        val = {}
        if self.mock:
            val = {
                "result": {
                    "state": "ready",
                    "state_message": "Printer is ready",
                    "hostname": "raspberrypi",
                    "klipper_path": "/home/chien/klipper",
                    "python_path": "/home/chien/klippy-env/bin/python",
                    "process_id": 566,
                    "user_id": 1000,
                    "group_id": 1000,
                    "log_file": "/home/chien/printer_data/logs/klippy.log",
                    "config_file": "/home/chien/printer_data/config/printer.cfg",
                    "software_version": "v0.13.0-347-g3fe594ef",
                    "cpu_info": "4 core ARMv7 Processor rev 4 (v7l)"
                }
            }
        else:
            url = f'{self.address_control}/printer/info'
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as res:
                    val = await res.json()
        return val

    async def getTemperature(self):
        val = {}
        if self.mock:
            val = {
                "result": {
                    "temperature_sensor raspberry": {
                        "temperatures": [66.07, 65.53, 64.99, 65.53, 65.53, 65.53, 65.53, 64.99, 65.53, 65.53]
                    },
                    "heater_bed": {
                        "temperatures": [28.91, 28.9, 28.9, 28.91, 28.93, 28.92, 28.94, 28.92, 28.92, 28.91],
                        "targets": [0.0] * 10
                    },
                    "extruder": {
                        "temperatures": [29.07, 29.07, 29.06, 29.06, 29.06, 29.07, 29.08, 29.09, 29.08, 29.06],
                        "targets": [0.0] * 10
                    }
                }
            }
        else:
            url = f'{self.address_control}/server/temperature_store?include_monitors=false'
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as res:
                    val = await res.json()
        return val

    async def runHome(self):
        rslt = False
        val = {}
        if self.mock:
            val = {"result": "ok"}
        else:
            url = f'{self.address_control}/printer/gcode/script?script={self.gcode_run_home}'
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as res:
                    val = await res.json()
        
        if val.get('result') == 'ok':
            rslt = True
        return rslt

    async def printModel(self, filename: str, **kwargs):
        # Klipper implementation uses spd folder prefix usually
        rslt = False
        val = {}
        
        if self.mock:
            val = {"result": "ok"}
        else:
            target_name = filename
            if filename.endswith('.3mf'):
                target_name = filename.replace('.3mf', '.gcode')
                
            targetFile = f'{target_name}'
            url = f'{self.address_control}/printer/print/start?filename={targetFile}'
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as res:
                    val = await res.json()
        
        # Check result
        if val.get('result') == 'ok':
            rslt = True
        return rslt

    async def getPrintStat(self):
        val = {}
        if self.mock:
            val = {
                "result": {
                    "eventtime": 69482.352456671,
                    "status": {
                        "print_stats": {
                            "filename": "spd/storage_8c68f18c-ee74-11f0-9cab-00d8619b4788.gcode",
                            "total_duration": 563.5267094730002,
                            "print_duration": 479.2465183070003,
                            "filament_used": 310.1952299999999,
                            "state": "complete",
                            "message": "",
                            "info": {
                                "total_layer": None,
                                "current_layer": None
                            }
                        }
                    }
                }
            }
        else:
            url = f'{self.address_control}/printer/objects/query?print_stats'
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as res:
                    val = await res.json()
        return val

    async def isReadyState(self):
        rslt = False
        res = await self.getPrintStat()
        try:
            state = res['result']['status']['print_stats']['state']
            if state != 'printing':
                rslt = True
        except (KeyError, TypeError):
            pass
        return rslt

    async def runCancel(self):
        rslt = False
        val = {}
        if self.mock:
            val = {"result": "ok"}
        else:
            url = f'{self.address_control}/printer/print/cancel'
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as res:
                    val = await res.json()
        if val.get('result') == 'ok':
            rslt = True
        return rslt

    async def runPause(self):
        rslt = False
        val = {}
        if self.mock:
            val = {"result": "ok"}
        else:
            url = f'{self.address_control}/printer/print/pause'
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as res:
                    val = await res.json()
        if val.get('result') == 'ok':
            rslt = True
        return rslt

    async def runResume(self):
        rslt = False
        val = {}
        if self.mock:
            val = {"result": "ok"}
        else:
            url = f'{self.address_control}/printer/print/resume'
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as res:
                    val = await res.json()
        if val.get('result') == 'ok':
            rslt = True
        return rslt

    async def uploadFile(self, filename: str, file_stream):
        target_filename = filename
        final_stream = file_stream
        rslt = False
        val = {}

        if self.mock:
            val = {
                "item": {
                    # "path": f"{self.target_folder}/{filename}",
                    "path": f"{filename}",
                    "root": "gcodes",
                    "modified": 1676984527.636818,
                    "size": 71973,
                    "permissions": "rw"
                },
                "print_started": False,
                "print_queued": False,
                "action": "create_file"
            }
        else:
            url = f'{self.address_control}/server/files/upload'
            
            if filename.endswith('.3mf'):
                final_stream = self._extract_3mf_archive_in_memory(file_stream)
                if final_stream is None:
                    return None
                target_filename = filename.replace('.3mf', '.gcode')

            data = aiohttp.FormData()
            data.add_field('file', final_stream, filename=target_filename, content_type='application/octet-stream')
            # data.add_field('path', self.target_folder)

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as res:
                    val = await res.json()
        
        if isinstance(val, dict):
            rslt = val.get('item', {}).get('path')
        return rslt

    async def removeFile(self, filename: str):
        rslt = False
        val = {}
        if self.mock:
            val = {
                "result": {
                    "action": "delete_file",
                    "item": {
                        "modified": 0,
                        "size": 0,
                        "permissions": "",
                        # "path": f"{self.target_folder}/{filename}",
                        "path": f"{filename}",
                        "root": "gcodes"
                    }
                }
            }
        else:
            target_filename = filename
            if filename.endswith('.3mf'):
                target_filename = filename.replace('.3mf', '.gcode')
            # targetFile = f'{self.target_folder}/{target_filename}'
            targetFile = f'{target_filename}'
            url = f'{self.address_control}/server/files/gcodes/{targetFile}'
            async with aiohttp.ClientSession() as session:
                async with session.delete(url) as res:
                    val = await res.json()
        
        # Check success
        if val.get('result', {}).get('action') == 'delete_file':
            rslt = True
        return rslt

    async def captureImage(self, addressCamera: str, file_path: str):
        rslt = False
        if self.mock:
            # Create a dummy image
            try:
                # White pixel JPEG
                dummy_jpg = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\xff\xc0\x00\x11\x08\x00\x10\x00\x10\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x15\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\bf\xa2\x8a\x28\x00\xff\xd9'
                with open(file_path, "wb") as f:
                     f.write(dummy_jpg)
                val = True
            except:
                val = False
        else:
            val = False
            if addressCamera:
                snapshot_url = addressCamera.replace('action=stream', 'action=snapshot')
                async with aiohttp.ClientSession() as session:
                    async with session.get(snapshot_url) as res:
                        if res.status == 200:
                            data = await res.read()
                            with open(file_path, "wb") as f:
                                f.write(data)
                            val = True
        
        if val == True:
            rslt = True
        return rslt

    # Additional Klipper specific methods
    async def runRestart(self):
        rslt = False
        val = {}
        if self.mock:
            val = {"result": "ok"}
        else:
            url = f'{self.address_control}/printer/firmware_restart'
            async with aiohttp.ClientSession() as session:
                 async with session.post(url) as res:
                    val = await res.json()
        
        if val.get('result') == 'ok':
            rslt = True
        return rslt

    async def runScript(self, script: str):
        rslt = False
        val = {}
        if self.mock:
            val = {"result": "ok"}
        else:
            url = f'{self.address_control}/printer/gcode/script?script={script}'
            async with aiohttp.ClientSession() as session:
                 async with session.post(url) as res:
                    val = await res.json()
        
        if val.get('result') == 'ok':
            rslt = True
        return rslt
