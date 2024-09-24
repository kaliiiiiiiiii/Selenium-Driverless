import numpy as np
import matplotlib.pyplot as plt
from selenium_driverless.scripts.geometry import overlap


def rectangle_corners(center: np.ndarray, width: float, height: float, angle: float) -> np.ndarray:
    """Calculate the corners of a rectangle given center, width, height, and rotation angle."""
    angle_rad: float = np.radians(angle)
    cos_angle: float = np.cos(angle_rad)
    sin_angle: float = np.sin(angle_rad)

    # Half dimensions
    w, h = width / 2, height / 2

    # Define the rectangle's corners in local coordinates
    corners: np.ndarray = np.array([
        [-w, -h],
        [w, -h],
        [w, h],
        [-w, h]
    ])

    # Rotate and translate corners
    rotation_matrix: np.ndarray = np.array([[cos_angle, -sin_angle],
                                            [sin_angle, cos_angle]])

    return np.dot(corners, rotation_matrix) + center


def plot_rect_and_intersect(rect1: np.ndarray, rect2: np.ndarray, intersection: np.ndarray, title: str,
                            percentage_overlap: float) -> None:
    """Plot the rectangles and their intersection."""
    plt.figure(figsize=(8, 8))
    plt.plot(*rect1.T, label='Rectangle 1', color='blue')
    plt.fill(*rect1.T, alpha=0.5, color='blue')
    plt.plot(*rect2.T, label='Rectangle 2', color='red')
    plt.fill(*rect2.T, alpha=0.5, color='red')

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
    plt.title(f'{title} (Overlap: {percentage_overlap:.2f}%)')
    plt.show()


def demo():
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

        # Calculate percentage overlap and plot
        percentage_overlap, intersection_polygon = overlap(rect1, rect2)
        plot_rect_and_intersect(rect1, rect2, intersection_polygon, case["title"], percentage_overlap)


if __name__ == "__main__":
    demo()
