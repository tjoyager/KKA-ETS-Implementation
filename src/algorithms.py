"""
algorithms.py
=============
Modul backward-compatibility yang menghubungkan impor lama ke paket modular `src.cognition`.
"""

from src.cognition.heuristics import (
    manhattan_distance,
    euclidean_distance,
    octile_distance,
    chebyshev_distance,
)
from src.cognition.pathfinding import (
    SearchResult,
    MissionLegs,
    DualRacePlan,
    a_star_search,
    greedy_best_first_search,
    DualPathPlanner,
)

__all__ = [
    "manhattan_distance",
    "euclidean_distance",
    "octile_distance",
    "chebyshev_distance",
    "SearchResult",
    "MissionLegs",
    "DualRacePlan",
    "a_star_search",
    "greedy_best_first_search",
    "DualPathPlanner",
]
