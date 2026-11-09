"""
robot_controller.py
===================
Pengendali robot AGV otonom (AGV Controller) berbasis Ursina Engine.
Menangani pergerakan halus antar-simpul grid (waypoint translation),
interpolasi sudut rotasi arah belokan (lerp_angle heading), animasi ambil & taruh kargo,
serta penanda jejak bercahaya dinamis (Trajectory Trail).

Menerapkan Arsitektur "Decoupled Follower" (Entitas Visual Independen):
1. Logic Pivot: AGVRobot bertindak sebagai entitas logika murni (invisible) yang bergerak
   100% tepat di tengah koordinat sel grid.
2. Independent Visual Body: self.visual_body adalah entitas independen (bukan child dari self)
   untuk mencegah isu frustum culling/clipping dan rotasi lokal yang salah hitung pada Ursina.
3. Global Directional Vector Offset: Posisi visual_body dihitung di setiap frame berdasarkan
   vektor arah absolut robot (self.right * offset_distance) dengan selisih elevasi mikro.
4. Billboard/Label: Tag nama melayang menempel langsung di atas visual_body.
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
)

from src.config import (
    grid_to_world,
    ROTATION_SPEED,
    ACTION_PAUSE_DURATION,
    ROBOT_OFFSET_DISTANCE,
    ALPHA_MODEL_ELEVATION,
    BETA_MODEL_ELEVATION,
    ALPHA_TRAIL_OFFSET_X,
    ALPHA_TRAIL_OFFSET_Y,
    BETA_TRAIL_OFFSET_X,
    BETA_TRAIL_OFFSET_Y,
    TRAIL_SCALE_SPLIT,
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
    Entitas pengontrol AGV dengan pergerakan kinematika halus,
    arsitektur Decoupled Visual Follower, dan trajectory trail split terbelah dua.
    """

    def __init__(
        self,
        name: str,
        algorithm_label: str,
        spawn_coord: Coord,
        primary_color_rgb: Tuple[int, int, int],
        trail_color_rgb: Tuple[int, int, int],
        speed: float = 6.5,
        is_alpha: Optional[bool] = None,
        trail_offset_x: Optional[float] = None,
        trail_offset_y: Optional[float] = None,
        **kwargs,
    ):
        self.robot_name = name
        self.algo_label = algorithm_label
        self.spawn_coord = spawn_coord
        self.primary_col = color.rgb32(*primary_color_rgb)
        self.trail_col = color.rgb32(*trail_color_rgb)
        self.speed = speed

        # Tentukan identitas robot (Alpha = Kiri, Beta = Kanan)
        if is_alpha is None:
            self.is_alpha: bool = ("Alpha" in name or "A*" in algorithm_label)
        else:
            self.is_alpha = is_alpha

        # Offset jejak lintasan (split trail terbelah dua)
        if trail_offset_x is None:
            self.trail_offset_x = ALPHA_TRAIL_OFFSET_X if self.is_alpha else BETA_TRAIL_OFFSET_X
        else:
            self.trail_offset_x = trail_offset_x

        if trail_offset_y is None:
            self.trail_offset_y = ALPHA_TRAIL_OFFSET_Y if self.is_alpha else BETA_TRAIL_OFFSET_Y
        else:
            self.trail_offset_y = trail_offset_y

        spawn_world = grid_to_world(spawn_coord[0], spawn_coord[1], 0.0)

        # ---------------------------------------------------------------------
        # 1. ROOT ENTITY: PIVOT LOGIKA MURNI (Bergerak tepat di grid, invisible)
        # ---------------------------------------------------------------------
        super().__init__(
            position=spawn_world,
            visible=False,
            **kwargs,
        )

        # ---------------------------------------------------------------------
        # 2. ENTITAS VISUAL INDEPENDEN (DECOUPLED FOLLOWER - TANPA parent=self)
        # ---------------------------------------------------------------------
        # Dibuat langsung di scene (bukan child self) untuk mencegah frustum culling
        # dan clipping saat kedua robot berpapasan atau menempati sel grid yang sama.
        self.visual_body = Entity(
            model=AssetLoader.get_agv_model(),
            position=spawn_world,
            scale=Vec3(0.55, 0.55, 0.55),
            color=self.primary_col,
        )

        # Sensor LIDAR dome (menempel pada visual_body)
        self.lidar_dome = Entity(parent=self.visual_body, enabled=False)

        # Kotak kargo di atas dek (menempel pada visual_body)
        self.deck_cargo = Entity(
            parent=self.visual_body,
            model=AssetLoader.get_cargo_model(),
            position=Vec3(0, 0.26, -0.08),
            scale=Vec3(0.52, 0.38, 0.52),
            color=color.rgb32(230, 180, 100),
            enabled=False,
        )

        # Label Billboard melayang tepat di atas visual_body yang sudah di-offset
        self.label_tag = Text(
            parent=self.visual_body,
            text=f"{name}\n[{algorithm_label}]",
            position=Vec3(0, 2.2, 0),
            scale=1.1,
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

        # Sinkronkan posisi dan rotasi visual follower secara absolut sejak spawn
        self._update_visual_body()

    @property
    def model(self):
        """Meneruskan akses model ke entitas visual independen."""
        return self.visual_body.model if hasattr(self, 'visual_body') and self.visual_body else None

    @model.setter
    def model(self, value):
        """Mengubah model 3D pada visual_body secara dinamis."""
        if hasattr(self, 'visual_body') and self.visual_body:
            self.visual_body.model = value

    def _update_visual_body(self):
        """
        Sistem Follower Independen (Decoupled Follower):
        Menyinkronkan rotasi dan posisi visual_body terhadap logic pivot di setiap frame.
        Menggunakan Directional Right Vector Offset absolut di world space.
        """
        if not hasattr(self, 'visual_body') or self.visual_body is None:
            return

        # 1. Salin rotasi secara absolut dari logic pivot
        self.visual_body.rotation = self.rotation

        # 2. Cari vektor "Kanan" (Right Vector) dari rotasi robot saat ini
        right_vector = self.right
        offset_distance = ROBOT_OFFSET_DISTANCE  # 0.20

        # 3. Posisikan visual_body dengan perhitungan vektor arah absolut:
        #    Jika Alpha (A*), geser ke Kiri (berlawanan right_vector).
        #    Jika Beta (GBFS), geser ke Kanan (+ right_vector).
        if self.is_alpha:
            self.visual_body.position = self.position - (right_vector * offset_distance)
            self.visual_body.y = self.y + ALPHA_MODEL_ELEVATION  # +0.010
        else:
            self.visual_body.position = self.position + (right_vector * offset_distance)
            self.visual_body.y = self.y + BETA_MODEL_ELEVATION   # +0.015

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
        self._update_visual_body()

    def clear_trail(self):
        """Menonaktifkan seluruh jejak bercahaya via pool recycling (Zero GC Churn)."""
        for i in range(self.trail_active_count):
            self.trail_pool[i].enabled = False
        self.trail_active_count = 0

    def spawn_trail_marker(self, pos: Vec3):
        """
        Menampilkan penanda jejak bercahaya menggunakan Entity Pool daur-ulang.
        Menerapkan 'Split Visual Jejak' dengan menggeser kotak lintasan ke kiri/kanan
        dan menggunakan ukuran terbelah dua agar jejak Alpha dan Beta terlihat berdampingan
        tanpa mengalami Z-fighting / flickering di sel yang sama.
        """
        marker_pos = Vec3(pos.x + self.trail_offset_x, self.trail_offset_y, pos.z)
        marker_scale = Vec3(*TRAIL_SCALE_SPLIT) if self.trail_offset_x != 0.0 else Vec3(0.55, 0.025, 0.55)

        if self.trail_active_count < len(self.trail_pool):
            marker = self.trail_pool[self.trail_active_count]
            marker.position = marker_pos
            marker.scale = marker_scale
            marker.enabled = True
        else:
            marker = Entity(
                model='cube',
                position=marker_pos,
                scale=marker_scale,
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
            self._update_visual_body()
        else:
            self.state = RobotState.FINISHED

    def update(self):
        """Loop pergerakan per frame (dipanggil otomatis oleh Ursina)."""
        # Sinkronkan posisi & rotasi visual_body independen terhadap logic pivot
        self._update_visual_body()

        # Sensor LIDAR berputar terus menerus
        if hasattr(self, 'lidar_dome') and self.lidar_dome:
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

        # Perbarui posisi visual follower setelah translasi & rotasi di frame ini
        self._update_visual_body()

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

        elif self.state == RobotState.FINISHED:
            pass

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

    def on_destroy(self):
        """Membersihkan entitas visual independen saat robot didestroy."""
        if hasattr(self, 'visual_body') and self.visual_body:
            destroy(self.visual_body)
