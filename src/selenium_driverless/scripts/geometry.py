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


ElemType = typing.Union[np.ndarray, typing.List[typing.Union[typing.List, typing.Tuple]]]


def point_in_rectangle(points: np.ndarray, a, b) -> typing.List[float]:
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


def edge_intersection(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray) -> typing.Optional[np.ndarray]:
    """Find intersection of two line segments (p1p2 and p3p4)."""
    a1 = p2[1] - p1[1]
    b1 = p1[0] - p2[0]
    c1 = a1 * p1[0] + b1 * p1[1]

    a2 = p4[1] - p3[1]
    b2 = p3[0] - p4[0]
    c2 = a2 * p3[0] + b2 * p3[1]

    determinant: float = a1 * b2 - a2 * b1

    if determinant == 0:
        return None  # Lines are parallel

    x: float = (b2 * c1 - b1 * c2) / determinant
    y: float = (a1 * c2 - a2 * c1) / determinant

    # Check if intersection point is within both line segments
    if (np.min([p1[0], p2[0]]) <= x <= np.max([p1[0], p2[0]]) and
            np.min([p1[1], p2[1]]) <= y <= np.max([p1[1], p2[1]]) and
            np.min([p3[0], p4[0]]) <= x <= np.max([p3[0], p4[0]]) and
            np.min([p3[1], p4[1]]) <= y <= np.max([p3[1], p4[1]])):
        return np.array([x, y])
    return None


def intersect_rectangles(rect1: np.ndarray, rect2: np.ndarray) -> np.ndarray:
    """Calculate the intersection polygon of two rectangles."""
    intersection_points: typing.List[np.ndarray] = []

    # Define the edges of the rectangles
    edges_rect1 = [(rect1[i], rect1[(i + 1) % 4]) for i in range(4)]
    edges_rect2 = [(rect2[i], rect2[(i + 1) % 4]) for i in range(4)]

    # Check for intersections between edges of the two rectangles
    for edge1 in edges_rect1:
        for edge2 in edges_rect2:
            point = edge_intersection(edge1[0], edge1[1], edge2[0], edge2[1])
            if point is not None:
                intersection_points.append(point)

    # Check if any corners of rectangle 1 are inside rectangle 2
    intersection_points.extend(corner for corner in rect1 if is_point_in_polygon(corner, rect2))

    # Check if any corners of rectangle 2 are inside rectangle 1
    intersection_points.extend(corner for corner in rect2 if is_point_in_polygon(corner, rect1))

    # Remove duplicates and convert to a NumPy array
    unique_points: np.ndarray = np.unique(np.array(intersection_points), axis=0)

    # Sort points to form a valid polygon
    if unique_points.shape[0] > 2:
        centroid: np.ndarray = np.mean(unique_points, axis=0)
        angles: np.ndarray = np.arctan2(unique_points[:, 1] - centroid[1], unique_points[:, 0] - centroid[0])
        sorted_indices: np.ndarray = np.argsort(angles)
        intersection_polygon: np.ndarray = unique_points[sorted_indices]

        return intersection_polygon
    return np.array([])  # Not enough points to form a polygon


def overlap(rect1: np.ndarray, rect2: np.ndarray) -> typing.Tuple[float, np.ndarray]:
    """Calculate the percentage of overlap any sub of two rectangles."""
    intersection = intersect_rectangles(rect1, rect2)
    if intersection.size == 0:
        return 0, np.array([])  # No overlap

    # Calculate areas
    overlap_area: float = polygon_area(intersection)
    rect1_area: float = polygon_area(rect1)
    rect2_area: float = polygon_area(rect2)

    # Take the smaller rectangle for percentage calculation
    smaller_area: float = min(rect1_area, rect2_area)

    # Calculate percentage overlap
    percentage_overlap: float = (overlap_area / smaller_area) * 100
    return percentage_overlap, intersection


def polygon_area(vertices: np.ndarray) -> float:
    """Calculate the area of a polygon using the shoelace formula."""
    x: np.ndarray = vertices[:, 0]
    y: np.ndarray = vertices[:, 1]
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def is_point_in_polygon(point: typing.Union[np.ndarray, list, tuple], polygon: np.ndarray) -> bool:
    """Check if a point is inside a polygon using ray casting."""
    x, y = point
    n: int = polygon.shape[0]
    inside: bool = False

    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints: float = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    # noinspection PyUnboundLocalVariable
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


# noinspection PyUnusedLocal
def rand_mid_loc(elem: ElemType, spread_a: float = 1, spread_b: float = 1, bias_a: float = 0.5, bias_b: float = 0.5,
                 border: float = 0.05) -> typing.List[float]:
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
