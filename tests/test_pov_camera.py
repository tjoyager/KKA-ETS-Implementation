"""
test_pov_camera.py
==================
Pengujian Headless Fitur Kamera POV (Point of View / First-Person / Dashcam):
1. Siklus pergantian kamera: Isometrik -> Top-Down -> POV Alpha (A*) -> POV Beta (GBFS) -> Isometrik.
2. Logika Camera Parenting:
   - pov_alpha: camera.parent = robot_alpha.visual_body, position=(0, 1.5, 0.5), rotation=(10, 0, 0).
   - pov_beta: camera.parent = robot_beta.visual_body, position=(0, 1.5, 0.5), rotation=(10, 0, 0).
   - isometrik/topdown: camera.parent = scene, reset posisi & rotasi arena statis.
3. Indikator UI (btn_cam & prompt_text).
4. Keyboard Input handling (tombol [C] dan [F]).
"""

import pytest
from unittest.mock import MagicMock
from ursina import Ursina, Entity, Vec3, camera, scene

from src.cognition.warehouse_graph import WarehouseGraph100
from src.behavior.robot_controller import AGVRobot
from src.behavior.mission_manager import MissionManager
from src.environment.warehouse_scene import WarehouseScene
from src.communication.interaction_system import InteractionSystem
from src.communication.ui_controller import UIController
from src.config import SPAWN_ALPHA, SPAWN_BETA, CAMERA_PRESETS


@pytest.fixture(scope="module")
def ursina_app():
    """Fixture inisialisasi Ursina headless untuk testing 3D scene graph."""
    app = Ursina(headless=True)
    yield app


def test_camera_mode_cycle(ursina_app):
    """Memverifikasi urutan siklus kamera: Isometrik -> Topdown -> POV Alpha -> POV Beta -> Isometrik."""
    graph = WarehouseGraph100(10, 10)
    scene_obj = WarehouseScene(graph=graph)

    # Inisialisasi awal harus Isometrik
    assert scene_obj.current_cam_mode == "isometrik"
    assert scene_obj.cam_modes == ["isometrik", "topdown", "pov_alpha", "pov_beta"]

    # 1. Isometrik -> Topdown
    m1 = scene_obj.cycle_camera_mode()
    assert m1 == "topdown"
    assert scene_obj.current_cam_mode == "topdown"

    # 2. Topdown -> POV Alpha
    m2 = scene_obj.cycle_camera_mode()
    assert m2 == "pov_alpha"
    assert scene_obj.current_cam_mode == "pov_alpha"

    # 3. POV Alpha -> POV Beta
    m3 = scene_obj.cycle_camera_mode()
    assert m3 == "pov_beta"
    assert scene_obj.current_cam_mode == "pov_beta"

    # 4. POV Beta -> Isometrik (Wrap around)
    m4 = scene_obj.cycle_camera_mode()
    assert m4 == "isometrik"
    assert scene_obj.current_cam_mode == "isometrik"


def test_camera_parenting_logic(ursina_app):
    """
    Memverifikasi parenting camera ke visual_body robot:
    - pov_alpha menempel ke robot_alpha.visual_body dengan pos=(0, 1.5, 0.5) & rot=(10, 0, 0).
    - pov_beta menempel ke robot_beta.visual_body dengan pos=(0, 1.5, 0.5) & rot=(10, 0, 0).
    - isometrik/topdown melepaskan kamera kembali ke scene.
    """
    graph = WarehouseGraph100(10, 10)
    scene_obj = WarehouseScene(graph=graph)

    r_alpha = AGVRobot("Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    mgr = MissionManager(graph, scene_obj, r_alpha, r_beta)
    scene_obj.mission_mgr = mgr

    # 1. Uji Mode POV Alpha
    scene_obj.apply_camera_mode("pov_alpha")
    assert camera.parent == r_alpha.visual_body, "Camera harus diparent ke visual_body robot Alpha"
    assert camera.position == Vec3(0, 1.5, 0.5), "Posisi camera harus (0, 1.5, 0.5)"
    assert camera.rotation == Vec3(10, 0, 0), "Rotasi camera harus (10, 0, 0)"

    # 2. Uji Mode POV Beta
    scene_obj.apply_camera_mode("pov_beta")
    assert camera.parent == r_beta.visual_body, "Camera harus diparent ke visual_body robot Beta"
    assert camera.position == Vec3(0, 1.5, 0.5), "Posisi camera harus (0, 1.5, 0.5)"
    assert camera.rotation == Vec3(10, 0, 0), "Rotasi camera harus (10, 0, 0)"

    # 3. Kembali ke Mode Isometrik
    scene_obj.apply_camera_mode("isometrik")
    assert camera.parent == scene, "Camera harus dilepas kembali ke scene"
    iso_cfg = CAMERA_PRESETS["isometrik"]
    assert camera.position == Vec3(*iso_cfg["pos"])

    # 4. Kembali ke Mode Topdown
    scene_obj.apply_camera_mode("topdown")
    assert camera.parent == scene, "Camera harus tetap di scene untuk mode topdown"
    top_cfg = CAMERA_PRESETS["topdown"]
    assert camera.position == Vec3(*top_cfg["pos"])
    assert camera.rotation == Vec3(90, 0, 0)


def test_ui_controller_pov_indicators_and_input(ursina_app):
    """Memverifikasi teks tombol, prompt text, dan shortcut input keyboard [C] & [F]."""
    graph = WarehouseGraph100(10, 10)
    scene_obj = WarehouseScene(graph=graph)

    r_alpha = AGVRobot("Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    mgr = MissionManager(graph, scene_obj, r_alpha, r_beta)
    interaction_sys = InteractionSystem(mission_manager=mgr, scene=scene_obj)
    ui_ctrl = UIController(mission_manager=mgr, interaction_system=interaction_sys, scene=scene_obj)

    # Awal: Isometrik
    assert ui_ctrl.btn_cam.text == "[C] Isometrik"

    # Tekan 'c' -> Top-Down
    ui_ctrl.handle_input('c')
    assert scene_obj.current_cam_mode == "topdown"
    assert ui_ctrl.btn_cam.text == "[C] Top-Down"

    # Tekan 'c' lagi -> POV Alpha
    ui_ctrl.handle_input('c')
    assert scene_obj.current_cam_mode == "pov_alpha"
    assert ui_ctrl.btn_cam.text == "[C] POV Alpha"
    assert "[CAM] DASHCAM AKTIF: AGV ALPHA (A*)" in interaction_sys.prompt_text
    assert camera.parent == r_alpha.visual_body

    # Tekan 'f' -> POV Beta
    ui_ctrl.handle_input('f')
    assert scene_obj.current_cam_mode == "pov_beta"
    assert ui_ctrl.btn_cam.text == "[C] POV Beta"
    assert "[CAM] DASHCAM AKTIF: AGV BETA (GBFS)" in interaction_sys.prompt_text
    assert camera.parent == r_beta.visual_body

    # Tekan 'f' lagi -> Isometrik (Wrap around)
    ui_ctrl.handle_input('f')
    assert scene_obj.current_cam_mode == "isometrik"
    assert ui_ctrl.btn_cam.text == "[C] Isometrik"
    assert camera.parent == scene
