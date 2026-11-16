"""
simulation.py
=============
Koordinator Utama Simulator Gudang 3D (Autonomous Warehouse AGV).
Mengintegrasikan seluruh subsistem arsitektur modular dengan siklus pemuatan asinkron:
1. Pemuatan asinkron dengan loading screen responsif (mencegah window hang/freeze).
2. Floor Optimization (Texture Tiling pada 1 plane raksasa).
3. Static Mesh Combining (Ribuan rak & dinding dilebur menjadi single mesh).
4. Separated Colliders untuk raycasting klik mouse presisi tinggi.
"""

import os
from typing import Tuple

from panda3d.core import getModelPath, loadPrcFileData
from ursina import Ursina, Entity, window, application

from src.config import (
    SPAWN_ALPHA,
    SPAWN_BETA,
    COLOR_ALPHA_PRIMARY,
    COLOR_ALPHA_TRAIL,
    COLOR_BETA_PRIMARY,
    COLOR_BETA_TRAIL,
    DEFAULT_ROBOT_SPEED,
    ALPHA_TRAIL_OFFSET_X,
    ALPHA_TRAIL_OFFSET_Y,
    BETA_TRAIL_OFFSET_X,
    BETA_TRAIL_OFFSET_Y,
    get_cache_root,
    get_resource_root,
)
from src.cognition.warehouse_graph import WarehouseGraph100
from src.environment.warehouse_scene import WarehouseScene
from src.behavior.robot_controller import AGVRobot
from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem
from src.communication.ui_controller import UIController


def _parse_window_size(default: Tuple[int, int] = (1280, 720)) -> Tuple[int, int]:
    """Membaca KKA_WINDOW_SIZE (format WxH) jika disetel oleh runner/container."""
    raw = os.environ.get("KKA_WINDOW_SIZE", "").strip().lower()
    if "x" in raw:
        try:
            w_str, h_str = raw.split("x", 1)
            w, h = int(w_str), int(h_str)
            if w >= 640 and h >= 480:
                return (w, h)
        except ValueError:
            pass
    return default


def _configure_runtime_paths():
    """Mengonfigurasi direktori aset & cache .bam agar portabel di segala metode distribusi."""
    resource_root = get_resource_root()
    cache_root = get_cache_root()
    try:
        (cache_root / "assets" / "models").mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    application.asset_folder = resource_root
    application.compressed_models_folder = cache_root
    model_path = getModelPath()
    model_path.append_path(str(resource_root.resolve()))
    assets_dir = resource_root / "assets"
    if assets_dir.exists():
        model_path.append_path(str(assets_dir.resolve()))

    if os.environ.get("KKA_DISABLE_AUDIO", "").strip().lower() in ("1", "true", "yes"):
        loadPrcFileData("", "audio-library-name null")


def run_warehouse_simulation():
    """
    Meluncurkan simulator gudang 3D secara langsung tanpa dependensi terminal teks.
    """
    _configure_runtime_paths()

    # 1. Inisialisasi Aplikasi Jendela Ursina
    app = Ursina(
        title="Simulasi Robot Gudang 3D - Dual-AGV Racing (35x25)",
        borderless=False,
        fullscreen=False,
        size=_parse_window_size(),
    )
    window.fps_counter.enabled = False
    window.exit_button.visible = False

    # 2. Bangun Graf Gudang Kompleks 35x25
    graph = WarehouseGraph100.generate_complex_warehouse()

    # Variabel state aplikasi
    app_state = {
        "ready": False,
        "mission_manager": None,
        "ui_controller": None,
    }

    # Callback yang dipanggil saat seluruh proses loading asinkron selesai
    def on_environment_ready():
        # 3. Instansiasi Dua Robot AGV Konkuren (Alpha: A* vs Beta: GBFS)
        robot_alpha = AGVRobot(
            name="AGV Alpha",
            algorithm_label="A* Search",
            spawn_coord=SPAWN_ALPHA,
            primary_color_rgb=COLOR_ALPHA_PRIMARY,
            trail_color_rgb=COLOR_ALPHA_TRAIL,
            speed=DEFAULT_ROBOT_SPEED,
            is_alpha=True,
            trail_offset_x=ALPHA_TRAIL_OFFSET_X,
            trail_offset_y=ALPHA_TRAIL_OFFSET_Y,
        )

        robot_beta = AGVRobot(
            name="AGV Beta",
            algorithm_label="GBFS",
            spawn_coord=SPAWN_BETA,
            primary_color_rgb=COLOR_BETA_PRIMARY,
            trail_color_rgb=COLOR_BETA_TRAIL,
            speed=DEFAULT_ROBOT_SPEED,
            is_alpha=False,
            trail_offset_x=BETA_TRAIL_OFFSET_X,
            trail_offset_y=BETA_TRAIL_OFFSET_Y,
        )

        # 4. Inisialisasi Manajer Misi & Interaksi Raycast
        mission_mgr = MissionManager(
            graph=graph,
            scene=scene,
            robot_alpha=robot_alpha,
            robot_beta=robot_beta,
        )
        if scene.forklift:
            mission_mgr.set_forklift(scene.forklift)

        interaction_sys = InteractionSystem(mission_manager=mission_mgr, scene=scene)

        # 5. Inisialisasi Pengendali UI & HUD Ganda
        ui_ctrl = UIController(
            mission_manager=mission_mgr,
            interaction_system=interaction_sys,
            scene=scene,
        )

        app_state["mission_manager"] = mission_mgr
        app_state["ui_controller"] = ui_ctrl
        app_state["ready"] = True

        print("\n" + "=" * 70)
        print("SIMULATOR GUDANG 3D 35x25 BERHASIL DIMUAT LENGKAP!")
        print("Fitur Peta & Optimasi Performa Aktif:")
        print("  - [Grid & Map Layout]  : Skala 35x25 dengan Docking Station & Target Goal")
        print("  - [Wall Obstacles]     : Rintangan Dinding Beton & Cul-de-Sac Traps (Jebakan GBFS)")
        print("  - [Floor Tiling]       : 1 Single-Plane Raksasa (Shader Texture Tiling 35x25)")
        print("  - [Static Combine]     : Ratusan Rak & Dinding dilebur ke Single Mesh (Zero Draw-Call)")
        print("  - [Visual Offset Split]: Offset lateral lokal 3D model & jejak split mencegah Z-fighting")
        print("  - [Graph Precompute]   : Pra-kalkulasi tabel ketetanggaan graf (Pathfinding ultra-cepat)")
        print("  - [A* Tie-Breaking]    : Prioritas h(n) terkecil pada f(n) setara (Memangkas simpul)")
        print("  - [Kamera Adaptif]     : Posisi isometrik & topdown mencakup seluruh area 35x25")
        print("  - [Singleton Marker]   : 3 Indikator global untuk 608 rak (Hemat 1.200+ scene entities)")
        print("  - [Trail Pool]         : Entity Pooling daur-ulang jejak robot (Zero GC allocations)")
        print("  - [HUD Dirty-Check]    : Rate-limiting 20 Hz (Pangkas 85% render font mesh micro-stutter)")
        print("  - [Async Loading]      : Pemuatan bertahap dengan Loading Screen di tengah layar")
        print("\nFitur Interaktif Aktif:")
        print("  - [Point-and-Click]    : Klik Rak Kargo (Pick-up) lalu Klik Rak Kosong (Drop-off)")
        print("  - [Heuristik (H)]      : Ganti Heuristik (Manhattan / Euclidean / Chebyshev / Octile)")
        print("  - [Misi Acak (G)]      : Balapan instan acak A* vs GBFS")
        print("  - [Mode HUD (M)]       : Beralih antara Serious (WMS) dan Gamifikasi (Arcade)")
        print("  - [Kamera (V)]         : Isometrik -> Top-Down -> Follow Alpha -> Follow Beta -> Bebas")
        print("  - [Spasi / R / Esc]    : Jeda / Reset Posisi / Keluar")
        print("=" * 70 + "\n")

    # Konstruksi Pemandangan 3D Gudang dengan Loading Asinkron
    scene = WarehouseScene(graph=graph, on_complete=on_environment_ready)

    # 6. Loop Entitas Pengontrol Per-Frame
    class SimulatorLoop(Entity):
        def update(self):
            if app_state["ready"]:
                app_state["mission_manager"].update()
                app_state["ui_controller"].update()

        def input(self, key):
            if app_state["ready"]:
                app_state["ui_controller"].handle_input(key)
            elif key == 'escape':
                application.quit()

    SimulatorLoop()

    # Jalankan loop engine Ursina
    app.run()


if __name__ == "__main__":
    run_warehouse_simulation()
