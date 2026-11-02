"""
mission_manager.py
==================
Manajer Misi & Pengelola Balapan Konkuren Dual-Robot AGV (A* Search vs GBFS).
Mengatur siklus hidup misi: seleksi titik jemput (Pick-up), titik antar (Drop-off),
kalkulasi rencana balapan sinkron, pelacakan waktu, sistem skor, dan penentuan pemenang.
"""

from typing import Optional, Tuple
from ursina import time

from src.config import (
    SPAWN_ALPHA,
    SPAWN_BETA,
    DEFAULT_ROBOT_SPEED,
    MIN_ROBOT_SPEED,
    MAX_ROBOT_SPEED,
)
from src.cognition.warehouse_graph import WarehouseGraph100
from src.cognition.pathfinding import DualPathPlanner, DualRacePlan
from src.behavior.robot_controller import AGVRobot, RobotState
from src.environment.interactive_shelf import InteractiveShelf
from src.environment.warehouse_scene import WarehouseScene

Coord = Tuple[int, int]


class MissionManager:
    """
    Koordinator sentral balapan dua robot AGV di gudang 50x50.
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
        self.robot_alpha = robot_alpha
        self.robot_beta = robot_beta

        # State Misi Aktif
        self.selected_pickup_shelf: Optional[InteractiveShelf] = None
        self.selected_dropoff_shelf: Optional[InteractiveShelf] = None
        self.dual_plan: Optional[DualRacePlan] = None

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
        self.selected_pickup_shelf = pickup_shelf
        self.selected_dropoff_shelf = dropoff_shelf

        # Ambil titik akses lorong terdekat untuk kedua rak
        pickup_coord = pickup_shelf.shelf_data.coord
        dropoff_coord = dropoff_shelf.shelf_data.coord

        pickup_access = self.graph.get_shelf_access_node(pickup_coord, from_coord=SPAWN_ALPHA)
        dropoff_access = self.graph.get_shelf_access_node(dropoff_coord, from_coord=pickup_access)

        # Hitung perencanaan rute dual-robot secara konkuren
        self.dual_plan = DualPathPlanner.plan_dual_race(
            graph=self.graph,
            spawn_alpha=self.robot_alpha.spawn_coord,
            spawn_beta=self.robot_beta.spawn_coord,
            pickup_access=pickup_access,
            dropoff_access=dropoff_access,
        )

        plan = self.dual_plan
        if not (plan.alpha_plan.leg1.success and plan.beta_plan.leg1.success):
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

        # Berikan rute ke Robot Alpha (A*)
        self.robot_alpha.speed = self.current_speed
        self.robot_alpha.set_mission_legs(
            leg1_path=plan.alpha_plan.leg1.path,
            leg2_path=plan.alpha_plan.leg2.path,
            on_pickup=self._on_robot_pickup,
            on_dropoff=self._on_robot_dropoff,
        )

        # Berikan rute ke Robot Beta (GBFS)
        self.robot_beta.speed = self.current_speed
        self.robot_beta.set_mission_legs(
            leg1_path=plan.beta_plan.leg1.path,
            leg2_path=plan.beta_plan.leg2.path,
            on_pickup=self._on_robot_pickup,
            on_dropoff=self._on_robot_dropoff,
        )

        return True

    def _on_robot_pickup(self, robot: AGVRobot):
        """Dipanggil saat salah satu robot tiba di rak pick-up."""
        if self.selected_pickup_shelf and self.selected_pickup_shelf.shelf_data.has_cargo:
            item_name = self.selected_pickup_shelf.remove_cargo()
            # print(f"[{robot.robot_name}] Mengambil kargo: {item_name}")

    def _on_robot_dropoff(self, robot: AGVRobot):
        """Dipanggil saat salah satu robot tiba di rak tujuan drop-off."""
        if not self.first_to_arrive:
            # Robot pertama yang mencapai garis akhir!
            self.first_to_arrive = f"{robot.robot_name} ({robot.algo_label})"
            if self.selected_dropoff_shelf:
                self.selected_dropoff_shelf.place_cargo("Industrial Package")

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

    def trigger_random_mission(self) -> bool:
        """
        Otomasi memilih secara acak satu rak kargo (Pick-up) dan satu rak kosong (Drop-off),
        lalu langsung meluncurkan balapan!
        """
        self.reset_race()

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

    def update(self):
        """Update loop per frame untuk penghitungan metrik gamifikasi dan deteksi finish."""
        if self.is_race_active and not self.is_paused:
            self.race_elapsed_time += time.dt

            # Cek apakah kedua robot sudah menyelesaikan pergerakan
            alpha_done = self.robot_alpha.state == RobotState.FINISHED
            beta_done = self.robot_beta.state == RobotState.FINISHED

            if alpha_done and beta_done and not self.race_finished:
                self._finalize_race_outcome()

    def _finalize_race_outcome(self):
        """Menghitung evaluasi komparatif akhir saat balapan selesai."""
        self.race_finished = True
        self.is_race_active = False
        self.missions_completed += 1

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
            self.rating_explanation = "SEMPURNA (⭐⭐⭐⭐⭐): Rute optimal dieksekusi dengan kecepatan puncak!"
            self.combo_multiplier += 1
        elif cost_ratio <= 1.08:
            self.star_rating = 4
            self.rating_explanation = "SANGAT BAIK (⭐⭐⭐⭐): Jalur efisien dengan sedikit deviasi waktu."
            self.combo_multiplier += 1
        elif cost_ratio <= 1.20:
            self.star_rating = 3
            self.rating_explanation = "CUKUP (⭐⭐⭐): GBFS mengambil rute memutar yang memperlambat armada."
            self.combo_multiplier = 1
        elif cost_ratio <= 1.35:
            self.star_rating = 2
            self.rating_explanation = "SUB-OPTIMAL (⭐⭐): GBFS terjebak sekat buntu lorong atas gudang."
            self.combo_multiplier = 1
        else:
            self.star_rating = 1
            self.rating_explanation = "BURUK (⭐): Terjadi inefisiensi navigasi parah pada rute rak."
            self.combo_multiplier = 1
