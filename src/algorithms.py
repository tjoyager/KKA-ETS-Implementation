"""
algorithms.py
=============
Modul implementasi algoritma Informed Search untuk navigasi robot pada grid.
Menyediakan:
1. Fungsi Heuristik: Manhattan Distance dan Euclidean Distance.
2. Algoritma A* (A-Star) Search.
3. Algoritma Greedy Best-First Search (GBFS).
4. Struktur data SearchResult untuk perbandingan metrik kinerja.
"""

import heapq
import math
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

# Tipe data untuk koordinat (x, y) dan fungsi heuristik
Coord = Tuple[int, int]
HeuristicFunc = Callable[[Coord, Coord], float]


# ============================================================================
# FUNGSI HEURISTIK
# ============================================================================

def manhattan_distance(a: Coord, b: Coord) -> float:
    """
    Menghitung jarak Manhattan: |x1 - x2| + |y1 - y2|.
    Sangat cocok untuk grid dengan pergerakan 4-arah (ortogonal).
    """
    return float(abs(a[0] - b[0]) + abs(a[1] - b[1]))


def euclidean_distance(a: Coord, b: Coord) -> float:
    """
    Menghitung jarak Euclidean garis lurus: sqrt((x1 - x2)^2 + (y1 - y2)^2).
    Cocok untuk pergerakan dengan sudut bebas atau diagonal (8-arah).
    """
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ============================================================================
# STRUKTUR HASIL PENCARIAN
# ============================================================================

@dataclass
class SearchResult:
    """Menyimpan data hasil pencarian dan metrik evaluasi algoritma."""
    algorithm_name: str
    success: bool
    path: List[Coord] = field(default_factory=list)
    cost: float = 0.0
    nodes_explored: int = 0
    explored_order: List[Coord] = field(default_factory=list)
    execution_time_ms: float = 0.0

    @property
    def path_length(self) -> int:
        """Jumlah langkah atau titik pada jalur yang ditemukan."""
        return len(self.path)

    def summary(self) -> str:
        """Menghasilkan ringkasan metrik dalam bentuk teks rapi."""
        status = "SUKSES" if self.success else "GAGAL (Tidak Ditemukan Jalur)"
        return (
            f"=== Hasil: {self.algorithm_name} ===\n"
            f"  Status             : {status}\n"
            f"  Panjang Jalur      : {self.path_length} sel\n"
            f"  Total Biaya (Cost) : {self.cost:.2f}\n"
            f"  Simpul Dieksplorasi: {self.nodes_explored} simpul\n"
            f"  Waktu Eksekusi     : {self.execution_time_ms:.4f} ms"
        )


# ============================================================================
# FUNGSI BANTUAN REKONSTRUKSI JALUR
# ============================================================================

def _reconstruct_path(came_from: Dict[Coord, Coord], current: Coord) -> List[Coord]:
    """Menyusun ulang jalur dari simpul awal ke tujuan berdasarkan dictionary came_from."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _calculate_path_cost(grid_map, path: List[Coord]) -> float:
    """Menghitung akumulasi total biaya pergerakan sepanjang jalur."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path) - 1):
        total += grid_map.get_step_cost(path[i], path[i + 1])
    return total


# ============================================================================
# ALGORITMA 1: A* SEARCH
# ============================================================================

def a_star_search(
    grid_map,
    start: Optional[Coord] = None,
    goal: Optional[Coord] = None,
    heuristic: HeuristicFunc = manhattan_distance,
    allow_diagonal: bool = False,
) -> SearchResult:
    """
    Implementasi A* Search.
    Fungsi evaluasi f(n) = g(n) + h(n), di mana:
      - g(n) = biaya aktual dari titik awal ke simpul n saat ini
      - h(n) = estimasi heuristik biaya dari simpul n ke tujuan (goal)
    Menjamin jalur terpendek/optimal jika fungsi heuristik bersifat admissible.
    """
    t_start = time.perf_counter()

    start_node = start if start is not None else grid_map.start
    goal_node = goal if goal is not None else grid_map.goal

    if start_node == goal_node:
        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        return SearchResult(
            algorithm_name="A* Search",
            success=True,
            path=[start_node],
            cost=0.0,
            nodes_explored=1,
            explored_order=[start_node],
            execution_time_ms=t_elapsed,
        )

    # Priority queue: elemen berupa tuple (f_score, counter, node)
    counter = 0
    open_heap = []
    heapq.heappush(open_heap, (heuristic(start_node, goal_node), counter, start_node))

    came_from: Dict[Coord, Coord] = {}
    g_score: Dict[Coord, float] = {start_node: 0.0}
    closed_set: Set[Coord] = set()
    explored_order: List[Coord] = []

    success = False
    final_node = start_node

    while open_heap:
        current_f, _, current = heapq.heappop(open_heap)

        if current in closed_set:
            continue

        closed_set.add(current)
        explored_order.append(current)

        # Cek apakah tujuan tercapai
        if current == goal_node:
            success = True
            final_node = current
            break

        for neighbor in grid_map.get_neighbors(current[0], current[1], allow_diagonal=allow_diagonal):
            step_cost = grid_map.get_step_cost(current, neighbor)
            tentative_g = g_score[current] + step_cost

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                h_val = heuristic(neighbor, goal_node)
                f_val = tentative_g + h_val

                came_from[neighbor] = current
                counter += 1
                heapq.heappush(open_heap, (f_val, counter, neighbor))

    t_elapsed = (time.perf_counter() - t_start) * 1000.0

    if success:
        path = _reconstruct_path(came_from, final_node)
        cost = _calculate_path_cost(grid_map, path)
    else:
        path = []
        cost = 0.0

    return SearchResult(
        algorithm_name="A* Search",
        success=success,
        path=path,
        cost=cost,
        nodes_explored=len(closed_set),
        explored_order=explored_order,
        execution_time_ms=t_elapsed,
    )


# ============================================================================
# ALGORITMA 2: GREEDY BEST-FIRST SEARCH (GBFS)
# ============================================================================

def greedy_best_first_search(
    grid_map,
    start: Optional[Coord] = None,
    goal: Optional[Coord] = None,
    heuristic: HeuristicFunc = manhattan_distance,
    allow_diagonal: bool = False,
) -> SearchResult:
    """
    Implementasi Greedy Best-First Search (GBFS).
    Fungsi evaluasi f(n) = h(n), hanya mempertimbangkan perkiraan jarak ke tujuan.
    Cenderung cepat menemukan solusi, namun tidak menjamin jalur yang ditemukan adalah optimal.
    """
    t_start = time.perf_counter()

    start_node = start if start is not None else grid_map.start
    goal_node = goal if goal is not None else grid_map.goal

    if start_node == goal_node:
        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        return SearchResult(
            algorithm_name="Greedy Best-First Search",
            success=True,
            path=[start_node],
            cost=0.0,
            nodes_explored=1,
            explored_order=[start_node],
            execution_time_ms=t_elapsed,
        )

    counter = 0
    open_heap = []
    heapq.heappush(open_heap, (heuristic(start_node, goal_node), counter, start_node))

    came_from: Dict[Coord, Coord] = {}
    visited: Set[Coord] = {start_node}
    explored_order: List[Coord] = []

    success = False
    final_node = start_node

    while open_heap:
        current_h, _, current = heapq.heappop(open_heap)
        explored_order.append(current)

        if current == goal_node:
            success = True
            final_node = current
            break

        for neighbor in grid_map.get_neighbors(current[0], current[1], allow_diagonal=allow_diagonal):
            if neighbor not in visited:
                visited.add(neighbor)
                came_from[neighbor] = current
                h_val = heuristic(neighbor, goal_node)
                counter += 1
                heapq.heappush(open_heap, (h_val, counter, neighbor))

    t_elapsed = (time.perf_counter() - t_start) * 1000.0

    if success:
        path = _reconstruct_path(came_from, final_node)
        cost = _calculate_path_cost(grid_map, path)
    else:
        path = []
        cost = 0.0

    return SearchResult(
        algorithm_name="Greedy Best-First Search",
        success=success,
        path=path,
        cost=cost,
        nodes_explored=len(explored_order),
        explored_order=explored_order,
        execution_time_ms=t_elapsed,
    )
