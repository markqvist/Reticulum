import importlib

PROVIDER_NONE     = 0x00
PROVIDER_INTERNAL = 0x01
PROVIDER_PYCA     = 0x02

PROVIDER = PROVIDER_NONE

pyca_v = None
use_pyca = False

try:
    if importlib.util.find_spec('cryptography') != None:
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