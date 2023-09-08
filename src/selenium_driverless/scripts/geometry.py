import numpy as np
import random

from matplotlib.patches import Polygon
from scipy.interpolate import splprep, splev


# Element middle
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

    try:
        sampled_index = np.random.choice(num_points ** 2, p=heatmap_probs)
    except ValueError as e:
        if e.args[0] == 'probabilities contain NaN':
            raise ValueError("Can't generate point from heatmap with 0-values only")
        else:
            raise e

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
    polygon2 = np.roll(vertices, -1, axis=0)

    # Compute signed area of each triangle
    signed_areas = 0.5 * np.cross(vertices, polygon2)

    # Compute centroid of each triangle
    centroids = (vertices + polygon2) / 3.0

    # Get average of those centroids, weighted by the signed areas.
    return np.average(centroids, axis=0, weights=signed_areas)


def visualize(rand_points: np.array, heatmap_grid: np.array, polygon_vertices: np.array):
    import matplotlib.pyplot as plt
    x_min, y_min, x_max, y_max = get_bounds(polygon_vertices)

    fig, ax = plt.subplots(figsize=(8, 6))

    ax.imshow(heatmap_grid, cmap='hot', extent=[x_min, x_max, y_min, y_max], origin='lower')
    ax.add_patch(
        Polygon(polygon_vertices, closed=True, edgecolor='yellow', facecolor='none'))  # Changed edgecolor to yellow

    ax.scatter(rand_points[:, 0], rand_points[:, 1], color='blue')
    ax.set_title('Random points inside element (Polygon) based on heatmap')

    plt.tight_layout()
    plt.show(block=True)


def bias_0_dot_5(strength: float, max_offset: float):
    # Calculate alpha and beta parameters for the beta distribution
    alpha = 2 * strength
    beta = 2 * (1 - strength)

    # Calculate the valid range for the random value based on max_offset
    lower_bound = max(0.5 - max_offset, 0)
    upper_bound = min(0.5 + max_offset, 1)

    # Generate a random value from the beta distribution
    rand_value = random.betavariate(alpha, beta)

    # Adjust the random value to the valid range
    biased_value = lower_bound + (rand_value * (upper_bound - lower_bound))

    return biased_value


# Mouse Path
def pos_at_time(path, total_time, time, accel, mid_time=0.5):
    if time > total_time or time < 0:
        raise ValueError("Time needs to be between 0 and total_time")

    def cubic_ease_in(t):
        return t ** accel

    def cubic_ease_out(t):
        return 1.0 - (1.0 - t) ** accel

    t_values = np.linspace(0, 1, len(path))
    normalized_time = time / total_time  # Normalize the input time to the range [0, 1]

    # Apply cubic easing for acceleration and deceleration
    if normalized_time < mid_time:
        normalized_time = cubic_ease_in(normalized_time * 2) / 2
    else:
        normalized_time = cubic_ease_out((normalized_time - 0.5) * 2) / 2 + 0.5

    # Find the index of the closest time value in the path
    idx = np.argmin(np.abs(t_values - normalized_time))

    return path[idx]


def generate_path(start, end, n: int = 10, smoothness: float = 2):
    x_points = np.linspace(start[0], end[0], n)
    y_points = np.linspace(start[1], end[1], n)
    x_points += np.random.normal(0, smoothness, n)
    y_points += np.random.normal(0, smoothness, n)

    x_points[0] = start[0]
    y_points[0] = start[1]
    x_points[-1] = end[0]
    y_points[-1] = end[1]

    # noinspection PyTupleAssignmentBalance
    tck, _ = splprep([x_points, y_points], s=0)
    t_values = np.linspace(0, 1, int(np.linalg.norm(np.array(end) - np.array(start)) * 10))
    new_points = np.column_stack(splev(t_values, tck))

    return new_points


def gen_combined_path(coordinates, n_points_soft: int = 5, smooth_soft: float = 10, n_points_distort: int = 100,
                      smooth_distort: float = 0.4):
    combined_path = []

    for i in range(len(coordinates) - 1):
        start = (coordinates[i][0], coordinates[i][1])
        end = (coordinates[i + 1][0], coordinates[i + 1][1])

        # Generate human-like segment
        segment_soft = generate_path(start, end, n_points_soft, smooth_soft)

        # Generate distorted segment
        segment_distort = generate_path(start, end, n_points_distort, smooth_distort)

        # Combine the segments with frequency-based interpolation
        combined_segment = []
        for t in np.linspace(0, 1, len(segment_soft)):
            interp_x = int((1 - t) * segment_distort[int(t * (len(segment_distort) - 1)), 0] + t * segment_soft[
                int(t * (len(segment_soft) - 1)), 0])
            interp_y = int((1 - t) * segment_distort[int(t * (len(segment_distort) - 1)), 1] + t * segment_soft[
                int(t * (len(segment_soft) - 1)), 1])
            if not combined_segment or (interp_x, interp_y) != combined_segment[-1]:
                combined_segment.append((interp_x, interp_y))

        combined_path.extend(combined_segment)

    return combined_path
