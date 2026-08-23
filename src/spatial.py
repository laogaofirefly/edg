"""用于查找附近实体的简单接口。"""
from array import array
from edg_hot import _LIB, _ptr


def nearby(xs, ys, radius, cell_size=None):
    x, y = array('d', map(float, xs)), array('d', map(float, ys))
    if len(x) != len(y):
        raise ValueError('arrays must have same size')
    if radius < 0:
        raise ValueError('radius must be non-negative')
    cell = radius if cell_size is None else cell_size
    if cell <= 0:
        raise ValueError('cell size must be positive')
    if _LIB:
        return _LIB.edg_nearby(_ptr(x), _ptr(y), len(x), radius, cell)
    grid = {}
    for i, (px, py) in enumerate(zip(x, y)):
        key = (int(px // cell), int(py // cell))
        grid.setdefault(key, []).append(i)
    reach = int(radius / cell + 0.999999)
    r2, total = radius * radius, 0
    for (cx, cy), items in grid.items():
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                for i in items:
                    for j in grid.get((cx + dx, cy + dy), ()):
                        if j > i and (x[i]-x[j])**2 + (y[i]-y[j])**2 <= r2:
                            total += 1
    return total