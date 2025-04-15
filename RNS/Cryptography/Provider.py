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

import importlib.util

PROVIDER_NONE     = 0x00
PROVIDER_INTERNAL = 0x01
PROVIDER_PYCA     = 0x02

FORCE_INTERNAL = False
PROVIDER = PROVIDER_NONE

pyca_v = None
use_pyca = False

try:
    if not FORCE_INTERNAL and importlib.util.find_spec('cryptography') != None:
        import cryptography
        pyca_v = cryptography.__version__
        v = pyca_v.split(".")

        if int(v[0]) == 2:
            if int(v[1]) >= 8:
                use_pyca = True
        elif int(v[0]) >= 3:
            use_pyca = True

except Exception as e:
    pass

if use_pyca:
    PROVIDER = PROVIDER_PYCA
else:
    PROVIDER = PROVIDER_INTERNAL

def backend():
    if PROVIDER == PROVIDER_NONE:
        return "none"
    elif PROVIDER == PROVIDER_INTERNAL:
        return "internal"
    elif PROVIDER == PROVIDER_PYCA:
        return "openssl, PyCA "+str(pyca_v)