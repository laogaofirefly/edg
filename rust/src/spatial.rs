use std::collections::HashMap;

/// 均匀网格宽相位：统计半径范围内的候选实体对。
pub fn nearby(xs: &[f64], ys: &[f64], radius: f64, cell_size: f64) -> usize {
    if xs.len() != ys.len() || cell_size <= 0.0 || radius < 0.0 { return 0; }
    let mut grid: HashMap<(i64, i64), Vec<usize>> = HashMap::new();
    for i in 0..xs.len() {
        let cell = ((xs[i] / cell_size).floor() as i64, (ys[i] / cell_size).floor() as i64);
        grid.entry(cell).or_default().push(i);
    }
    let reach = (radius / cell_size).ceil() as i64;
    let r2 = radius * radius;
    let mut pairs = 0;
    for (&(cx, cy), indices) in &grid {
        for dx in -reach..=reach {
            for dy in -reach..=reach {
                if let Some(other) = grid.get(&(cx + dx, cy + dy)) {
                    for &i in indices {
                        for &j in other {
                            if j > i {
                                let ax = xs[i] - xs[j];
                                let ay = ys[i] - ys[j];
                                if ax * ax + ay * ay <= r2 { pairs += 1; }
                            }
                        }
                    }
                }
            }
        }
    }
    pairs
}