def get_platform():
    from os import environ
    if 'ANDROID_ARGUMENT' in environ:
        return 'android'
    else:
        import sys
        return sys.platform

def platform_checks():
    if str(get_platform()).startswith("win32"):
        if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
            pass
        else:
            RNS.log("On Windows, Reticulum requires Python 3.8 or higher.")
            RNS.log("Please update Python to run Reticulum.")
            RNS.panic()