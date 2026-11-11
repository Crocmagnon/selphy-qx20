"""Experiment: can Pythonista join a Wi-Fi network through NEHotspotConfiguration?

Asks for the SSID and password at runtime; nothing is stored.
"""
import ctypes
import threading

import console
from objc_util import ObjCBlock, ObjCClass, ObjCInstance, ns

ctypes.cdll.LoadLibrary("/System/Library/Frameworks/NetworkExtension.framework/NetworkExtension")
NEHotspotConfiguration = ObjCClass("NEHotspotConfiguration")
NEHotspotConfigurationManager = ObjCClass("NEHotspotConfigurationManager")

ssid = console.input_alert("SSID de l'imprimante")
password = console.password_alert("Mot de passe")

conf = NEHotspotConfiguration.alloc().initWithSSID_passphrase_isWEP_(ns(ssid), ns(password), False)
conf.setJoinOnce_(False)

done = threading.Event()
result = {}


def handler(_block, error):
    result["error"] = ObjCInstance(error) if error else None
    done.set()


block = ObjCBlock(handler, restype=None, argtypes=[ctypes.c_void_p, ctypes.c_void_p])
NEHotspotConfigurationManager.sharedManager().applyConfiguration_completionHandler_(conf, block)

if not done.wait(30):
    print("pas de réponse au bout de 30 s")
elif result["error"] is None:
    print("OK : iOS a accepté la configuration")
else:
    err = result["error"]
    print("refusé :", err.domain(), err.code(), err.localizedDescription())
