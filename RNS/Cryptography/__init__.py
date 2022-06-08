import os
import glob

from .Hashes import sha256
from .HKDF import hkdf
from .PKCS7 import PKCS7
from .Fernet import Fernet

import RNS.Cryptography.Provider as cp

if cp.PROVIDER == cp.PROVIDER_INTERNAL:
    from RNS.Cryptography.X25519 import X25519PrivateKey, X25519PublicKey

    # TODO: Use internal Ed25519
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

elif cp.PROVIDER == cp.PROVIDER_PYCA:
    from RNS.Cryptography.Proxies import X25519PrivateKeyProxy as X25519PrivateKey
    from RNS.Cryptography.Proxies import X25519PublicKeyProxy as X25519PublicKey

modules = glob.glob(os.path.dirname(__file__)+"/*.py")
__all__ = [ os.path.basename(f)[:-3] for f in modules if not f.endswith('__init__.py')]
