import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import time

from selenium_driverless.scripts.geometry import rand_mid_loc


def rotate(point, angle, center):
    x, y = point
    cx, cy = center
    rotated_x = (x - cx) * np.cos(angle) - (y - cy) * np.sin(angle) + cx
    rotated_y = (x - cx) * np.sin(angle) + (y - cy) * np.cos(angle) + cy
    return [rotated_x, rotated_y]


if __name__ == "__main__":
    elem = [
        (300, 200),  # A
        (400, 200),  # B
        (400, 400),  # C
        (300, 400)  # D
    ]
    elem_angle = np.radians(30)  # Center of the rectangle
    elem = [rotate(point, elem_angle, elem[0]) for point in elem]

    n = 100_000  # Number of random points
    spread_a = 1  # Bias for a
    spread_b = 1  # Bias for b
    bias_a = 0.5
    bias_b = 0.5
    border = 0.05

    # create grid
    x_grid = np.linspace(min(point[0] for point in elem),
                         max(point[0] for point in elem), 100)
    y_grid = np.linspace(min(point[1] for point in elem),
                         max(point[1] for point in elem), 100)
    x_grid, y_grid = np.meshgrid(x_grid, y_grid)
    z_values = np.zeros_like(x_grid)

    start_time = time.perf_counter()
    for _ in range(n):
        result_point = rand_mid_loc(elem, spread_a, spread_b, bias_a, bias_b, border)
        x_idx = np.argmin(np.abs(x_grid[0] - result_point[0]))
        y_idx = np.argmin(np.abs(y_grid[:, 0] - result_point[1]))
        z_values[y_idx, x_idx] += 1
    end_time = time.perf_counter()
    print(f"Average time to get one random coordinate: {(end_time - start_time) / n:.6f} seconds")

    # Interpolate surface
    x_flat, y_flat, z_flat = x_grid.flatten(), y_grid.flatten(), z_values.flatten()
    grid_x, grid_y = np.meshgrid(np.linspace(min(x_flat), max(x_flat), 200), np.linspace(min(y_flat), max(y_flat), 200))
    # noinspection PyTypeChecker
    grid_z = griddata((x_flat, y_flat), z_flat, (grid_x, grid_y), method="linear")

    # Plot
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    elem_x = [point[0] for point in elem + [elem[0]]]
    elem_y = [point[1] for point in elem + [elem[0]]]
    elem_z = [0] * 5
    # Label elem corners
    for i, corner in enumerate(elem):
        # noinspection PyTypeChecker
        ax.text(corner[0], corner[1], 0, ["A", "B", "C", "D"][i], ha='right', va='bottom')

    ax.plot(elem_x, elem_y, elem_z, marker='o', label='Rectangle')
    ax.plot_surface(grid_x, grid_y, grid_z, cmap='viridis', alpha=0.8, label=f'Distribution')

    # Set equal scaling for x and y axes
    ax.set_box_aspect([1, 1, 1])
    ax.legend()
    ax.grid(True)

    plt.show()
