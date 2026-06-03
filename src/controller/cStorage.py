import os
from src.library import handler as hdl
import json

from constants import HOST_SERVER as hostServer


async def readCondition(*args):
    [condition, structure] = args
    jsData = {
        'target': 'storage',
        'action': 'readCondition',
        'condition': condition,
        'structure': structure
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

async def signGet(*args):
    [id] = args
    jsData = {
        'target': 'storage',
        'action': 'signGet',
        'id': id
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

async def signPut(*args):
    [possessorId, description] = args
    jsData = {
        'target': 'storage',
        'action': 'signPut',
        'possessorId': possessorId,
        'description': description
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt