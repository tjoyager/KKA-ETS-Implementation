"""
map_grid.py
===========
Modul backward-compatibility yang menghubungkan impor lama ke paket modular `src.cognition`.
Menyediakan `WarehouseGrid`, `CellType`, dan `ShelfData` dengan representasi
sel rintangan Dinding (WALL), Rak (SHELF_OBSTACLE), Titik Docking (DOCK/START), dan Titik Tujuan (GOAL).
"""

from src.cognition.warehouse_graph import (
    WarehouseGraph100,
    WarehouseGraph35,
    WarehouseGraph,
    CellType,
    ShelfData,
)

# Alias backward compatibility
WarehouseGrid = WarehouseGraph100

# Ekstensi alias ramah pengguna pada CellType jika belum ada
if not hasattr(CellType, 'SHELF'):
    CellType.SHELF = CellType.SHELF_OBSTACLE
if not hasattr(CellType, 'START'):
    CellType.START = CellType.DOCK

__all__ = [
    "WarehouseGraph100",
    "WarehouseGraph35",
    "WarehouseGraph",
    "WarehouseGrid",
    "CellType",
    "ShelfData",
]
