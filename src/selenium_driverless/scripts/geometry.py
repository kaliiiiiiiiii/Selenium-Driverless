import numpy as np
import random
import typing

from scipy.interpolate import splprep, splev


def gaussian_bias_rand(spread, border=0.05, bias=0.5) -> float:
    """Generate random Gaussian distributed values with bias."""
    if spread == 0:
        return bias
    res = np.random.normal(scale=spread / 6, loc=bias)
    while not (border <= res <= 1 - border):
        res = np.random.normal(scale=spread / 6, loc=bias)
    return res


ElemType = typing.Union[np.ndarray[(int, int)], typing.List[typing.Union[typing.List, typing.Tuple]]]


def point_in_rectangle(points: np.ndarray[(int, int)], a, b) -> typing.List[float]:
    """
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


# noinspection PyUnusedLocal
def rand_mid_loc(elem: ElemType, spread_a: float = 1, spread_b: float = 1, bias_a: float = 0.5, bias_b: float = 0.5, border:float=0.05) -> typing.List[float]:
    if len(elem) != 4:
        raise ValueError("Input should contain four points defining a rectangle.")
    assert 0 <= bias_a <= 1
    assert 0 <= bias_b <= 1
    elem = np.array(elem)

    # ensure element has an area
    a_b = elem[1] - elem[0]
    b_c = elem[2] - elem[1]
    # noinspection PyUnreachableCode
    area = np.abs(np.cross(a_b, b_c))
    if area == 0:
        raise ValueError("The area of the element is 0")

    point_a = gaussian_bias_rand(spread_a, bias=bias_a, border=border)
    point_b = gaussian_bias_rand(spread_b, bias=bias_b, border=border)
    return point_in_rectangle(elem, point_a, point_b)


def get_bounds(vertices: np.array):
    x_min, y_min = vertices.min(axis=0)
    x_max, y_max = vertices.max(axis=0)
    return x_min, y_min, x_max, y_max


def bias_0_dot_5(strength: float, max_offset: float) -> float:
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
def pos_at_time(path, total_time, time, accel, mid_time=0.5) -> typing.Tuple[int]:
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
