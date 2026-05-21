import aiohttp
import os
import ssl
try:
    import certifi
except ImportError:
    certifi = None

async def requestPut(presignedUrl, mimeType, file_path):
    rslt = False
    try:
        if not os.path.exists(file_path):
            return False

        headers = {
            'Content-Type': mimeType,
        }

        ssl_context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            with open(file_path, 'rb') as f:
                data = f.read()
                async with session.put(presignedUrl, data=data, headers=headers) as response:
                    if response.status == 200:
                        rslt = True
    except Exception as e:
        print(f"Upload error: {e}")
        rslt = False

    return rslt
