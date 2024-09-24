import numpy as np
import matplotlib.pyplot as plt
# generated with chatgpt.com


def rectangle_corners(center, width, height, angle):
    """Calculate the corners of a rectangle given center, width, height, and rotation angle."""
    angle_rad = np.radians(angle)
    cos_angle = np.cos(angle_rad)
    sin_angle = np.sin(angle_rad)

    # Half dimensions
    w, h = width / 2, height / 2

    # Define the rectangle's corners in local coordinates
    corners = np.array([
        [-w, -h],
        [w, -h],
        [w, h],
        [-w, h]
    ])

    # Rotate and translate corners
    rotation_matrix = np.array([[cos_angle, -sin_angle],
                                [sin_angle, cos_angle]])

    return np.dot(corners, rotation_matrix) + center


def edge_intersection(p1, p2, p3, p4):
    """Find intersection of two line segments (p1p2 and p3p4)."""
    # Check for identical points
    if np.array_equal(p1, p2) or np.array_equal(p3, p4):
        return None

    A1, B1 = p2[1] - p1[1], p1[0] - p2[0]
    C1 = A1 * p1[0] + B1 * p1[1]

    A2, B2 = p4[1] - p3[1], p3[0] - p4[0]
    C2 = A2 * p3[0] + B2 * p3[1]

    determinant = A1 * B2 - A2 * B1

    if determinant == 0:
        return None  # Lines are parallel

    # Calculate intersection coordinates
    x = (B2 * C1 - B1 * C2) / determinant
    y = (A1 * C2 - A2 * C1) / determinant

    # Check if intersection point is within both line segments
    if (np.min([p1[0], p2[0]]) <= x <= np.max([p1[0], p2[0]]) and
        np.min([p1[1], p2[1]]) <= y <= np.max([p1[1], p2[1]]) and
        np.min([p3[0], p4[0]]) <= x <= np.max([p3[0], p4[0]]) and
        np.min([p3[1], p4[1]]) <= y <= np.max([p3[1], p4[1]])):
        return np.array([x, y])
    return None



def point_in_polygon(point, polygon):
    """Check if a point is inside a polygon using ray casting."""
    x, y = point
    n = polygon.shape[0]
    inside = False

    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def intersect_rectangles(rect1, rect2):
    """Calculate the intersection polygon of two rectangles."""
    intersection_points = []

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
    intersection_points.extend(corner for corner in rect1 if point_in_polygon(corner, rect2))

    # Check if any corners of rectangle 2 are inside rectangle 1
    intersection_points.extend(corner for corner in rect2 if point_in_polygon(corner, rect1))

    # Remove duplicates and convert to a NumPy array
    unique_points = np.unique(np.array(intersection_points), axis=0)

    # Sort points to form a valid polygon
    if unique_points.shape[0] > 2:
        centroid = np.mean(unique_points, axis=0)
        angles = np.arctan2(unique_points[:, 1] - centroid[1], unique_points[:, 0] - centroid[0])
        sorted_indices = np.argsort(angles)
        return unique_points[sorted_indices]
    return np.array([])  # Not enough points to form a polygon


def plot_rectangles_and_intersection(rect1, rect2, intersection, title):
    """Plot the rectangles and their intersection."""
    plt.figure(figsize=(8, 8))
    plt.plot(*rect1.T, label='Rectangle 1', color='blue')
    plt.fill(*rect1.T, alpha=0.5, color='blue')
    plt.plot(*rect2.T, label='Rectangle 2', color='red')
    plt.fill(*rect2.T, alpha=0.2, color='red')

    if intersection.size > 0:
        plt.plot(*intersection.T, label='Intersection', color='green')
        plt.fill(*intersection.T, alpha=0.5, color='green')

    plt.xlim(-10, 10)
    plt.ylim(-10, 10)
    plt.axhline(0, color='black', linewidth=0.5, ls='--')
    plt.axvline(0, color='black', linewidth=0.5, ls='--')
    plt.grid()
    plt.gca().set_aspect('equal', adjustable='box')
    plt.legend()
    plt.title(title)
    plt.show()


def main():
    test_cases = [
        # Full Inclusion
        {
            "rect1": (np.array([0, 0]), 8, 4, 0),  # center, width, height, angle
            "rect2": (np.array([0, 0]), 4, 2, 0),
            "title": "Full Inclusion"
        },
        # Partial Overlap
        {
            "rect1": (np.array([2, 2]), 6, 4, 30),
            "rect2": (np.array([-1, 1]), 4, 6, -45),
            "title": "Partial Overlap"
        },
        # No Intersection
        {
            "rect1": (np.array([-5, -5]), 2, 1, 0),
            "rect2": (np.array([5, 5]), 2, 1, 0),
            "title": "No Intersection"
        },
        # One Rectangle Inside Another
        {
            "rect1": (np.array([-1, -1]), 4, 4, 0),
            "rect2": (np.array([0, 0]), 2, 2, 0),
            "title": "One Inside Another"
        },
        # Complex Overlap with Different Rotations
        {
            "rect1": (np.array([2, 0]), 9, 3, 45),
            "rect2": (np.array([0, 2]), 3, 5, -30),
            "title": "Complex Overlap"
        },
        # One Corner Outside
        {
            "rect1": (np.array([0, 0]), 4, 4, 0),
            "rect2": (np.array([3, 3]), 2, 2, 0),
            "title": "One Corner Outside"
        },
    ]

    for case in test_cases:
        center1, width1, height1, angle1 = case["rect1"]
        rect1 = rectangle_corners(center1, width1, height1, angle1)

        center2, width2, height2, angle2 = case["rect2"]
        rect2 = rectangle_corners(center2, width2, height2, angle2)

        # Calculate intersection
        intersection = intersect_rectangles(rect1, rect2)

        # Plot the results
        plot_rectangles_and_intersection(rect1, rect2, intersection, case["title"])


if __name__ == "__main__":
    main()
