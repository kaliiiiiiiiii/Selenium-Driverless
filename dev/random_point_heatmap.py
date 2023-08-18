import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import time
from selenium_driverless.scripts.geometry import gen_heatmap, gen_rand_point, get_bounds


def gen_rand_points(polygon_vertices: np.array, heatmap_grid: np.array, n_points: int = 150):
    points = []
    for _ in range(n_points):
        rand_point = gen_rand_point(polygon_vertices, heatmap_grid, bias_value=5)
        points.append(rand_point)

    return np.array(points)


def visualize(rand_points: np.array, heatmap_grid: np.array, polygon_vertices: np.array):
    x_min, y_min, x_max, y_max = get_bounds(polygon_vertices)

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.imshow(heatmap_grid, cmap='hot', extent=[x_min, x_max, y_min, y_max], origin='lower')
    ax.add_patch(
        Polygon(polygon_vertices, closed=True, edgecolor='yellow', facecolor='none'))  # Changed edgecolor to yellow

    ax.scatter(rand_points[:, 0], rand_points[:, 1], color='blue')
    ax.set_title('Random points inside element (Polygon) based on heatmap')

    plt.tight_layout()
    plt.show()


elem = np.array([
    [0, 0],
    [0, 1],
    [1, 1],
    [1, 0],
])

start = time.process_time()
heatmap = gen_heatmap(elem, num_points=50)

random_points = gen_rand_points(elem, heatmap, n_points=500)
# random_points = np.array([gen_rand_point(elem, heatmap)])

stop = time.process_time()

print(stop - start)

visualize(random_points, heatmap, elem)
