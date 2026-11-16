"""
warehouse_graph.py
==================
Representasi graf peta gudang skala 35x25 dan generator tata letak (layout) realistis.
Menyediakan pengelolaan entitas rak dinamis sebagai target node dengan access nodes (titik akses terdekat),
stasiun docking Start, target Goal, dan rintangan dinding (Wall Obstacles / Cul-de-Sac traps).
"""

import random
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple, Set
import numpy as np

from src.config import (
    GRID_WIDTH,
    GRID_HEIGHT,
    SPAWN_ALPHA,
    SPAWN_BETA,
    CHARGING_STATIONS,
    DEFAULT_START,
    DEFAULT_GOAL,
    STANDBY_ZONE_MIN,
    STANDBY_ZONE_MAX,
)

Coord = Tuple[int, int]


class CellType(IntEnum):
    EMPTY = 0           # Lorong kosong (Walkable aisle)
    SHELF_OBSTACLE = 1  # Tapak fisik rak gudang (Obstacle, but interactive node)
    WALL = 2            # Dinding luar atau sekat partisi buntu (Wall obstacle)
    DOCK = 3            # Titik docking stasiun pengisian AGV (Start)
    GOAL = 4            # Titik target utama / drop-off pad (Goal)
    TRANSFER_GATE = 5   # Gerbang transfer antar-zona (Inter-zone portal)
    FORKLIFT = 6        # Entitas rintangan bergerak dinamis (User-controlled forklift)
    HAZARD_OIL = 7      # Tumpahan oli licin (Walkable, biaya cost 5.0, perlambatan robot)
    BOOST_PAD = 8       # Speed Boost Pad konveyor (Walkable, biaya cost 0.35, akselerasi robot)


@dataclass
class ShelfData:
    """Informasi semantik untuk setiap rak di gudang."""
    coord: Coord
    shelf_id: str
    has_cargo: bool = True
    cargo_item: str = "Industrial Package"
    access_nodes: List[Coord] = field(default_factory=list)

    @property
    def x(self) -> int:
        return self.coord[0]

    @property
    def y(self) -> int:
        return self.coord[1]


# Daftar kategori barang kargo realistis untuk WMS
CARGO_CATEGORIES = [
    "Semiconductor Wafers",
    "Lithium Battery Modules",
    "Servo Actuators",
    "Optical Sensors",
    "Microcontroller Boards",
    "Pneumatic Cylinders",
    "Robotic Grippers",
    "Precision Ball Bearings",
    "Fiber Optic Cables",
    "PLC Control Units",
]


class WarehouseGraph100:
    """
    Kelas representasi graf grid 35x25 untuk navigasi AGV.
    Mengelola grid 2D, blok rak, rintangan dinding, access nodes, dan jebakan cul-de-sac.
    (Nama kelas dipertahankan untuk backward-compatibility).
    """

    def __init__(self, width: int = GRID_WIDTH, height: int = GRID_HEIGHT):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=np.int8)
        self.shelves: Dict[Coord, ShelfData] = {}
        self.dock_alpha: Coord = SPAWN_ALPHA
        self.dock_beta: Coord = SPAWN_BETA
        self.start: Coord = DEFAULT_START
        self.goal: Coord = DEFAULT_GOAL

        # Cache tetangga teroptimasi untuk pencarian rute ultra-cepat
        self._neighbors_4way: Dict[Coord, Tuple[Coord, ...]] = {}
        self._neighbors_8way: Dict[Coord, Tuple[Coord, ...]] = {}

        # Himpunan koordinat rintangan dinamis (real-time user-placed obstacles)
        self.dynamic_obstacles: Set[Coord] = set()

        # Peta bobot medan berbobot dinamis (Weighted Terrain Modifiers)
        self.terrain_weights: Dict[Coord, float] = {}

        # Koordinat gerbang transfer antar-zona
        self.transfer_gate_coords: Set[Coord] = {(34, 12), (34, 13), (34, 14)}

    def is_in_bounds(self, x: int, y: int) -> bool:
        """Memeriksa apakah koordinat (x, y) berada dalam batas arena gudang."""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        """
        Memeriksa apakah sel dapat dilintasi oleh roda AGV.
        Sel dianggap walkable jika bukan rak fisik (1), bukan dinding (2), dan bukan rintangan forklift (6).
        Dinding (WALL), Rak (SHELF_OBSTACLE), dan Forklift (FORKLIFT) memblokir pergerakan robot.
        """
        if not self.is_in_bounds(x, y):
            return False
        cell = self.grid[y, x]
        return cell not in (CellType.SHELF_OBSTACLE, CellType.WALL, CellType.FORKLIFT)

    def get_charging_docks(self) -> List[Coord]:
        """Semua titik pengisian daya aktif: 2 dock spawn + stasiun tambahan yang walkable."""
        docks: List[Coord] = [self.dock_alpha, self.dock_beta]
        for c in CHARGING_STATIONS:
            if c not in docks and self.is_walkable(c[0], c[1]):
                docks.append(c)
        return docks

    def set_cell(self, x: int, y: int, cell_type: CellType) -> None:
        """Mengatur tipe sel pada koordinat (x, y)."""
        if self.is_in_bounds(x, y):
            self.grid[y, x] = int(cell_type)

    def update_forklift_cell(self, old_coord: Optional[Coord], new_coord: Optional[Coord], forklift_id: Optional[Any] = None) -> None:
        """
        Memperbarui posisi sel rintangan Forklift secara real-time.
        Mendukung multi-forklift independen tanpa konflik / race-condition menggunakan tracking multiset sel.
        Hanya merekomputasi tetangga lokal (radius 1 sel) di sekitar koordinat lama dan baru
        dalam waktu sub-milidetik (< 0.01 ms) tanpa GC freeze, menjaga FPS Ursina stabil di 60 FPS.
        """
        if not hasattr(self, '_forklift_cell_counts'):
            self._forklift_cell_counts: Dict[Coord, int] = {}

        affected: Set[Coord] = set()

        if old_coord and self.is_in_bounds(old_coord[0], old_coord[1]):
            ox, oy = old_coord
            if old_coord in self._forklift_cell_counts:
                self._forklift_cell_counts[old_coord] -= 1
                if self._forklift_cell_counts[old_coord] <= 0:
                    del self._forklift_cell_counts[old_coord]
                    if self.grid[oy, ox] == CellType.FORKLIFT:
                        # Kembalikan ke tipe sel aslinya jika sudah tidak ada forklift lain
                        if old_coord == self.dock_alpha or old_coord == self.dock_beta:
                            self.grid[oy, ox] = CellType.DOCK
                        elif old_coord in self.transfer_gate_coords:
                            self.grid[oy, ox] = CellType.TRANSFER_GATE
                        elif old_coord == self.goal:
                            self.grid[oy, ox] = CellType.GOAL
                        else:
                            self.grid[oy, ox] = CellType.EMPTY
            else:
                if self.grid[oy, ox] == CellType.FORKLIFT:
                    if old_coord == self.dock_alpha or old_coord == self.dock_beta:
                        self.grid[oy, ox] = CellType.DOCK
                    elif old_coord in self.transfer_gate_coords:
                        self.grid[oy, ox] = CellType.TRANSFER_GATE
                    elif old_coord == self.goal:
                        self.grid[oy, ox] = CellType.GOAL
                    else:
                        self.grid[oy, ox] = CellType.EMPTY

            affected.add(old_coord)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
                nx, ny = ox + dx, oy + dy
                if self.is_in_bounds(nx, ny):
                    affected.add((nx, ny))

        if new_coord and self.is_in_bounds(new_coord[0], new_coord[1]):
            nx, ny = new_coord
            self._forklift_cell_counts[new_coord] = self._forklift_cell_counts.get(new_coord, 0) + 1
            # Jangan timpa rintangan permanen rak atau dinding
            if self.grid[ny, nx] in (CellType.EMPTY, CellType.DOCK, CellType.GOAL, CellType.TRANSFER_GATE):
                self.grid[ny, nx] = CellType.FORKLIFT
            affected.add(new_coord)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
                adj_x, adj_y = nx + dx, ny + dy
                if self.is_in_bounds(adj_x, adj_y):
                    affected.add((adj_x, adj_y))

        # Update cache tetangga hanya untuk koordinat yang terdampak
        dirs_4 = ((0, 1), (0, -1), (1, 0), (-1, 0))
        dirs_diag = ((1, 1), (1, -1), (-1, 1), (-1, -1))

        for coord in affected:
            cx, cy = coord
            if not self.is_walkable(cx, cy):
                self._neighbors_4way.pop(coord, None)
                self._neighbors_8way.pop(coord, None)
                continue

            n4 = []
            for dx, dy in dirs_4:
                tx, ty = cx + dx, cy + dy
                if self.is_walkable(tx, ty):
                    n4.append((tx, ty))
            self._neighbors_4way[coord] = tuple(n4)

            n8 = list(n4)
            for dx, dy in dirs_diag:
                tx, ty = cx + dx, cy + dy
                if self.is_walkable(tx, ty):
                    if self.is_walkable(cx + dx, cy) and self.is_walkable(cx, cy + dy):
                        n8.append((tx, ty))
            self._neighbors_8way[coord] = tuple(n8)

    def add_dynamic_obstacle(self, x: int, y: int) -> bool:
        """
        Menempatkan rintangan dinamis secara real-time pada sel lorong kosong.
        Mengubah status sel menjadi WALL dan memperbarui matriks keterhubungan graf.
        """
        if not self.is_in_bounds(x, y) or not self.is_walkable(x, y):
            return False
        self.set_cell(x, y, CellType.WALL)
        self.dynamic_obstacles.add((x, y))
        self.precompute_adjacency()
        return True

    def remove_dynamic_obstacle(self, x: int, y: int) -> bool:
        """
        Menghapus rintangan dinamis yang sebelumnya ditempatkan pengguna.
        Mengembalikan sel ke status EMPTY dan memperbarui keterhubungan graf.
        """
        if (x, y) not in self.dynamic_obstacles:
            return False
        self.set_cell(x, y, CellType.EMPTY)
        self.dynamic_obstacles.remove((x, y))
        self.precompute_adjacency()
        return True

    def clear_dynamic_obstacles(self) -> None:
        """Menghapus seluruh rintangan dinamis dan merestorasi graf ke kondisi awal."""
        for (x, y) in list(self.dynamic_obstacles):
            self.set_cell(x, y, CellType.EMPTY)
        self.dynamic_obstacles.clear()
        self.precompute_adjacency()

    def precompute_adjacency(self) -> None:
        """
        Melakukan pra-kalkulasi daftar tetangga walkable untuk traversal 4-arah & 8-arah.
        Menghilangkan alokasi memori berulang dan mempercepat pathfinding belasan kali lipat.
        """
        self._neighbors_4way.clear()
        self._neighbors_8way.clear()
        dirs_4 = ((0, 1), (0, -1), (1, 0), (-1, 0))
        dirs_diag = ((1, 1), (1, -1), (-1, 1), (-1, -1))

        for y in range(self.height):
            for x in range(self.width):
                if not self.is_walkable(x, y):
                    continue
                coord = (x, y)
                n4 = []
                for dx, dy in dirs_4:
                    nx, ny = x + dx, y + dy
                    if self.is_walkable(nx, ny):
                        n4.append((nx, ny))
                self._neighbors_4way[coord] = tuple(n4)

                n8 = list(n4)
                for dx, dy in dirs_diag:
                    nx, ny = x + dx, y + dy
                    if self.is_walkable(nx, ny):
                        if self.is_walkable(x + dx, y) and self.is_walkable(x, y + dy):
                            n8.append((nx, ny))
                self._neighbors_8way[coord] = tuple(n8)

    def get_neighbors(self, x: int, y: int, allow_diagonal: bool = False):
        """
        Mengambil tetangga walkable yang valid dari koordinat (x, y).
        Menggunakan cache pra-kalkulasi instan jika tersedia.
        """
        coord = (x, y)
        if allow_diagonal:
            if self._neighbors_8way and coord in self._neighbors_8way:
                return self._neighbors_8way[coord]
        else:
            if self._neighbors_4way and coord in self._neighbors_4way:
                return self._neighbors_4way[coord]

        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        if allow_diagonal:
            directions += [(1, 1), (1, -1), (-1, 1), (-1, -1)]

        neighbors = []
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                # Cegah corner-cutting jika diagonal aktif
                if allow_diagonal and abs(dx) == 1 and abs(dy) == 1:
                    if not (self.is_walkable(x + dx, y) and self.is_walkable(x, y + dy)):
                        continue
                neighbors.append((nx, ny))
        return neighbors

    def get_step_cost(self, from_node: Coord, to_node: Coord) -> float:
        """Biaya pergerakan dasar: 1.0 ortogonal, sqrt(2) diagonal."""
        dx = abs(to_node[0] - from_node[0])
        dy = abs(to_node[1] - from_node[1])
        if dx == 1 and dy == 1:
            return 1.41421356
        return 1.0

    def get_movement_cost(self, from_node: Coord, to_node: Coord) -> float:
        """
        Menghitung biaya pergerakan g(n) berbobot (Weighted Terrain Movement Cost).
        Biaya dasar: 1.0 ortogonal, sqrt(2) diagonal.
        Jika to_node memiliki bobot medan khusus di terrain_weights, terapkan pengali bobot tersebut:
        - HAZARD_OIL: bobot pengali 5.0 (membuat A* menghindar / memutar).
        - BOOST_PAD: bobot pengali 0.35 (membuat A* memprioritaskan konveyor cepat).
        """
        base = self.get_step_cost(from_node, to_node)
        weight = self.terrain_weights.get(to_node, 1.0)
        return base * weight

    def add_hazard_oil(self, x: int, y: int) -> bool:
        """Menempatkan tumpahan oli berbahaya dengan bobot cost = 5.0 pada sel lorong."""
        if not self.is_in_bounds(x, y) or not self.is_walkable(x, y):
            return False
        coord = (x, y)
        self.set_cell(x, y, CellType.HAZARD_OIL)
        self.terrain_weights[coord] = 5.0
        return True

    def add_boost_pad(self, x: int, y: int) -> bool:
        """Menempatkan konveyor boost pad dengan bobot cost = 0.35 pada sel lorong."""
        if not self.is_in_bounds(x, y) or not self.is_walkable(x, y):
            return False
        coord = (x, y)
        self.set_cell(x, y, CellType.BOOST_PAD)
        self.terrain_weights[coord] = 0.35
        return True

    def remove_terrain_modifier(self, x: int, y: int) -> bool:
        """Menghapus modifier medan tumpahan oli / boost pad dari sel."""
        coord = (x, y)
        if coord in self.terrain_weights:
            del self.terrain_weights[coord]
            if self.is_in_bounds(x, y) and self.grid[y, x] in (CellType.HAZARD_OIL, CellType.BOOST_PAD):
                self.set_cell(x, y, CellType.EMPTY)
            return True
        return False

    def clear_terrain_modifiers(self) -> None:
        """Membersihkan seluruh modifier medan di peta."""
        for coord in list(self.terrain_weights.keys()):
            self.remove_terrain_modifier(coord[0], coord[1])
        self.terrain_weights.clear()

    def compute_access_nodes(self, shelf_coord: Coord) -> List[Coord]:
        """Menghitung sel lorong terdekat di sekeliling rak yang dapat diakses robot."""
        sx, sy = shelf_coord
        candidates = [(sx + 1, sy), (sx - 1, sy), (sx, sy + 1), (sx, sy - 1)]
        return [c for c in candidates if self.is_walkable(c[0], c[1])]

    def get_shelf_access_node(self, shelf_coord: Coord, from_coord: Optional[Coord] = None) -> Coord:
        """
        Mendapatkan titik akses lorong terdekat ke rak.
        Jika from_coord diberikan, mengembalikan access node yang memiliki
        jarak Manhattan terdekat dari from_coord.
        """
        shelf = self.shelves.get(shelf_coord)
        access_list = shelf.access_nodes if shelf else self.compute_access_nodes(shelf_coord)

        if not access_list:
            # Fallback jika tidak ada tetangga langsung yang walkable: cari dalam radius 2
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    nx, ny = shelf_coord[0] + dx, shelf_coord[1] + dy
                    if self.is_walkable(nx, ny):
                        access_list.append((nx, ny))

        if not access_list:
            return shelf_coord  # Fallback darurat

        if from_coord is None:
            return access_list[0]

        best_node = access_list[0]
        fx, fy = from_coord
        best_dist = abs(best_node[0] - fx) + abs(best_node[1] - fy)
        for i in range(1, len(access_list)):
            node = access_list[i]
            d = abs(node[0] - fx) + abs(node[1] - fy)
            if d < best_dist:
                best_dist = d
                best_node = node
        return best_node

    def get_random_cargo_shelf(self) -> Optional[ShelfData]:
        """Memilih secara acak satu rak yang memiliki kargo."""
        cargo_shelves = [s for s in self.shelves.values() if s.has_cargo and s.access_nodes]
        if cargo_shelves:
            return random.choice(cargo_shelves)
        return None

    def get_random_empty_shelf(self, exclude_coord: Optional[Coord] = None) -> Optional[ShelfData]:
        """Memilih secara acak satu rak yang kosong (siap menerima drop-off)."""
        empty_shelves = [
            s for s in self.shelves.values()
            if not s.has_cargo and s.access_nodes and s.coord != exclude_coord
        ]
        if empty_shelves:
            return random.choice(empty_shelves)
        all_other = [s for s in self.shelves.values() if s.coord != exclude_coord and s.access_nodes]
        return random.choice(all_other) if all_other else None

    # =========================================================================
    # GENERATOR LAYOUT GUDANG REALISTIS SKALA 35x25 (DENGAN PARTISI DINDING & CUL-DE-SAC)
    # =========================================================================
    @classmethod
    def generate_complex_warehouse(cls) -> "WarehouseGraph100":
        """
        Membangun layout denah gudang modern skala 35x25 sel dengan:
        1. Zona Standby & Docking Pad di pojok kiri bawah (0..4, 0..4).
           - Dock Alpha (A* Search) di (1, 1)
           - Dock Beta (GBFS) di (1, 3)
        2. Titik Goal di pojok kanan atas di (32, 21).
        3. Lorong Arteri Utama (Cross Aisles):
           - Horizontal: y = 7, 8 dan y = 16
           - Vertikal: x = 11 dan x = 23
           - Perimeter buffer: x in (0, 34), y in (0, 24)
        4. Blok-blok rak palet modular terdistribusi dalam 3 zona X dan 3 zona Y.
        5. Rintangan Dinding (Wall Obstacles / Partisi Beton & Cul-de-Sac Traps):
           - Partisi Vertikal Utara (x=17, y=16..24): menyekat lorong atas gudang.
           - Partisi Vertikal Selatan (x=17, y=1..5): sekat pemisah ruang bawah.
           - Cul-de-Sac Trap Utama (U-shape): kantong buntu di x=24..31, y=11..16 yang menjebak
             GBFS agar salah arah ke ujung buntu karena terlalu serakah (greedy).
           - Sekat Partisi Tenggara: x=27, y=2..5.
        """
        wh = cls(GRID_WIDTH, GRID_HEIGHT)

        # 1. Kunci Zona Standby Docking di pojok kiri bawah (0..4, 0..4)
        standby_set: Set[Coord] = set()
        for x in range(STANDBY_ZONE_MIN[0], STANDBY_ZONE_MAX[0] + 1):
            for y in range(STANDBY_ZONE_MIN[1], STANDBY_ZONE_MAX[1] + 1):
                wh.set_cell(x, y, CellType.EMPTY)
                standby_set.add((x, y))

        # Tandai platform docking kedua robot
        wh.set_cell(SPAWN_ALPHA[0], SPAWN_ALPHA[1], CellType.DOCK)
        wh.set_cell(SPAWN_BETA[0], SPAWN_BETA[1], CellType.DOCK)
        wh.dock_alpha = SPAWN_ALPHA
        wh.dock_beta = SPAWN_BETA
        wh.start = DEFAULT_START
        wh.goal = DEFAULT_GOAL

        # 2. Lorong Arteri Utama (Cross Aisles / Highways)
        horiz_arteries = [7, 8, 16]
        vert_arteries = [11, 23]

        artery_cells: Set[Coord] = set()
        for y in horiz_arteries:
            for x in range(wh.width):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))

        for x in vert_arteries:
            for y in range(wh.height):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))

        # Perimeter buffer lanes (sekeliling dinding luar arena)
        for x in range(wh.width):
            for y in (0, wh.height - 1):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))
        for y in range(wh.height):
            for x in (0, wh.width - 1):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))

        # 3. Pemasangan Blok Rak Palet Modular dalam 9 Klaster Gudang (35x25)
        # Sektor X: (2, 9), (13, 21), (25, 32)
        # Sektor Y: (2, 5), (10, 14), (18, 22)
        shelf_counter = 1
        zone_ranges_x = [(2, 9), (13, 21), (25, 32)]
        zone_ranges_y = [(2, 5), (10, 14), (18, 22)]

        for zx_min, zx_max in zone_ranges_x:
            for zy_min, zy_max in zone_ranges_y:
                cur_y = zy_min
                while cur_y <= zy_max:
                    for x in range(zx_min, zx_max + 1):
                        # Celah lorong selebar 1 sel di antara blok rak
                        if (x - zx_min) % 4 == 3:
                            continue

                        coord = (x, cur_y)
                        if (
                            coord not in artery_cells
                            and coord not in standby_set
                            and coord != SPAWN_ALPHA
                            and coord != SPAWN_BETA
                            and coord != DEFAULT_GOAL
                        ):
                            wh.set_cell(x, cur_y, CellType.SHELF_OBSTACLE)

                            has_cargo = (shelf_counter % 3 != 0)
                            cargo_name = random.choice(CARGO_CATEGORIES) if has_cargo else ""

                            shelf_id = f"R-{x:02d}{cur_y:02d}"
                            wh.shelves[coord] = ShelfData(
                                coord=coord,
                                shelf_id=shelf_id,
                                has_cargo=has_cargo,
                                cargo_item=cargo_name,
                            )
                            shelf_counter += 1

                    cur_y += 2  # Rak dipisahkan oleh 1 sel lorong sirkulasi

        # 4. RINTANGAN DINDING (WALL OBSTACLES) & SEKAT CUL-DE-SAC LABIRIN
        # Tujuannya menciptakan jebakan buntu di mana GBFS (f=h) tergiur rute lurus
        # ke arah target namun menabrak dinding dan membuang waktu/langkah,
        # sedangkan A* Search memilih lorong alternatif yang optimal.
        wall_coords: Set[Coord] = set()

        # Partisi Dinding 1: Pembatas ruangan vertikal di zona atas (x=17, y=16..24)
        for y in range(16, wh.height):
            wall_coords.add((17, y))

        # Partisi Dinding 2: Sekat partisi ruangan di zona bawah (x=17, y=3..5)
        for y in range(3, 6):
            wall_coords.add((17, y))

        # Pastikan docking station kembar Alpha (17, 1) & Beta (18, 1) tidak tertutup dinding
        wall_coords.discard(SPAWN_ALPHA)
        wall_coords.discard(SPAWN_BETA)

        # Partisi Dinding 3: Cul-de-Sac Trap Utama (Kantong Buntu U-Shape)
        # Menghadap ke barat di antara x=24..31 dan y=11..16
        # Atap kantong buntu: y=16, x=24..31
        for x in range(24, 32):
            wall_coords.add((x, 16))
        # Dinding ujung buntu timur: x=31, y=11..16
        for y in range(11, 17):
            wall_coords.add((31, y))
        # Lantai kantong buntu: y=11, x=27..31 (pintu masuk kantong terbuka di x=24..26)
        for x in range(27, 32):
            wall_coords.add((x, 11))

        # Partisi Dinding 4: Sekat lorong buntu di kuadran kanan bawah (x=27, y=2..5)
        for y in range(2, 6):
            wall_coords.add((27, y))

        # Terapkan dinding ke dalam matriks grid dan hapus rak yang bertabrakan
        for wx, wy in wall_coords:
            wh.set_cell(wx, wy, CellType.WALL)
            if (wx, wy) in wh.shelves:
                del wh.shelves[(wx, wy)]

        # 5. Titik Target Goal di (32, 21) & Docking Station Kembar
        wh.set_cell(DEFAULT_GOAL[0], DEFAULT_GOAL[1], CellType.GOAL)
        if DEFAULT_GOAL in wh.shelves:
            del wh.shelves[DEFAULT_GOAL]

        wh.set_cell(SPAWN_ALPHA[0], SPAWN_ALPHA[1], CellType.DOCK)
        wh.set_cell(SPAWN_BETA[0], SPAWN_BETA[1], CellType.DOCK)
        if SPAWN_ALPHA in wh.shelves:
            del wh.shelves[SPAWN_ALPHA]
        if SPAWN_BETA in wh.shelves:
            del wh.shelves[SPAWN_BETA]

        # 5b. Gerbang Transfer Antar-Zona (Zone Transfer Gate) di x=34, y=12..14
        wh.transfer_gate_coords = {(34, 12), (34, 13), (34, 14)}
        for tx, ty in wh.transfer_gate_coords:
            wh.set_cell(tx, ty, CellType.TRANSFER_GATE)
            if (tx, ty) in wh.shelves:
                del wh.shelves[(tx, ty)]

        # 6. Hitung Access Nodes untuk semua rak yang valid
        for coord, shelf in list(wh.shelves.items()):
            shelf.access_nodes = wh.compute_access_nodes(coord)

        # 7. Pra-kalkulasi tabel tetangga graf untuk performa pencarian rute maksimal
        wh.precompute_adjacency()

        return wh

    @classmethod
    def generate_zone_b_warehouse(cls) -> "WarehouseGraph100":
        """
        Membangun layout denah gudang Zone B (High-Tech Automated Electronics & Bio-Hub):
        - Docking Station tetap di (1, 1) dan (1, 3)
        - Transfer Gate penghubung di (34, 12..14)
        - Layout klaster rak baru yang lebih padat dengan lorong zig-zag
        - Rintangan dinding kubah penyimpanan central vault (x=16..20, y=10..14)
        - Kategori barang mutakhir khusus Zone B
        """
        wh = cls(GRID_WIDTH, GRID_HEIGHT)

        # Standby Docking (0..4, 0..4)
        standby_set: Set[Coord] = set()
        for x in range(STANDBY_ZONE_MIN[0], STANDBY_ZONE_MAX[0] + 1):
            for y in range(STANDBY_ZONE_MIN[1], STANDBY_ZONE_MAX[1] + 1):
                wh.set_cell(x, y, CellType.EMPTY)
                standby_set.add((x, y))

        wh.set_cell(SPAWN_ALPHA[0], SPAWN_ALPHA[1], CellType.DOCK)
        wh.set_cell(SPAWN_BETA[0], SPAWN_BETA[1], CellType.DOCK)
        wh.dock_alpha = SPAWN_ALPHA
        wh.dock_beta = SPAWN_BETA
        wh.start = DEFAULT_START
        wh.goal = DEFAULT_GOAL

        # Arteri utama Zone B
        horiz_arteries = [6, 12, 18]
        vert_arteries = [9, 18, 26]
        artery_cells: Set[Coord] = set()
        for y in horiz_arteries:
            for x in range(wh.width):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))
        for x in vert_arteries:
            for y in range(wh.height):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))

        for x in range(wh.width):
            for y in (0, wh.height - 1):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))
        for y in range(wh.height):
            for x in (0, wh.width - 1):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))

        # Klaster rak Zone B
        shelf_counter = 1
        zone_ranges_x = [(2, 7), (11, 16), (20, 24), (28, 32)]
        zone_ranges_y = [(2, 4), (8, 10), (14, 16), (20, 22)]

        zone_b_categories = [
            "Quantum Processor Array",
            "Cryogenic Biospecimens",
            "Nanotech Supercapacitors",
            "Avionics Telemetry Nodes",
            "Solid-State Battery Cores",
            "High-Precision Gyroscopes",
            "Superconducting Magnets",
            "AI Neural Accelerator Cards"
        ]

        for zx_min, zx_max in zone_ranges_x:
            for zy_min, zy_max in zone_ranges_y:
                for y in range(zy_min, zy_max + 1):
                    for x in range(zx_min, zx_max + 1):
                        if (x - zx_min) % 3 == 2:
                            continue
                        coord = (x, y)
                        if (
                            coord not in artery_cells
                            and coord not in standby_set
                            and coord != SPAWN_ALPHA
                            and coord != SPAWN_BETA
                            and coord != DEFAULT_GOAL
                        ):
                            wh.set_cell(x, y, CellType.SHELF_OBSTACLE)
                            has_cargo = (shelf_counter % 2 == 0)
                            cargo_name = random.choice(zone_b_categories) if has_cargo else ""
                            wh.shelves[coord] = ShelfData(
                                coord=coord,
                                shelf_id=f"ZB-{x:02d}{y:02d}",
                                has_cargo=has_cargo,
                                cargo_item=cargo_name,
                            )
                            shelf_counter += 1

        # Dinding Partisi & Vault Khusus Zone B
        wall_coords: Set[Coord] = set()
        # Central Security Vault
        for x in range(16, 21):
            wall_coords.add((x, 14))
            wall_coords.add((x, 10))
        for y in range(10, 15):
            wall_coords.add((20, y))
        # Partisi barat laut
        for x in range(4, 9):
            wall_coords.add((x, 15))
        # Partisi timur laut
        for y in range(17, 24):
            wall_coords.add((28, y))

        for wx, wy in wall_coords:
            wh.set_cell(wx, wy, CellType.WALL)
            if (wx, wy) in wh.shelves:
                del wh.shelves[(wx, wy)]

        # Goal Pad di (32, 21) & Docking Station Kembar
        wh.set_cell(DEFAULT_GOAL[0], DEFAULT_GOAL[1], CellType.GOAL)
        if DEFAULT_GOAL in wh.shelves:
            del wh.shelves[DEFAULT_GOAL]

        wh.set_cell(SPAWN_ALPHA[0], SPAWN_ALPHA[1], CellType.DOCK)
        wh.set_cell(SPAWN_BETA[0], SPAWN_BETA[1], CellType.DOCK)
        if SPAWN_ALPHA in wh.shelves:
            del wh.shelves[SPAWN_ALPHA]
        if SPAWN_BETA in wh.shelves:
            del wh.shelves[SPAWN_BETA]

        # Transfer Gate di (34, 12..14)
        wh.transfer_gate_coords = {(34, 12), (34, 13), (34, 14)}
        for tx, ty in wh.transfer_gate_coords:
            wh.set_cell(tx, ty, CellType.TRANSFER_GATE)
            if (tx, ty) in wh.shelves:
                del wh.shelves[(tx, ty)]

        for coord, shelf in list(wh.shelves.items()):
            shelf.access_nodes = wh.compute_access_nodes(coord)

        wh.precompute_adjacency()
        return wh

    def to_ascii_map(self, path: Optional[List[Coord]] = None) -> str:
        """
        Menghasilkan representasi visual teks ASCII dari denah gudang.
        Simbol:
          - 'A' : Docking Station AGV Alpha
          - 'B' : Docking Station AGV Beta
          - 'G' : Titik Target Goal
          - '#' : Rintangan Dinding (Wall Obstacle)
          - '=' : Rak Penyimpanan (Shelf Obstacle)
          - '*' : Jejak Jalur Pathfinding
          - '.' : Lorong Jalan Kosong (Walkable Aisle)
        """
        path_set = set(path) if path else set()
        lines = []
        lines.append("+" + "-" * (self.width * 2 + 1) + "+")
        for y in range(self.height - 1, -1, -1):
            row = ["| "]
            for x in range(self.width):
                coord = (x, y)
                if coord in path_set:
                    ch = "*"
                elif coord == self.dock_alpha:
                    ch = "A"
                elif coord == self.dock_beta:
                    ch = "B"
                elif coord == self.goal:
                    ch = "G"
                elif self.grid[y, x] == CellType.WALL:
                    ch = "#"
                elif self.grid[y, x] == CellType.SHELF_OBSTACLE:
                    ch = "="
                elif self.grid[y, x] == CellType.DOCK:
                    ch = "D"
                else:
                    ch = "."
                row.append(f"{ch} ")
            row.append("|")
            lines.append("".join(row))
        lines.append("+" + "-" * (self.width * 2 + 1) + "+")
        return "\n".join(lines)

    def print_ascii_map(self, path: Optional[List[Coord]] = None) -> None:
        """Mencetak representasi peta gudang ke konsol terminal."""
        print(self.to_ascii_map(path))


# Alias untuk fleksibilitas impor dan backward-compatibility
WarehouseGraph35 = WarehouseGraph100
WarehouseGraph50 = WarehouseGraph100
WarehouseGraph = WarehouseGraph100
WarehouseGrid = WarehouseGraph100
