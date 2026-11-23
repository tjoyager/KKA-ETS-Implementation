"""
mission_manager.py
==================
Manajer Misi & Pengelola Balapan Konkuren Dual-Robot AGV (A* Search vs GBFS).
Mengatur siklus hidup misi: seleksi titik jemput (Pick-up), titik antar (Drop-off),
kalkulasi rencana balapan sinkron, pelacakan waktu, sistem skor, dan penentuan pemenang.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional, Set, Tuple, Union
from ursina import time, camera, color, invoke, Entity, Vec3, Text, destroy

from src.config import (
    SPAWN_ALPHA,
    SPAWN_BETA,
    DEFAULT_ROBOT_SPEED,
    MIN_ROBOT_SPEED,
    MAX_ROBOT_SPEED,
    grid_to_world,
)
from src.cognition.warehouse_graph import WarehouseGraph100
from src.cognition.heuristics import AVAILABLE_HEURISTICS
from src.cognition.pathfinding import DualPathPlanner, DualRacePlan
from src.behavior.robot_controller import AGVRobot, RobotState
from src.environment.interactive_shelf import InteractiveShelf
from src.environment.warehouse_scene import WarehouseScene

Coord = Tuple[int, int]


class MissionType(Enum):
    STANDARD_DELIVERY = "Pengantaran Standar (Pick-up -> Drop-off)"
    INTER_ZONE_TRANSFER = "Transfer Antar-Zona (Menuju Gerbang Zone B)"


@dataclass
class DeliveryOrder:
    """Representasi satu tiket pesanan pengantaran barang dalam antrean sistem WMS."""
    order_id: int
    pickup_shelf: InteractiveShelf
    dropoff_shelf: InteractiveShelf


class MissionManager:
    """
    Koordinator sentral balapan dua robot AGV di gudang 35x25.
    """

    def __init__(
        self,
        graph: WarehouseGraph100,
        scene: WarehouseScene,
        robot_alpha: AGVRobot,
        robot_beta: AGVRobot,
    ):
        self.graph = graph
        self.scene = scene
        self.scene.mission_mgr = self
        self.robot_alpha = robot_alpha
        self.robot_beta = robot_beta

        # State Misi Aktif
        self.selected_pickup_shelf: Optional[InteractiveShelf] = None
        self.selected_dropoff_shelf: Optional[InteractiveShelf] = None
        self.current_pickup_access: Optional[Coord] = None
        self.current_dropoff_access: Optional[Coord] = None
        self.dual_plan: Optional[DualRacePlan] = None

        # Konfigurasi Heuristik Dinamis
        self.heuristic_names = ["Manhattan", "Euclidean", "Chebyshev", "Octile"]
        self.heuristic_idx = 0
        self.current_heuristic_name = "Manhattan"
        self.current_heuristic_info = AVAILABLE_HEURISTICS["Manhattan"]
        self.current_heuristic_fn = AVAILABLE_HEURISTICS["Manhattan"]["fn"]
        self._sync_robot_context()

        # Multi-Stage & Zone Transfer (Fitur 2)
        self.mission_type = MissionType.STANDARD_DELIVERY
        self.current_zone = "Zone A"
        self.is_transitioning = False

        self.is_race_active: bool = False
        self.race_start_time: Optional[float] = None
        self.race_elapsed_time: float = 0.0
        self.current_speed: float = DEFAULT_ROBOT_SPEED
        self.is_paused: bool = False

        # Status Hasil Balapan
        self.first_to_arrive: Optional[str] = None
        self.arrival_delta_time: float = 0.0
        self.overall_efficiency_winner: Optional[str] = None
        self.race_finished: bool = False

        # State Gamifikasi
        self.score: int = 0
        self.combo_multiplier: int = 1
        self.star_rating: int = 5
        self.missions_completed: int = 0
        self.rating_explanation: str = "Pilih tugas pertama Anda!"

        # Sistem Antrean Pesanan Misi (Order Task Queue - FIFO)
        self.task_queue: List[DeliveryOrder] = []
        self._order_counter: int = 1

        # Rintangan Bergerak Dinamis (User Forklifts)
        self.forklift = None
        self.forklifts: List[Any] = []
        self._charger_markers: list = []
        self._refresh_charging_markers()
        self._sync_robot_context()

    def _sync_robot_context(self):
        """Sinkronkan graf & heuristik aktif ke kedua robot (dipakai protokol baterai darurat)."""
        self.graph.traffic_manager = self
        for robot in (self.robot_alpha, self.robot_beta):
            robot.graph = self.graph
            robot.heuristic_fn = self.current_heuristic_fn

    def _refresh_charging_markers(self):
        """Menggambar penanda stasiun pengisian tambahan (startup & ganti zona)."""
        for ent in self._charger_markers:
            destroy(ent)
        self._charger_markers = []
        for dock in self.graph.get_charging_docks():
            if dock in (self.graph.dock_alpha, self.graph.dock_beta):
                continue  # dock spawn sudah punya model 3D sendiri
            from src.environment.interior_charging_station import InteriorChargingStation
            self._charger_markers.append(InteriorChargingStation(self, dock))

    def set_forklift(self, forklift):
        """Mendaftarkan objek Forklift interaktif untuk deteksi ancaman tabrakan real-time."""
        if isinstance(forklift, (list, tuple)):
            self.forklifts = list(forklift)
            self.forklift = self.forklifts[0] if self.forklifts else None
        else:
            self.forklift = forklift
            self.forklifts = [forklift] if forklift else []

    def set_forklifts(self, forklifts: List[Any]):
        """Mendaftarkan daftar beberapa unit Forklift."""
        self.forklifts = list(forklifts)
        self.forklift = forklifts[0] if forklifts else None

    def enqueue_order(
        self,
        pickup_shelf: InteractiveShelf,
        dropoff_shelf: InteractiveShelf,
    ) -> int:
        """
        Menambahkan tiket pesanan baru ke antrean FIFO.
        Mengembalikan order_id tiket yang dibuat.
        """
        order_id = self._order_counter
        self._order_counter += 1
        order = DeliveryOrder(
            order_id=order_id,
            pickup_shelf=pickup_shelf,
            dropoff_shelf=dropoff_shelf,
        )
        self.task_queue.append(order)
        return order_id

    @property
    def pending_orders(self) -> List[DeliveryOrder]:
        """Daftar antrean pesanan pengantaran tertunda (alias untuk task_queue)."""
        return self.task_queue

    def is_pickup_booked(self, x: Union[int, Tuple[int, int]], y: Optional[int] = None) -> bool:
        """
        Mengecek apakah sebuah koordinat (x, y) sudah ada di dalam daftar pending_orders / task_queue
        sebagai lokasi pickup (atau sedang ditargetkan untuk diambil oleh misi aktif).
        Mendukung pemanggilan:
            is_pickup_booked(x, y)
            is_pickup_booked((x, y))
        """
        if isinstance(x, (tuple, list)):
            target_x, target_y = int(x[0]), int(x[1])
        else:
            target_x, target_y = int(x), int(y)

        # 1. Cek di daftar pending_orders / task_queue
        for order in self.task_queue:
            ps = order.pickup_shelf
            if ps is not None:
                ps_coord = (ps.shelf_data.x, ps.shelf_data.y) if hasattr(ps, 'shelf_data') else (getattr(ps, 'x', None), getattr(ps, 'y', None))
                if ps_coord == (target_x, target_y):
                    return True

        # 2. Cek juga misi aktif saat ini jika kargo di rak belum selesai diambil
        if self.is_race_active and not self.race_finished and self.selected_pickup_shelf:
            ps = self.selected_pickup_shelf
            ps_coord = (ps.shelf_data.x, ps.shelf_data.y) if hasattr(ps, 'shelf_data') else (getattr(ps, 'x', None), getattr(ps, 'y', None))
            if ps_coord == (target_x, target_y) and hasattr(ps, 'shelf_data') and ps.shelf_data.has_cargo:
                return True

        return False

    def is_cargo_booked(self, x: Union[int, Tuple[int, int]], y: Optional[int] = None) -> bool:
        """Alias kompatibilitas untuk is_pickup_booked."""
        return self.is_pickup_booked(x, y)

    def dispatch_race(
        self,
        pickup_shelf: InteractiveShelf,
        dropoff_shelf: InteractiveShelf,
    ) -> bool:
        """
        Memulai simulasi balapan konkurensi:
        1. Menghitung rute A* untuk Robot Alpha.
        2. Menghitung rute GBFS untuk Robot Beta.
        3. Menjalankan kedua robot secara serentak.
        """
        self._sync_robot_context()
        self.selected_pickup_shelf = pickup_shelf
        self.selected_dropoff_shelf = dropoff_shelf
        pickup_shelf.mark_as_pickup(True)
        dropoff_shelf.mark_as_dropoff(True)

        # Ambil titik akses lorong terdekat untuk kedua rak
        pickup_coord = pickup_shelf.shelf_data.coord
        dropoff_coord = dropoff_shelf.shelf_data.coord

        pickup_access = self.graph.get_shelf_access_node(pickup_coord, from_coord=SPAWN_ALPHA)
        dropoff_access = self.graph.get_shelf_access_node(dropoff_coord, from_coord=pickup_access)

        self.current_pickup_access = pickup_access
        self.current_dropoff_access = dropoff_access

        # Hitung perencanaan rute dual-robot secara konkuren
        self.dual_plan = DualPathPlanner.plan_dual_race(
            graph=self.graph,
            spawn_alpha=self.robot_alpha.spawn_coord,
            spawn_beta=self.robot_beta.spawn_coord,
            pickup_access=pickup_access,
            dropoff_access=dropoff_access,
            heuristic=self.current_heuristic_fn,
        )

        plan = self.dual_plan
        if not (plan.alpha_plan.success and plan.beta_plan.success):
            print("[MissionManager] Gagal: Tidak ada rute yang dapat diakses ke rak tersebut.")
            return False

        # Reset status balapan
        self.first_to_arrive = None
        self.arrival_delta_time = 0.0
        self.overall_efficiency_winner = None
        self.race_finished = False
        self.race_start_time = time.time()
        self.race_elapsed_time = 0.0
        self.is_race_active = True
        self.is_paused = False

        # Reset posisi awal robot ke dock sebelum memulai balapan baru
        self.robot_alpha.reset_to_dock()
        self.robot_beta.reset_to_dock()
        if hasattr(self.scene, 'clear_exploration_heatmap'):
            self.scene.clear_exploration_heatmap()

        # Berikan rute 3 Etape (Pick-up -> Drop-off -> Return to Base) ke Robot Alpha (A*)
        leg3_alpha = plan.alpha_plan.leg3.path if plan.alpha_plan.leg3 and plan.alpha_plan.leg3.success else []
        self.robot_alpha.graph = self.graph
        self.robot_alpha.speed = self.current_speed
        self.robot_alpha.set_mission_legs(
            leg1_path=plan.alpha_plan.leg1.path,
            leg2_path=plan.alpha_plan.leg2.path,
            leg3_path=leg3_alpha,
            on_pickup=self._on_robot_pickup,
            on_dropoff=self._on_robot_dropoff,
            on_finish=self._on_robot_finish,
        )

        # Berikan rute 3 Etape ke Robot Beta (GBFS)
        leg3_beta = plan.beta_plan.leg3.path if plan.beta_plan.leg3 and plan.beta_plan.leg3.success else []
        self.robot_beta.graph = self.graph
        self.robot_beta.speed = self.current_speed
        self.robot_beta.set_mission_legs(
            leg1_path=plan.beta_plan.leg1.path,
            leg2_path=plan.beta_plan.leg2.path,
            leg3_path=leg3_beta,
            on_pickup=self._on_robot_pickup,
            on_dropoff=self._on_robot_dropoff,
            on_finish=self._on_robot_finish,
        )

        # Visualisasikan Heatmap Komputasi Node Exploration (Fitur 1: A* vs GBFS)
        alpha_nodes = plan.alpha_visited_nodes
        beta_nodes = plan.beta_visited_nodes
        self.robot_alpha.last_explored_nodes = set(alpha_nodes)
        self.robot_beta.last_explored_nodes = set(beta_nodes)
        if hasattr(self.scene, 'render_exploration_heatmap'):
            self.scene.render_exploration_heatmap(alpha_nodes, beta_nodes)

        return True

    def _on_robot_pickup(self, robot: AGVRobot):
        """Dipanggil saat salah satu robot tiba di rak pick-up."""
        if self.selected_pickup_shelf and self.selected_pickup_shelf.shelf_data.has_cargo:
            item_name = self.selected_pickup_shelf.remove_cargo()

    def _on_robot_dropoff(self, robot: AGVRobot):
        """Dipanggil saat salah satu robot tiba di rak tujuan drop-off dan menaruh kargo."""
        if self.selected_dropoff_shelf:
            self.selected_dropoff_shelf.place_cargo("Industrial Package")

    def _on_robot_finish(self, robot: AGVRobot):
        """Dipanggil saat salah satu robot telah kembali dan standby di stasiun docking asalnya (Leg 3 selesai)."""
        if not self.first_to_arrive:
            self.first_to_arrive = f"{robot.robot_name} ({robot.algo_label})"
            self.arrival_delta_time = time.time() - self.race_start_time

    def reset_race(self):
        """Mereset seluruh arena, posisi robot, dan seleksi rak."""
        self.is_race_active = False
        self.race_finished = False
        self.race_start_time = None
        self.race_elapsed_time = 0.0
        self.first_to_arrive = None
        self.overall_efficiency_winner = None

        if self.selected_pickup_shelf:
            self.selected_pickup_shelf.clear_selection()
            self.selected_pickup_shelf = None

        if self.selected_dropoff_shelf:
            self.selected_dropoff_shelf.clear_selection()
            self.selected_dropoff_shelf = None

        self.robot_alpha.reset_to_dock()
        self.robot_beta.reset_to_dock()
        if hasattr(self.scene, 'clear_exploration_heatmap'):
            self.scene.clear_exploration_heatmap()

    def toggle_pause(self) -> bool:
        """Menjeda atau melanjutkan pergerakan kedua robot."""
        self.is_paused = not self.is_paused
        self.robot_alpha.is_paused = self.is_paused
        self.robot_beta.is_paused = self.is_paused
        return self.is_paused

    def adjust_speed(self, delta: float) -> float:
        """Mengatur laju kecepatan balapan kedua robot."""
        self.current_speed = max(MIN_ROBOT_SPEED, min(MAX_ROBOT_SPEED, self.current_speed + delta))
        self.robot_alpha.speed = self.current_speed
        self.robot_beta.speed = self.current_speed
        return self.current_speed

    def cycle_heuristic(self) -> str:
        """Beralih ke heuristik berikutnya dalam siklus (Manhattan -> Euclidean -> Chebyshev -> Octile)."""
        self.heuristic_idx = (self.heuristic_idx + 1) % len(self.heuristic_names)
        self.current_heuristic_name = self.heuristic_names[self.heuristic_idx]
        self.current_heuristic_info = AVAILABLE_HEURISTICS[self.current_heuristic_name]
        self.current_heuristic_fn = self.current_heuristic_info["fn"]
        self._sync_robot_context()

        # Jika misi sedang berjalan atau rak sudah dipilih, rencanakan ulang segera!
        if self.selected_pickup_shelf and self.selected_dropoff_shelf:
            self.replan_race()
        return self.current_heuristic_name

    def replan_race(self):
        """Update search plans without restarting robots from their spawns.

        ``dual_plan`` remains the full-route, dock-origin comparison shown
        in the HUD. Active AGVs instead replan their *remaining* mission
        from their current position, preserving the current cargo phase.
        """
        if not (self.selected_pickup_shelf and self.selected_dropoff_shelf):
            return
        if self.race_finished or self.is_transitioning:
            return

        pickup_coord = self.selected_pickup_shelf.shelf_data.coord
        dropoff_coord = self.selected_dropoff_shelf.shelf_data.coord

        # Keep the selected access nodes stable during a running delivery.
        # This avoids silently switching the pickup/dropoff target mid-mission.
        pickup_access = self.current_pickup_access
        dropoff_access = self.current_dropoff_access
        if pickup_access is None:
            pickup_access = self.graph.get_shelf_access_node(
                pickup_coord, from_coord=SPAWN_ALPHA
            )
        if dropoff_access is None:
            dropoff_access = self.graph.get_shelf_access_node(
                dropoff_coord, from_coord=pickup_access
            )
        if pickup_access is None or dropoff_access is None:
            return

        plan = DualPathPlanner.plan_dual_race(
            graph=self.graph,
            spawn_alpha=self.robot_alpha.spawn_coord,
            spawn_beta=self.robot_beta.spawn_coord,
            pickup_access=pickup_access,
            dropoff_access=dropoff_access,
            heuristic=self.current_heuristic_fn,
        )
        if not (plan.alpha_plan.success and plan.beta_plan.success):
            return
        self.dual_plan = plan
        self.current_pickup_access = pickup_access
        self.current_dropoff_access = dropoff_access

        if not self.is_race_active or self.mission_type != MissionType.STANDARD_DELIVERY:
            return

        # Recalculate only remaining legs. Do NOT call set_mission_legs():
        # that method is for a fresh mission and teleports to waypoint zero.
        updated_a = self.robot_alpha.replan_for_heuristic(
            self.graph, self.current_heuristic_fn, pickup_coord, dropoff_coord
        )
        updated_b = self.robot_beta.replan_for_heuristic(
            self.graph, self.current_heuristic_fn, pickup_coord, dropoff_coord
        )
        if (updated_a or updated_b) and hasattr(self.scene, "render_exploration_heatmap"):
            self.scene.render_exploration_heatmap(
                self.robot_alpha.last_explored_nodes,
                self.robot_beta.last_explored_nodes,
            )

    def handle_dynamic_obstacle(self, obs_coord: Coord) -> Tuple[bool, bool]:
        """
        Memeriksa apakah rintangan baru memotong rute aktif Robot Alpha (A*) dan/atau Robot Beta (GBFS).
        Jika ya, paksa algoritma masing-masing untuk segera menghitung ulang rute secara real-time.
        Returns: (alpha_replanned, beta_replanned)
        """
        alpha_replanned = False
        beta_replanned = False

        pickup_coord = self.selected_pickup_shelf.shelf_data.coord if self.selected_pickup_shelf else None
        dropoff_coord = self.selected_dropoff_shelf.shelf_data.coord if self.selected_dropoff_shelf else None

        if self.is_race_active and not self.race_finished:
            if self.robot_alpha.is_path_blocked_by(obs_coord):
                success = self.robot_alpha.recalculate_route(
                    graph=self.graph,
                    heuristic_fn=self.current_heuristic_fn,
                    pickup_shelf_coord=pickup_coord,
                    dropoff_shelf_coord=dropoff_coord,
                )
                if success:
                    alpha_replanned = True

            if self.robot_beta.is_path_blocked_by(obs_coord):
                success = self.robot_beta.recalculate_route(
                    graph=self.graph,
                    heuristic_fn=self.current_heuristic_fn,
                    pickup_shelf_coord=pickup_coord,
                    dropoff_shelf_coord=dropoff_coord,
                )
                if success:
                    beta_replanned = True

        if (alpha_replanned or beta_replanned) and hasattr(self.scene, 'render_exploration_heatmap'):
            self.scene.render_exploration_heatmap(
                self.robot_alpha.last_explored_nodes,
                self.robot_beta.last_explored_nodes,
            )

        return (alpha_replanned, beta_replanned)

    def handle_dynamic_obstacle_removed(self, removed_coord: Coord):
        """Ketika rintangan dihapus, memungkinkan kedua robot mengevaluasi kembali rute mereka."""
        pickup_coord = self.selected_pickup_shelf.shelf_data.coord if self.selected_pickup_shelf else None
        dropoff_coord = self.selected_dropoff_shelf.shelf_data.coord if self.selected_dropoff_shelf else None

        if self.is_race_active and not self.race_finished:
            self.robot_alpha.recalculate_route(
                graph=self.graph,
                heuristic_fn=self.current_heuristic_fn,
                pickup_shelf_coord=pickup_coord,
                dropoff_shelf_coord=dropoff_coord,
            )
            self.robot_beta.recalculate_route(
                graph=self.graph,
                heuristic_fn=self.current_heuristic_fn,
                pickup_shelf_coord=pickup_coord,
                dropoff_shelf_coord=dropoff_coord,
            )
            if hasattr(self.scene, 'render_exploration_heatmap'):
                self.scene.render_exploration_heatmap(
                    self.robot_alpha.last_explored_nodes,
                    self.robot_beta.last_explored_nodes,
                )

    def handle_terrain_modified(self, coord: Coord):
        """Ketika modifier medan (Tumpahan Oli / Boost Pad) diletakkan atau dihapus."""
        pickup_coord = self.selected_pickup_shelf.shelf_data.coord if self.selected_pickup_shelf else None
        dropoff_coord = self.selected_dropoff_shelf.shelf_data.coord if self.selected_dropoff_shelf else None

        if self.is_race_active and not self.race_finished:
            rep_a = self.robot_alpha.recalculate_route(
                graph=self.graph,
                heuristic_fn=self.current_heuristic_fn,
                pickup_shelf_coord=pickup_coord,
                dropoff_shelf_coord=dropoff_coord,
            )
            rep_b = self.robot_beta.recalculate_route(
                graph=self.graph,
                heuristic_fn=self.current_heuristic_fn,
                pickup_shelf_coord=pickup_coord,
                dropoff_shelf_coord=dropoff_coord,
            )
            if (rep_a or rep_b) and hasattr(self.scene, 'render_exploration_heatmap'):
                self.scene.render_exploration_heatmap(
                    self.robot_alpha.last_explored_nodes,
                    self.robot_beta.last_explored_nodes,
                )

    def trigger_random_mission(self) -> bool:
        """
        Otomasi memilih secara acak satu rak kargo (Pick-up) dan satu rak kosong (Drop-off),
        lalu langsung meluncurkan balapan!
        """
        self.reset_race()
        self._sync_robot_context()

        cargo_data = self.graph.get_random_cargo_shelf()
        if not cargo_data:
            return False

        empty_data = self.graph.get_random_empty_shelf(exclude_coord=cargo_data.coord)
        if not empty_data:
            return False

        pickup_ent = self.scene.interactive_shelves.get(cargo_data.coord)
        dropoff_ent = self.scene.interactive_shelves.get(empty_data.coord)

        if not (pickup_ent and dropoff_ent):
            return False

        pickup_ent.mark_as_pickup(True)
        dropoff_ent.mark_as_dropoff(True)

        return self.dispatch_race(pickup_ent, dropoff_ent)

    # =========================================================================
    # FITUR 2: TRANSFER ANTAR-ZONA (STAGE / MULTI-ZONE TRANSITION)
    # =========================================================================
    def dispatch_zone_transfer(self) -> bool:
        """
        Meluncurkan balapan menuju Transfer Gate di x=34, y=13 untuk beralih zona.
        AGV Alpha (A*) vs AGV Beta (GBFS) berpacu menuju gerbang transfer.
        """
        if self.is_transitioning:
            return False

        self.reset_race()
        self._sync_robot_context()
        self.mission_type = MissionType.INTER_ZONE_TRANSFER
        gate_target = (33, 13)

        from src.cognition.pathfinding import a_star_search, greedy_best_first_search
        res_alpha = a_star_search(self.graph, self.robot_alpha.spawn_coord, gate_target, heuristic=self.current_heuristic_fn)
        res_beta = greedy_best_first_search(self.graph, self.robot_beta.spawn_coord, gate_target, heuristic=self.current_heuristic_fn)

        if not (res_alpha.success and res_beta.success):
            print("[MissionManager] Gagal: Rute ke Gerbang Transfer terhalang.")
            return False

        self.robot_alpha.reset_to_dock()
        self.robot_beta.reset_to_dock()
        if hasattr(self.scene, 'clear_exploration_heatmap'):
            self.scene.clear_exploration_heatmap()

        self.robot_alpha.speed = self.current_speed
        self.robot_alpha.set_mission_legs(
            leg1_path=res_alpha.path,
            leg2_path=[],
            on_pickup=None,
            on_dropoff=None,
        )

        self.robot_beta.speed = self.current_speed
        self.robot_beta.set_mission_legs(
            leg1_path=res_beta.path,
            leg2_path=[],
            on_pickup=None,
            on_dropoff=None,
        )

        self.is_race_active = True
        self.race_finished = False
        self.race_start_time = time.time()
        self.race_elapsed_time = 0.0
        return True

    # Alias kompatibilitas
    trigger_zone_transfer_mission = dispatch_zone_transfer

    def execute_zone_transition(self):
        """Memulai sekuens transisi ruangan antar-zona dengan efek fade-out kamera."""
        if self.is_transitioning:
            return
        self.is_transitioning = True
        self.is_race_active = False

        self._alpha_batt_temp = self.robot_alpha.battery
        self._beta_batt_temp = self.robot_beta.battery

        self.robot_alpha.is_paused = True
        self.robot_beta.is_paused = True

        from ursina import camera, color, invoke
        camera.overlay.color = color.clear
        camera.overlay.animate_color(color.black, duration=1.0)
        invoke(self._finish_zone_transition, delay=1.0)

    def _finish_zone_transition(self):
        """Mengeksekusi regenerasi layout matriks rintangan/rak baru di balik layar hitam dan fade-in."""
        from ursina import camera, color

        # Simpan nilai baterai saat ini sebelum robot di-reset atau di-rebuild untuk zona baru
        alpha_batt_temp = getattr(self, '_alpha_batt_temp', self.robot_alpha.battery)
        beta_batt_temp = getattr(self, '_beta_batt_temp', self.robot_beta.battery)

        # Beralih antara Zone A dan Zone B
        if self.current_zone == "Zone A":
            self.current_zone = "Zone B"
            new_graph = WarehouseGraph100.generate_zone_b_warehouse()
        else:
            self.current_zone = "Zone A"
            new_graph = WarehouseGraph100.generate_complex_warehouse()

        self.graph = new_graph
        self.scene.rebuild_for_new_zone(new_graph)
        self._sync_robot_context()
        self._refresh_charging_markers()

        # 1. Teleportasi robot ke sel grid tepat di depan Transfer Gate (keluar dari gerbang)
        gate_alpha = (33, 12)
        gate_beta = (33, 14)
        if not self.graph.is_walkable(gate_alpha[0], gate_alpha[1]):
            gate_alpha = (33, 13)
        if not self.graph.is_walkable(gate_beta[0], gate_beta[1]):
            gate_beta = (33, 13)

        self.robot_alpha.clear_trail()
        self.robot_beta.clear_trail()
        self.robot_alpha.position = grid_to_world(gate_alpha[0], gate_alpha[1], 0.0)
        self.robot_beta.position = grid_to_world(gate_beta[0], gate_beta[1], 0.0)
        self.robot_alpha.rotation_y = -90.0  # Menghadap ke barat (masuk ke dalam gudang)
        self.robot_beta.rotation_y = -90.0
        self.robot_alpha.deck_cargo.enabled = False
        self.robot_beta.deck_cargo.enabled = False

        if hasattr(self.scene, 'clear_exploration_heatmap'):
            self.scene.clear_exploration_heatmap()

        # 2. Pewarisan sisa baterai dari zona sebelumnya (override baterai dengan nilai temp)
        self.robot_alpha.battery = alpha_batt_temp
        self.robot_beta.battery = beta_batt_temp
        self.robot_alpha._update_battery_visual()
        self.robot_beta._update_battery_visual()

        # Sambungkan callback kedatangan di base dock
        self.robot_alpha.on_finish_callback = self._on_robot_finish
        self.robot_beta.on_finish_callback = self._on_robot_finish

        # Set state non-idle agar force_return_to_dock mengkalkulasi rute pulang
        self.robot_alpha.state = RobotState.MOVING_TO_DROPOFF
        self.robot_beta.state = RobotState.MOVING_TO_DROPOFF

        # 3. Panggil force_return_to_dock agar robot mengkalkulasi rute mandiri pulang ke Twin Dock
        self.robot_alpha.force_return_to_dock(self.graph, self.current_heuristic_fn)
        self.robot_beta.force_return_to_dock(self.graph, self.current_heuristic_fn)

        self.mission_type = MissionType.STANDARD_DELIVERY
        self.is_race_active = True
        self.race_finished = False
        self.race_start_time = time.time()
        self.race_elapsed_time = 0.0

        # Fade-In kembali ke tampilan normal
        camera.overlay.animate_color(color.clear, duration=1.0)
        self.is_transitioning = False
        print(f"[MissionManager] Berhasil berpindah ke {self.current_zone}!")

    def update(self):
        """Update loop per frame untuk pengecekan ancaman forklift, auto-dispatch antrean, dan gamifikasi."""
        # 2. Penugasan Otomatis Antrean Pesanan FIFO (Auto-Dispatch Task Queue)
        if not self.is_transitioning and len(self.task_queue) > 0:
            alpha_ready = self.robot_alpha.state in (RobotState.IDLE_DOCK, RobotState.FINISHED)
            beta_ready = self.robot_beta.state in (RobotState.IDLE_DOCK, RobotState.FINISHED)
            if (not self.is_race_active or self.race_finished) and alpha_ready and beta_ready:
                next_order = self.task_queue.pop(0)
                self.dispatch_race(next_order.pickup_shelf, next_order.dropoff_shelf)

        if self.is_race_active and not self.is_paused:
            self.race_elapsed_time += time.dt

            # Deteksi pencapaian Transfer Gate untuk transisi ruangan
            if self.mission_type == MissionType.INTER_ZONE_TRANSFER and not self.is_transitioning:
                c_alpha = self.robot_alpha.get_current_grid_coord()
                c_beta = self.robot_beta.get_current_grid_coord()
                gate_targets = self.graph.transfer_gate_coords | {(33, 12), (33, 13), (33, 14)}
                if c_alpha in gate_targets or c_beta in gate_targets or self.robot_alpha.state == RobotState.FINISHED or self.robot_beta.state == RobotState.FINISHED:
                    self.execute_zone_transition()
                    return

            # Cek apakah kedua robot sudah menyelesaikan pergerakan
            alpha_done = self.robot_alpha.state in (RobotState.FINISHED, RobotState.DEAD)
            beta_done = self.robot_beta.state in (RobotState.FINISHED, RobotState.DEAD)

            if alpha_done and beta_done and not self.race_finished:
                self._finalize_race_outcome()

    def _finalize_race_outcome(self):
        """Menghitung evaluasi komparatif akhir saat balapan selesai."""
        self.race_finished = True
        self.is_race_active = False
        self.missions_completed += 1
        if hasattr(self.scene, 'clear_exploration_heatmap'):
            self.scene.clear_exploration_heatmap()

        plan = self.dual_plan
        cost_alpha = plan.alpha_plan.total_cost if plan else 1.0
        cost_beta = plan.beta_plan.total_cost if plan else 1.0

        # Evaluasi Efisiensi Teori Graf
        if cost_alpha < cost_beta:
            savings_pct = ((cost_beta - cost_alpha) / cost_beta) * 100.0
            self.overall_efficiency_winner = f"AGV Alpha (A*) — Rute Lebih Hemat {savings_pct:.1f}%!"
        elif cost_beta < cost_alpha:
            self.overall_efficiency_winner = "AGV Beta (GBFS)!"
        else:
            self.overall_efficiency_winner = "Seri! Kedua Rute Menghasilkan Panjang yang Sama."

        # Kalkulasi Skor Gamifikasi
        # Skor dasar 5000 dikurangi penalti selisih langkah dan durasi
        cost_ratio = cost_beta / max(cost_alpha, 1.0)
        time_penalty = int(self.race_elapsed_time * 25)
        path_penalty = int(max(0, cost_beta - cost_alpha) * 120)

        mission_score = max(500, int((4500 - time_penalty - path_penalty) * self.combo_multiplier))
        self.score += mission_score

        # Kalkulasi Rating Bintang (1 - 5 Bintang)
        if cost_ratio <= 1.02 and self.race_elapsed_time < 25.0:
            self.star_rating = 5
            self.rating_explanation = "SEMPURNA ([5/5 BINTANG]): Rute optimal dieksekusi dengan kecepatan puncak!"
            self.combo_multiplier += 1
        elif cost_ratio <= 1.08:
            self.star_rating = 4
            self.rating_explanation = "SANGAT BAIK ([4/5 BINTANG]): Jalur efisien dengan sedikit deviasi waktu."
            self.combo_multiplier += 1
        elif cost_ratio <= 1.20:
            self.star_rating = 3
            self.rating_explanation = "CUKUP ([3/5 BINTANG]): GBFS mengambil rute memutar yang memperlambat armada."
            self.combo_multiplier = 1
        elif cost_ratio <= 1.35:
            self.star_rating = 2
            self.rating_explanation = "SUB-OPTIMAL ([2/5 BINTANG]): GBFS terjebak sekat buntu lorong atas gudang."
            self.combo_multiplier = 1
        else:
            self.star_rating = 1
            self.rating_explanation = "BURUK ([1/5 BINTANG]): Terjadi inefisiensi navigasi parah pada rute rak."
            self.combo_multiplier = 1
