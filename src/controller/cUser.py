import os
from src.library import handler as hdl
from src.controller import cUser, cMachine
import json

# Start load env.
from dotenv import load_dotenv
import sys
from pathlib import Path
from constants import HOST_SERVER as hostServer
from utils import get_base_path

base_path = get_base_path()

load_dotenv(dotenv_path=base_path / ".env", override=True) # Load environment variables at the very beginning, overriding existing ones
# End load env.



async def refreshToken(*args):
    refreshToken, = args
    jsData = {
        'target': 'user',
        'action': 'refreshToken'
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithToken(url, jsData, refreshToken)
    return rslt

async def verify(emailUsername: str, password: str):
    userId = ''
    try:
        currentUser = await login(emailUsername, password)
        if 'error' in currentUser or 'accessToken' not in currentUser:
            if 'error' in currentUser:
                print(f"Lỗi đăng nhập: {currentUser['error']}")
            return ''

        # Start store token.
        accessToken = currentUser['accessToken']
        await hdl.setSecret('access_token', accessToken, 'local')
        refreshToken = currentUser['refreshToken']
        await hdl.setSecret('refresh_token', refreshToken, 'local')
        # End store token.

        # Start store profile user.
        profileUser = await getProfile()
        if 'error' in profileUser or 'data' not in profileUser:
            if 'error' in profileUser:
                print(f"Lỗi khi lấy thông tin người dùng: {profileUser['error']}")
            return ''

        tempProfileUser = json.dumps(profileUser['data'])
        await hdl.setSecret('profile_user', tempProfileUser, 'session')
        # End store profile user.

        userId = currentUser['data']['id']
    except Exception as e:
        print(f"Ngoại lệ khi xác minh người dùng: {e}")
        pass

    return userId

async def login(emailUsername: str, password: str):
    jsData = {
        'target': 'user',
        'action': 'login',
        'emailUsername': emailUsername,
        'password': password
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

async def logout(*args):
    request, = args
    valid = hdl.resetSecret('session')
    valid = hdl.resetSecret('local')
    if valid == True:
        rslt = {
                    'data': 'success'
                }
        # temp = hdl.getLocale(request)
        # locale = temp['locale']
        # targetPath = f'/{locale}/auth/login'
        # return HttpResponseRedirect(targetPath)
    else:
        rslt = {
                    'error': 'fail'
                }
    return rslt

async def getProfile():
    jsData = {
        'target': 'user',
        'action': 'getProfile'
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

async def refreshToken(*args):
    refreshToken, = args
    jsData = {
        'target': 'user',
        'action': 'refreshToken'
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithToken(url, jsData, refreshToken)
    return rslt

