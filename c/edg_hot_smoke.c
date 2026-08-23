#include <stdio.h>
#include "edg_hot.h"

int main(void) {
    const double values[] = {1.0, 2.0, 3.0, 4.0};
    const double other[] = {2.0, 2.0, 2.0, 2.0};
    double xs[] = {0.0, 10.0};
    double ys[] = {0.0, 10.0};
    double vx[] = {1.0, -1.0};
    double vy[] = {2.0, -2.0};
    unsigned char hit[2] = {0, 0};
    printf("sum=%g dot=%g dist=%g\n",
           edg_sum_f64(values, 4),
           edg_dot_f64(values, other, 4),
           edg_dist(0.0, 0.0, 3.0, 4.0));
    edg_move(xs, ys, vx, vy, 2, 0.5);
    edg_hit_box(xs, ys, 2, -1.0, -1.0, 2.0, 2.0, hit);
    printf("moved=(%g,%g) hit=%u\n", xs[0], ys[0], (unsigned)hit[0]);
    return 0;
}