import aiohttp, ssl, certifi, asyncio;
async def t():
    ssl_ctx = ssl.create_default_context(cafile=certifi.where());
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as s:
        async with s.get('https://api.github.com/repos/seprinder-org/failure-ai-detection-in-3d-printing/contents/model') as r:
            print(r.status)
asyncio.run(t())