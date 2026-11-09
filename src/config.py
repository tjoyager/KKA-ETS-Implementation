"""
config.py
=========
Konfigurasi global dan parameter simulasi simulator gudang 3D (35x25).
Menyimpan konfigurasi grid 35x25, titik docking Start & Goal,
palet warna robot & tema, rintangan dinding (wall obstacles),
preset kamera yang disesuaikan, serta parameter rendering visual offset.
"""

from typing import Tuple

# ============================================================================
# DIMENSI GRID & KOORDINAT DUNIA 3D (SKALA 35x25)
# ============================================================================
GRID_WIDTH: int = 35   # Panjang sumbu X (35 sel: 0..34)
GRID_HEIGHT: int = 25  # Lebar sumbu Z / Y (25 sel: 0..24)

WORLD_SCALE: float = 1.0
OFFSET_X: float = (GRID_WIDTH - 1) / 2.0   # 17.0
OFFSET_Z: float = (GRID_HEIGHT - 1) / 2.0  # 12.0


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
# TITIK START (DOCKING STATIONS) & GOAL PROPORSIONAL DALAM GRID 35x25
# ============================================================================
# Area Standby & Docking di pojok kiri bawah arena
SPAWN_ALPHA: Tuple[int, int] = (1, 1)   # AGV Alpha (A* Search)
SPAWN_BETA: Tuple[int, int] = (1, 3)    # AGV Beta (Greedy Best-First Search)
DEFAULT_START: Tuple[int, int] = (1, 2) # Titik tengah docking area

# Titik Target Goal di seberang diagonal (pojok kanan atas arena)
DEFAULT_GOAL: Tuple[int, int] = (32, 21)

STANDBY_ZONE_MIN: Tuple[int, int] = (0, 0)
STANDBY_ZONE_MAX: Tuple[int, int] = (4, 4)

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
# WARNA & VISUAL RAK (SHELF), DINDING (WALL), & KARGO
# ============================================================================
COLOR_SHELF_FRAME = (45, 65, 90)         # Rangka baja biru industrial
COLOR_SHELF_BEAM = (235, 125, 35)        # Balok penopang oranye keselamatan
COLOR_SHELF_HOVER = (255, 235, 59)       # Kuning terang saat disorot mouse
COLOR_SHELF_PICKUP = (0, 229, 255)       # Cyan neon untuk titik jemput (Pick-up)
COLOR_SHELF_DROPOFF = (224, 64, 251)     # Magenta neon untuk titik antar (Drop-off)

COLOR_CARGO_BOX = (180, 135, 90)         # Kardus cokelat karton standar
COLOR_CARGO_PRIORITY = (241, 196, 15)    # Emas kontainer kargo bernilai tinggi

# Rintangan Dinding (Wall Obstacles) - Abu-abu beton kontras
COLOR_WALL = (125, 132, 145)             # Abu-abu beton industrial
COLOR_WALL_ACCENT = (80, 88, 100)        # Aksen tepi balok dinding
COLOR_PERIMETER_WALL = (60, 66, 76)      # Dinding pembatas luar arena
COLOR_GOAL_PAD = (46, 204, 113)          # Hijau Emerald untuk target Goal

WALL_HEIGHT: float = 2.0                 # Tinggi balok dinding (rak = 1.0, dinding = 2.0 agar kontras)
PERIMETER_WALL_HEIGHT: float = 2.4       # Dinding batas luar arena

# ============================================================================
# RENDERING OFFSETS (MENCEGAH Z-FIGHTING & MODEL OVERLAP)
# ============================================================================
# Decoupled Follower directional right-vector lateral offset distance
ROBOT_OFFSET_DISTANCE: float = 0.20      # Jarak lateral dari center pivot (0.20)
ALPHA_MODEL_ELEVATION: float = 0.010     # Elevasi mikro visual Alpha
BETA_MODEL_ELEVATION: float = 0.015      # Elevasi mikro visual Beta (mencegah Z-fighting)

ALPHA_VISUAL_OFFSET_X: float = -0.20     # Backward compatibility alias
ALPHA_VISUAL_OFFSET_Y: float = 0.010
BETA_VISUAL_OFFSET_X: float = 0.20
BETA_VISUAL_OFFSET_Y: float = 0.015

ALPHA_TRAIL_OFFSET_X: float = -0.16      # Geser kotak jejak ke kiri
ALPHA_TRAIL_OFFSET_Y: float = 0.028      # Ketinggian jejak Alpha di lantai
BETA_TRAIL_OFFSET_X: float = 0.16        # Geser kotak jejak ke kanan
BETA_TRAIL_OFFSET_Y: float = 0.032       # Ketinggian jejak Beta di lantai

TRAIL_SCALE_SPLIT: Tuple[float, float, float] = (0.28, 0.025, 0.55)  # Ukuran kotak jejak terbelah dua

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

# ============================================================================
# PRESET KAMERA ARENA 35x25 (Disesuaikan agar seluruh grid masuk frame penuh)
# ============================================================================
CAMERA_PRESETS = {
    "isometrik": {
        "pos": (0, 42.0, -36.0),
        "target": (0, 0, 0),
        "fov": 52,
    },
    "topdown": {
        "pos": (0, 45.0, 0.001),
        "target": (0, 0, 0),
        "fov": 50,
    },
    "follow_alpha": {
        "offset": (0, 11.0, -13.0),
        "fov": 58,
    },
    "follow_beta": {
        "offset": (0, 11.0, -13.0),
        "fov": 58,
    },
}
