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
from typing import List, Optional, Set, Tuple
from ursina import (
    Entity,
    Vec3,
    color,
    time,
    lerp_angle,
    destroy,
    Text,
    Cylinder,
    curve,
)
from ursina.shaders import lit_with_shadows_shader

from src.config import (
    grid_to_world,
    world_to_grid,
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
from src.cognition.pathfinding import a_star_search, greedy_best_first_search
from src.cognition.warehouse_graph import WarehouseGraph100

Coord = Tuple[int, int]


class RobotState(Enum):
    IDLE_DOCK = "Standby di Dock"
    MOVING_TO_PICKUP = "Menuju Titik Jemput"
    LOADING_CARGO = "Mengambil Kargo..."
    MOVING_TO_DROPOFF = "Balapan Menuju Titik Antar"
    UNLOADING_CARGO = "Menaruh Kargo..."
    RETURNING_TO_DOCK = "Kembali ke Dock (Isi Daya)"
    CHARGING = "Mengisi Daya Baterai..."
    DEAD = "Baterai Habis (DEAD)"
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
            shader=lit_with_shadows_shader,
            collider='box',
        )
        self.visual_body.cast_shadows = True
        self.visual_body.robot_owner = self
        self.cast_shadows = True

        self.is_beta = ("Beta" in name or "GBFS" in algorithm_label)
        halo_radius = 1.55 if self.is_beta else 1.22
        beacon_y = 1.20 if self.is_beta else 0.95
        label_y = 3.4 if self.is_beta else 2.6

        # Elemen Visual Tambahan Robot
        # 1. Cincin Halo Bercahaya di Lantai Bawah Robot (Ground Underglow Neon)
        # Menjadikan kedua robot sangat mencolok dan membentuk cincin konsentris saat di sel yang sama
        self.ground_halo = Entity(
            parent=self,
            model=Cylinder(resolution=24),
            scale=Vec3(halo_radius, 0.08, halo_radius),
            position=Vec3(0, 0.08 if self.is_beta else 0.05, 0),
            color=self.primary_col,
        )

        # 2. Indikator Beacon Bola Bercahaya di Atas Robot
        self.top_beacon = Entity(
            parent=self,
            model='sphere',
            scale=Vec3(0.30, 0.30, 0.30),
            position=Vec3(0, beacon_y, 0),
            color=self.primary_col,
        )

        # 3. Sensor LIDAR dome berputar
        self.lidar_dome = Entity(parent=self, enabled=False)

        # Kotak kargo di atas dek (menempel pada visual_body)
        self.deck_cargo = Entity(
            parent=self.visual_body,
            model=AssetLoader.get_cargo_model(),
            position=Vec3(0, 0.26, -0.08),
            scale=Vec3(0.52, 0.38, 0.52),
            color=color.rgb32(230, 180, 100),
            enabled=False,
        )

        # 5. Label Billboard melayang di atas robot (ketinggian bertingkat anti Z-fighting)
        self.label_tag = Text(
            parent=self.visual_body,
            text=f"{name}\n[{algorithm_label}]",
            position=Vec3(0, label_y, 0),
            scale=1.8,
            color=self.primary_col,
            billboard=True,
            origin=(0, 0),
        )

        # 6. Sistem Manajemen Energi & Baterai AGV
        self.battery: float = 100.0
        self.battery_drain_rate: float = 0.5  # -0.5% kapasitas per langkah petak grid
        self.is_critical_battery: bool = False

        # Visual Indikator Baterai Melayang (Floating ProgressBar Billboard)
        bar_y = label_y + 0.65
        self.battery_bar_bg = Entity(
            parent=self.visual_body,
            model='quad',
            position=Vec3(0, bar_y, 0),
            scale=Vec3(1.3, 0.22, 1),
            color=color.rgba32(18, 22, 30, 215),
            billboard=True,
        )
        self.battery_bar_fill = Entity(
            parent=self.battery_bar_bg,
            model='quad',
            position=Vec3(-0.48, 0, -0.01),
            scale=Vec3(0.96, 0.70, 1),
            origin=(-0.5, 0),
            color=color.rgb32(46, 204, 113),
        )
        self.battery_text = Text(
            parent=self.battery_bar_bg,
            text="100%",
            position=Vec3(0, 0, -0.02),
            scale=2.2,
            color=color.white,
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

        # Pelacakan koordinat grid untuk replanning dinamis
        self.leg1_grid_path: List[Coord] = []
        self.leg2_grid_path: List[Coord] = []
        self.active_grid_path: List[Coord] = []
        self.pickup_access: Optional[Coord] = None
        self.dropoff_access: Optional[Coord] = None
        self.replan_count: int = 0
        self.last_explored_nodes: Set[Coord] = set()

        # Weighted Terrain & Status Flags (Fitur 1 & 2)
        self.graph: Optional[WarehouseGraph100] = None
        self._on_oil: bool = False
        self._on_boost: bool = False

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
        """Mengubah model 3D pada visual_body secara dinamis dengan shader bayangan."""
        if hasattr(self, 'visual_body') and self.visual_body:
            self.visual_body.model = value
            self.visual_body.shader = lit_with_shadows_shader
            self.visual_body.cast_shadows = True

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
        self.deck_cargo.enabled = False
        self.leg1_waypoints.clear()
        self.leg2_waypoints.clear()
        self.active_waypoints.clear()
        self.leg1_grid_path.clear()
        self.leg2_grid_path.clear()
        self.active_grid_path.clear()
        self.pickup_access = None
        self.dropoff_access = None
        self.replan_count = 0
        self.last_explored_nodes.clear()
        self.waypoint_idx = 0
        self.is_paused = False
        self.pause_timer = 0.0
        self.total_steps_executed = 0
        self.total_mission_steps = 0
        self.finish_time = None
        self.recharge_full()
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

    @staticmethod
    def _compute_lane_offset(waypoints: List[Vec3], offset: float) -> List[Vec3]:
        """
        Menambahkan separasi lajur lateral tegak lurus arah lintasan (Lateral Lane Offset).
        Mencegah kedua robot bertabrakan atau saling menumpuk/clipping saat melalui lorong yang sama.
        """
        n = len(waypoints)
        if n < 2:
            return list(waypoints)
        out = []
        for i in range(n):
            if i == 0:
                dx = waypoints[1].x - waypoints[0].x
                dz = waypoints[1].z - waypoints[0].z
            elif i == n - 1:
                dx = waypoints[i].x - waypoints[i - 1].x
                dz = waypoints[i].z - waypoints[i - 1].z
            else:
                dx = waypoints[i + 1].x - waypoints[i - 1].x
                dz = waypoints[i + 1].z - waypoints[i - 1].z

            length = math.hypot(dx, dz)
            if length > 0.001:
                nx = dz / length
                nz = -dx / length
            else:
                nx, nz = 0.0, 0.0

            out.append(Vec3(waypoints[i].x + nx * offset, waypoints[i].y, waypoints[i].z + nz * offset))
        return out

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
        Menggunakan pemisahan lajur lateral (Dual-Lane AGV separation).
        """
        self.clear_trail()
        self.on_pickup_callback = on_pickup
        self.on_dropoff_callback = on_dropoff

        raw_leg1 = [grid_to_world(p[0], p[1], 0.0) for p in leg1_path]
        raw_leg2 = [grid_to_world(p[0], p[1], 0.0) for p in leg2_path]

        # Separasi lajur lateral: Alpha di lajur kanan (+0.22), Beta di lajur kiri (-0.22)
        offset = -0.22 if self.is_beta else 0.22
        self.leg1_waypoints = self._compute_lane_offset(raw_leg1, offset)
        self.leg2_waypoints = self._compute_lane_offset(raw_leg2, offset)

        self.total_mission_steps = len(leg1_path) + len(leg2_path)
        self.total_steps_executed = 0
        self.finish_time = None

        self.leg1_grid_path = list(leg1_path)
        self.leg2_grid_path = list(leg2_path)
        self.pickup_access = leg1_path[-1] if leg1_path else None
        self.dropoff_access = leg2_path[-1] if leg2_path else None
        self.replan_count = 0

        if self.leg1_waypoints:
            self.active_waypoints = self.leg1_waypoints
            self.active_grid_path = list(self.leg1_grid_path)
            self.waypoint_idx = 0
            self.state = RobotState.MOVING_TO_PICKUP
            self.position = self.active_waypoints[0]
            self.spawn_trail_marker(self.position)
            self._update_visual_body()
            self.trigger_radar_pulse()
        else:
            self.state = RobotState.FINISHED

    def trigger_radar_pulse(self):
        """Memunculkan efek gelombang cincin pemindaian LIDAR radar pulse 3D membesar & memudar."""
        from ursina import curve
        pulse_ring = Entity(
            model='circle',
            rotation_x=90,
            position=self.position + Vec3(0, 0.08, 0),
            scale=Vec3(0.5, 0.5, 0.5),
            color=self.primary_col,
        )
        pulse_ring.animate_scale(Vec3(6.5, 6.5, 6.5), duration=0.55, curve=curve.out_quad)
        pulse_ring.animate_color(color.clear, duration=0.55)
        destroy(pulse_ring, delay=0.58)

    def spawn_floating_text(self, text_str: str, text_color=color.yellow):
        """Memunculkan teks 3D melayang status robot yang naik ke atas dan memudar secara halus."""
        from ursina import curve
        spawn_pos = self.position + Vec3(0, 2.8, 0)
        popup = Text(
            text=text_str,
            position=spawn_pos,
            scale=2.2,
            color=text_color,
            origin=(0, 0),
            billboard=True,
        )
        popup.animate_position(spawn_pos + Vec3(0, 1.4, 0), duration=0.9, curve=curve.out_cubic)
        popup.animate_color(color.clear, duration=0.9)
        destroy(popup, delay=0.95)

    def update(self):
        """Loop pergerakan per frame (dipanggil otomatis oleh Ursina)."""
        # Efek denyut halus pada underglow neon robot agar dinamis dan selalu terlihat
        base_r = 1.55 if self.is_beta else 1.22
        pulse = base_r + math.sin(time.time() * 5.0) * 0.08
        self.ground_halo.scale_x = pulse
        self.ground_halo.scale_z = pulse

        # Sensor LIDAR berputar terus menerus
        if hasattr(self, 'lidar_dome') and self.lidar_dome:
            self.lidar_dome.rotation_y += 360 * time.dt

        # 1. Penanganan Status Baterai Habis (DEAD)
        if self.state == RobotState.DEAD:
            self.top_beacon.color = color.red
            return

        # 2. Penanganan Pengisian Daya di Dock (CHARGING)
        if self.state == RobotState.CHARGING:
            self.pause_timer -= time.dt
            self.battery = min(100.0, self.battery + (100.0 / 2.0) * time.dt)
            self._update_battery_visual()
            if self.pause_timer <= 0:
                self.recharge_full()
                self.state = RobotState.IDLE_DOCK
            return

        # 3. Indikator Kondisi Baterai Kritis (<= 20%)
        if 0.0 < self.battery <= 20.0:
            blink = (int(time.time() * 8.0) % 2) == 0
            self.top_beacon.color = color.yellow if blink else self.primary_col
        else:
            self.top_beacon.color = self.primary_col

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

        # Translasi pergerakan AGV teroptimasi dengan efek Weighted Terrain (Fitur 1)
        curr_grid = self.get_current_grid_coord()
        speed_mult = 1.0
        drain_mult = 1.0

        if hasattr(self, 'graph') and self.graph and hasattr(self.graph, 'terrain_weights'):
            weight = self.graph.terrain_weights.get(curr_grid, 1.0)
            if weight > 2.0:  # HAZARD_OIL (Cost 5.0 -> Slowdown 0.4x, Drain 2.5x)
                speed_mult = 0.4
                drain_mult = 2.5
                if not getattr(self, '_on_oil', False):
                    self._on_oil = True
                    self.spawn_floating_text("! OIL SLOWDOWN !", color.rgb32(245, 180, 20))
            elif weight < 0.8:  # BOOST_PAD (Cost 0.35 -> Speed 1.75x, Drain 0.5x)
                speed_mult = 1.75
                drain_mult = 0.5
                if not getattr(self, '_on_boost', False):
                    self._on_boost = True
                    self.spawn_floating_text(">> SPEED BOOST >>", color.rgb32(46, 204, 113))
            else:
                self._on_oil = False
                self._on_boost = False

        step = (self.speed * speed_mult) * time.dt
        if dist <= step:
            self.position = target_pos
            self.waypoint_idx = target_idx
            self.total_steps_executed += 1
            self.consume_battery(self.battery_drain_rate * drain_mult)
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
            self.spawn_floating_text("+CARGO LOADED+", color.rgb32(46, 204, 113))
            if self.on_pickup_callback:
                self.on_pickup_callback(self)

        elif self.state == RobotState.MOVING_TO_DROPOFF:
            # Tiba di titik antar (Drop-off)
            self.state = RobotState.UNLOADING_CARGO
            self.pause_timer = ACTION_PAUSE_DURATION
            self.spawn_floating_text("+MISSION COMPLETE+", color.rgb32(241, 196, 15))
            if self.on_dropoff_callback:
                self.on_dropoff_callback(self)

        elif self.state == RobotState.RETURNING_TO_DOCK:
            # Tiba di stasiun dock untuk isi daya
            self.state = RobotState.CHARGING
            self.pause_timer = 2.0
            self.label_tag.text = f"{self.robot_name}\n[MENGISI DAYA (CHARGING)...]"
            self.label_tag.color = color.rgb32(46, 204, 113)

        elif self.state == RobotState.FINISHED:
            pass

    def _resume_after_action(self):
        """Melanjutkan pergerakan setelah animasi ambil / taruh kargo selesai."""
        if self.state == RobotState.LOADING_CARGO:
            # Kargo berhasil dimuat ke dek, mulai balapan ke Drop-off!
            self.deck_cargo.enabled = True
            self.active_waypoints = self.leg2_waypoints
            self.active_grid_path = list(self.leg2_grid_path)
            self.waypoint_idx = 0
            self.state = RobotState.MOVING_TO_DROPOFF

        elif self.state == RobotState.UNLOADING_CARGO:
            # Kargo berhasil diturunkan, misi selesai!
            self.deck_cargo.enabled = False
            self.state = RobotState.FINISHED
            self.finish_time = time.time()

    # =========================================================================
    # METODE MANAJEMEN BATERAI & RECHARGE (FITUR 1)
    # =========================================================================
    def consume_battery(self, amount: Optional[float] = None):
        """Mengurangi kapasitas baterai setiap robot melintasi sel grid."""
        if self.state in (RobotState.IDLE_DOCK, RobotState.DEAD, RobotState.CHARGING):
            return

        drain = amount if amount is not None else self.battery_drain_rate
        self.battery = max(0.0, self.battery - drain)
        self._update_battery_visual()

        if self.battery <= 0.0:
            self.state = RobotState.DEAD
            self.visual_body.color = color.rgb32(180, 50, 50)
            self.label_tag.text = f"{self.robot_name}\n[BATERAI HABIS (DEAD)]"
            self.label_tag.color = color.red
            self.top_beacon.color = color.red

    def _update_battery_visual(self):
        """Memperbarui skala dan warna progress bar baterai melayang."""
        if not hasattr(self, 'battery_bar_fill') or not self.battery_bar_fill:
            return

        pct = max(0.0, min(100.0, self.battery)) / 100.0
        self.battery_bar_fill.scale_x = max(0.01, 0.96 * pct)
        self.battery_text.text = f"{int(self.battery)}%"

        if self.battery > 50.0:
            self.battery_bar_fill.color = color.rgb32(46, 204, 113)  # Hijau sehat
        elif self.battery > 20.0:
            self.battery_bar_fill.color = color.rgb32(241, 196, 15)  # Kuning perhatian
        else:
            self.battery_bar_fill.color = color.rgb32(231, 76, 60)   # Merah kritis/mati

    def recharge_full(self):
        """Mengisi daya baterai penuh kembali ke 100% dan merestorasi status normal."""
        self.battery = 100.0
        self.visual_body.color = self.primary_col
        self.top_beacon.color = self.primary_col
        self.label_tag.color = self.primary_col
        self.label_tag.text = f"{self.robot_name}\n[{self.algo_label}]"
        self._update_battery_visual()
        self.spawn_floating_text("+100% RECHARGED+", color.rgb32(46, 204, 113))

    def force_return_to_dock(self, graph: WarehouseGraph100, heuristic_fn) -> bool:
        """
        Perintah intervensi user (Klik Kanan): Memaksa robot kembali ke stasiun docking
        untuk mengisi daya baterai hingga 100%.
        """
        if self.state in (RobotState.IDLE_DOCK, RobotState.CHARGING):
            self.recharge_full()
            return True

        curr_coord = self.get_current_grid_coord()
        dock_coord = self.spawn_coord

        start_node = curr_coord
        if not graph.is_walkable(start_node[0], start_node[1]):
            neighbors = graph.get_neighbors(curr_coord[0], curr_coord[1])
            if neighbors:
                start_node = neighbors[0]
            else:
                return False

        search_fn = a_star_search if self.is_alpha else greedy_best_first_search
        res = search_fn(graph, start_node, dock_coord, heuristic=heuristic_fn)

        if not res.success or not res.path:
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                alt = (dock_coord[0] + dx, dock_coord[1] + dy)
                if graph.is_walkable(alt[0], alt[1]):
                    res = search_fn(graph, start_node, alt, heuristic=heuristic_fn)
                    if res.success and res.path:
                        break

        if not res.success or not res.path:
            return False

        self.clear_trail()
        self._apply_new_active_path(res.path)
        self.state = RobotState.RETURNING_TO_DOCK
        self.is_paused = False
        self.visual_body.color = self.primary_col
        self.label_tag.text = f"{self.robot_name}\n[KEMBALI KE DOCK]"
        self.label_tag.color = color.rgb32(241, 196, 15)
        return True

    # =========================================================================
    # KALKULASI ULANG RUTE DINAMIS (DYNAMIC OBSTACLE REPLANNING)
    # =========================================================================
    def get_current_grid_coord(self) -> Coord:
        """Mengonversi posisi dunia aktual robot saat ini ke koordinat grid integer."""
        return world_to_grid(self.position)

    def is_path_blocked_by(self, obs_coord: Coord) -> bool:
        """
        Memeriksa apakah koordinat rintangan memotong rute robot yang sedang ditempuh:
        1. Memeriksa sisa simpul pada etape aktif (dari waypoint_idx ke depan).
        2. Jika robot masih di etape jemput (Leg 1), memeriksa juga seluruh rute Leg 2.
        """
        if self.state in (RobotState.IDLE_DOCK, RobotState.FINISHED):
            return False

        # Cek sisa rute di etape yang sedang aktif
        if self.active_grid_path:
            remaining_active = self.active_grid_path[max(0, self.waypoint_idx):]
            if obs_coord in remaining_active:
                return True

        # Jika sedang Leg 1 atau sedang loading kargo, cek apakah rintangan memotong Leg 2
        if self.state in (RobotState.MOVING_TO_PICKUP, RobotState.LOADING_CARGO):
            if obs_coord in self.leg2_grid_path:
                return True

        return False

    def recalculate_route(
        self,
        graph: WarehouseGraph100,
        heuristic_fn,
        pickup_shelf_coord: Optional[Coord] = None,
        dropoff_shelf_coord: Optional[Coord] = None,
    ) -> bool:
        """
        Menghitung ulang rute secara real-time dari posisi saat ini ke target.
        - Robot Alpha (A* Search)
        - Robot Beta (Greedy Best-First Search)
        """
        if self.state in (RobotState.IDLE_DOCK, RobotState.FINISHED):
            return False

        self.graph = graph
        curr_coord = self.get_current_grid_coord()

        # Tentukan titik awal pencarian yang walkable
        start_node = curr_coord
        if not graph.is_walkable(start_node[0], start_node[1]):
            neighbors = graph.get_neighbors(curr_coord[0], curr_coord[1])
            if neighbors:
                start_node = neighbors[0]
            else:
                return False

        search_fn = a_star_search if self.is_alpha else greedy_best_first_search

        # ---------------------------------------------------------------------
        # KASUS 1: SEDANG BERJALAN MENUJU PICK-UP (LEG 1)
        # ---------------------------------------------------------------------
        if self.state == RobotState.MOVING_TO_PICKUP:
            target_access = self.pickup_access
            if target_access is None or not graph.is_walkable(target_access[0], target_access[1]):
                if pickup_shelf_coord:
                    target_access = graph.get_shelf_access_node(pickup_shelf_coord, from_coord=start_node)
                    self.pickup_access = target_access

            if target_access is None:
                return False

            res = search_fn(graph, start_node, target_access, heuristic=heuristic_fn)
            if not res.success or not res.path:
                return False

            self.last_explored_nodes = set(res.explored_order)
            self._apply_new_active_path(res.path)
            self.replan_count += 1

            # Hitung ulang juga Leg 2 jika ikut terpotong rintangan
            if self.dropoff_access:
                target_dropoff = self.dropoff_access
                if not graph.is_walkable(target_dropoff[0], target_dropoff[1]) and dropoff_shelf_coord:
                    target_dropoff = graph.get_shelf_access_node(dropoff_shelf_coord, from_coord=target_access)
                    self.dropoff_access = target_dropoff

                res2 = search_fn(graph, target_access, target_dropoff, heuristic=heuristic_fn)
                if res2.success and res2.path:
                    self.last_explored_nodes.update(res2.explored_order)
                    self.leg2_grid_path = res2.path
                    raw2 = [grid_to_world(p[0], p[1], 0.0) for p in res2.path]
                    offset = -0.22 if self.is_beta else 0.22
                    self.leg2_waypoints = self._compute_lane_offset(raw2, offset)

            return True

        # ---------------------------------------------------------------------
        # KASUS 2: SEDANG BERJALAN MENUJU DROP-OFF (LEG 2)
        # ---------------------------------------------------------------------
        elif self.state == RobotState.MOVING_TO_DROPOFF:
            target_access = self.dropoff_access
            if target_access is None or not graph.is_walkable(target_access[0], target_access[1]):
                if dropoff_shelf_coord:
                    target_access = graph.get_shelf_access_node(dropoff_shelf_coord, from_coord=start_node)
                    self.dropoff_access = target_access

            if target_access is None:
                return False

            res = search_fn(graph, start_node, target_access, heuristic=heuristic_fn)
            if not res.success or not res.path:
                return False

            self.last_explored_nodes = set(res.explored_order)
            self._apply_new_active_path(res.path)
            self.replan_count += 1
            return True

        # ---------------------------------------------------------------------
        # KASUS 3: SEDANG LOADING KARGO DI PICK-UP POINT
        # ---------------------------------------------------------------------
        elif self.state == RobotState.LOADING_CARGO:
            if self.dropoff_access:
                target_dropoff = self.dropoff_access
                if not graph.is_walkable(target_dropoff[0], target_dropoff[1]) and dropoff_shelf_coord:
                    target_dropoff = graph.get_shelf_access_node(dropoff_shelf_coord, from_coord=start_node)
                    self.dropoff_access = target_dropoff

                res = search_fn(graph, start_node, target_dropoff, heuristic=heuristic_fn)
                if res.success and res.path:
                    self.last_explored_nodes = set(res.explored_order)
                    self.leg2_grid_path = res.path
                    raw2 = [grid_to_world(p[0], p[1], 0.0) for p in res.path]
                    offset = -0.22 if self.is_beta else 0.22
                    self.leg2_waypoints = self._compute_lane_offset(raw2, offset)
                    self.replan_count += 1
                    return True

        return False

    def _apply_new_active_path(self, new_grid_path: List[Coord]):
        """Menyambungkan posisi aktual robot saat ini ke waypoints rute baru secara halus."""
        self.active_grid_path = list(new_grid_path)
        raw_wps = [grid_to_world(p[0], p[1], 0.0) for p in new_grid_path]
        offset = -0.22 if self.is_beta else 0.22
        lane_wps = self._compute_lane_offset(raw_wps, offset)

        if lane_wps:
            # Sambungkan posisi dunia robot saat ini sebagai simpul awal
            self.active_waypoints = [self.position] + lane_wps
            self.waypoint_idx = 0
            self.spawn_trail_marker(self.position)
            self.trigger_radar_pulse()
            self.spawn_floating_text("REPLANNING ROUTE...", color.rgb32(0, 229, 255))

    def on_destroy(self):
        """Membersihkan entitas visual independen saat robot didestroy."""
        if hasattr(self, 'visual_body') and self.visual_body:
            destroy(self.visual_body)
