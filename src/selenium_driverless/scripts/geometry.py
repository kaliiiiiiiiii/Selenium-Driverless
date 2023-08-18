import numpy as np
from matplotlib.patches import Polygon
import matplotlib.pyplot as plt


def gen_heatmap(polygon_vertices: np.array, num_points: int = 70):
    polygon = Polygon(polygon_vertices, closed=True, edgecolor='black', facecolor='none')

    x_min, y_min, x_max, y_max = get_bounds(polygon_vertices)

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


def gen_rand_point(polygon_vertices: np.array, heatmap_grid: np.array, bias_value: float = 7):
    num_points = len(heatmap_grid)

    heatmap_probs = heatmap_grid.flatten() ** bias_value
    heatmap_probs /= np.sum(heatmap_probs)

    sampled_index = np.random.choice(num_points ** 2, p=heatmap_probs)

    row = sampled_index // num_points
    col = sampled_index % num_points

    x_min, y_min, x_max, y_max = get_bounds(polygon_vertices)

    x_range = polygon_vertices.max(axis=0) - polygon_vertices.min(axis=0)
    x_sample = x_min + col * (x_range[0] / (num_points - 1))
    y_sample = y_min + row * (x_range[1] / (num_points - 1))

    return x_sample, y_sample


def get_bounds(vertices: np.array):
    x_min, y_min = vertices.min(axis=0)
    x_max, y_max = vertices.max(axis=0)
    return x_min, y_min, x_max, y_max


def centroid(vertices):
    x, y = 0, 0
    n = len(vertices)
    signed_area = 0
    for i in range(len(vertices)):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        # shoelace formula
        area = (x0 * y1) - (x1 * y0)
        signed_area += area
        x += (x0 + x1) * area
        y += (y0 + y1) * area
    signed_area *= 0.5
    x /= 6 * signed_area
    y /= 6 * signed_area
    return x, y


def visualize(rand_points: np.array, heatmap_grid: np.array, polygon_vertices: np.array):
    x_min, y_min, x_max, y_max = get_bounds(polygon_vertices)

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.imshow(heatmap_grid, cmap='hot', extent=[x_min, x_max, y_min, y_max], origin='lower')
    ax.add_patch(
        Polygon(polygon_vertices, closed=True, edgecolor='yellow', facecolor='none'))  # Changed edgecolor to yellow

    ax.scatter(rand_points[:, 0], rand_points[:, 1], color='blue')
    ax.set_title('Random points inside element (Polygon) based on heatmap')

    plt.tight_layout()
    plt.show(block=True)
