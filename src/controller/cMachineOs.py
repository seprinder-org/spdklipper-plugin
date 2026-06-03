import os
from src.library import handler as hdl
import json

from constants import HOST_SERVER as hostServer


async def readOne(*args):
    [id, filterOwner] = args
    jsData = {
      'target': 'machineos',
      'action': 'readOne',
      'id': id,
      'filterOwner': filterOwner,
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt