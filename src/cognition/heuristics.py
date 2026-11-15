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


AVAILABLE_HEURISTICS = {
    "Manhattan": {
        "fn": manhattan_distance,
        "name": "Manhattan (L1)",
        "formula": "|dx| + |dy|",
        "description": "Optimal untuk grid ortogonal 4-arah (Admissible & Konsisten)",
    },
    "Euclidean": {
        "fn": euclidean_distance,
        "name": "Euclidean (L2)",
        "formula": "sqrt(dx^2 + dy^2)",
        "description": "Jarak garis lurus (Admissible, eksplorasi simpul lebih luas)",
    },
    "Chebyshev": {
        "fn": chebyshev_distance,
        "name": "Chebyshev (Linf)",
        "formula": "max(|dx|, |dy|)",
        "description": "Admissible untuk 8-arah (Underestimates untuk 4-arah)",
    },
    "Octile": {
        "fn": octile_distance,
        "name": "Octile",
        "formula": "dx + dy + (sqrt(2)-2)*min",
        "description": "Metrik diagonal D=1, D2=1.414",
    },
}
