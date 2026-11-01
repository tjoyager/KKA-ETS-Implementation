"""
map_grid.py
============
Modul untuk representasi peta grid 2D gudang (Warehouse Grid Map).
Menyimpan informasi sel kosong (lorong), rintangan (rak penyimpanan/dinding),
posisi awal (start/docking robot), dan posisi tujuan (goal/paket).
"""

from enum import IntEnum
from typing import List, Tuple, Optional
import numpy as np


class CellType(IntEnum):
    EMPTY = 0      # Lorong / jalan kosong yang dapat dilalui
    OBSTACLE = 1   # Rak gudang / dinding penghalang
    START = 2      # Titik awal robot (charging station / docking)
    GOAL = 3       # Titik tujuan (rak barang / drop-off point)


class WarehouseGrid:
    """
    Kelas representasi peta grid 2D untuk gudang.
    Sistem koordinat: (x, y) di mana:
      - x = sumbu horizontal (kolom), dari 0 sampai width - 1
      - y = sumbu vertikal (baris), dari 0 sampai height - 1
    """

    def __init__(
        self,
        width: int = 30,
        height: int = 20,
        start: Tuple[int, int] = (1, 2),
        goal: Tuple[int, int] = (28, 17),
    ):
        self.width = width
        self.height = height
        self.grid = np.zeros((height, width), dtype=int)
        self.start = start
        self.goal = goal

    def is_in_bounds(self, x: int, y: int) -> bool:
        """Memeriksa apakah koordinat (x, y) berada di dalam batas peta."""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        """
        Memeriksa apakah sel pada (x, y) dapat dilalui (bukan rintangan/rak).
        """
        if not self.is_in_bounds(x, y):
            return False
        return self.grid[y, x] != CellType.OBSTACLE

    def set_obstacle(self, x: int, y: int) -> None:
        """Menambahkan rintangan pada koordinat (x, y)."""
        if self.is_in_bounds(x, y):
            if (x, y) != self.start and (x, y) != self.goal:
                self.grid[y, x] = CellType.OBSTACLE

    def remove_obstacle(self, x: int, y: int) -> None:
        """Menghapus rintangan dari koordinat (x, y)."""
        if self.is_in_bounds(x, y):
            self.grid[y, x] = CellType.EMPTY

    def add_shelf_block(self, x_start: int, y_start: int, block_w: int, block_h: int) -> None:
        """
        Menempatkan blok rak persegi panjang dari (x_start, y_start)
        dengan lebar block_w dan tinggi block_h.
        """
        for dx in range(block_w):
            for dy in range(block_h):
                self.set_obstacle(x_start + dx, y_start + dy)

    def get_neighbors(
        self, x: int, y: int, allow_diagonal: bool = False
    ) -> List[Tuple[int, int]]:
        """
        Mengambil daftar tetangga yang valid dan dapat dilalui dari posisi (x, y).
        Secara default menggunakan 4 arah pergerakan (Utara, Selatan, Timur, Barat).
        """
        # Pergerakan 4-arah: Atas, Bawah, Kiri, Kanan
        directions = [(0, 1), (0, -1), (-1, 0), (1, 0)]
        if allow_diagonal:
            # Pergerakan 8-arah
            directions += [(1, 1), (1, -1), (-1, 1), (-1, -1)]

        neighbors = []
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                # Cegah diagonal corner-cutting jika diagonal diaktifkan
                if allow_diagonal and abs(dx) == 1 and abs(dy) == 1:
                    if not (self.is_walkable(x + dx, y) and self.is_walkable(x, y + dy)):
                        continue
                neighbors.append((nx, ny))

        return neighbors

    def get_step_cost(
        self, from_node: Tuple[int, int], to_node: Tuple[int, int]
    ) -> float:
        """
        Menghitung biaya pergerakan dari satu sel ke sel tetangga.
        1.0 untuk gerakan ortogonal, sqrt(2) ~ 1.414 untuk diagonal.
        """
        dx = abs(to_node[0] - from_node[0])
        dy = abs(to_node[1] - from_node[1])
        if dx == 1 and dy == 1:
            return 1.41421356
        return 1.0

    @classmethod
    def create_default_warehouse(cls) -> "WarehouseGrid":
        """
        Membuat layout denah gudang kompleks (30x20 sel) dengan lorong bertingkat
        dan rintangan labirin realistis.
        
        Start: (1, 2)  - Docking station / Charging Pad di pojok kiri bawah.
        Goal:  (28, 17) - Rak penyimpanan kargo tingkat tinggi di pojok kanan atas.
        
        Karakteristik Layout:
        - Terdapat 4 zona baris rak penyimpanan utama dengan lorong-lorong alternatif.
        - Memiliki jebakan buntu (*cul-de-sac trap*) dan sekat partisi di jalur diagonal.
        - Perbedaan Algoritma Sangat Nyata:
          * A* Search mengevaluasi biaya aktual g(n) sehingga memilih lorong tembus
            tengah yang optimal (biaya 42 langkah).
          * Greedy Best-First Search (GBFS) hanya terpaku pada nilai heuristik h(n)
            sehingga terburu-buru ke lorong atas yang terbentur dinding pembatas,
            terpaksa memutar jauh (biaya 48 langkah / +6 langkah lebih panjang).
        """
        warehouse = cls(width=30, height=20, start=(1, 2), goal=(28, 17))

        # Zona 1: Rak Area Bawah (y = 1..4)
        warehouse.add_shelf_block(x_start=3, y_start=1, block_w=6, block_h=4)
        warehouse.add_shelf_block(x_start=12, y_start=1, block_w=7, block_h=4)
        warehouse.add_shelf_block(x_start=22, y_start=1, block_w=6, block_h=4)

        # Zona 2: Rak Area Tengah-Bawah (y = 7..10)
        warehouse.add_shelf_block(x_start=3, y_start=7, block_w=6, block_h=4)
        warehouse.add_shelf_block(x_start=12, y_start=7, block_w=8, block_h=4)
        warehouse.add_shelf_block(x_start=23, y_start=7, block_w=5, block_h=4)

        # Zona 3: Rak Area Tengah-Atas (y = 13..15)
        warehouse.add_shelf_block(x_start=3, y_start=13, block_w=7, block_h=3)
        warehouse.add_shelf_block(x_start=13, y_start=13, block_w=7, block_h=3)
        warehouse.add_shelf_block(x_start=23, y_start=13, block_w=5, block_h=3)

        # Zona 4: Rak Area Atas (y = 17..18)
        warehouse.add_shelf_block(x_start=3, y_start=17, block_w=6, block_h=2)
        warehouse.add_shelf_block(x_start=12, y_start=17, block_w=8, block_h=2)

        # Rintangan Strategis & Sekat Partisi Labirin:
        # 1. Lorong buntu di persimpangan tengah (x=10, 11)
        warehouse.set_obstacle(10, 8)
        warehouse.set_obstacle(10, 9)
        warehouse.set_obstacle(10, 10)
        warehouse.set_obstacle(11, 10)
        warehouse.set_obstacle(11, 11)
        warehouse.set_obstacle(11, 12)

        # 2. Dinding pembatas vertikal dekat tujuan (menjebak greedy search)
        warehouse.set_obstacle(21, 14)
        warehouse.set_obstacle(21, 15)
        warehouse.set_obstacle(21, 16)
        warehouse.set_obstacle(21, 17)
        warehouse.set_obstacle(21, 18)

        # 3. Sekat lorong bawah (mengarahkan aliran robot ke jalur tengah)
        warehouse.set_obstacle(20, 3)
        warehouse.set_obstacle(20, 4)
        warehouse.set_obstacle(20, 5)

        return warehouse

    def to_ascii_map(self, path: Optional[List[Tuple[int, int]]] = None) -> str:
        """
        Menghasilkan representasi teks ASCII dari grid peta gudang.
        Simbol:
          - 'S' : Start
          - 'G' : Goal
          - '#' : Rak / Dinding
          - '*' : Jalur robot
          - '.' : Lorong kosong
        """
        path_set = set(path) if path else set()
        lines = []

        # Border atas
        lines.append("+" + "-" * (self.width * 2 + 1) + "+")

        # Cetak baris dari atas (y = height - 1) ke bawah (y = 0)
        for y in range(self.height - 1, -1, -1):
            row_str = ["| "]
            for x in range(self.width):
                coord = (x, y)
                if coord == self.start:
                    ch = "S"
                elif coord == self.goal:
                    ch = "G"
                elif coord in path_set:
                    ch = "*"
                elif self.grid[y, x] == CellType.OBSTACLE:
                    ch = "#"
                else:
                    ch = "."
                row_str.append(f"{ch} ")
            row_str.append("|")
            lines.append("".join(row_str))

        # Border bawah
        lines.append("+" + "-" * (self.width * 2 + 1) + "+")
        return "\n".join(lines)

    def print_ascii_map(self, path: Optional[List[Tuple[int, int]]] = None) -> None:
        """Mencetak representasi peta ke konsol terminal."""
        print(self.to_ascii_map(path))
