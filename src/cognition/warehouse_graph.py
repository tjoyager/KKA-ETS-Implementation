"""
warehouse_graph.py
==================
Representasi graf peta gudang skala 50x50 dan generator tata letak (layout) realistis.
Menyediakan pengelolaan entitas rak dinamis sebagai target node dengan access nodes (titik akses terdekat).
"""

import random
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple, Set
import numpy as np

from src.config import (
    GRID_WIDTH,
    GRID_HEIGHT,
    SPAWN_ALPHA,
    SPAWN_BETA,
    STANDBY_ZONE_MIN,
    STANDBY_ZONE_MAX,
)

Coord = Tuple[int, int]


class CellType(IntEnum):
    EMPTY = 0           # Lorong kosong (Walkable aisle)
    SHELF_OBSTACLE = 1  # Tapak fisik rak gudang (Obstacle, but interactive node)
    WALL = 2            # Dinding luar atau sekat partisi buntu
    DOCK = 3            # Titik docking stasiun pengisian AGV


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
    Kelas representasi graf grid 50x50 untuk navigasi AGV.
    Mengelola grid 2D, blok rak, access nodes, dan jebakan cul-de-sac.
    (Nama kelas dipertahankan untuk backward-compatibility).
    """

    def __init__(self, width: int = GRID_WIDTH, height: int = GRID_HEIGHT):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=np.int8)
        self.shelves: Dict[Coord, ShelfData] = {}
        self.dock_alpha = SPAWN_ALPHA
        self.dock_beta = SPAWN_BETA
        # Cache tetangga teroptimasi untuk pencarian rute ultra-cepat
        self._neighbors_4way: Dict[Coord, Tuple[Coord, ...]] = {}
        self._neighbors_8way: Dict[Coord, Tuple[Coord, ...]] = {}

    def is_in_bounds(self, x: int, y: int) -> bool:
        """Memeriksa apakah koordinat (x, y) berada dalam batas 50x50."""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        """
        Memeriksa apakah sel dapat dilintasi oleh roda AGV.
        Sel dianggap walkable jika bukan rak fisik dan bukan dinding.
        """
        if not self.is_in_bounds(x, y):
            return False
        return self.grid[y, x] in (CellType.EMPTY, CellType.DOCK)

    def set_cell(self, x: int, y: int, cell_type: CellType) -> None:
        """Mengatur tipe sel pada koordinat (x, y)."""
        if self.is_in_bounds(x, y):
            self.grid[y, x] = int(cell_type)

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
        """Biaya pergerakan: 1.0 ortogonal, sqrt(2) diagonal."""
        dx = abs(to_node[0] - from_node[0])
        dy = abs(to_node[1] - from_node[1])
        if dx == 1 and dy == 1:
            return 1.41421356
        return 1.0

    def compute_access_nodes(self, shelf_coord: Coord) -> List[Coord]:
        """Menghitung sel lorong terdekat di sekeliling rak yang dapat diakses robot."""
        sx, sy = shelf_coord
        candidates = [(sx + 1, sy), (sx - 1, sy), (sx, sy + 1), (sx, sy - 1)]
        return [c for c in candidates if self.is_walkable(c[0], c[1])]

    def get_shelf_access_node(self, shelf_coord: Coord, from_coord: Optional[Coord] = None) -> Coord:
        """
        Mendapatkan titik akses lorong terdekat ke rak.
        Jika from_coord diberikan, mengembalikan access node yang memiliki
        jarak Manhattan terdekat dari from_coord (dioptimasi tanpa alokasi lambda).
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

        # Pilih titik akses terdekat dengan posisi robot (inlined Manhattan distance)
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
        # Jika semua rak terisi, cari rak mana pun yang berbeda koordinat
        all_other = [s for s in self.shelves.values() if s.coord != exclude_coord and s.access_nodes]
        return random.choice(all_other) if all_other else None

    # =========================================================================
    # GENERATOR LAYOUT GUDANG REALISTIS SKALA 50x50
    # =========================================================================
    @classmethod
    def generate_complex_warehouse(cls) -> "WarehouseGraph100":
        """
        Membangun layout denah gudang modern skala 50x50 sel dengan:
        1. Zona Standby & Docking Pad statis di pojok kiri bawah (0..5, 0..5).
        2. Lorong Arteri Utama (Cross Aisles lebar 3 sel) di y = 10..12, 24..26, 38..40 dan x = 10..12, 24..26, 38..40.
        3. Blok-blok rak palet ganda (Double-deep racks) dengan lorong sempit (Narrow aisles).
        4. Sekat partisi labirin strategis (cul-de-sac) berskala proporsional yang menjebak GBFS vs A*.
        5. Alokasi kargo dinamis pada rak-rak interaktif.
        """
        wh = cls(GRID_WIDTH, GRID_HEIGHT)

        # 1. Kunci Zona Standby Docking di pojok kiri bawah (0..5, 0..5)
        standby_set: Set[Coord] = set()
        for x in range(STANDBY_ZONE_MIN[0], STANDBY_ZONE_MAX[0] + 1):
            for y in range(STANDBY_ZONE_MIN[1], STANDBY_ZONE_MAX[1] + 1):
                wh.set_cell(x, y, CellType.EMPTY)
                standby_set.add((x, y))

        # Tandai platform docking kedua robot
        wh.set_cell(SPAWN_ALPHA[0], SPAWN_ALPHA[1], CellType.DOCK)
        wh.set_cell(SPAWN_BETA[0], SPAWN_BETA[1], CellType.DOCK)

        # 2. Lorong Arteri Utama (Cross Aisles / Highways)
        # Lorong Horizontal: y = 10..12, 24..26, 38..40
        horiz_arteries = [
            (10, 12),
            (24, 26),
            (38, 40),
        ]
        # Lorong Vertikal: x = 10..12, 24..26, 38..40
        vert_arteries = [
            (10, 12),
            (24, 26),
            (38, 40),
        ]

        artery_cells: Set[Coord] = set()
        for y_start, y_end in horiz_arteries:
            for y in range(y_start, y_end + 1):
                for x in range(wh.width):
                    wh.set_cell(x, y, CellType.EMPTY)
                    artery_cells.add((x, y))

        for x_start, x_end in vert_arteries:
            for x in range(x_start, x_end + 1):
                for y in range(wh.height):
                    wh.set_cell(x, y, CellType.EMPTY)
                    artery_cells.add((x, y))

        # Perimeter buffer lanes (lebar 2 di sekeliling dinding)
        for x in range(wh.width):
            for y in (0, 1, wh.height - 2, wh.height - 1):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))
        for y in range(wh.height):
            for x in (0, 1, wh.width - 2, wh.width - 1):
                wh.set_cell(x, y, CellType.EMPTY)
                artery_cells.add((x, y))

        # 3. Pemasangan Blok Rak Palet Modular dalam 16 Sektor Gudang (50x50)
        # Setiap blok rak terdiri dari baris ganda rak (2 sel) memanjang,
        # dipisahkan oleh lorong sempit selebar 2 sel.
        shelf_counter = 1
        zone_ranges_x = [
            (2, 9),
            (13, 23),
            (27, 37),
            (41, 47),
        ]
        zone_ranges_y = [
            (2, 9),
            (13, 23),
            (27, 37),
            (41, 47),
        ]

        for zx_min, zx_max in zone_ranges_x:
            for zy_min, zy_max in zone_ranges_y:
                # Pasang rak baris ganda sepanjang sumbu X
                cur_y = zy_min
                while cur_y + 1 <= zy_max:
                    for x in range(zx_min, zx_max + 1):
                        # Celah lorong selebar 1 sel di antara blok rak
                        if (x - zx_min) % 5 == 4:
                            continue

                        # Pasang sepasang rak (cur_y dan cur_y + 1)
                        for sy in (cur_y, cur_y + 1):
                            coord = (x, sy)
                            if (
                                coord not in artery_cells
                                and coord not in standby_set
                                and coord != SPAWN_ALPHA
                                and coord != SPAWN_BETA
                            ):
                                wh.set_cell(x, sy, CellType.SHELF_OBSTACLE)

                                # Tentukan apakah rak memiliki kargo (rasio ~55% terisi, 45% kosong)
                                has_cargo = (shelf_counter % 9 < 5)
                                cargo_name = random.choice(CARGO_CATEGORIES) if has_cargo else ""

                                shelf_id = f"R-{x:02d}{sy:02d}"
                                wh.shelves[coord] = ShelfData(
                                    coord=coord,
                                    shelf_id=shelf_id,
                                    has_cargo=has_cargo,
                                    cargo_item=cargo_name,
                                )
                                shelf_counter += 1

                    cur_y += 4  # 2 sel rak + 2 sel lorong sempit

        # 4. Rintangan Strategis & Sekat Partisi Labirin (Cul-de-Sacs Trap)
        # Ditempatkan di zona utara-tengah (x=32, y=30..37 dan penutup y=37, x=27..32)
        # Ini menciptakan jebakan buntu berskala proporsional 50x50 di mana GBFS (f=h)
        # tergiur rute lurus ke arah target di kanan-atas namun terbentur sekat vertikal,
        # sedangkan A* Search memilih lorong arteri yang bebas hambatan.
        for y in range(30, 38):
            wh.set_cell(32, y, CellType.WALL)
            if (32, y) in wh.shelves:
                del wh.shelves[(32, y)]

        for x in range(27, 33):
            wh.set_cell(x, 37, CellType.WALL)
            if (x, 37) in wh.shelves:
                del wh.shelves[(x, 37)]

        # 4b. Dinding Partisi Tambahan Acak di Sekitar Rak (Random Warehouse Obstacles)
        # Mengumpulkan kandidat posisi sel kosong di sekitar rak tanpa memutus konektivitas graf
        random_gen = random.Random(42)
        candidate_wall_cells = []
        for (sx, sy) in list(wh.shelves.keys()):
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = sx + dx, sy + dy
                if 2 <= nx < wh.width - 2 and 2 <= ny < wh.height - 2:
                    if (
                        wh.grid[ny, nx] == CellType.EMPTY
                        and (nx > 5 or ny > 5)  # Jangan letakkan di standby/docking zone
                        and (nx, ny) not in artery_cells  # Pertahankan arteri utama tetap lancar
                        and (nx, ny) != SPAWN_ALPHA
                        and (nx, ny) != SPAWN_BETA
                    ):
                        candidate_wall_cells.append((nx, ny))

        candidate_wall_cells = list(set(candidate_wall_cells))
        random_gen.shuffle(candidate_wall_cells)

        # Helper untuk validasi keterjangkauan dan akses rak
        def _check_connectivity_and_shelf_access() -> bool:
            from collections import deque
            q = deque([SPAWN_ALPHA])
            visited = {SPAWN_ALPHA}
            while q:
                cx, cy = q.popleft()
                for nx, ny in wh.get_neighbors(cx, cy):
                    if (nx, ny) not in visited:
                        visited.add((nx, ny))
                        q.append((nx, ny))
            total_empty = sum(
                1 for gy in range(wh.height) for gx in range(wh.width)
                if wh.grid[gy, gx] == CellType.EMPTY
            )
            if len(visited) != total_empty:
                return False

            # Pastikan semua rak (kecuali jebakan labirin) tetap memiliki minimal 1 titik akses kosong
            for coord, sdata in wh.shelves.items():
                if coord in ((28, 36), (29, 36)):  # Trap labirin yang sengaja terisolasi
                    continue
                sx, sy = coord
                has_access = any(
                    0 <= sx + dx < wh.width and 0 <= sy + dy < wh.height
                    and wh.grid[sy + dy, sx + dx] == CellType.EMPTY
                    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
                )
                if not has_access:
                    return False
            return True

        target_random_walls = 35
        walls_added = 0
        for wx, wy in candidate_wall_cells:
            if walls_added >= target_random_walls:
                break
            wh.set_cell(wx, wy, CellType.WALL)
            wh.precompute_adjacency()
            if _check_connectivity_and_shelf_access():
                walls_added += 1
            else:
                wh.set_cell(wx, wy, CellType.EMPTY)

        wh.precompute_adjacency()

        # 5. Hitung Access Nodes untuk semua rak yang valid
        for coord, shelf in list(wh.shelves.items()):
            shelf.access_nodes = wh.compute_access_nodes(coord)

        # 6. Pra-kalkulasi tabel tetangga graf untuk performa pencarian rute maksimal
        wh.precompute_adjacency()

        return wh


# Alias untuk fleksibilitas impor
WarehouseGraph50 = WarehouseGraph100
WarehouseGraph = WarehouseGraph100
