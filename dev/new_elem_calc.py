import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import time


def generate_random_values(size, spread, border=0.05):
    """Generate random Gaussian distributed values with bias."""
    values = np.zeros(size)
    for idx in np.ndindex(values.shape):
        values[idx] = np.random.normal(scale=spread/3, loc=0.5)
        while not (border <= values[idx] <= 1 - border):
            values[idx] = np.random.normal(scale=spread/3, loc=0.5)

    return values


def rotate_point(point, angle, center):
    """Rotate a point around a center by a given angle."""
    x, y = point
    cx, cy = center
    rotated_x = (x - cx) * np.cos(angle) - (y - cy) * np.sin(angle) + cx
    rotated_y = (x - cx) * np.sin(angle) + (y - cy) * np.cos(angle) + cy
    return [rotated_x, rotated_y]


def rotate_rectangle(rectangle_points, angle, center):
    """Rotate a rectangle around a center by a given angle."""
    rotated_rectangle = [rotate_point(point, angle, center) for point in rectangle_points]
    return rotated_rectangle


def get_point_within_rectangle(points, a, b):
    """
    Given a rectangle defined by four points and two points (a and b) ranging from 0 to 1,
    returns a point within the rectangle based on the input parameters.

    Args:
    - points: List of four coordinates [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    - a: float, a point ranging from 0 to 1 on line |AB|
    - b: float, a point ranging from 0 to 1 on line |BC|

    Returns:
    - List: Coordinates of a point within the rectangle.
    """
    # Validate input points
    if len(points) != 4:
        raise ValueError("Input should contain four points defining a rectangle.")

    # Calculate coordinates of the point within the rectangle
    x = (1 - b) * (points[0][0] + a * (points[1][0] - points[0][0])) + b * (
            points[3][0] + a * (points[2][0] - points[3][0]))
    y = (1 - b) * (points[0][1] + a * (points[1][1] - points[0][1])) + b * (
            points[3][1] + a * (points[2][1] - points[3][1]))

    return [x, y]


if __name__ == "__main__":
    # Example with a rotated rectangle representing a web element
    # Original rectangle sides: |AB| = 100, |BC| = 200
    original_rectangle_points = [[300, 200], [400, 200], [400, 400], [300, 400]]
    rotation_angle = np.radians(30)  # Rotate by 30 degrees
    rotation_center = [350, 300]  # Center of the rectangle

    rotated_rectangle_points = rotate_rectangle(original_rectangle_points, rotation_angle, rotation_center)

    # Generate random Gaussian distributed values for a and b with biases
    size = 100_000  # Number of random points
    bias_a = 0.5  # Bias for a
    bias_b = 1  # Bias for b
    point_a = generate_random_values(size, bias_a)
    point_b = generate_random_values(size, bias_b)

    # Create a 3D plot
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Create a grid of points within the rotated rectangle
    x_grid = np.linspace(min(point[0] for point in rotated_rectangle_points),
                         max(point[0] for point in rotated_rectangle_points), 100)
    y_grid = np.linspace(min(point[1] for point in rotated_rectangle_points),
                         max(point[1] for point in rotated_rectangle_points), 100)
    x_grid, y_grid = np.meshgrid(x_grid, y_grid)

    # Calculate heights based on the random point distribution
    z_values = np.zeros_like(x_grid)
    for i in range(size):
        result_point = get_point_within_rectangle(rotated_rectangle_points, point_a[i], point_b[i])
        x_idx = np.argmin(np.abs(x_grid[0] - result_point[0]))
        y_idx = np.argmin(np.abs(y_grid[:, 0] - result_point[1]))
        z_values[y_idx, x_idx] += 1

    # Interpolation method (change this variable to control interpolation)
    interpolation_method = 'linear'  # You can use 'linear', 'nearest', 'cubic', etc.

    # Interpolate values on a regular grid for smoother heatmap
    x_flat, y_flat, z_flat = x_grid.flatten(), y_grid.flatten(), z_values.flatten()

    start_time = time.time()
    grid_x, grid_y = np.meshgrid(np.linspace(min(x_flat), max(x_flat), 200), np.linspace(min(y_flat), max(y_flat), 200))
    # noinspection PyTypeChecker
    grid_z = griddata((x_flat, y_flat), z_flat, (grid_x, grid_y), method=interpolation_method)
    end_time = time.time()

    # Print average time to get one random coordinate
    average_time_per_coordinate = (end_time - start_time) / size
    print(f"Average time to get one random coordinate: {average_time_per_coordinate:.6f} seconds")

    # Plotting the rotated rectangle as a 3D surface
    rotated_rectangle_x = [point[0] for point in rotated_rectangle_points + [rotated_rectangle_points[0]]]
    rotated_rectangle_y = [point[1] for point in rotated_rectangle_points + [rotated_rectangle_points[0]]]
    rotated_rectangle_z = [0] * 5  # Z values for the rectangle

    ax.plot(rotated_rectangle_x, rotated_rectangle_y, rotated_rectangle_z, marker='o', label='Rectangle')

    # Plotting the smooth 3D heatmap surface
    ax.plot_surface(grid_x, grid_y, grid_z, cmap='viridis', alpha=0.8,
                    label=f'Heatmap ({interpolation_method.capitalize()})')

    # Labeling the four corners
    for i, corner in enumerate(rotated_rectangle_points):
        # noinspection PyTypeChecker
        ax.text(corner[0], corner[1], 0, ["A", "B", "C", "D"][i], ha='right', va='bottom')

    # Set equal scaling for x and y axes
    ax.set_box_aspect([1, 1, 1])
    ax.legend()
    ax.grid(True)
    plt.show()
