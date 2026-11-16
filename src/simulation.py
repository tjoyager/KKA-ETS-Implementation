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
from ursina import Ursina, Entity, window, application, camera, color, AmbientLight, DirectionalLight, Vec3, Text
from ursina.shaders import lit_with_shadows_shader

from src.config import (
    SPAWN_ALPHA, SPAWN_BETA, COLOR_ALPHA_PRIMARY, COLOR_ALPHA_TRAIL,
    COLOR_BETA_PRIMARY, COLOR_BETA_TRAIL, DEFAULT_ROBOT_SPEED,
    ALPHA_TRAIL_OFFSET_X, ALPHA_TRAIL_OFFSET_Y, BETA_TRAIL_OFFSET_X, BETA_TRAIL_OFFSET_Y,
)
from src.cognition.warehouse_graph import WarehouseGraph100
from src.environment.warehouse_scene import WarehouseScene
from src.behavior.robot_controller import AGVRobot
from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem
from src.communication.ui_controller import UIController


def run_warehouse_simulation():
    app = Ursina(
        title="Simulasi Robot Gudang 3D - Dual-AGV Racing",
        borderless=False,
        fullscreen=False,
        size=(1280, 720),
    )
    
    # --- MATIKAN SEMUA UI DEBUG BAWAAN URSINA ---
    window.fps_counter.enabled = False
    window.exit_button.visible = False
    window.entity_counter.enabled = False   # Matikan teks "entities"
    window.collider_counter.enabled = False # Matikan teks "colliders"
    window.cog_button.enabled = False       # Matikan tombol gear
    window.color = color.rgb32(10, 12, 18)

    # PAKSA FONT GLOBAL
    font_path = 'assets/fonts/Roboto-Regular.ttf'
    if os.path.exists(font_path):
        Text.default_font = font_path

    # Pencahayaan Standar
    AmbientLight(color=color.rgba(120, 120, 140, 0.15))
    sun = DirectionalLight(shadows=True)
    sun.look_at(Vec3(1, -1, -1))
    Entity.default_shader = lit_with_shadows_shader

    graph = WarehouseGraph100.generate_complex_warehouse()
    app_state = {"ready": False, "mission_manager": None, "ui_controller": None}

    def on_environment_ready():
        robot_alpha = AGVRobot(
            name="AGV Alpha", algorithm_label="A* Search", spawn_coord=SPAWN_ALPHA,
            primary_color_rgb=COLOR_ALPHA_PRIMARY, trail_color_rgb=COLOR_ALPHA_TRAIL,
            speed=DEFAULT_ROBOT_SPEED, is_alpha=True,
            trail_offset_x=ALPHA_TRAIL_OFFSET_X, trail_offset_y=ALPHA_TRAIL_OFFSET_Y,
        )
        robot_beta = AGVRobot(
            name="AGV Beta", algorithm_label="GBFS", spawn_coord=SPAWN_BETA,
            primary_color_rgb=COLOR_BETA_PRIMARY, trail_color_rgb=COLOR_BETA_TRAIL,
            speed=DEFAULT_ROBOT_SPEED, is_alpha=False,
            trail_offset_x=BETA_TRAIL_OFFSET_X, trail_offset_y=BETA_TRAIL_OFFSET_Y,
        )

        mission_mgr = MissionManager(graph=graph, scene=scene, robot_alpha=robot_alpha, robot_beta=robot_beta)
        if scene.forklift:
            mission_mgr.set_forklift(scene.forklift)

        interaction_sys = InteractionSystem(mission_manager=mission_mgr, scene=scene)
        ui_ctrl = UIController(mission_manager=mission_mgr, interaction_system=interaction_sys, scene=scene)

        app_state["mission_manager"] = mission_mgr
        app_state["ui_controller"] = ui_ctrl
        app_state["ready"] = True

        print("\nSIMULATOR BERHASIL DIMUAT!\n")

    scene = WarehouseScene(graph=graph, on_complete=on_environment_ready)

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
    app.run()

if __name__ == "__main__":
    run_warehouse_simulation()