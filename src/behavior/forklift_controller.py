"""
forklift_controller.py
======================
Pengendali Rintangan Bergerak Dinamis (User-Controlled Moving Obstacle).
Memungkinkan pengguna mengendalikan unit Forklift industri secara interaktif menggunakan kontrol WASD.
Pergerakan Forklift secara real-time memperbarui matriks WarehouseGraph100 dan memicu
dynamic replanning bagi AGV Alpha (A*) dan Beta (GBFS) jika lintasan mereka terancam.
"""

import math
from typing import Optional, Set, Tuple
from ursina import (
    Entity,
    Vec3,
    color,
    held_keys,
    time,
    Text,
    destroy,
    Cylinder,
)
from ursina.shaders import lit_with_shadows_shader

from src.cognition.warehouse_graph import WarehouseGraph100, CellType
from src.config import grid_to_world, world_to_grid, GRID_WIDTH, GRID_HEIGHT

Coord = Tuple[int, int]


def lerp_angle(a: float, b: float, t: float) -> float:
    """Interpolasi sudut terpendek (derajat) untuk rotasi halus kendaraan."""
    diff = (b - a + 180.0) % 360.0 - 180.0
    return a + diff * min(1.0, max(0.0, t))


class ForkliftController(Entity):
    """
    Entitas Forklift Industri 3D yang dikendalikan oleh User dengan tombol WASD.
    Mendeteksi tabrakan dengan rak/dinding, memperbarui sel graf secara sub-milidetik,
    dan melaporkan zona koordinat ancaman (threatened cells) ke sistem navigasi AGV.
    """

    def __init__(
        self,
        graph: WarehouseGraph100,
        start_coord: Optional[Coord] = None,
        speed: float = 5.2,
        **kwargs,
    ):
        self.graph = graph
        self.speed = speed

        # Cari koordinat awal lorong kosong yang valid jika tidak ditentukan
        if start_coord is None:
            # Tempatkan di lorong tengah arena
            cand = (17, 11)
            if not self.graph.is_walkable(cand[0], cand[1]):
                found = False
                for cx in range(10, 25):
                    for cy in range(5, 20):
                        if self.graph.is_walkable(cx, cy):
                            cand = (cx, cy)
                            found = True
                            break
                    if found:
                        break
            start_coord = cand

        self.current_grid_coord: Coord = start_coord
        self.last_grid_coord: Optional[Coord] = None
        self.last_move_dir: Tuple[int, int] = (0, 1)  # Menghadap utara secara default
        spawn_pos = grid_to_world(start_coord[0], start_coord[1], 0.0)

        super().__init__(
            position=spawn_pos,
            **kwargs,
        )

        # ---------------------------------------------------------------------
        # VISUAL FORKLIFT INDUSTRI 3D
        # ---------------------------------------------------------------------
        # 1. Badan / Chassis Utama (Hazard Industrial Orange)
        self.chassis = Entity(
            parent=self,
            model='cube',
            position=Vec3(0, 0.35, 0),
            scale=Vec3(0.84, 0.45, 1.15),
            color=color.rgb32(235, 125, 25),
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

        # 6. Label Billboard Pengendalian User
        self.label = Text(
            parent=self,
            text="FORKLIFT [WASD]",
            position=Vec3(0, 2.2, 0),
            scale=2.2,
            color=color.rgb32(245, 145, 30),
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
        self.graph.update_forklift_cell(None, self.current_grid_coord)
        self.last_grid_coord = self.current_grid_coord
        self.enabled_control = True

    def set_control_enabled(self, enabled: bool):
        """Mengaktifkan atau menonaktifkan kendali keyboard WASD (misal saat Free-Cam aktif)."""
        self.enabled_control = enabled
        if hasattr(self, 'label') and self.label:
            if enabled:
                self.label.text = "FORKLIFT [WASD]"
                self.label.color = color.rgb32(245, 145, 30)
            else:
                self.label.text = "FORKLIFT [STANDBY]"
                self.label.color = color.rgb32(180, 185, 195)

    def update(self):
        """Loop per frame: membaca held_keys WASD, translasi & rotasi halus, dan sinkronisasi graf."""
        # 1. Animasi Kedip Strobo Beacon Kuning
        blink = (int(time.time() * 6.0) % 2) == 0
        self.beacon.color = color.yellow if blink else color.orange

        # Jika kontrol dinonaktifkan (misal presenter sedang dalam mode Free-Cam), abaikan input
        if not getattr(self, 'enabled_control', True):
            return

        # 2. Deteksi Input WASD / Tombol Panah
        input_x = 0.0
        input_z = 0.0

        if held_keys['w'] or held_keys['up arrow']:
            input_z += 1.0
        if held_keys['s'] or held_keys['down arrow']:
            input_z -= 1.0
        if held_keys['d'] or held_keys['right arrow']:
            input_x += 1.0
        if held_keys['a'] or held_keys['left arrow']:
            input_x -= 1.0

        if input_x == 0.0 and input_z == 0.0:
            return

        # Normalisasi vektor input agar pergerakan diagonal tidak lebih cepat
        length = math.hypot(input_x, input_z)
        if length > 0.001:
            input_x /= length
            input_z /= length

        # Update orientasi arah pergerakan diskret untuk prediksi sel depan
        dir_gx = 1 if input_x > 0.3 else (-1 if input_x < -0.3 else 0)
        dir_gz = 1 if input_z > 0.3 else (-1 if input_z < -0.3 else 0)
        if dir_gx != 0 or dir_gz != 0:
            self.last_move_dir = (dir_gx, dir_gz)

        # 3. Rotasi Halus Menghadap Arah Gerak
        target_rot = math.degrees(math.atan2(input_x, input_z))
        self.rotation_y = lerp_angle(self.rotation_y, target_rot, time.dt * 12.0)

        # 4. Translasi Posisi dengan Pengecekan Tabrakan Dinding/Rak
        step = self.speed * time.dt
        new_pos_x = self.x + (input_x * step)
        new_pos_z = self.z + (input_z * step)

        # Pengecekan batas sumbu X
        test_coord_x = world_to_grid(Vec3(new_pos_x, self.y, self.z))
        if self._can_move_to(test_coord_x):
            self.x = new_pos_x

        # Pengecekan batas sumbu Z
        test_coord_z = world_to_grid(Vec3(self.x, self.y, new_pos_z))
        if self._can_move_to(test_coord_z):
            self.z = new_pos_z

        # 5. Sinkronisasi Grid Coordinate & Matriks Graf
        new_grid_coord = world_to_grid(self.position)
        if (
            0 <= new_grid_coord[0] < self.graph.width
            and 0 <= new_grid_coord[1] < self.graph.height
            and new_grid_coord != self.current_grid_coord
        ):
            self.last_grid_coord = self.current_grid_coord
            self.current_grid_coord = new_grid_coord
            self.graph.update_forklift_cell(self.last_grid_coord, self.current_grid_coord)

    def _can_move_to(self, coord: Coord) -> bool:
        """Memeriksa apakah sel grid tujuan dapat dimasuki oleh forklift (bukan tembok luar/sekat/rak)."""
        gx, gy = coord
        if not (0 <= gx < self.graph.width and 0 <= gy < self.graph.height):
            return False

        cell = self.graph.grid[gy, gx]
        # Forklift tidak boleh menembus rak permanen atau balok dinding
        if cell in (CellType.SHELF_OBSTACLE, CellType.WALL):
            return False
        return True

    def get_threatened_coords(self) -> Set[Coord]:
        """
        Mengembalikan himpunan sel grid yang terancam/diblokir oleh Forklift:
        1. Sel yang sedang diduduki Forklift saat ini (`current_grid_coord`).
        2. Sel tepat 1 petak di depan arah hadap/gerak Forklift (`front_coord`).
        Digunakan oleh AGV Alpha & Beta untuk collision avoidance & dynamic replanning.
        """
        threatened = {self.current_grid_coord}
        fx = self.current_grid_coord[0] + self.last_move_dir[0]
        fy = self.current_grid_coord[1] + self.last_move_dir[1]
        if 0 <= fx < self.graph.width and 0 <= fy < self.graph.height:
            threatened.add((fx, fy))
        return threatened

    def reset_position(self, coord: Optional[Coord] = None):
        """Mereset posisi Forklift ke koordinat aman."""
        old = self.current_grid_coord
        target = coord or (17, 11)
        self.position = grid_to_world(target[0], target[1], 0.0)
        self.rotation_y = 0.0
        self.current_grid_coord = target
        self.last_grid_coord = old
        self.graph.update_forklift_cell(old, target)

    def on_destroy(self):
        """Membersihkan tanda sel rintangan Forklift saat entitas dihancurkan."""
        if hasattr(self, 'graph') and self.graph and self.current_grid_coord:
            self.graph.update_forklift_cell(self.current_grid_coord, None)
