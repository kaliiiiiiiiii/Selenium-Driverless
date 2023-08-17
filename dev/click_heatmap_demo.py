import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon


def generate_polygon_heatmap(polygon_vertices, num_points=200):
    polygon = Polygon(polygon_vertices, closed=True, edgecolor='black', facecolor='none')

    x_min, y_min = polygon_vertices.min(axis=0)
    x_max, y_max = polygon_vertices.max(axis=0)

    x_vals = np.linspace(x_min, x_max, num_points)
    y_vals = np.linspace(y_min, y_max, num_points)
    X, Y = np.meshgrid(x_vals, y_vals)
    points = np.column_stack((X.flatten(), Y.flatten()))

    distances = np.empty(num_points ** 2)
    for i, point in enumerate(points):
        min_distance = np.inf
        for j in range(len(polygon_vertices)):
            edge_start = polygon_vertices[j]
            edge_end = polygon_vertices[(j + 1) % len(polygon_vertices)]
            v1 = edge_end - edge_start
            v2 = point - edge_start
            distance = np.linalg.norm(np.cross(v1, v2)) / np.linalg.norm(v1)
            min_distance = min(min_distance, distance)
        distances[i] = min_distance

    distances_normalized = distances / np.max(distances)
    distances_grid = distances_normalized.reshape((num_points, num_points))

    path = polygon.get_path()
    mask = ~path.contains_points(points).reshape((num_points, num_points))
    distances_grid[mask] = 0.0

    return distances_grid


def generate_random_point_biased(polygon_vertices, heatmap_grid, bias_value=10):
    num_points = len(heatmap_grid)

    heatmap_probs = heatmap_grid.flatten() ** bias_value
    heatmap_probs /= np.sum(heatmap_probs)

    sampled_index = np.random.choice(num_points ** 2, p=heatmap_probs)

    row = sampled_index // num_points
    col = sampled_index % num_points

    x_min, y_min = polygon_vertices.min(axis=0)
    x_range = polygon_vertices.max(axis=0) - polygon_vertices.min(axis=0)
    x_sample = x_min + col * (x_range[0] / (num_points - 1))
    y_sample = y_min + row * (x_range[1] / (num_points - 1))

    return x_sample, y_sample


polygon_vertices = np.array([
    [59.13952637, -55.31472397],
    [140.13952637, 84.98139191],
    [126.86047363, 92.64805603],
    [45.86047363, -47.64805603],
])

heatmap_grid = generate_polygon_heatmap(polygon_vertices, num_points=70)

num_points_to_simulate = 500
simulated_points = []
for _ in range(num_points_to_simulate):
    random_point = generate_random_point_biased(polygon_vertices, heatmap_grid, bias_value=5)
    simulated_points.append(random_point)

simulated_points = np.array(simulated_points)

x_min, y_min = polygon_vertices.min(axis=0)
x_max, y_max = polygon_vertices.max(axis=0)

fig, ax = plt.subplots(figsize=(8, 6))

heatmap = ax.imshow(heatmap_grid, cmap='hot', extent=[x_min, x_max, y_min, y_max], origin='lower')
ax.add_patch(Polygon(polygon_vertices, closed=True, edgecolor='yellow', facecolor='none'))  # Changed edgecolor to yellow

ax.scatter(simulated_points[:, 0], simulated_points[:, 1], color='blue')
ax.set_title('Random points inside element (polygon) based on heatmap')

plt.tight_layout()
plt.show()
