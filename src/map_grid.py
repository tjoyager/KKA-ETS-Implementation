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
        width: int = 20,
        height: int = 15,
        start: Tuple[int, int] = (1, 1),
        goal: Tuple[int, int] = (18, 13),
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
        Membuat layout denah gudang standar dengan lorong dan rak-rak realistis.
        Ukuran: 20x15 grid.
        Start: (1, 2) - Docking station pojok kiri bawah.
        Goal: (18, 12) - Rak target barang pojok kanan atas.
        
        Layout ini dirancang agar memperlihatkan perbedaan teoritis antara A*
        (menjamin jalur optimal terpendek) dan Greedy Best-First Search
        (terjebak mengambil jalur memutar karena sifat greedy-nya).
        """
        warehouse = cls(width=20, height=15, start=(1, 2), goal=(18, 12))

        # Baris 1: Rak area bawah (x, y, w, h)
        warehouse.add_shelf_block(3, 1, 4, 3)
        warehouse.add_shelf_block(10, 1, 6, 3)

        # Baris 2: Rak area tengah
        warehouse.add_shelf_block(3, 6, 5, 3)
        warehouse.add_shelf_block(11, 6, 5, 3)

        # Baris 3: Rak area atas
        warehouse.add_shelf_block(3, 11, 4, 3)
        warehouse.add_shelf_block(10, 11, 6, 3)

        # Rintangan lorong tengah vertikal (lorong buntu/sekat partisi)
        warehouse.set_obstacle(9, 7)
        warehouse.set_obstacle(9, 8)
        warehouse.set_obstacle(9, 9)

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
