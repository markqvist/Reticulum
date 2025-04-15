# Reticulum License
#
# Copyright (c) 2016-2025 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

def get_platform():
    from os import environ
    if "ANDROID_ARGUMENT" in environ: return "android"
    elif "ANDROID_ROOT" in environ:   return "android"
    else:
        import sys
        return sys.platform

def is_linux():
    if get_platform() == "linux": return True
    else: return False

def is_darwin():
    if get_platform() == "darwin": return True
    else: return False

def is_android():
    if get_platform() == "android": return True
    else: return False

def is_windows():
    if str(get_platform()).startswith("win"): return True
    else: return False

def use_epoll():
    if is_linux() or is_android(): return True
    else: return False

def use_af_unix():
    if is_linux() or is_android(): return True
    else: return False

def platform_checks():
    if is_windows():
        import sys
        if sys.version_info.major >= 3 and sys.version_info.minor >= 8: pass
        else:
            import RNS
            RNS.log("On Windows, Reticulum requires Python 3.8 or higher.", RNS.LOG_ERROR)
            RNS.log("Please update Python to run Reticulum.", RNS.LOG_ERROR)
            RNS.panic()

def cryptography_old_api():
    import cryptography
    if cryptography.__version__ == "2.8": return True
    else: return False
