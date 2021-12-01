def get_platform():
    from os import environ
    if 'ANDROID_ARGUMENT' in environ:
        return 'android'
    else:
        import sys
        return sys.platform