"""EDG 的快速计算工具。"""
import ctypes
import os
from array import array


def _load():
    names = ("libedg_hot.so", "edg_hot.dll", "libedg_hot.dylib")
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rust", "target", "release"))
    for name in names:
        path = os.path.join(root, name)
        if not os.path.exists(path):
            continue
        lib = ctypes.CDLL(path)
        p = ctypes.POINTER(ctypes.c_double)
        lib.edg_sum_f64.argtypes = [p, ctypes.c_size_t]
        lib.edg_sum_f64.restype = ctypes.c_double
        lib.edg_dot_f64.argtypes = [p, p, ctypes.c_size_t]
        lib.edg_dot_f64.restype = ctypes.c_double
        lib.edg_dist.argtypes = [ctypes.c_double] * 4
        lib.edg_dist.restype = ctypes.c_double
        lib.edg_in_circle.argtypes = [p, p, ctypes.c_size_t, ctypes.c_double, ctypes.c_double, ctypes.c_double]
        lib.edg_in_circle.restype = ctypes.c_size_t
        lib.edg_nearby.argtypes = [p, p, ctypes.c_size_t, ctypes.c_double, ctypes.c_double]
        lib.edg_nearby.restype = ctypes.c_size_t
        lib.edg_move.argtypes = [p, p, p, p, ctypes.c_size_t, ctypes.c_double]
        lib.edg_move.restype = None
        lib.edg_hit_box.argtypes = [p, p, ctypes.c_size_t, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.POINTER(ctypes.c_uint8)]
        lib.edg_hit_box.restype = None
        return lib
    return None

_LIB = _load()

def _buf(values):
    return array('d', (float(x) for x in values))

def _ptr(buf):
    return (ctypes.c_double * len(buf)).from_buffer(buf)

def sum_f64(values):
    b = _buf(values)
    return _LIB.edg_sum_f64(_ptr(b), len(b)) if _LIB else sum(b)

def dot_f64(a, b):
    x, y = _buf(a), _buf(b)
    if len(x) != len(y): raise ValueError('arrays must have same size')
    return _LIB.edg_dot_f64(_ptr(x), _ptr(y), len(x)) if _LIB else sum(i*j for i,j in zip(x,y))

def dist(x1, y1, x2, y2):
    return _LIB.edg_dist(x1, y1, x2, y2) if _LIB else (x2-x1)**2 + (y2-y1)**2

def in_circle(xs, ys, cx, cy, radius):
    x, y = _buf(xs), _buf(ys)
    if len(x) != len(y): raise ValueError('arrays must have same size')
    if _LIB: return _LIB.edg_in_circle(_ptr(x), _ptr(y), len(x), cx, cy, radius)
    r2 = radius * radius
    return sum((px-cx)**2 + (py-cy)**2 <= r2 for px,py in zip(x,y))

def move(xs, ys, vxs, vys, dt):
    x, y, vx, vy = map(_buf, (xs, ys, vxs, vys))
    if not len(x) == len(y) == len(vx) == len(vy): raise ValueError('arrays must have same size')
    if _LIB: _LIB.edg_move(_ptr(x), _ptr(y), _ptr(vx), _ptr(vy), len(x), dt)
    else:
        for i in range(len(x)): x[i] += vx[i] * dt; y[i] += vy[i] * dt
    return list(x), list(y)

def hit_box(xs, ys, min_x, min_y, max_x, max_y):
    x, y = _buf(xs), _buf(ys)
    if len(x) != len(y): raise ValueError('arrays must have same size')
    if _LIB:
        out = (ctypes.c_uint8 * len(x))()
        _LIB.edg_hit_box(_ptr(x), _ptr(y), len(x), min_x, min_y, max_x, max_y, out)
        return list(out)
    return [int(min_x <= px <= max_x and min_y <= py <= max_y) for px,py in zip(x,y)]

USING_RUST = _LIB is not None