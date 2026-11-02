"""
map_grid.py
===========
Modul backward-compatibility yang menghubungkan impor lama ke paket modular `src.cognition`.
"""

from src.cognition.warehouse_graph import (
    WarehouseGraph100,
    CellType,
    ShelfData,
)

# Alias backward compatibility
WarehouseGrid = WarehouseGraph100

__all__ = [
    "WarehouseGraph100",
    "WarehouseGrid",
    "CellType",
    "ShelfData",
]
