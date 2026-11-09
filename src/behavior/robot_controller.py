"""
robot_controller.py
===================
Pengendali robot AGV otonom (AGV Controller) berbasis Ursina Engine.
Menangani pergerakan halus antar-simpul grid (waypoint translation),
interpolasi sudut rotasi arah belokan (lerp_angle heading), animasi ambil & taruh kargo,
serta penanda jejak bercahaya dinamis (Trajectory Trail).
"""

import math
from enum import Enum
from typing import List, Optional, Tuple
from ursina import (
    Entity,
    Vec3,
    color,
    time,
    lerp_angle,
    destroy,
    Text,
    Cylinder,
)

from src.config import (
    grid_to_world,
    ROTATION_SPEED,
    ACTION_PAUSE_DURATION,
)
from src.environment.asset_loader import AssetLoader

Coord = Tuple[int, int]


class RobotState(Enum):
    IDLE_DOCK = "Standby di Dock"
    MOVING_TO_PICKUP = "Menuju Titik Jemput"
    LOADING_CARGO = "Mengambil Kargo..."
    MOVING_TO_DROPOFF = "Balapan Menuju Titik Antar"
    UNLOADING_CARGO = "Menaruh Kargo..."
    FINISHED = "Misi Selesai!"


class AGVRobot(Entity):
    """
    Entitas pengontrol AGV dengan pergerakan kinematika halus, visualisasi LIDAR berputar,
    kargo dinamis di dek, dan animasi trajectory trail.
    """

    def __init__(
        self,
        name: str,
        algorithm_label: str,
        spawn_coord: Coord,
        primary_color_rgb: Tuple[int, int, int],
        trail_color_rgb: Tuple[int, int, int],
        speed: float = 6.5,
        **kwargs,
    ):
        self.robot_name = name
        self.algo_label = algorithm_label
        self.spawn_coord = spawn_coord
        self.primary_col = color.rgb32(*primary_color_rgb)
        self.trail_col = color.rgb32(*trail_color_rgb)
        self.speed = speed

        spawn_world = grid_to_world(spawn_coord[0], spawn_coord[1], 0.0)

        super().__init__(
            model=AssetLoader.get_agv_model(),
            position=spawn_world,
            scale=Vec3(0.55, 0.55, 0.55),
            color=self.primary_col,
            **kwargs,
        )

        self.is_beta = ("Beta" in name or "GBFS" in algorithm_label)
        halo_radius = 3.0 if self.is_beta else 2.3
        beacon_y = 1.15 if self.is_beta else 0.95
        label_y = 3.4 if self.is_beta else 2.6

        # Elemen Visual Tambahan Robot
        # 1. Cincin Halo Bercahaya di Lantai Bawah Robot (Ground Beacon)
        # Menjadikan kedua robot sangat mencolok dan membentuk cincin konsentris saat di sel yang sama
        self.ground_halo = Entity(
            parent=self,
            model=Cylinder(resolution=24),
            scale=Vec3(halo_radius, 0.08, halo_radius),
            position=Vec3(0, 0.06 if not self.is_beta else 0.08, 0),
            color=self.primary_col,
        )

        # 2. Indikator Beacon Bola Bercahaya di Atas Robot
        self.top_beacon = Entity(
            parent=self,
            model='sphere',
            scale=Vec3(0.28, 0.28, 0.28),
            position=Vec3(0, beacon_y, 0),
            color=self.primary_col,
        )

        # 3. Sensor LIDAR dome berputar
        self.lidar_dome = Entity(parent=self, enabled=False)

        # 4. Kotak kargo di atas dek (awalnya disembunyikan sampai robot menjemput barang)
        self.deck_cargo = Entity(
            parent=self,
            model=AssetLoader.get_cargo_model(),
            position=Vec3(0, 0.26, -0.08),
            scale=Vec3(0.52, 0.38, 0.52),
            color=color.rgb32(230, 180, 100),
            enabled=False,
        )

        # 5. Label Billboard melayang di atas robot (ketinggian bertingkat anti Z-fighting)
        self.label_tag = Text(
            parent=self,
            text=f"{name}\n[{algorithm_label}]",
            position=Vec3(0, label_y, 0),
            scale=1.8,
            color=self.primary_col,
            billboard=True,
            origin=(0, 0),
        )

        # State navigasi & waypoints
        self.state = RobotState.IDLE_DOCK
        self.leg1_waypoints: List[Vec3] = []
        self.leg2_waypoints: List[Vec3] = []
        self.active_waypoints: List[Vec3] = []
        self.waypoint_idx: int = 0
        self.is_paused: bool = False
        self.pause_timer: float = 0.0

        # Statistik kinerja & Trail Entity Pool (Zero Allocations pada runtime)
        self.trail_pool: List[Entity] = []
        self.trail_active_count: int = 0
        self.total_steps_executed: int = 0
        self.total_mission_steps: int = 0
        self.finish_time: Optional[float] = None
        self.on_pickup_callback = None
        self.on_dropoff_callback = None

    def reset_to_dock(self):
        """Mereset posisi robot ke stasiun dock awal dan menonaktifkan trail (tanpa destroy)."""
        self.clear_trail()
        self.position = grid_to_world(self.spawn_coord[0], self.spawn_coord[1], 0.0)
        self.rotation_y = 0.0
        self.state = RobotState.IDLE_DOCK
        self.model = AssetLoader.get_agv_model()
        self.leg1_waypoints.clear()
        self.leg2_waypoints.clear()
        self.active_waypoints.clear()
        self.waypoint_idx = 0
        self.is_paused = False
        self.pause_timer = 0.0
        self.total_steps_executed = 0
        self.total_mission_steps = 0
        self.finish_time = None

    def clear_trail(self):
        """Menonaktifkan seluruh jejak bercahaya via pool recycling (Zero GC Churn)."""
        for i in range(self.trail_active_count):
            self.trail_pool[i].enabled = False
        self.trail_active_count = 0

    def spawn_trail_marker(self, pos: Vec3):
        """Menampilkan penanda jejak bercahaya menggunakan Entity Pool daur-ulang."""
        if self.trail_active_count < len(self.trail_pool):
            marker = self.trail_pool[self.trail_active_count]
            marker.position = Vec3(pos.x, 0.03, pos.z)
            marker.enabled = True
        else:
            marker = Entity(
                model='cube',
                position=Vec3(pos.x, 0.03, pos.z),
                scale=Vec3(0.55, 0.025, 0.55),
                color=self.trail_col,
            )
            self.trail_pool.append(marker)
        self.trail_active_count += 1

    def set_mission_legs(
        self,
        leg1_path: List[Coord],
        leg2_path: List[Coord],
        on_pickup=None,
        on_dropoff=None,
    ):
        """
        Memuat rute misi dua etape:
        - Leg 1: Dari posisi saat ini ke Pick-up Access Node
        - Leg 2: Dari Pick-up Access Node ke Drop-off Access Node
        """
        self.clear_trail()
        self.on_pickup_callback = on_pickup
        self.on_dropoff_callback = on_dropoff

        self.leg1_waypoints = [grid_to_world(p[0], p[1], 0.0) for p in leg1_path]
        self.leg2_waypoints = [grid_to_world(p[0], p[1], 0.0) for p in leg2_path]

        self.total_mission_steps = len(leg1_path) + len(leg2_path)
        self.total_steps_executed = 0
        self.finish_time = None

        if self.leg1_waypoints:
            self.active_waypoints = self.leg1_waypoints
            self.waypoint_idx = 0
            self.state = RobotState.MOVING_TO_PICKUP
            self.position = self.active_waypoints[0]
            self.spawn_trail_marker(self.position)
        else:
            self.state = RobotState.FINISHED

    def update(self):
        """Loop pergerakan per frame (dipanggil otomatis oleh Ursina)."""
        # Efek denyut halus pada halo robot agar dinamis dan selalu terlihat
        base_r = 3.0 if self.is_beta else 2.3
        pulse = base_r + math.sin(time.time() * 5.0) * 0.15
        self.ground_halo.scale_x = pulse
        self.ground_halo.scale_z = pulse

        # Sensor LIDAR berputar terus menerus
        self.lidar_dome.rotation_y += 360 * time.dt

        if self.is_paused or self.state in (RobotState.IDLE_DOCK, RobotState.FINISHED):
            return

        # Penanganan jeda animasi ambil / taruh kargo
        if self.pause_timer > 0:
            self.pause_timer -= time.dt
            if self.pause_timer <= 0:
                self._resume_after_action()
            return

        # Navigasi waypoint saat ini
        if not self.active_waypoints or self.waypoint_idx >= len(self.active_waypoints):
            return

        target_idx = self.waypoint_idx + 1
        if target_idx >= len(self.active_waypoints):
            # Capai akhir etape rute saat ini
            self._handle_leg_completion()
            return

        target_pos = self.active_waypoints[target_idx]
        current_pos = self.position
        dx = target_pos.x - current_pos.x
        dz = target_pos.z - current_pos.z
        dist = math.hypot(dx, dz)

        # Rotasi halus menghadap arah belokan
        if dist > 0.01:
            target_angle = math.degrees(math.atan2(dx, dz))
            self.rotation_y = lerp_angle(self.rotation_y, target_angle, time.dt * ROTATION_SPEED)

        # Translasi pergerakan AGV teroptimasi tanpa instansiasi Vec3 berlebih
        step = self.speed * time.dt
        if dist <= step:
            self.position = target_pos
            self.waypoint_idx = target_idx
            self.total_steps_executed += 1
            self.spawn_trail_marker(target_pos)
        else:
            ratio = step / dist
            self.x += dx * ratio
            self.z += dz * ratio

    def _handle_leg_completion(self):
        """Dipanggil saat robot mencapai titik akhir etape rute."""
        if self.state == RobotState.MOVING_TO_PICKUP:
            # Tiba di titik jemput (Pick-up)
            self.state = RobotState.LOADING_CARGO
            self.pause_timer = ACTION_PAUSE_DURATION
            if self.on_pickup_callback:
                self.on_pickup_callback(self)

        elif self.state == RobotState.MOVING_TO_DROPOFF:
            # Tiba di titik antar (Drop-off)
            self.state = RobotState.UNLOADING_CARGO
            self.pause_timer = ACTION_PAUSE_DURATION
            if self.on_dropoff_callback:
                self.on_dropoff_callback(self)

    def _resume_after_action(self):
        """Melanjutkan pergerakan setelah animasi ambil / taruh kargo selesai."""
        if self.state == RobotState.LOADING_CARGO:
            # Kargo berhasil dimuat ke dek, mulai balapan ke Drop-off!
            self.model = AssetLoader.get_agv_loaded_model()
            self.active_waypoints = self.leg2_waypoints
            self.waypoint_idx = 0
            self.state = RobotState.MOVING_TO_DROPOFF

        elif self.state == RobotState.UNLOADING_CARGO:
            # Kargo berhasil diturunkan, misi selesai!
            self.model = AssetLoader.get_agv_model()
            self.state = RobotState.FINISHED
            self.finish_time = time.time()
