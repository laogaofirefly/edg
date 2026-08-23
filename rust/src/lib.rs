use std::slice;
use std::collections::HashMap;
mod spatial;

/// Rust 热点计算库的 C ABI。
/// Python 通过 ctypes 调用，避免每次计算启动新进程。

#[no_mangle]
pub unsafe extern "C" fn edg_sum_f64(ptr: *const f64, len: usize) -> f64 {
    if ptr.is_null() { return 0.0; }
    slice::from_raw_parts(ptr, len).iter().copied().sum()
}

#[no_mangle]
pub unsafe extern "C" fn edg_dot_f64(a: *const f64, b: *const f64, len: usize) -> f64 {
    if a.is_null() || b.is_null() { return 0.0; }
    let left = slice::from_raw_parts(a, len);
    let right = slice::from_raw_parts(b, len);
    left.iter().zip(right.iter()).map(|(x, y)| x * y).sum()
}

#[no_mangle]
pub unsafe extern "C" fn edg_dist(x1: f64, y1: f64, x2: f64, y2: f64) -> f64 {
    let dx = x2 - x1;
    let dy = y2 - y1;
    dx * dx + dy * dy
}

#[no_mangle]
pub unsafe extern "C" fn edg_in_circle(
    xs: *const f64,
    ys: *const f64,
    len: usize,
    cx: f64,
    cy: f64,
    radius: f64,
) -> usize {
    if xs.is_null() || ys.is_null() { return 0; }
    let x = slice::from_raw_parts(xs, len);
    let y = slice::from_raw_parts(ys, len);
    let r2 = radius * radius;
    x.iter().zip(y.iter()).filter(|(px, py)| {
        let dx = **px - cx;
        let dy = **py - cy;
        dx * dx + dy * dy <= r2
    }).count()
}

/// 原地批量更新二维实体位置：x += vx * dt，y += vy * dt。
#[no_mangle]
pub unsafe extern "C" fn edg_nearby(xs: *const f64, ys: *const f64, len: usize, radius: f64, cell_size: f64) -> usize {
    if xs.is_null() || ys.is_null() { return 0; }
    spatial::nearby(slice::from_raw_parts(xs, len), slice::from_raw_parts(ys, len), radius, cell_size)
}

#[no_mangle]
pub unsafe extern "C" fn edg_move(
    xs: *mut f64,
    ys: *mut f64,
    vxs: *const f64,
    vys: *const f64,
    len: usize,
    dt: f64,
) {
    if xs.is_null() || ys.is_null() || vxs.is_null() || vys.is_null() { return; }
    let x = slice::from_raw_parts_mut(xs, len);
    let y = slice::from_raw_parts_mut(ys, len);
    let vx = slice::from_raw_parts(vxs, len);
    let vy = slice::from_raw_parts(vys, len);
    for i in 0..len {
        x[i] += vx[i] * dt;
        y[i] += vy[i] * dt;
    }
}

/// 批量 AABB 碰撞测试，输出每个实体是否与矩形相交（0/1）。
#[no_mangle]
pub unsafe extern "C" fn edg_hit_box(
    xs: *const f64,
    ys: *const f64,
    len: usize,
    min_x: f64,
    min_y: f64,
    max_x: f64,
    max_y: f64,
    out: *mut u8,
) {
    if xs.is_null() || ys.is_null() || out.is_null() { return; }
    let x = slice::from_raw_parts(xs, len);
    let y = slice::from_raw_parts(ys, len);
    let result = slice::from_raw_parts_mut(out, len);
    for i in 0..len {
        result[i] = (x[i] >= min_x && x[i] <= max_x && y[i] >= min_y && y[i] <= max_y) as u8;
    }
}
