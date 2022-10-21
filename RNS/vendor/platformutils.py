def get_platform():
    from os import environ
    if "ANDROID_ARGUMENT" in environ:
        return "android"
    elif "ANDROID_ROOT" in environ:
        return "android"
    else:
        import sys
        return sys.platform

def is_linux():
    if get_platform() == "linux":
        return True
    else:
        return False

def is_darwin():
    if get_platform() == "darwin":
        return True
    else:
        return False

def is_android():
    if get_platform() == "android":
        return True
    else:
        return False

def is_windows():
    if str(get_platform()).startswith("win"):
        return True
    else:
        return False

def platform_checks():
    if is_windows():
        import sys
        if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
            pass
        else:
            import RNS
            RNS.log("On Windows, Reticulum requires Python 3.8 or higher.", RNS.LOG_ERROR)
            RNS.log("Please update Python to run Reticulum.", RNS.LOG_ERROR)
            RNS.panic()

def cryptography_old_api():
    import cryptography
    if cryptography.__version__ == "2.8":
        return True
    else:
        return False
