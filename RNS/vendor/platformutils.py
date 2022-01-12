def get_platform():
    from os import environ
    if 'ANDROID_ARGUMENT' in environ:
        return 'android'
    else:
        import sys
        return sys.platform

def platform_checks():
    if str(get_platform()).startswith("win32"):
        import sys
        if sys.version_info.major >= 3 and sys.version_info.minor >= 8:
            pass
        else:
            import RNS
            RNS.log("On Windows, Reticulum requires Python 3.8 or higher.", RNS.LOG_ERROR)
            RNS.log("Please update Python to run Reticulum.", RNS.LOG_ERROR)
            RNS.panic()