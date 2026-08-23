"""EDG 0.9 的简单游戏世界，支持 Rust 批量移动和邻近检测。"""
try:
    from edg_hot import move as hot_move
except ImportError:
    hot_move = None
try:
    from spatial import nearby as nearby_pairs
except ImportError:
    nearby_pairs = None


class Body:
    def __init__(self, name="body", x=0.0, y=0.0, vx=0.0, vy=0.0, size=1.0):
        self.name = name
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.size = float(size)


class World:
    def __init__(self):
        self.items = []
        self.time = 0.0

    def add(self, item):
        self.items.append(item)
        return item

    def remove(self, item):
        if item in self.items:
            self.items.remove(item)
        return item

    def size(self):
        return len(self.items)

    def tick(self, dt):
        """批量更新实体；Rust 可用时只跨 FFI 一次。"""
        dt = float(dt)
        self.time += dt
        if hot_move and self.items:
            xs = [item.x for item in self.items]
            ys = [item.y for item in self.items]
            vxs = [item.vx for item in self.items]
            vys = [item.vy for item in self.items]
            nx, ny = hot_move(xs, ys, vxs, vys, dt)
            for item, x, y in zip(self.items, nx, ny):
                item.x, item.y = x, y
        else:
            for item in self.items:
                item.x += item.vx * dt
                item.y += item.vy * dt
        return self.time

    def nearby(self, radius, cell_size=None):
        if not nearby_pairs or len(self.items) < 2:
            return 0
        return nearby_pairs([x.x for x in self.items], [x.y for x in self.items], radius, cell_size)

    def hit_box(self, min_x, min_y, max_x, max_y):
        """返回矩形内实体；使用实体中心点进行快速检测。"""
        if not self.items:
            return []
        flags = None
        try:
            from edg_hot import hit_box
            flags = hit_box([x.x for x in self.items], [x.y for x in self.items], min_x, min_y, max_x, max_y)
        except (ImportError, ValueError):
            flags = [int(min_x <= x.x <= max_x and min_y <= x.y <= max_y) for x in self.items]
        return [item for item, flag in zip(self.items, flags) if flag]

    def collisions(self):
        """返回实体之间的 AABB 碰撞对，size 表示正方形边长。"""
        result = []
        for i, left in enumerate(self.items):
            for right in self.items[i + 1:]:
                if abs(left.x - right.x) * 2 <= left.size + right.size and abs(left.y - right.y) * 2 <= left.size + right.size:
                    result.append([left, right])
        return result

    def positions(self):
        return [[item.x, item.y] for item in self.items]

    def clear(self):
        self.items.clear()


def body(name="body", x=0.0, y=0.0, vx=0.0, vy=0.0, size=1.0):
    return Body(name, x, y, vx, vy, size)
