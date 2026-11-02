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

from ursina import Ursina, Entity, window, application

from src.config import (
    SPAWN_ALPHA,
    SPAWN_BETA,
    COLOR_ALPHA_PRIMARY,
    COLOR_ALPHA_TRAIL,
    COLOR_BETA_PRIMARY,
    COLOR_BETA_TRAIL,
    DEFAULT_ROBOT_SPEED,
)
from src.cognition.warehouse_graph import WarehouseGraph100
from src.environment.warehouse_scene import WarehouseScene
from src.behavior.robot_controller import AGVRobot
from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem
from src.communication.ui_controller import UIController


def run_warehouse_simulation():
    """
    Meluncurkan simulator gudang 3D secara langsung tanpa dependensi terminal teks.
    """
    # 1. Inisialisasi Aplikasi Jendela Ursina
    app = Ursina(
        title="Simulasi Robot Gudang 3D - Dual-AGV Racing (50x50)",
        borderless=False,
        fullscreen=False,
        size=(1280, 720),
    )
    window.fps_counter.enabled = True
    window.exit_button.visible = False

    # 2. Bangun Graf Gudang Kompleks 50x50
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
        )

        robot_beta = AGVRobot(
            name="AGV Beta",
            algorithm_label="GBFS",
            spawn_coord=SPAWN_BETA,
            primary_color_rgb=COLOR_BETA_PRIMARY,
            trail_color_rgb=COLOR_BETA_TRAIL,
            speed=DEFAULT_ROBOT_SPEED,
        )

        # 4. Inisialisasi Manajer Misi & Interaksi Raycast
        mission_mgr = MissionManager(
            graph=graph,
            scene=scene,
            robot_alpha=robot_alpha,
            robot_beta=robot_beta,
        )

        interaction_sys = InteractionSystem(mission_manager=mission_mgr)

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
        print("SIMULATOR GUDANG 3D 50x50 BERHASIL DIMUAT LENGKAP!")
        print("Optimasi Performa Aktif:")
        print("  - [Floor Tiling]    : 1 Single-Plane Raksasa (Shader Texture Tiling 50x50)")
        print("  - [Static Combine]  : Ratusan Rak & Dinding dilebur ke Single Mesh (Zero Draw-Call)")
        print("  - [Async Loading]   : Pemuatan bertahap dengan Loading Screen di tengah layar")
        print("\nFitur Interaktif Aktif:")
        print("  - [Point-and-Click] : Klik Rak Kargo (Pick-up) lalu Klik Rak Kosong (Drop-off)")
        print("  - [Misi Acak (G)]   : Balapan instan acak A* vs GBFS")
        print("  - [Mode HUD (M)]    : Beralih antara Serious (WMS) dan Gamifikasi (Arcade)")
        print("  - [Kamera (V)]      : Isometrik -> Top-Down -> Follow Alpha -> Follow Beta -> Bebas")
        print("  - [Spasi / R / Esc] : Jeda / Reset Posisi / Keluar")
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
