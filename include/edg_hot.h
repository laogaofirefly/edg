#ifndef EDG_HOT_H
#define EDG_HOT_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

double edg_sum_f64(const double *ptr, size_t len);
double edg_dot_f64(const double *a, const double *b, size_t len);
double edg_dist(double x1, double y1, double x2, double y2);
size_t edg_in_circle(const double *xs, const double *ys, size_t len,
                     double cx, double cy, double radius);
size_t edg_nearby(const double *xs, const double *ys, size_t len,
                  double radius, double cell_size);
void edg_move(double *xs, double *ys, const double *vxs, const double *vys,
              size_t len, double dt);
void edg_hit_box(const double *xs, const double *ys, size_t len,
                 double min_x, double min_y, double max_x, double max_y,
                 unsigned char *out);

#ifdef __cplusplus
}
#endif
#endif
