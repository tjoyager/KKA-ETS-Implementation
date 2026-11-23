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
    BATTERY_DRAIN_PER_GRID,
    BATTERY_CRITICAL_THRESHOLD,
)
from src.behavior.traffic_clearance import ClearanceGraph, obstacles
from src.environment.asset_loader import AssetLoader
from src.cognition.heuristics import manhattan_distance
from src.cognition.pathfinding import a_star_search, greedy_best_first_search, find_nearest_dock
from src.cognition.warehouse_graph import WarehouseGraph100

Coord = Tuple[int, int]

class RobotState(Enum):
    IDLE_DOCK = "Standby di Dock"
    MOVING_TO_PICKUP = "Menuju Titik Jemput"
    LOADING_CARGO = "Mengambil Kargo..."
    MOVING_TO_DROPOFF = "Balapan Menuju Titik Antar"
    UNLOADING_CARGO = "Menaruh Kargo..."
    RETURNING_TO_DOCK = "Kembali ke Dock (Isi Daya)"
    TO_CHARGER = "Menuju Charging Station"
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
        self.body_offset: float = min(ROBOT_OFFSET_DISTANCE, .10)
        self.traffic_radius: float = 0.45
        self._measure_traffic_radius()
        self._traffic_retry = 0.0
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
        self.battery_drain_rate: float = BATTERY_DRAIN_PER_GRID  # % kapasitas per langkah petak grid (diadaptasi dari feature/battery-system: 1.5%)
        self.battery_safety_margin: float = 5.0
        self.is_critical_battery: bool = False
        self.battery_critical_threshold: float = BATTERY_CRITICAL_THRESHOLD
        self._charge_retry = 0.0
        self.heuristic_fn = manhattan_distance  # diisi MissionManager (heuristik aktif)
        self.emergency_dock: Optional[Coord] = None
        self._emergency_cooldown: float = 0.0
        self._resume_state: Optional["RobotState"] = None  # state misi yang dikesampingkan

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
        self.leg3_waypoints: List[Vec3] = []
        self.active_waypoints: List[Vec3] = []
        self.waypoint_idx: int = 0
        self.is_paused: bool = False
        self.pause_timer: float = 0.0

        # Pelacakan koordinat grid untuk replanning dinamis
        self.leg1_grid_path: List[Coord] = []
        self.leg2_grid_path: List[Coord] = []
        self.leg3_grid_path: List[Coord] = []
        self.active_grid_path: List[Coord] = []
        self.pickup_access: Optional[Coord] = None
        self.dropoff_access: Optional[Coord] = None
        self.on_pickup_callback = None
        self.on_dropoff_callback = None
        self.on_finish_callback = None
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
            self._measure_traffic_radius()
            self.visual_body.shader = lit_with_shadows_shader
            self.visual_body.cast_shadows = True

    def _measure_traffic_radius(self):
        # Measure only the model (HUD labels and halo are not solid).
        body = self.visual_body
        bounds = body.model.getTightBounds(body) if body.model is not None else None
        radius = .39  # .55-scaled fallback cube, including its corners
        if bounds:
            lo, hi = bounds
            radius = max(radius, math.hypot(max(abs(lo.x), abs(hi.x)) * abs(body.scale_x),
                                            max(abs(lo.z), abs(hi.z)) * abs(body.scale_z)))
        self.body_offset = min(ROBOT_OFFSET_DISTANCE, .10)
        self.traffic_radius = radius + self.body_offset + .01

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
        offset_distance = self.body_offset

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
        self.leg3_waypoints.clear()
        self.active_waypoints.clear()
        self.leg1_grid_path.clear()
        self.leg2_grid_path.clear()
        self.leg3_grid_path.clear()
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
        self.is_critical_battery = False
        self.emergency_dock = None
        self._resume_state = None
        self._charge_retry = 0.0
        self._emergency_cooldown = 0.0
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
        leg3_path: Optional[List[Coord]] = None,
        on_pickup=None,
        on_dropoff=None,
        on_finish=None,
    ):
        """
        Memuat rute misi 3 etape (Round-Trip):
        - Leg 1: Dari titik spawn ke Pick-up Access Node
        - Leg 2: Dari Pick-up Access Node ke Drop-off Access Node
        - Leg 3: Dari Drop-off Access Node kembali ke stasiun Dock asal (Auto-Return to Base)
        Menggunakan pemisahan lajur lateral (Dual-Lane AGV separation).
        """
        self.clear_trail()
        self.on_pickup_callback = on_pickup
        self.on_dropoff_callback = on_dropoff
        self.on_finish_callback = on_finish

        raw_leg1 = [grid_to_world(p[0], p[1], 0.0) for p in leg1_path]
        raw_leg2 = [grid_to_world(p[0], p[1], 0.0) for p in leg2_path]
        raw_leg3 = [grid_to_world(p[0], p[1], 0.0) for p in leg3_path] if leg3_path else []

        # Separasi lajur lateral: Alpha di lajur kanan (+0.22), Beta di lajur kiri (-0.22)
        offset = -0.22 if self.is_beta else 0.22
        self.leg1_waypoints = self._compute_lane_offset(raw_leg1, offset)
        self.leg2_waypoints = self._compute_lane_offset(raw_leg2, offset)
        self.leg3_waypoints = self._compute_lane_offset(raw_leg3, offset) if raw_leg3 else []

        self.total_mission_steps = len(leg1_path) + len(leg2_path) + (len(leg3_path) if leg3_path else 0)
        self.total_steps_executed = 0
        self.finish_time = None

        self.leg1_grid_path = list(leg1_path)
        self.leg2_grid_path = list(leg2_path)
        self.leg3_grid_path = list(leg3_path) if leg3_path else []
        self.pickup_access = leg1_path[-1] if leg1_path else None
        self.dropoff_access = leg2_path[-1] if leg2_path else None
        self.replan_count = 0

        if self.leg1_waypoints:
            self.active_waypoints = self.leg1_waypoints
            self.active_grid_path = list(self.leg1_grid_path)
            self.waypoint_idx = 0
            self.state = RobotState.MOVING_TO_PICKUP
            self.active_waypoints[0] = self.position
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

        if self.is_paused:
            return

        if self.state == RobotState.CHARGING:
            if self.battery < 100.0:
                self.battery = min(100.0, self.battery + 50.0 * time.dt)
                self._update_battery_visual()
                if self.battery < 100.0:
                    return
                self.recharge_full()
            self._charge_retry -= time.dt
            if self._charge_retry <= 0:
                self._finish_charging()
            return

        if 0.0 < self.battery < self.battery_critical_threshold:
            blink = (int(time.time() * 8.0) % 2) == 0
            self.top_beacon.color = color.yellow if blink else self.primary_col
        else:
            self.top_beacon.color = self.primary_col

        if self.state in (RobotState.IDLE_DOCK, RobotState.FINISHED):
            return

        # Penanganan jeda animasi ambil / taruh kargo
        if self.pause_timer > 0:
            self.pause_timer -= time.dt
            if self.pause_timer <= 0:
                self._resume_after_action()
            return

        # Interrupt before the next motion or mission-completion callback.
        if self._check_battery_emergency():
            return
        if self.state == RobotState.TO_CHARGER and self.emergency_dock is None:
            self._charge_retry -= time.dt
            if self._charge_retry <= 0:
                self._plan_charge_trip()
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

        # Check the entire edge before rotation, movement, battery or arrival events.
        if self.graph is not None:
            barriers = obstacles(self.graph)
            if any(b.hits_segment(current_pos, target_pos, self.traffic_radius) for b in barriers):
                self._traffic_retry -= time.dt
                if self._traffic_retry <= 0:
                    self._traffic_retry = .5
                    if self.state == RobotState.TO_CHARGER:
                        self._plan_charge_trip()
                    else:
                        self._replan_clearance(barriers)
                return
        self._traffic_retry = 0.0

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
            if weight > 2.0:  # HAZARD_OIL (Cost 5.0 -> Slowdown 0.4x, Drain 2.5x proporsional)
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
            if self.state != RobotState.TO_CHARGER or len(self.active_grid_path) > 1:
                self.total_steps_executed += 1
                self.consume_battery(self.battery_drain_rate * drain_mult)
            self.spawn_trail_marker(target_pos)
            if self.state == RobotState.TO_CHARGER and target_idx == len(self.active_waypoints) - 1:
                self._start_charging()
            else:
                self._check_battery_emergency()
        else:
            ratio = step / dist
            self.x += dx * ratio
            self.z += dz * ratio

        # Perbarui posisi visual follower setelah translasi & rotasi di frame ini
        self._update_visual_body()

    def _replan_clearance(self, barriers):
        start = self.get_current_grid_coord()
        goal = world_to_grid(self.active_waypoints[-1])
        graph = ClearanceGraph(self.graph, barriers, self.traffic_radius, start, self.position)
        search = a_star_search if self.is_alpha else greedy_best_first_search
        result = search(graph, start, goal, heuristic=self.heuristic_fn)
        if not result.success:
            return
        # Aim for cell centers on the detour, leaving the most space at corners.
        nodes = result.path[1:] or [goal]
        points = [grid_to_world(*node) for node in nodes]
        if any(b.hits_segment(self.position, points[0], self.traffic_radius) for b in barriers):
            return
        self.active_grid_path = [start] + nodes
        self.active_waypoints = [self.position] + points
        self.waypoint_idx = 0
        self.last_explored_nodes = set(result.explored_order)
        self.replan_count += 1

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
            self.spawn_floating_text("+CARGO UNLOADED+", color.rgb32(241, 196, 15))
            if self.on_dropoff_callback:
                self.on_dropoff_callback(self)

        elif self.state == RobotState.RETURNING_TO_DOCK:
            # Tiba di Charging Dock karena baterai kritis: isi daya dulu, misi dilanjutkan setelahnya
            if self.emergency_dock is not None:
                self.state = RobotState.CHARGING
                self.pause_timer = 2.0
                self.spawn_floating_text("+CHARGING+", color.rgb32(46, 204, 113))
                self.label_tag.text = f"{self.robot_name}\n[MENGISI DAYA...]"
                self.label_tag.color = color.rgb32(46, 204, 113)
                return

            # Tiba di stasiun dock asal (Leg 3 Selesai)!
            self.state = RobotState.FINISHED
            self.finish_time = time.time()
            self.spawn_floating_text("+BASE REACHED+", color.rgb32(46, 204, 113))
            self.visual_body.color = self.primary_col
            self.top_beacon.color = self.primary_col
            self._update_battery_visual()
            self.label_tag.text = f"{self.robot_name}\n[STANDBY DI DOCK]\nSisa baterai: {self.battery:.0f}%"
            self.label_tag.color = self.primary_col
            if self.on_finish_callback:
                self.on_finish_callback(self)

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
            # Kargo berhasil diturunkan, robot otomatis memulai Leg 3: Auto-Return to Base!
            self.deck_cargo.enabled = False
            self._start_return_leg()

    def _start_return_leg(self):
        """Memulai perjalanan Leg 3: Pulang dari rak Drop-off menuju Dock asal."""
        self.state = RobotState.RETURNING_TO_DOCK
        self.spawn_floating_text(">> RETURNING TO BASE >>", color.rgb32(0, 229, 255))
        self.label_tag.text = f"{self.robot_name}\n[PULANG KE BASE (LEG 3)]"

        if self.leg3_waypoints:
            self.active_waypoints = self.leg3_waypoints
            self.active_grid_path = list(self.leg3_grid_path)
            self.waypoint_idx = 0
        else:
            # Kalkulasi rute kembali ke spawn_coord jika belum terisi
            start_coord = world_to_grid(self.position)
            from src.cognition.pathfinding import a_star_search, greedy_best_first_search
            search_fn = a_star_search if self.is_alpha else greedy_best_first_search
            res = search_fn(self.graph, start_coord, self.spawn_coord) if self.graph else None
            if res and res.success and res.path:
                self.leg3_grid_path = list(res.path)
                raw3 = [grid_to_world(p[0], p[1], 0.0) for p in res.path]
                offset = -0.22 if self.is_beta else 0.22
                self.leg3_waypoints = self._compute_lane_offset(raw3, offset)
                self.active_waypoints = self.leg3_waypoints
                self.active_grid_path = list(self.leg3_grid_path)
                self.waypoint_idx = 0
            else:
                self.state = RobotState.FINISHED
                self.finish_time = time.time()
                if self.on_finish_callback:
                    self.on_finish_callback(self)

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

        docked = (self.state == RobotState.TO_CHARGER
                  and self.waypoint_idx == len(self.active_waypoints) - 1
                  and self.get_current_grid_coord() == self.emergency_dock)
        if self.battery <= 0.0 and not docked:
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
        elif self.battery >= self.battery_critical_threshold:
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
        if self.state in (RobotState.IDLE_DOCK, RobotState.CHARGING, RobotState.FINISHED):
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
        self._resume_state = None
        self.emergency_dock = None
        self.is_critical_battery = False
        self._charge_retry = 0.0
        self._apply_new_active_path(res.path)
        self.state = RobotState.RETURNING_TO_DOCK
        self.is_paused = False
        self.visual_body.color = self.primary_col
        self.label_tag.text = f"{self.robot_name}\n[KEMBALI KE DOCK]"
        self.label_tag.color = color.rgb32(241, 196, 15)
        return True

    def _check_battery_emergency(self) -> bool:
        if self.graph is None or self.battery >= self.battery_critical_threshold:
            return False
        if self.state not in (
            RobotState.MOVING_TO_PICKUP,
            RobotState.MOVING_TO_DROPOFF,
            RobotState.RETURNING_TO_DOCK,  # Leg 3 (pulang ke dock asal)
        ):
            return False

        self._resume_state = self.state
        self.state = RobotState.TO_CHARGER
        self.is_critical_battery = True
        self._plan_charge_trip()
        if self.state != RobotState.TO_CHARGER:
            self._emergency_cooldown = 0.5
            return False
        return True

    def _plan_charge_trip(self):
        """Select a reachable dock using the same clearances as the movement controller."""
        start = self.get_current_grid_coord()
        barriers = obstacles(self.graph)
        graph = ClearanceGraph(self.graph, barriers, self.traffic_radius, start, self.position)
        docks = self.graph.get_charging_docks()
        if start in docks and any(b.hits_segment(self.position, grid_to_world(*start),
                                                 self.traffic_radius) for b in barriers):
            docks = [dock for dock in docks if dock != start]
        found = find_nearest_dock(graph, start, docks,
                                  heuristic=self.heuristic_fn, use_astar=True)
        self._charge_retry = .5
        if found is None:
            self.emergency_dock = None
            self.active_waypoints = []
            self.active_grid_path = []
            self.waypoint_idx = 0
            self.label_tag.text = f"{self.robot_name}\n[Menunggu jalur ke charger]"
            return False
        dock, res = found

        is_low = self.battery <= self.battery_critical_threshold
        # Baterai yang dibutuhkan untuk pulang: (cost + 1 langkah sambungan) x drain + cadangan
        margin = max(self.battery_safety_margin, 2.0 * self.battery_drain_rate + 1.0)
        needed = (res.cost + 1.0) * self.battery_drain_rate + margin

        is_returning = (self.state == RobotState.RETURNING_TO_DOCK or self._resume_state == RobotState.RETURNING_TO_DOCK)
        if is_returning:
            # Leg 3: tetap pulang ke dock asal selama baterai masih cukup untuk sampai ke sana.
            # Mampir ke charging dock lain hanya jika dock asal tidak terjangkau.
            if dock == self.spawn_coord:
                if self._resume_state is not None:
                    self.state = self._resume_state
                    self._resume_state = None
                    self.is_critical_battery = False
                return False
            home = a_star_search(self.graph, self.get_current_grid_coord(), self.spawn_coord, self.heuristic_fn)
            if home.success and self.battery > (home.cost + 1.0) * self.battery_drain_rate + margin:
                if self._resume_state is not None:
                    self.state = self._resume_state
                    self._resume_state = None
                    self.is_critical_battery = False
                return False
        elif not is_low and self.battery > needed:
            if self._resume_state is not None:
                self.state = self._resume_state
                self._resume_state = None
                self.is_critical_battery = False
            return False

        self.emergency_dock, route = found
        self.active_grid_path = list(route.path)
        self.last_explored_nodes = set(route.explored_order)
        self.waypoint_idx = 0
        # Skip the current cell on departure. If already in the dock cell,
        # align to its center before charging without billing an extra tile.
        nodes = route.path[1:] or [self.emergency_dock]
        self.active_waypoints = [self.position] + [grid_to_world(*coord) for coord in nodes]
        self.label_tag.text = f"{self.robot_name}\n[Ke charger {self.emergency_dock}]"
        return True

    def _begin_emergency_charge(self, dock: Coord, path: List[Coord]):
        """Menyimpan state misi, lalu mengarahkan robot ke Charging Dock terdekat."""
        if self.state != RobotState.TO_CHARGER:
            self._resume_state = self.state
        self.is_critical_battery = True
        self.emergency_dock = dock
        self.state = RobotState.TO_CHARGER
        self.active_grid_path = list(path)
        self.waypoint_idx = 0
        nodes = path[1:] or [dock]
        self.active_waypoints = [self.position] + [grid_to_world(*coord) for coord in nodes]
        self.label_tag.text = f"{self.robot_name}\n[Ke charger {dock}]"


    def _start_charging(self):
        if self.get_current_grid_coord() != self.emergency_dock:
            self._plan_charge_trip()
            return
        self.state = RobotState.CHARGING
        self._charge_retry = 0.0
        self.label_tag.text = f"{self.robot_name}\n[Mengisi daya]"

    def _finish_charging(self):
        # Keep the cargo, leg and callbacks. A temporary obstacle at the
        # mission destination may require another attempt from the dock.
        dock = self.emergency_dock
        self.state = self._resume_state
        self.emergency_dock = None
        manager = getattr(self.graph, 'traffic_manager', None)
        pickup = getattr(manager, 'selected_pickup_shelf', None)
        dropoff = getattr(manager, 'selected_dropoff_shelf', None)
        if not self.recalculate_route(self.graph, self.heuristic_fn,
                                      pickup.shelf_data.coord if pickup else None,
                                      dropoff.shelf_data.coord if dropoff else None):
            self.state = RobotState.CHARGING
            self.emergency_dock = dock
            self._charge_retry = .5
            self.label_tag.text = f"{self.robot_name}\n[Terisi penuh, menunggu jalur]"
            return
        self.is_critical_battery = False
        self._resume_state = None
        self.label_tag.text = f"{self.robot_name}\n[{self.state.value}]"

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

    def replan_for_heuristic(
        self,
        graph: WarehouseGraph100,
        heuristic_fn,
        pickup_shelf_coord: Optional[Coord] = None,
        dropoff_shelf_coord: Optional[Coord] = None,
    ) -> bool:
        """Replan the *remaining* mission when H changes, without restarting.

        The active leg is updated from the robot's current grid cell through
        ``recalculate_route``. Future return routes are updated separately.
        Crucially this never calls ``set_mission_legs`` or resets position,
        cargo state, pause timer, callbacks, elapsed time, or completed steps.
        """
        if self.state in (RobotState.IDLE_DOCK, RobotState.FINISHED,
                          RobotState.DEAD, RobotState.CHARGING):
            return False
        # An emergency detour must keep heading to its charging station.
        if getattr(self, "is_critical_battery", False):
            return False

        search_fn = a_star_search if self.is_alpha else greedy_best_first_search
        current_state = self.state
        # Route for the return stage must remain valid even when the user
        # changes heuristics while cargo is loading/unloading.
        updated_return = False
        if current_state in (
            RobotState.MOVING_TO_PICKUP, RobotState.LOADING_CARGO,
            RobotState.MOVING_TO_DROPOFF, RobotState.UNLOADING_CARGO,
        ):
            dropoff = self.dropoff_access
            if dropoff is not None and not graph.is_walkable(*dropoff):
                if dropoff_shelf_coord is not None:
                    dropoff = graph.get_shelf_access_node(
                        dropoff_shelf_coord, from_coord=self.get_current_grid_coord()
                    )
            if dropoff is not None:
                future = search_fn(graph, dropoff, self.spawn_coord,
                                   heuristic=heuristic_fn)
                if future.success and future.path:
                    offset = -0.22 if self.is_beta else 0.22
                    raw = [grid_to_world(x, y, 0.0) for x, y in future.path]
                    future_waypoints = self._compute_lane_offset(raw, offset)
                    self.leg3_grid_path = list(future.path)
                    self.leg3_waypoints = future_waypoints
                    updated_return = True

        if current_state == RobotState.UNLOADING_CARGO:
            # Do not interrupt the unloading animation or fire callbacks again.
            if updated_return:
                self.replan_count += 1
            return updated_return

        # recalculate_route already handles moving on leg 1 / leg 2,
        # loading, and returning from the *current* cell without teleporting.
        updated_active = self.recalculate_route(
            graph=graph, heuristic_fn=heuristic_fn,
            pickup_shelf_coord=pickup_shelf_coord,
            dropoff_shelf_coord=dropoff_shelf_coord,
        )
        return updated_active or updated_return

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
        if self.state in (RobotState.IDLE_DOCK, RobotState.FINISHED, RobotState.CHARGING,
                          RobotState.TO_CHARGER):
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

                if target_dropoff is None:
                    return True
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

                if target_dropoff is None:
                    return False
                res = search_fn(graph, start_node, target_dropoff, heuristic=heuristic_fn)
                if res.success and res.path:
                    self.last_explored_nodes = set(res.explored_order)
                    self.leg2_grid_path = res.path
                    raw2 = [grid_to_world(p[0], p[1], 0.0) for p in res.path]
                    offset = -0.22 if self.is_beta else 0.22
                    self.leg2_waypoints = self._compute_lane_offset(raw2, offset)
                    self.replan_count += 1
                    return True

        # ---------------------------------------------------------------------
        # KASUS 4: SEDANG PULANG MENUJU DOCK / BASE (LEG 3)
        # ---------------------------------------------------------------------
        elif self.state == RobotState.RETURNING_TO_DOCK:
            home_target = self.emergency_dock if self.emergency_dock is not None else self.spawn_coord
            res = search_fn(graph, start_node, home_target, heuristic=heuristic_fn)
            if not res.success or not res.path:
                return False

            self.last_explored_nodes = set(res.explored_order)
            self._apply_new_active_path(res.path)
            self.replan_count += 1
            return True

        return False

    def _apply_new_active_path(self, new_grid_path: List[Coord], message: str = "REPLANNING ROUTE..."):
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
            self.spawn_floating_text(message, color.rgb32(0, 229, 255))

    def on_destroy(self):
        """Membersihkan entitas visual independen saat robot didestroy."""
        if hasattr(self, 'visual_body') and self.visual_body:
            destroy(self.visual_body)
