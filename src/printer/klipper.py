import aiohttp
import zipfile
from io import BytesIO

from src.printer.base import BasePrinter

class KlipperPrinter(BasePrinter):
    def __init__(self, address_control: str):
        super().__init__(address_control)
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
        url = f'{self.address_control}/printer/info'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as res:
                val = await res.json()
        return val

    async def getTemperature(self):
        val = {}
        url = f'{self.address_control}/server/temperature_store?include_monitors=false'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as res:
                val = await res.json()
        return val

    async def runHome(self):
        rslt = False
        val = {}
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
        url = f'{self.address_control}/printer/objects/query?print_stats'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as res:
                val = await res.json()
        return val

    async def isReadyState(self):
        """
        Kiểm tra máy in đã sẵn sàng nhận lệnh in mới chưa.
        - Nếu đang 'printing' → chưa sẵn sàng (busy)
        - Nếu 'complete', 'error', 'cancelled' → tự động reset file để về standby
        - Nếu 'standby' hoặc state khác không phải 'printing' → sẵn sàng
        """
        rslt = False
        res = await self.getPrintStat()
        try:
            state = res['result']['status']['print_stats']['state']
            if state == 'printing':
                rslt = False
            elif state in ('complete', 'error', 'cancelled'):
                # Klipper giữ file cũ trong bộ nhớ, cần reset để in file mới
                print(f'Klipper state is "{state}". Resetting job state before accepting new job...')
                reset_ok = await self.resetJobState()
                if reset_ok:
                    rslt = True
                else:
                    print('Failed to reset Klipper job state.')
                    rslt = False
            else:
                # 'standby' hoặc các state khác → sẵn sàng
                rslt = True
        except (KeyError, TypeError):
            pass
        return rslt

    async def resetJobState(self):
        """
        Gửi lệnh SDCARD_RESET_FILE để clear file cũ khỏi bộ nhớ Klipper.
        Cần thiết khi Klipper ở state 'complete' để có thể in file mới.
        """
        rslt = False
        val = {}
        url = f'{self.address_control}/printer/gcode/script?script=SDCARD_RESET_FILE'
        async with aiohttp.ClientSession() as session:
            async with session.post(url) as res:
                val = await res.json()
        if val.get('result') == 'ok':
            rslt = True
        return rslt

    async def runCancel(self):
        rslt = False
        val = {}
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

    # async def captureImage(self, addressCamera: str, file_path: str):
    #     rslt = False
    #     if self.mock:
    #         # Create a dummy image
    #         try:
    #             # White pixel JPEG
    #             dummy_jpg = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\xff\xc0\x00\x11\x08\x00\x10\x00\x10\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x15\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\bf\xa2\x8a\x28\x00\xff\xd9'
    #             with open(file_path, "wb") as f:
    #                  f.write(dummy_jpg)
    #             val = True
    #         except:
    #             val = False
    #     else:
    #         val = False
    #         if addressCamera:
    #             snapshot_url = addressCamera.replace('action=stream', 'action=snapshot')
    #             async with aiohttp.ClientSession() as session:
    #                 async with session.get(snapshot_url) as res:
    #                     if res.status == 200:
    #                         data = await res.read()
    #                         with open(file_path, "wb") as f:
    #                             f.write(data)
    #                         val = True
        
    #     if val == True:
    #         rslt = True
    #     return rslt

    # Additional Klipper specific methods
    async def runRestart(self):
        rslt = False
        val = {}
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
        url = f'{self.address_control}/printer/gcode/script?script={script}'
        async with aiohttp.ClientSession() as session:
            async with session.post(url) as res:
                val = await res.json()
        
        if val.get('result') == 'ok':
            rslt = True
        return rslt
