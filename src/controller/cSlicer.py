import os
from src.library import handler as hdl
import json

from constants import HOST_SERVER as hostServer


async def readCondition(*args):
    [condition, structure] = args
    jsData = {
        'target': 'slicer',
        'action': 'readCondition',
        'condition': condition,
        'structure': structure
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt