# By Nicko van Someren, 2021. This code is released into the public domain.
# Small modifications for use in Reticulum, and constant time key exchange
# added by Mark Qvist in 2022.

# WARNING! Only the X25519PrivateKey.exchange() method attempts to hide execution time.
# In the context of Reticulum, this is sufficient, but it may not be in other systems. If
# this code is to be used to provide cryptographic security in an environment where the
# start and end times of the execution can be guessed, inferred or measured then it is
# critical that steps are taken to hide the execution time, for instance by adding a
# delay so that encrypted packets are not sent until a fixed time after the _start_ of
# execution.


import os
import time

P = 2 ** 255 - 19
_A = 486662


def _point_add(point_n, point_m, point_diff):
    """Given the projection of two points and their difference, return their sum"""
    (xn, zn) = point_n
    (xm, zm) = point_m
    (x_diff, z_diff) = point_diff
    x = (z_diff << 2) * (xm * xn - zm * zn) ** 2
    z = (x_diff << 2) * (xm * zn - zm * xn) ** 2
    return x % P, z % P


def _point_double(point_n):
    """Double a point provided in projective coordinates"""
    (xn, zn) = point_n
    xn2 = xn ** 2
    zn2 = zn ** 2
    x = (xn2 - zn2) ** 2
    xzn = xn * zn
    z = 4 * xzn * (xn2 + _A * xzn + zn2)
    return x % P, z % P


def _const_time_swap(a, b, swap):
    """Swap two values in constant time"""
    index = int(swap) * 2
    temp = (a, b, b, a)
    return temp[index:index+2]


def _raw_curve25519(base, n):
    """Raise the point base to the power n"""
    zero = (1, 0)
    one = (base, 1)
    mP, m1P = zero, one

    for i in reversed(range(256)):
        bit = bool(n & (1 << i))
        mP, m1P = _const_time_swap(mP, m1P, bit)
        mP, m1P = _point_double(mP), _point_add(mP, m1P, one)
        mP, m1P = _const_time_swap(mP, m1P, bit)

    x, z = mP
    inv_z = pow(z, P - 2, P)
    return (x * inv_z) % P


def _unpack_number(s):
    """Unpack 32 bytes to a 256 bit value"""
    if len(s) != 32:
        raise ValueError('Curve25519 values must be 32 bytes')
    return int.from_bytes(s, "little")


def _pack_number(n):
    """Pack a value into 32 bytes"""
    return n.to_bytes(32, "little")


def _fix_secret(n):
    """Mask a value to be an acceptable exponent"""
    n &= ~7
    n &= ~(128 << 8 * 31)
    n |= 64 << 8 * 31
    return n


def curve25519(base_point_raw, secret_raw):
    """Raise the base point to a given power"""
    base_point = _unpack_number(base_point_raw)
    secret = _fix_secret(_unpack_number(secret_raw))
    return _pack_number(_raw_curve25519(base_point, secret))


def curve25519_base(secret_raw):
    """Raise the generator point to a given power"""
    secret = _fix_secret(_unpack_number(secret_raw))
    return _pack_number(_raw_curve25519(9, secret))


class X25519PublicKey:
    def __init__(self, x):
        self.x = x

    @classmethod
    def from_public_bytes(cls, data):
        return cls(_unpack_number(data))

    def public_bytes(self):
        return _pack_number(self.x)


class X25519PrivateKey:
    MIN_EXEC_TIME = 0.002
    MAX_EXEC_TIME = 0.5
    DELAY_WINDOW = 10

    T_CLEAR = None
    T_MAX = 0

    def __init__(self, a):
        self.a = a

    @classmethod
    def generate(cls):
        return cls.from_private_bytes(os.urandom(32))

    @classmethod
    def from_private_bytes(cls, data):
        return cls(_fix_secret(_unpack_number(data)))

    def private_bytes(self):
        return _pack_number(self.a)

    def public_key(self):
        return X25519PublicKey.from_public_bytes(_pack_number(_raw_curve25519(9, self.a)))

    def exchange(self, peer_public_key):
        if isinstance(peer_public_key, bytes):
            peer_public_key = X25519PublicKey.from_public_bytes(peer_public_key)

        start = time.time()
        
        shared = _pack_number(_raw_curve25519(peer_public_key.x, self.a))
        
        end = time.time()
        duration = end-start

        if X25519PrivateKey.T_CLEAR == None:
            X25519PrivateKey.T_CLEAR = end + X25519PrivateKey.DELAY_WINDOW

        if end > X25519PrivateKey.T_CLEAR:
            X25519PrivateKey.T_CLEAR = end + X25519PrivateKey.DELAY_WINDOW
            X25519PrivateKey.T_MAX = 0
        
        if duration < X25519PrivateKey.T_MAX or duration < X25519PrivateKey.MIN_EXEC_TIME:
            target = start+X25519PrivateKey.T_MAX

            if target > start+X25519PrivateKey.MAX_EXEC_TIME:
                target = start+X25519PrivateKey.MAX_EXEC_TIME

            if target < start+X25519PrivateKey.MIN_EXEC_TIME:
                target = start+X25519PrivateKey.MIN_EXEC_TIME

            try:
                time.sleep(target-time.time())
            except Exception as e:
                pass

        elif duration > X25519PrivateKey.T_MAX:
            X25519PrivateKey.T_MAX = duration

        return shared