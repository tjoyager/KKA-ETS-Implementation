"""
forklift_controller.py
======================
Pengendali Rintangan Bergerak Dinamis Otonom (Autonomous Moving Obstacle).
Forklift berpatroli secara mandiri (AI Patrol - Random Wandering dengan preferensi maju lurus)
di lorong-lorong gudang 35x25 tanpa memerlukan input manual pengguna.
Pergerakan Forklift secara real-time memperbarui matriks WarehouseGraph100 dalam sub-milidetik,
memicu Dynamic Collision Avoidance & Replanning bagi AGV Alpha (A*) dan Beta (GBFS)
jika lintasan aktif mereka terpotong atau terancam.
"""

import math
import random
from typing import Any, List, Optional, Set, Tuple
from ursina import (
    Entity,
    Vec3,
    color,
    time,
    Text,
    destroy,
    Cylinder,
)
from ursina.shaders import lit_with_shadows_shader

from src.cognition.warehouse_graph import WarehouseGraph100, CellType
from src.behavior.traffic_clearance import carton_bounds, forklift_bounds, touches_robot
from src.config import grid_to_world, world_to_grid, GRID_WIDTH, GRID_HEIGHT

Coord = Tuple[int, int]


def lerp_angle(a: float, b: float, t: float) -> float:
    """Interpolasi sudut terpendek (derajat) untuk rotasi halus kendaraan."""
    diff = (b - a + 180.0) % 360.0 - 180.0
    return a + diff * min(1.0, max(0.0, t))


class ForkliftController(Entity):
    """
    Entitas Forklift Industri 3D Otonom (AI Patrol / Autonomous Moving Obstacle).
    Mondar-mandir secara acak dan alami di lorong gudang tanpa menabrak dinding atau rak.
    Memperbarui sel graf secara sub-milidetik sebelum bergerak, dan melaporkan
    zona koordinat ancaman (threatened cells) ke MissionManager AGV.
    """

    def __init__(
        self,
        graph: WarehouseGraph100,
        start_coord: Optional[Coord] = None,
        speed: float = 1.5,
        move_speed: float = 1.5,
        control_scheme: str = "wasd",
        name: Optional[str] = None,
        chassis_color: Optional[Tuple[int, int, int]] = None,
        **kwargs,
    ):
        self.graph = graph
        self.control_scheme = control_scheme.lower()

        # Parameter AI Patroli Otonom
        self.is_moving: bool = False
        self.move_speed: float = float(move_speed)  # Detik per petak grid (default: 1.5 s)
        self.speed: float = float(speed)
        self.move_timer: float = 0.0
        self.wait_timer: float = random.uniform(0.0, 0.25)  # Staggering awal antar forklift

        if self.control_scheme == "arrows":
            self.scheme_label = "AUTO-ARROWS"
            fl_name = name or "FORKLIFT 2"
            col = chassis_color or (240, 195, 20)
        elif self.control_scheme == "ijkl":
            self.scheme_label = "AUTO-IJKL"
            fl_name = name or "FORKLIFT 3"
            col = chassis_color or (220, 50, 45)
        else:
            self.scheme_label = "AUTO-WASD"
            fl_name = name or "FORKLIFT 1"
            col = chassis_color or (235, 125, 25)

        self.chassis_rgb = col
        self.display_name = fl_name

        # Cari koordinat awal lorong kosong yang valid jika tidak ditentukan / terhalang
        start_coord = self._resolve_walkable_coord(self.graph, start_coord or (17, 11))

        self.start_coord: Coord = start_coord
        self.current_coord: Coord = start_coord
        self.current_grid_coord: Coord = start_coord
        self.target_coord: Optional[Coord] = start_coord
        self.last_grid_coord: Optional[Coord] = None
        self.last_move_dir: Tuple[int, int] = (0, 1)  # Menghadap utara secara default
        self.is_paused: bool = False

        spawn_pos = grid_to_world(start_coord[0], start_coord[1], 0.0)
        self.start_pos: Vec3 = Vec3(spawn_pos.x, spawn_pos.y, spawn_pos.z)
        self.target_pos: Vec3 = Vec3(spawn_pos.x, spawn_pos.y, spawn_pos.z)
        self.target_rot: float = 0.0

        super().__init__(
            position=spawn_pos,
            **kwargs,
        )
        self.name = fl_name
        self.forklift_id: int = id(self)

        # ---------------------------------------------------------------------
        # VISUAL FORKLIFT INDUSTRI 3D
        # ---------------------------------------------------------------------
        # 1. Badan / Chassis Utama
        self.chassis = Entity(
            parent=self,
            model='cube',
            position=Vec3(0, 0.35, 0),
            scale=Vec3(0.84, 0.45, 1.15),
            color=color.rgb32(*self.chassis_rgb),
            shader=lit_with_shadows_shader,
        )
        self.chassis.cast_shadows = True

        # Counterweight Belakang (Besi Abu-Abu Tua)
        self.counterweight = Entity(
            parent=self,
            model='cube',
            position=Vec3(0, 0.42, -0.42),
            scale=Vec3(0.80, 0.50, 0.32),
            color=color.rgb32(45, 48, 55),
            shader=lit_with_shadows_shader,
        )

        # 2. Kabin Pengemudi / Roll Cage (Tiang Besi Hitam)
        self.roll_cage_roof = Entity(
            parent=self,
            model='cube',
            position=Vec3(0, 1.25, -0.10),
            scale=Vec3(0.75, 0.06, 0.65),
            color=color.rgb32(35, 38, 42),
        )
        # 4 Tiang Kabin
        for px in (-0.32, 0.32):
            for pz in (-0.38, 0.18):
                Entity(
                    parent=self,
                    model='cube',
                    position=Vec3(px, 0.88, pz),
                    scale=Vec3(0.06, 0.70, 0.06),
                    color=color.rgb32(30, 32, 36),
                )

        # 3. Front Mast (Tiang Vertikal Pengangkat Garpu)
        self.mast_left = Entity(
            parent=self,
            model='cube',
            position=Vec3(-0.25, 0.85, 0.58),
            scale=Vec3(0.08, 1.10, 0.08),
            color=color.rgb32(50, 55, 62),
        )
        self.mast_right = Entity(
            parent=self,
            model='cube',
            position=Vec3(0.25, 0.85, 0.58),
            scale=Vec3(0.08, 1.10, 0.08),
            color=color.rgb32(50, 55, 62),
        )

        # 4. Garpu Depan (Forks - Besi Baja Horizontal)
        self.fork_carriage = Entity(
            parent=self,
            model='cube',
            position=Vec3(0, 0.18, 0.60),
            scale=Vec3(0.68, 0.12, 0.06),
            color=color.rgb32(70, 75, 82),
        )
        self.fork_left = Entity(
            parent=self,
            model='cube',
            position=Vec3(-0.20, 0.06, 0.90),
            scale=Vec3(0.10, 0.04, 0.62),
            color=color.rgb32(95, 100, 110),
        )
        self.fork_right = Entity(
            parent=self,
            model='cube',
            position=Vec3(0.20, 0.06, 0.90),
            scale=Vec3(0.10, 0.04, 0.62),
            color=color.rgb32(95, 100, 110),
        )

        # 5. Lampu Strobo / Warning Beacon Atas
        self.beacon = Entity(
            parent=self,
            model='sphere',
            position=Vec3(0, 1.34, -0.10),
            scale=Vec3(0.18, 0.16, 0.18),
            color=color.yellow,
        )

        # 6. Label Billboard Pengenal Entitas Otonom
        self.label = Text(
            parent=self,
            text=f"{self.display_name} [{self.scheme_label}]",
            position=Vec3(0, 2.2, 0),
            scale=2.2,
            color=color.rgb32(*self.chassis_rgb),
            origin=(0, 0),
            billboard=True,
        )

        # Roda-Roda Industri
        for wx in (-0.42, 0.42):
            for wz in (-0.35, 0.35):
                Entity(
                    parent=self,
                    model=Cylinder(resolution=16),
                    position=Vec3(wx, 0.14, wz),
                    rotation_z=90,
                    scale=Vec3(0.28, 0.10, 0.28),
                    color=color.rgb32(20, 20, 22),
                )

        # Inisialisasi rintangan sel awal di graf
        self.graph.update_forklift_cell(None, self.current_coord, forklift_id=self.forklift_id)
        self.last_grid_coord = self.current_coord
        self.enabled_control: bool = True

    def set_control_enabled(self, enabled: bool):
        """Mengaktifkan atau menonaktifkan AI patroli (misal saat Free-Cam aktif)."""
        self.enabled_control = enabled
        if hasattr(self, 'label') and self.label:
            if enabled:
                self.label.text = f"{self.display_name} [{self.scheme_label}]"
                self.label.color = color.rgb32(*self.chassis_rgb)
            else:
                self.label.text = f"{self.display_name} [STANDBY]"
                self.label.color = color.rgb32(180, 185, 195)

    def think_next_move(self) -> Optional[Coord]:
        """
        Logika Pemilihan Rute Acak (Random Wandering) Otonom:
        1. Mengambil seluruh petak tetangga 4-arah (Kiri, Kanan, Atas, Bawah) dari self.current_coord.
        2. Memfilter petak yang benar-benar is_walkable (bebas rak, dinding, dan forklift lain).
        3. Memberikan pembobotan alami (preferensi maju lurus) agar tidak bolak-balik di tempat:
           - Maju lurus (searah last_move_dir): bobot 6.0
           - Belok 90 derajat (kiri / kanan): bobot 2.0
           - Mundur 180 derajat: bobot 0.3 (hanya jika jalan buntu)
        4. Tepat sebelum mulai bergerak, memanggil graph.update_forklift_cell(old_coord, new_coord, self.forklift_id).
        5. Mengatur orientasi target_rot dan memicu interpolasi translasi mulus ke target_pos.
        """
        if self.is_moving or not getattr(self, 'enabled_control', True):
            return None

        cx, cy = self.current_coord

        # 1. Dapatkan daftar tetangga 4-arah yang valid
        neighbors = self.graph.get_neighbors(cx, cy, allow_diagonal=False)
        candidates = [c for c in neighbors if self._can_move_to(c)]

        # Hindari masuk ke docking station AGV jika ada rute lorong lain yang tersedia
        dock_coords = {
            getattr(self.graph, 'dock_alpha', None),
            getattr(self.graph, 'dock_beta', None),
        }
        non_dock = [c for c in candidates if c not in dock_coords]
        if non_dock:
            candidates = non_dock

        if not candidates:
            # Tidak ada jalan keluar saat ini (terjebak sementara), tunggu sejenak
            self.wait_timer = 0.5
            return None

        # 2. Pembobotan terarah (Preferensi Maju Lurus)
        weights: List[float] = []
        reverse_dir = (-self.last_move_dir[0], -self.last_move_dir[1])

        for cand in candidates:
            cand_dir = (cand[0] - cx, cand[1] - cy)
            if cand_dir == self.last_move_dir:
                weights.append(6.0)   # Maju lurus menyusuri lorong
            elif cand_dir == reverse_dir:
                weights.append(0.3)   # Mundur/balik arah hanya jika terpaksa
            else:
                weights.append(2.0)   # Belok 90 derajat di persimpangan

        next_coord: Coord = random.choices(candidates, weights=weights, k=1)[0]

        # 3. Hitung arah dan rotasi hadap baru
        dir_x = next_coord[0] - cx
        dir_y = next_coord[1] - cy
        self.last_move_dir = (dir_x, dir_y)

        # 4. UPDATE GRAF SUB-MILIDETIK SEBELUM BERGERAK
        # Memblokir petak baru segera sehingga AGV langsung menghitung ulang rute jika terancam
        old_coord = self.current_coord
        self.graph.update_forklift_cell(old_coord, next_coord, forklift_id=self.forklift_id)

        self.last_grid_coord = old_coord
        self.current_coord = next_coord
        self.current_grid_coord = next_coord
        self.target_coord = next_coord

        # 5. Persiapkan parameter interpolasi posisi & rotasi 3D
        start_world = grid_to_world(old_coord[0], old_coord[1], 0.0)
        target_world = grid_to_world(next_coord[0], next_coord[1], 0.0)

        self.start_pos = Vec3(start_world.x, getattr(self, 'y', 0.0), start_world.z)
        self.target_pos = Vec3(target_world.x, getattr(self, 'y', 0.0), target_world.z)
        self.target_rot = math.degrees(math.atan2(dir_x, dir_y))

        self.is_moving = True
        self.move_timer = 0.0

        return next_coord

    def update(self):
        """Loop per frame: animasi beacon strobo, otomasi AI patroli, dan interpolasi pergerakan halus."""
        # 1. Animasi Kedip Strobo Beacon Kuning
        blink = (int(time.time() * 6.0) % 2) == 0
        if hasattr(self, 'beacon') and self.beacon:
            self.beacon.color = color.yellow if blink else color.orange

        # Jika kontrol dinonaktifkan (Free-Cam) atau simulasi dijeda, hentikan pergerakan
        if not getattr(self, 'enabled_control', True) or getattr(self, 'is_paused', False):
            return

        dt = getattr(time, 'dt', 0.0)

        # 2. Pengecekan AI Patroli: Jika sedang diam, pikirkan langkah selanjutnya
        if not self.is_moving:
            if getattr(self, 'wait_timer', 0.0) > 0:
                self.wait_timer -= dt
                return
            self.think_next_move()
            return

        # 3. Interpolasi Pergerakan Halus Antar Petak (Smooth Lerp)
        if dt > 0:
            self.move_timer += dt
            t = min(1.0, self.move_timer / max(0.001, self.move_speed))

            # Translasi posisi secara halus
            self.x = self.start_pos.x + (self.target_pos.x - self.start_pos.x) * t
            self.z = self.start_pos.z + (self.target_pos.z - self.start_pos.z) * t

            # Rotasi badan forklift secara halus menghadap arah pergerakan
            self.rotation_y = lerp_angle(self.rotation_y, self.target_rot, min(1.0, dt * 10.0))

            if t >= 1.0:
                self.position = self.target_pos
                self.rotation_y = self.target_rot
                self.is_moving = False
                self.move_timer = 0.0

    def _can_move_to(self, coord: Coord) -> bool:
        """Memeriksa apakah sel grid tujuan dapat dimasuki oleh forklift."""
        gx, gy = coord
        if not (0 <= gx < self.graph.width and 0 <= gy < self.graph.height):
            return False
        if not self.graph.is_walkable(gx, gy):
            return False
        cx, cy = self.current_coord
        heading = math.degrees(math.atan2(gx - cx, gy - cy))
        reserved = forklift_bounds(self, grid_to_world(gx, gy), heading)
        manager = getattr(self.graph, 'traffic_manager', None)
        if touches_robot(reserved, manager):
            return False
        return not any(reserved.overlaps(carton_bounds(c)) for c in self.graph.dynamic_obstacles)

    def get_threatened_coords(self) -> Set[Coord]:
        """
        Mengembalikan himpunan sel grid yang terancam/diblokir oleh Forklift:
        1. Sel yang sedang diduduki Forklift saat ini (`current_coord`).
        2. Sel tujuan pergerakan aktif (`target_coord`).
        3. Sel tepat 1 petak di depan arah hadap/gerak Forklift (`front_coord`).
        Digunakan oleh AGV Alpha & Beta untuk collision avoidance & dynamic replanning.
        """
        threatened = {self.current_coord}
        if self.is_moving:
            threatened.add(self.last_grid_coord)
        if hasattr(self, 'target_coord') and self.target_coord:
            threatened.add(self.target_coord)
        fx = self.current_coord[0] + self.last_move_dir[0]
        fy = self.current_coord[1] + self.last_move_dir[1]
        if 0 <= fx < self.graph.width and 0 <= fy < self.graph.height:
            threatened.add((fx, fy))
        return threatened

    @staticmethod
    def _resolve_walkable_coord(graph: WarehouseGraph100, preferred: Coord) -> Coord:
        """Memastikan koordinat forklift selalu berada pada sel walkable (bukan rak/dinding)."""
        if graph.is_walkable(preferred[0], preferred[1]):
            return preferred
        dock_coords = {
            getattr(graph, 'dock_alpha', None),
            getattr(graph, 'dock_beta', None),
        }
        fallback: Optional[Coord] = None
        max_r = max(graph.width, graph.height)
        for radius in range(1, max_r):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    cx, cy = preferred[0] + dx, preferred[1] + dy
                    if not graph.is_walkable(cx, cy):
                        continue
                    if (cx, cy) not in dock_coords:
                        return (cx, cy)
                    if fallback is None:
                        fallback = (cx, cy)
        return fallback if fallback is not None else preferred

    def reset_position(self, coord: Optional[Coord] = None):
        """Mereset posisi Forklift ke koordinat aman yang walkable."""
        old = self.current_coord
        preferred = coord or getattr(self, 'start_coord', (17, 11))
        target = self._resolve_walkable_coord(self.graph, preferred)
        self.start_coord = target
        spawn_pos = grid_to_world(target[0], target[1], 0.0)

        self.position = spawn_pos
        self.rotation_y = 0.0
        self.current_coord = target
        self.current_grid_coord = target
        self.target_coord = target
        self.last_grid_coord = old
        self.last_move_dir = (0, 1)

        self.is_moving = False
        self.move_timer = 0.0
        self.wait_timer = 0.0
        self.start_pos = Vec3(spawn_pos.x, spawn_pos.y, spawn_pos.z)
        self.target_pos = Vec3(spawn_pos.x, spawn_pos.y, spawn_pos.z)
        self.target_rot = 0.0

        self.graph.update_forklift_cell(old, target, forklift_id=self.forklift_id)

    def on_destroy(self):
        """Membersihkan tanda sel rintangan Forklift saat entitas dihancurkan."""
        if hasattr(self, 'graph') and self.graph and hasattr(self, 'current_coord') and self.current_coord:
            self.graph.update_forklift_cell(self.current_coord, None, forklift_id=self.forklift_id)
