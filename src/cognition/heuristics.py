"""
heuristics.py
=============
Fungsi-fungsi heuristik matematis untuk algoritma Informed Search.
"""

import math
from typing import Tuple

Coord = Tuple[int, int]


def manhattan_distance(a: Coord, b: Coord) -> float:
    """
    Menghitung jarak Manhattan: |x1 - x2| + |y1 - y2|.
    Sangat cocok untuk pergerakan ortogonal 4-arah (grid gudang standar).
    Bersifat admissible (tidak pernah melebih-lebihkan biaya aktual).
    """
    return float(abs(a[0] - b[0]) + abs(a[1] - b[1]))


def euclidean_distance(a: Coord, b: Coord) -> float:
    """
    Menghitung jarak garis lurus Euclidean: sqrt((x1 - x2)^2 + (y1 - y2)^2).
    Cocok untuk navigasi dengan sudut bebas atau pergerakan diagonal.
    """
    return math.hypot(a[0] - b[0], a[1] - b[1])


def octile_distance(a: Coord, b: Coord) -> float:
    """
    Menghitung jarak Octile untuk grid dengan pergerakan 8-arah (diagonal).
    D = 1.0 (ortogonal), D2 = sqrt(2) ~ 1.41421356.
    Formula: D * (dx + dy) + (D2 - 2*D) * min(dx, dy)
    """
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return (dx + dy) + (1.41421356 - 2.0) * min(dx, dy)


def chebyshev_distance(a: Coord, b: Coord) -> float:
    """
    Menghitung jarak Chebyshev: max(|x1 - x2|, |y1 - y2|).
    """
    return float(max(abs(a[0] - b[0]), abs(a[1] - b[1])))
