"""
config.py
=========
Konfigurasi global dan parameter simulasi simulator gudang 3D (50x50).
Menyimpan konfigurasi grid, titik spawn, palet warna robot & tema,
serta path aset 3D eksternal.
"""

from typing import Tuple

# ============================================================================
# DIMENSI GRID & KOORDINAT DUNIA 3D
# ============================================================================
GRID_WIDTH: int = 50
GRID_HEIGHT: int = 50

WORLD_SCALE: float = 1.0
OFFSET_X: float = (GRID_WIDTH - 1) / 2.0   # 24.5
OFFSET_Z: float = (GRID_HEIGHT - 1) / 2.0  # 24.5


def grid_to_world(x: float, y: float, elevation: float = 0.0):
    """Mengonversi koordinat sel grid (x, y) menjadi koordinat dunia 3D Ursina (X, Y, Z)."""
    from ursina import Vec3
    return Vec3((x - OFFSET_X) * WORLD_SCALE, elevation, (y - OFFSET_Z) * WORLD_SCALE)


def world_to_grid(world_pos) -> Tuple[int, int]:
    """Mengonversi koordinat dunia 3D Ursina (X, Y, Z) kembali ke koordinat grid (x, y)."""
    gx = int(round((world_pos.x / WORLD_SCALE) + OFFSET_X))
    gy = int(round((world_pos.z / WORLD_SCALE) + OFFSET_Z))
    gx = max(0, min(GRID_WIDTH - 1, gx))
    gy = max(0, min(GRID_HEIGHT - 1, gy))
    return gx, gy


# ============================================================================
# TITIK SPAWN STATIS DOCKING (STANDBY AREA POJOK KIRI BAWAH)
# ============================================================================
# Koordinat absolut di pojok kiri bawah arena
SPAWN_ALPHA: Tuple[int, int] = (1, 1)  # AGV Alpha (A* Search)
SPAWN_BETA: Tuple[int, int] = (1, 3)   # AGV Beta (Greedy Best-First Search)

STANDBY_ZONE_MIN: Tuple[int, int] = (0, 0)
STANDBY_ZONE_MAX: Tuple[int, int] = (5, 5)

# ============================================================================
# PARAMETER PERGERAKAN & KINEMATIKA ROBOT
# ============================================================================
DEFAULT_ROBOT_SPEED: float = 6.0     # Kecepatan default (sel/detik)
MIN_ROBOT_SPEED: float = 2.0
MAX_ROBOT_SPEED: float = 20.0
ROTATION_SPEED: float = 14.0         # Faktor lerp sudut hadap robot (heading)
ACTION_PAUSE_DURATION: float = 0.55  # Jeda animasi ambil/taruh kargo (detik)

# ============================================================================
# IDENTITAS & WARNA ROBOT DUAL-AGV
# ============================================================================
COLOR_ALPHA_PRIMARY = (0, 195, 255)      # Cyan Elektrik
COLOR_ALPHA_SECONDARY = (25, 30, 45)     # Dark Slate
COLOR_ALPHA_TRAIL = (46, 204, 113)       # Hijau Neon (Optimal Path)

COLOR_BETA_PRIMARY = (255, 140, 0)       # Amber / Oranye Terang
COLOR_BETA_SECONDARY = (35, 25, 20)      # Dark Bronze
COLOR_BETA_TRAIL = (231, 76, 60)         # Merah Oranye Api (Sub-optimal Path)

# ============================================================================
# WARNA & VISUAL RAK (SHELF) & KARGO
# ============================================================================
COLOR_SHELF_FRAME = (45, 65, 90)         # Rangka baja biru industrial
COLOR_SHELF_BEAM = (235, 125, 35)        # Balok penopang oranye keselamatan
COLOR_SHELF_HOVER = (255, 235, 59)       # Kuning terang saat disorot mouse
COLOR_SHELF_PICKUP = (0, 229, 255)       # Cyan neon untuk titik jemput (Pick-up)
COLOR_SHELF_DROPOFF = (224, 64, 251)     # Magenta neon untuk titik antar (Drop-off)

COLOR_CARGO_BOX = (180, 135, 90)         # Kardus cokelat karton standar
COLOR_CARGO_PRIORITY = (241, 196, 15)    # Emas kontainer kargo bernilai tinggi

# ============================================================================
# JALUR BERKAS ASET MODEL 3D EKSTERNAL
# ============================================================================
MODEL_PATH_AGV = "assets/models/robot.obj"
MODEL_PATH_AGV_LOADED = "assets/models/robot-box.obj"
MODEL_PATH_SHELF_EMPTY = "assets/models/empty-shelf.obj"
MODEL_PATH_SHELF_OCCUPIED = "assets/models/occupied-shelf.obj"
MODEL_PATH_DOCK = "assets/models/docking-station.obj"
MODEL_PATH_SHELF = "assets/models/empty-shelf.obj"
MODEL_PATH_CARGO = "assets/models/cargo.obj"
MODEL_PATH_WALL = "assets/models/wall.obj"

# ============================================================================
# PRESET KAMERA ARENA 50x50
# ============================================================================
CAMERA_PRESETS = {
    "isometrik": {
        "pos": (0, 56.0, -46.0),
        "target": (0, 0, 0),
        "fov": 54,
    },
    "topdown": {
        "pos": (0, 72.0, 0.001),
        "target": (0, 0, 0),
        "fov": 50,
    },
    "follow_alpha": {
        "offset": (0, 12.0, -14.0),
        "fov": 60,
    },
    "follow_beta": {
        "offset": (0, 12.0, -14.0),
        "fov": 60,
    },
}
