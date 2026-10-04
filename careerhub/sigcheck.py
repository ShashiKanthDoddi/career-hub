"""sigcheck: checks that a release was signed by the helper (Ed25519, RFC 8032, pure Python: no extra packages).

tools/make_release.py signs release.json with a private key that only the helper has (never in the repo).
The app refuses any release whose signature doesn't match PUBLIC_KEY, so a hijacked GitHub repo can't push code to her laptop.
"""
import base64
import hashlib
import json

# The helper's public key (hex). The private half lives only on the helper's computer: ~/.careerhub_release_key
PUBLIC_KEY = "a721bd6866c15f5503afde2a0d92dc0c1938952f94c1268788f255679e786c16"

_p = 2 ** 255 - 19
_d = -121665 * pow(121666, _p - 2, _p) % _p
_q = 2 ** 252 + 27742317777372353535851937790883648493


def _inv(x):
    return pow(x, _p - 2, _p)


def _recover_x(y, sign):
    if y >= _p:
        return None
    x2 = (y * y - 1) * _inv(_d * y * y + 1) % _p
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p:
        x = x * pow(2, (_p - 1) // 4, _p) % _p
    if (x * x - x2) % _p:
        return None
    return _p - x if (x & 1) != sign else x


def _add(P, Q):
    A, B = (P[1] - P[0]) * (Q[1] - Q[0]) % _p, (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C, D = 2 * P[3] * Q[3] * _d % _p, 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _equal(P, Q):
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _compress(P):
    zi = _inv(P[2])
    x, y = P[0] * zi % _p, P[1] * zi % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _p)


_Gy = 4 * _inv(5) % _p
_Gx = _recover_x(_Gy, 0)
_G = (_Gx, _Gy, 1, _Gx * _Gy % _p)


def _h(m):
    return int.from_bytes(hashlib.sha512(m).digest(), "little")


def _expand(seed):
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    return (a & ((1 << 254) - 8)) | (1 << 254), h[32:]


def public_key(seed):
    return _compress(_mul(_expand(seed)[0], _G))


def sign(seed, msg):
    a, prefix = _expand(seed)
    A = _compress(_mul(a, _G))
    r = _h(prefix + msg) % _q
    R = _compress(_mul(r, _G))
    s = (r + _h(R + A + msg) % _q * a) % _q
    return R + int.to_bytes(s, 32, "little")


def verify(pub, msg, sig):
    try:
        if len(pub) != 32 or len(sig) != 64:
            return False
        A, R = _decompress(pub), _decompress(sig[:32])
        s = int.from_bytes(sig[32:], "little")
        if A is None or R is None or s >= _q:
            return False
        h = _h(sig[:32] + pub + msg) % _q
        return _equal(_mul(s, _G), _add(R, _mul(h, A)))
    except Exception:
        return False


def canonical(manifest):
    """The bytes that are signed: the manifest without its 'signature', as sorted compact JSON."""
    body = {k: v for k, v in manifest.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def manifest_ok(manifest, pub_hex=None):
    """True only if the manifest carries a valid signature from the helper's key."""
    try:
        sig = base64.b64decode(str(manifest.get("signature") or ""))
        return verify(bytes.fromhex(pub_hex or PUBLIC_KEY), canonical(manifest), sig)
    except Exception:
        return False
