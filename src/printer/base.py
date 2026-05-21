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
        """
        rslt = False
        
        # Start the print job
        started = await self.printModel(filename, **kwargs)
        # We assume truthy return means started successfully or returned valid JSON
        if started == False:
            return False

        # Loop to check for completion
        isCompleted = False
        while not isCompleted:
            # Check status every 15 seconds
            await asyncio.sleep(15)
            
            # Check if printer is ready (meaning job finished)
            if await self.isReadyState():
                isCompleted = True
                rslt = True
                
        return rslt

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
