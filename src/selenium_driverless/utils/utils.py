# from https://github.com/ultrafunkamsterdam/undetected-chromedriver/blob/1c704a71cf4f29181a59ecf19ddff32f1b4fbfc0/undetected_chromedriver/__init__.py#L844
# edited by kaliiiiiiiiii | Aurin Aegerter

import sys
import typing
import json
import os
import selenium
from matplotlib.patches import Polygon

import selenium_driverless
import socket
from contextlib import closing

IS_POSIX = sys.platform.startswith(("darwin", "cygwin", "linux", "linux2"))
T_JSON_DICT = typing.Dict[str, typing.Any]


def find_chrome_executable():
    """
    Finds the chrome, chrome beta, chrome canary, chromium executable

    Returns
    -------
    executable_path :  str
        the full file path to found executable

    """
    candidates = set()
    if IS_POSIX:
        for item in os.environ.get("PATH").split(os.pathsep):
            for subitem in (
                    "google-chrome",
                    "chromium",
                    "chromium-browser",
                    "chrome",
                    "google-chrome-stable",
            ):
                candidates.add(os.sep.join((item, subitem)))
        if "darwin" in sys.platform:
            candidates.update(
                [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    "/Applications/Chromium.app/Contents/MacOS/Chromium",
                ]
            )
    else:
        for item in map(
                os.environ.get,
                ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA", "PROGRAMW6432"),
        ):
            if item is not None:
                for subitem in (
                        "Google/Chrome/Application",
                        "Google/Chrome Beta/Application",
                        "Google/Chrome Canary/Application",
                ):
                    candidates.add(os.sep.join((item, subitem, "chrome.exe")))
    for candidate in candidates:
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return os.path.normpath(candidate)


def sel_driverless_path():
    return os.path.dirname(selenium_driverless.__file__) + "/"


def sel_path():
    return os.path.dirname(selenium.__file__) + "/"


def read(filename: str, encoding: str = "utf-8", sel_root: bool = True):
    if sel_root:
        path = sel_driverless_path() + filename
    else:
        path = filename
    with open(path, encoding=encoding) as f:
        return f.read()


def write(filename: str, content: str, encoding: str = "utf-8", sel_root: bool = True):
    if sel_root:
        path = sel_driverless_path() + filename
    else:
        path = filename
    with open(path, "w+", encoding=encoding) as f:
        return f.write(content)


def read_json(filename: str = 'example.json', encoding: str = "utf-8", sel_root: bool = True):
    if sel_root:
        path = sel_driverless_path() + filename
    else:
        path = filename
    with open(path, 'r', encoding=encoding) as f:
        return json.load(f)


def write_json(obj: dict or list, filename: str = "out.json", encoding: str = "utf-8", sel_root=True):
    if sel_root:
        path = sel_driverless_path() + filename
    else:
        path = filename
    with open(path, "w", encoding=encoding) as outfile:
        outfile.write(json.dumps(obj))


def random_port(host: str = None):
    if not host:
        host = ''
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind((host, 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def plot_polygon(poly: Polygon):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.add_patch(poly)

    points = poly.get_path()
    points = list(points.vertices)
    left, right = min(points, key=lambda p: p[0]), max(points, key=lambda p: p[0])
    bottom, top = min(points, key=lambda p: p[1]), max(points, key=lambda p: p[1])

    ax.set_xlim(left[0], right[0])
    ax.set_ylim(top[1], bottom[1])
    ax.set_aspect('equal', adjustable='box')
    plt.show()


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
