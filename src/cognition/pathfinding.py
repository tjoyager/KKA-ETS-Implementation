"""
pathfinding.py
==============
Implementasi algoritma Informed Search (A* Search vs Greedy Best-First Search)
dan perencana rute konkuren untuk simulasi balapan dual-robot di grid 50x50.
"""

import heapq
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from src.cognition.heuristics import manhattan_distance
from src.cognition.warehouse_graph import WarehouseGraph100

Coord = Tuple[int, int]
HeuristicFunc = Callable[[Coord, Coord], float]


@dataclass
class SearchResult:
    """Struktur data hasil eksekusi algoritma pencarian jalur."""
    algorithm_name: str
    success: bool
    path: List[Coord] = field(default_factory=list)
    cost: float = 0.0
    nodes_explored: int = 0
    explored_order: List[Coord] = field(default_factory=list)
    execution_time_ms: float = 0.0

    @property
    def path_length(self) -> int:
        return len(self.path)


@dataclass
class MissionLegs:
    """Rute lengkap dua etape: Spawn -> Pick-up -> Drop-off."""
    leg1: SearchResult   # Spawn ke Pick-up
    leg2: SearchResult   # Pick-up ke Drop-off
    full_path: List[Coord] = field(default_factory=list)
    total_cost: float = 0.0
    total_nodes_explored: int = 0
    total_compute_time_ms: float = 0.0


@dataclass
class DualRacePlan:
    """Hasil kalkulasi rute simultan untuk kedua robot AGV (A* vs GBFS)."""
    alpha_plan: MissionLegs   # A* Search
    beta_plan: MissionLegs    # Greedy Best-First Search
    shared_bottleneck_nodes: List[Coord] = field(default_factory=list)
    congestion_index: float = 0.0
    cost_delta: float = 0.0
    nodes_delta: int = 0


def _reconstruct_path(came_from: Dict[Coord, Coord], current: Coord) -> List[Coord]:
    """Menyusun ulang jalur dari titik awal ke titik akhir."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _calculate_path_cost(graph: WarehouseGraph100, path: List[Coord]) -> float:
    """Menghitung akumulasi total biaya pergerakan sepanjang jalur."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path) - 1):
        total += graph.get_step_cost(path[i], path[i + 1])
    return total


# ============================================================================
# ALGORITMA 1: A* SEARCH (OPTIMAL INFORMED SEARCH TEROPTIMASI)
# ============================================================================

def a_star_search(
    graph: WarehouseGraph100,
    start: Coord,
    goal: Coord,
    heuristic: HeuristicFunc = manhattan_distance,
    allow_diagonal: bool = False,
) -> SearchResult:
    """
    Implementasi A* Search pada grid graf 50x50 teroptimasi tinggi.
    Fungsi evaluasi f(n) = g(n) + h(n) dengan prioritas tie-breaking h(n) terkecil.
    Menjamin rute terpendek dan optimal secara matematis dengan waktu komputasi sub-milidetik.
    """
    t_start = time.perf_counter()

    if start == goal:
        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        return SearchResult(
            algorithm_name="A* Search",
            success=True,
            path=[start],
            cost=0.0,
            nodes_explored=1,
            explored_order=[start],
            execution_time_ms=t_elapsed,
        )

    is_manhattan = (heuristic == manhattan_distance)
    gx, gy = goal

    if is_manhattan:
        h_start = float(abs(start[0] - gx) + abs(start[1] - gy))
    else:
        h_start = heuristic(start, goal)

    counter = 0
    open_heap = []
    # (f_val, h_val, counter, node) -> tie-break dengan h_val terkecil memandu A* langsung ke target
    heapq.heappush(open_heap, (h_start, h_start, counter, start))

    came_from: Dict[Coord, Coord] = {}
    g_score: Dict[Coord, float] = {start: 0.0}
    closed_set: Set[Coord] = set()
    explored_order: List[Coord] = []

    success = False
    final_node = start

    while open_heap:
        current_f, current_h, _, current = heapq.heappop(open_heap)

        if current in closed_set:
            continue

        closed_set.add(current)
        explored_order.append(current)

        if current == goal:
            success = True
            final_node = current
            break

        current_g = g_score[current]
        # Traversal tetangga menggunakan pra-kalkulasi graf cepat
        neighbors = graph.get_neighbors(current[0], current[1], allow_diagonal=allow_diagonal)

        for neighbor in neighbors:
            step_cost = graph.get_step_cost(current, neighbor)
            tentative_g = current_g + step_cost

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                g_score[neighbor] = tentative_g
                if is_manhattan:
                    h_val = float(abs(neighbor[0] - gx) + abs(neighbor[1] - gy))
                else:
                    h_val = heuristic(neighbor, goal)
                f_val = tentative_g + h_val

                came_from[neighbor] = current
                counter += 1
                heapq.heappush(open_heap, (f_val, h_val, counter, neighbor))

    t_elapsed = (time.perf_counter() - t_start) * 1000.0

    if success:
        path = _reconstruct_path(came_from, final_node)
        cost = _calculate_path_cost(graph, path)
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
# ALGORITMA 2: GREEDY BEST-FIRST SEARCH (GBFS TEROPTIMASI)
# ============================================================================

def greedy_best_first_search(
    graph: WarehouseGraph100,
    start: Coord,
    goal: Coord,
    heuristic: HeuristicFunc = manhattan_distance,
    allow_diagonal: bool = False,
) -> SearchResult:
    """
    Implementasi Greedy Best-First Search (GBFS) pada grid graf 50x50 teroptimasi.
    Fungsi evaluasi f(n) = h(n).
    Mengeksplorasi simpul dengan rakus ke arah target; cepat namun rentan suboptimal.
    """
    t_start = time.perf_counter()

    if start == goal:
        t_elapsed = (time.perf_counter() - t_start) * 1000.0
        return SearchResult(
            algorithm_name="Greedy Best-First Search",
            success=True,
            path=[start],
            cost=0.0,
            nodes_explored=1,
            explored_order=[start],
            execution_time_ms=t_elapsed,
        )

    is_manhattan = (heuristic == manhattan_distance)
    gx, gy = goal

    if is_manhattan:
        h_start = float(abs(start[0] - gx) + abs(start[1] - gy))
    else:
        h_start = heuristic(start, goal)

    counter = 0
    open_heap = []
    heapq.heappush(open_heap, (h_start, counter, start))

    came_from: Dict[Coord, Coord] = {}
    visited: Set[Coord] = {start}
    explored_order: List[Coord] = []

    success = False
    final_node = start

    while open_heap:
        current_h, _, current = heapq.heappop(open_heap)
        explored_order.append(current)

        if current == goal:
            success = True
            final_node = current
            break

        neighbors = graph.get_neighbors(current[0], current[1], allow_diagonal=allow_diagonal)
        for neighbor in neighbors:
            if neighbor not in visited:
                visited.add(neighbor)
                came_from[neighbor] = current
                if is_manhattan:
                    h_val = float(abs(neighbor[0] - gx) + abs(neighbor[1] - gy))
                else:
                    h_val = heuristic(neighbor, goal)
                counter += 1
                heapq.heappush(open_heap, (h_val, counter, neighbor))

    t_elapsed = (time.perf_counter() - t_start) * 1000.0

    if success:
        path = _reconstruct_path(came_from, final_node)
        cost = _calculate_path_cost(graph, path)
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


# ============================================================================
# PERENCANA RUTE KONKUREN DUAL-ROBOT (DUAL PATH PLANNER)
# ============================================================================

class DualPathPlanner:
    """
    Mengelola perencanaan rute simultan untuk AGV Alpha (A*) dan AGV Beta (GBFS).
    Menghitung metrik perbandingan dan analisis bottleneck jaringan gudang.
    """

    @staticmethod
    def plan_mission_legs(
        graph: WarehouseGraph100,
        start_pos: Coord,
        pickup_pos: Coord,
        dropoff_pos: Coord,
        algo_name: str = "A*",
        heuristic: HeuristicFunc = manhattan_distance,
        allow_diagonal: bool = False,
    ) -> MissionLegs:
        """Menghitung rute dua tahap: Start -> Pick-up, lalu Pick-up -> Drop-off."""
        search_fn = a_star_search if "A*" in algo_name else greedy_best_first_search

        # Etape 1: Dari titik spawn ke titik jemput (Pick-up)
        leg1 = search_fn(graph, start_pos, pickup_pos, heuristic, allow_diagonal)

        # Etape 2: Dari titik jemput ke titik antar (Drop-off)
        leg2 = search_fn(graph, pickup_pos, dropoff_pos, heuristic, allow_diagonal)

        # Gabungkan rute utuh (hindari duplikasi titik temu)
        full_path = []
        if leg1.success:
            full_path.extend(leg1.path)
        if leg2.success:
            if full_path and leg2.path and full_path[-1] == leg2.path[0]:
                full_path.extend(leg2.path[1:])
            else:
                full_path.extend(leg2.path)

        total_cost = leg1.cost + leg2.cost
        total_nodes = leg1.nodes_explored + leg2.nodes_explored
        total_time = leg1.execution_time_ms + leg2.execution_time_ms

        return MissionLegs(
            leg1=leg1,
            leg2=leg2,
            full_path=full_path,
            total_cost=total_cost,
            total_nodes_explored=total_nodes,
            total_compute_time_ms=total_time,
        )

    @classmethod
    def plan_dual_race(
        cls,
        graph: WarehouseGraph100,
        spawn_alpha: Coord,
        spawn_beta: Coord,
        pickup_access: Coord,
        dropoff_access: Coord,
        heuristic: HeuristicFunc = manhattan_distance,
        allow_diagonal: bool = False,
    ) -> DualRacePlan:
        """
        Kalkulasi rute simultan untuk kedua robot AGV:
        - AGV Alpha menggunakan A* Search
        - AGV Beta menggunakan Greedy Best-First Search
        """
        plan_alpha = cls.plan_mission_legs(
            graph, spawn_alpha, pickup_access, dropoff_access,
            algo_name="A*", heuristic=heuristic, allow_diagonal=allow_diagonal,
        )

        plan_beta = cls.plan_mission_legs(
            graph, spawn_beta, pickup_access, dropoff_access,
            algo_name="GBFS", heuristic=heuristic, allow_diagonal=allow_diagonal,
        )

        # Analisis Bottleneck & Kemacetan: cari simpul yang dilalui oleh kedua robot
        set_alpha = set(plan_alpha.full_path)
        set_beta = set(plan_beta.full_path)
        shared_nodes = list(set_alpha.intersection(set_beta))

        max_len = max(len(plan_alpha.full_path), len(plan_beta.full_path), 1)
        congestion_index = len(shared_nodes) / float(max_len)

        cost_delta = plan_beta.total_cost - plan_alpha.total_cost
        nodes_delta = plan_alpha.total_nodes_explored - plan_beta.total_nodes_explored

        return DualRacePlan(
            alpha_plan=plan_alpha,
            beta_plan=plan_beta,
            shared_bottleneck_nodes=shared_nodes,
            congestion_index=congestion_index,
            cost_delta=cost_delta,
            nodes_delta=nodes_delta,
        )
