import os
from src.library import handler as hdl
import json

from constants import HOST_SERVER as hostServer


async def readOne(*args):
    [id, filterOwner] = args
    jsData = {
      'target': 'job',
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
        'target': 'job',
        'action': 'readCondition',
        'condition': condition,
        'structure': structure
    }
    url = f'{hostServer}/backend'
    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt

async def notify(targetId, targetStatus, targetEstimatedPrintingTime=None, targetFilamentUsed=None, targetPrintDuration=None):
    jsData = {
        'target': 'job',
        'action': 'notify',
        'targetId': targetId,
        'targetStatus': targetStatus
    }
    import math
    if targetEstimatedPrintingTime is not None:
        jsData['targetEstimatedPrintingTime'] = int(math.ceil(float(targetEstimatedPrintingTime)))
    if targetFilamentUsed is not None:
        jsData['targetFilamentUsed'] = int(math.ceil(float(targetFilamentUsed)))
    if targetPrintDuration is not None:
        jsData['targetPrintDuration'] = int(math.ceil(float(targetPrintDuration)))

    print(f"[cJob.notify] Sending to server: {jsData}")
    url = f'{hostServer}/backend'

    rslt = await hdl.asyncRequestWithAccess(url, jsData)
    return rslt