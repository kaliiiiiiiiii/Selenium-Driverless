import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev


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


def gen_combined_path(coordinates, n_points_soft: int = 10, smooth_soft: float = 2, n_points_distort: int = 100,
                      smooth_distort: float = 1):
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


def visualize_paths(paths_list, points, trancparency=0.5):
    plt.figure(figsize=(8, 6))

    for path_points in paths_list:
        x_path, y_path = zip(*path_points)
        plt.plot(x_path, y_path, color='blue', linewidth=1, alpha=trancparency)  # Set color and alpha for transparency

    plt.plot(*zip(*points), 'go')
    plt.show(block=True)


def demo(points, n_paths=30):
    paths_list = []

    for _ in range(n_paths):
        full_pixel_path = gen_combined_path(points, n_points_soft=5, smooth_soft=60, n_points_distort=100,
                                            smooth_distort=0.7)
        paths_list.append(full_pixel_path)

    visualize_paths(paths_list, click_points)


click_points = [(100, 100),
                (300, 500),
                (700, 300),
                (1000, 1000),
                (200, 800)]

demo(click_points)

path = gen_combined_path(click_points, n_points_soft=5, smooth_soft=60, n_points_distort=100,smooth_distort=0.7)
visualize_paths([path], click_points)
