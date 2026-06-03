import os
from src.library import handler as hdl
import json

from constants import HOST_SERVER as hostServer


async def readOne(*args):
    [id, filterOwner] = args
    jsData = {
      'target': 'notification',
      'action': 'readOne',
      'id': id,
      'filterOwner': filterOwner,
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

async def readCondition(*args):
    [condition, structure] = args
    jsData = {
        'target': 'notification',
        'action': 'readCondition',
        'condition': condition,
        'structure': structure
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

async def createOne(*args):
    [record] = args
    jsData = {
        'target': 'notification',
        'action': 'createOne',
        'record': record
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt