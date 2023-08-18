import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import splprep, splev


def gen_path(a, b, n_points: int = 10, smooth: float = 2, n_float: int = 2):
    smooth = smooth/100
    def normalize(coord, min_val, max_val):
        return (coord - min_val) / (max_val - min_val)

    def denormalize(normalized_coord, min_val, max_val):
        return normalized_coord * (max_val - min_val) + min_val

    min_x, min_y = min(a[0], b[0]), min(a[1], b[1])
    max_x, max_y = max(a[0], b[0]), max(a[1], b[1])

    normalized_a = (normalize(a[0], min_x, max_x), normalize(a[1], min_y, max_y))
    normalized_b = (normalize(b[0], min_x, max_x), normalize(b[1], min_y, max_y))

    n_float_resolution = 10 ** n_float
    t_values = np.linspace(0, 1, n_float_resolution)

    x = np.linspace(normalized_a[0], normalized_b[0], n_points)
    y = np.linspace(normalized_a[1], normalized_b[1], n_points)
    x += np.random.normal(0, smooth, n_points)
    y += np.random.normal(0, smooth, n_points)

    x[0] = normalized_a[0]
    y[0] = normalized_a[1]
    x[-1] = normalized_b[0]
    y[-1] = normalized_b[1]

    tck, u = splprep([x, y], s=0)
    new_points = np.column_stack(splev(t_values, tck))

    denormalized_points = [(denormalize(x, min_x, max_x), denormalize(y, min_y, max_y)) for x, y in new_points]

    return denormalized_points


def gen_paths(coordinates, n_points: int = 10, smooth: float = 0.2, n_float: int = 2):
    path = []
    min_x, min_y = min(coord[0] for coord in coordinates), min(coord[1] for coord in coordinates)
    max_x, max_y = max(coord[0] for coord in coordinates), max(coord[1] for coord in coordinates)

    for i in range(len(coordinates) - 1):
        a = (coordinates[i][0], coordinates[i][1])
        b = (coordinates[i + 1][0], coordinates[i + 1][1])
        segment_points = gen_path(a, b, n_points, smooth, n_float)
        path.extend(segment_points)

    return path


def visualise(path_points: np.array, points: np.array):
    x_line_path, y_line_path = zip(*path_points)

    plt.figure(figsize=(8, 6))
    plt.plot(x_line_path, y_line_path, linewidth=5)
    plt.plot(*zip(*points), 'go')
    plt.title('Human-like path')
    plt.grid(True)
    plt.show(block=True)


click_points = [(100, 100),
                (300, 500),
                (700, 300),
                (1000, 1000)]

path = gen_paths(click_points, n_points=4, smooth=2, n_float=1)
visualise(path, click_points)
