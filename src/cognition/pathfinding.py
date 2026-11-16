"""
pathfinding.py
==============
Implementasi algoritma Informed Search (A* Search vs Greedy Best-First Search)
dan perencana rute konkuren untuk simulasi balapan dual-robot di grid 35x25.
"""

import heapq
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from src.cognition.heuristics import manhattan_distance, octile_distance, euclidean_distance
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

    @property
    def visited_nodes(self) -> List[Coord]:
        """Daftar seluruh simpul grid yang dievaluasi/dieksplorasi (closed list)."""
        return self.explored_order


@dataclass
class MissionLegs:
    """Rute lengkap misi 3 etape: Spawn -> Pick-up -> Drop-off -> Return to Base."""
    leg1: SearchResult   # Spawn ke Pick-up
    leg2: SearchResult   # Pick-up ke Drop-off
    leg3: Optional[SearchResult] = None  # Drop-off ke Spawn (Auto-Return to Base)
    full_path: List[Coord] = field(default_factory=list)
    total_cost: float = 0.0
    total_nodes_explored: int = 0
    total_compute_time_ms: float = 0.0

    @property
    def success(self) -> bool:
        return self.leg1.success and self.leg2.success and (self.leg3 is None or self.leg3.success)

    @property
    def visited_nodes(self) -> List[Coord]:
        """Akumulasi seluruh simpul yang dieksplorasi di ketiga etape misi."""
        nodes = list(self.leg1.explored_order)
        if self.leg2 and self.leg2.explored_order:
            nodes.extend(self.leg2.explored_order)
        if self.leg3 and self.leg3.explored_order:
            nodes.extend(self.leg3.explored_order)
        return nodes


@dataclass
class DualRacePlan:
    """Hasil kalkulasi rute simultan untuk kedua robot AGV (A* vs GBFS)."""
    alpha_plan: MissionLegs   # A* Search
    beta_plan: MissionLegs    # Greedy Best-First Search
    shared_bottleneck_nodes: List[Coord] = field(default_factory=list)
    congestion_index: float = 0.0
    cost_delta: float = 0.0
    nodes_delta: int = 0

    @property
    def alpha_visited_nodes(self) -> Set[Coord]:
        """Himpunan seluruh simpul unik yang dieksplorasi oleh Robot Alpha (A*)."""
        return set(self.alpha_plan.visited_nodes)

    @property
    def beta_visited_nodes(self) -> Set[Coord]:
        """Himpunan seluruh simpul unik yang dieksplorasi oleh Robot Beta (GBFS)."""
        return set(self.beta_plan.visited_nodes)


def _reconstruct_path(came_from: Dict[Coord, Coord], current: Coord) -> List[Coord]:
    """Menyusun ulang jalur dari titik awal ke titik akhir."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _calculate_path_cost(graph: WarehouseGraph100, path: List[Coord]) -> float:
    """Menghitung akumulasi total biaya pergerakan sepanjang jalur (mempertimbangkan bobot medan)."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for i in range(len(path) - 1):
        if hasattr(graph, 'get_movement_cost'):
            total += graph.get_movement_cost(path[i], path[i + 1])
        else:
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
    Implementasi A* Search pada grid graf 35x25 teroptimasi tinggi.
    Fungsi evaluasi f(n) = g(n) + h(n) dengan prioritas tie-breaking h(n) terkecil.
    Optimal untuk biaya nonnegatif dan heuristik admissible; waktu bergantung pada peta.
    """
    t_start = time.perf_counter()

    if not graph.is_walkable(*start) or not graph.is_walkable(*goal):
        return SearchResult(algorithm_name='A* Search', success=False,
                            execution_time_ms=(time.perf_counter() - t_start) * 1000)

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

    # Scale distance by the cheapest terrain multiplier. Raw distances
    # overestimate cost when a boost cell costs less than one unit.
    scale = min(1.0, min(getattr(graph, 'terrain_weights', {}).values(), default=1.0))
    if scale < 0:
        raise ValueError("A* requires nonnegative terrain costs")
    distance = octile_distance if allow_diagonal and heuristic == manhattan_distance else heuristic
    def estimate(node):
        value = distance(node, goal)
        # Match the graph's diagonal constant (1.41421356).
        if allow_diagonal and distance == euclidean_distance:
            value = min(value, octile_distance(node, goal))
        return scale * value

    counter = 0
    h_start = estimate(start)
    open_heap = [(h_start, h_start, counter, start, 0.0)]
    came_from = {}
    g_score = {start: 0.0}
    explored_order = []
    success = False
    final_node = start
    while open_heap:
        _, _, _, current, queued_g = heapq.heappop(open_heap)
        if queued_g != g_score[current]:
            continue  # An obsolete entry from a more expensive route.
        explored_order.append(current)
        if current == goal:
            success, final_node = True, current
            break
        for neighbor in graph.get_neighbors(*current, allow_diagonal=allow_diagonal):
            step = (graph.get_movement_cost(current, neighbor)
                    if hasattr(graph, 'get_movement_cost') else graph.get_step_cost(current, neighbor))
            tentative_g = queued_g + step
            if tentative_g < g_score.get(neighbor, float('inf')):
                # Reopening also supports admissible but inconsistent heuristics.
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current
                h = estimate(neighbor)
                counter += 1
                heapq.heappush(open_heap, (tentative_g + h, h, counter, neighbor, tentative_g))

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
        nodes_explored=len(explored_order),
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
    Implementasi Greedy Best-First Search (GBFS) pada grid graf 35x25 teroptimasi.
    Fungsi evaluasi f(n) = h(n).
    Mengeksplorasi simpul dengan rakus ke arah target; cepat namun rentan suboptimal.
    """
    t_start = time.perf_counter()

    if not graph.is_walkable(*start) or not graph.is_walkable(*goal):
        return SearchResult(algorithm_name='Greedy Best-First Search', success=False,
                            execution_time_ms=(time.perf_counter() - t_start) * 1000)

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

def find_nearest_dock(
    graph: WarehouseGraph100,
    start: Coord,
    docks: List[Coord],
    heuristic: HeuristicFunc = manhattan_distance,
    use_astar: bool = True,
    allow_diagonal: bool = False,
) -> Optional[Tuple[Coord, SearchResult]]:
    """
    Mencari Charging Dock dengan biaya rute (g) terkecil dari posisi `start`.
    Menjalankan pencarian ke setiap dock lalu memilih hasil ber-cost terendah.
    use_astar=True memakai A* (rute optimal), False memakai GBFS.
    Mengembalikan (koordinat_dock, SearchResult), atau None jika tidak ada dock terjangkau.
    """
    search_fn = a_star_search if use_astar else greedy_best_first_search
    best_dock: Optional[Coord] = None
    best_res: Optional[SearchResult] = None
    for dock in docks:
        res = search_fn(graph, start, dock, heuristic, allow_diagonal)
        if res.success and (best_res is None or res.cost < best_res.cost):
            best_dock, best_res = dock, res
    if best_res is None or best_dock is None:
        return None
    return best_dock, best_res

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
        return_pos: Optional[Coord] = None,
        algo_name: str = "A*",
        heuristic: HeuristicFunc = manhattan_distance,
        allow_diagonal: bool = False,
    ) -> MissionLegs:
        """Menghitung rute tiga tahap: Start -> Pick-up -> Drop-off -> Return to Base."""
        search_fn = a_star_search if "A*" in algo_name else greedy_best_first_search

        # Etape 1: Dari titik spawn ke titik jemput (Pick-up)
        leg1 = search_fn(graph, start_pos, pickup_pos, heuristic, allow_diagonal)

        # Etape 2: Dari titik jemput ke titik antar (Drop-off)
        leg2 = search_fn(graph, pickup_pos, dropoff_pos, heuristic, allow_diagonal)

        # Etape 3: Dari titik antar kembali ke dock asal (Auto-Return to Base)
        leg3 = None
        if return_pos:
            leg3 = search_fn(graph, dropoff_pos, return_pos, heuristic, allow_diagonal)

        # Gabungkan rute utuh (hindari duplikasi titik temu)
        full_path = []
        if leg1.success:
            full_path.extend(leg1.path)
        if leg2.success:
            if full_path and leg2.path and full_path[-1] == leg2.path[0]:
                full_path.extend(leg2.path[1:])
            else:
                full_path.extend(leg2.path)
        if leg3 and leg3.success:
            if full_path and leg3.path and full_path[-1] == leg3.path[0]:
                full_path.extend(leg3.path[1:])
            else:
                full_path.extend(leg3.path)

        complete = leg1.success and leg2.success and (leg3 is None or leg3.success)
        if not complete:
            full_path = []  # Never expose disconnected successful fragments as a route.

        total_cost = leg1.cost + leg2.cost + (leg3.cost if leg3 else 0.0)
        if not complete:
            total_cost = float("inf")
        total_nodes = leg1.nodes_explored + leg2.nodes_explored + (leg3.nodes_explored if leg3 else 0)
        total_time = leg1.execution_time_ms + leg2.execution_time_ms + (leg3.execution_time_ms if leg3 else 0.0)

        return MissionLegs(
            leg1=leg1,
            leg2=leg2,
            leg3=leg3,
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
        return_to_dock: bool = True,
    ) -> DualRacePlan:
        """
        Kalkulasi rute simultan untuk kedua robot AGV (Leg 1, Leg 2, Leg 3):
        - AGV Alpha menggunakan A* Search
        - AGV Beta menggunakan Greedy Best-First Search
        """
        ret_alpha = spawn_alpha if return_to_dock else None
        ret_beta = spawn_beta if return_to_dock else None

        plan_alpha = cls.plan_mission_legs(
            graph, spawn_alpha, pickup_access, dropoff_access,
            return_pos=ret_alpha,
            algo_name="A*", heuristic=heuristic, allow_diagonal=allow_diagonal,
        )

        plan_beta = cls.plan_mission_legs(
            graph, spawn_beta, pickup_access, dropoff_access,
            return_pos=ret_beta,
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
