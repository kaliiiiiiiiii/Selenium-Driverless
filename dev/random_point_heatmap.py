import numpy as np
import time
from selenium_driverless.scripts.geometry import gen_heatmap, gen_rand_point, visualize


def gen_rand_points(polygon_vertices: np.array, heatmap_grid: np.array, n_points: int = 150):
    points = []
    for _ in range(n_points):
        rand_point = gen_rand_point(polygon_vertices, heatmap_grid, bias_value=5)
        points.append(rand_point)

    return np.array(points)


elem = np.array([[54.66666794, 17.66666794], [54.66666794, 17.66666794], [54.66666794, 17.66666794], [54.66666794, 17.66666794]])

start = time.process_time()
heatmap = gen_heatmap(elem, num_points=50)

random_points = gen_rand_points(elem, heatmap, n_points=100)
# random_points = np.array([gen_rand_point(elem, heatmap)])

stop = time.process_time()

print(stop - start)

visualize(random_points, heatmap, elem)
