import unittest

from .hashes import TestSHA256
from .hashes import TestSHA512
from .identity import TestIdentity
from .link import TestLink

if __name__ == '__main__':
    unittest.main(verbosity=2)