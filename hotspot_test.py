"""Experiment: can Pythonista join a Wi-Fi network through NEHotspotConfiguration?

Asks for the SSID and password at runtime; nothing is stored. Every step is appended to
hotspot_test.log next to this script, flushed to disk, so the log survives a crash.
"""
import ctypes
import os
import threading
import time

import console
from objc_util import ObjCBlock, ObjCClass, ObjCInstance, ns

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hotspot_test.log")


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
        f.flush()
        os.fsync(f.fileno())
    print(msg)


log("--- start")
ctypes.cdll.LoadLibrary("/System/Library/Frameworks/NetworkExtension.framework/NetworkExtension")
NEHotspotConfiguration = ObjCClass("NEHotspotConfiguration")
NEHotspotConfigurationManager = ObjCClass("NEHotspotConfigurationManager")
log("framework loaded")

with_callback = console.alert("Mode", "", "Sans callback", "Avec callback", hide_cancel_button=True) == 2
log(f"mode: {'with' if with_callback else 'without'} callback")
ssid = console.input_alert("SSID de l'imprimante")
password = console.password_alert("Mot de passe")
log("inputs ok")

conf = NEHotspotConfiguration.alloc().initWithSSID_passphrase_isWEP_(ns(ssid), ns(password), False)
log(f"config created: {conf is not None}")
conf.setJoinOnce_(False)
log("joinOnce set")
manager = NEHotspotConfigurationManager.sharedManager()
log(f"manager: {manager is not None}")

if not with_callback:
    manager.applyConfiguration_completionHandler_(conf, None)
    log("apply called (no callback), waiting 20 s for an iOS prompt")
    time.sleep(20)
    log("end")
else:
    done = threading.Event()
    result = {}

    def handler(_block, error):
        log("callback entered")
        result["error"] = ObjCInstance(error) if error else None
        done.set()

    block = ObjCBlock(handler, restype=None, argtypes=[ctypes.c_void_p, ctypes.c_void_p])
    log("block created")
    manager.applyConfiguration_completionHandler_(conf, block)
    log("apply called")
    if not done.wait(30):
        log("no callback after 30 s")
    elif result["error"] is None:
        log("OK: iOS accepted the configuration")
    else:
        err = result["error"]
        log(f"refused: {err.domain()} {err.code()} {err.localizedDescription()}")
