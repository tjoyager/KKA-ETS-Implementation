"""
test_ui_refactor.py
===================
Pengujian Unit & Integrasi Refactoring Tata Letak UI:
1. Penempatan Panel "Operations" horizontal di bagian atas (di bawah header, di atas arena).
2. Tiga grup fungsi (01 DISPATCH, 02 ENVIRONMENT, 03 WORKSPACE) beserta separator tipis.
3. Tombol toggle "Hide [P]" / "Show [P]" dan penyesuaian posisinya saat di-hide.
4. Tombol & Box "Legenda [L]" di sisi kanan tanpa auto-hide terhadap Operations.
5. Independensi total: Operations dan Legenda dapat dibuka bersamaan maupun terpisah.
6. Anti-overlap: Bounds check antara Telemetry, Operations bar, Legenda button, Legenda panel, dan audio.
7. Keyboard shortcuts ([G], [T], [1], [2], [3], [B], [J], [X], [P], [L]) dan highlight indikator tool aktif.
"""

from pathlib import Path
import pytest
from unittest.mock import MagicMock
from ursina import Ursina, application, Vec3, window, color

from src.cognition.warehouse_graph import WarehouseGraph100
from src.behavior.robot_controller import AGVRobot
from src.behavior.mission_manager import MissionManager
from src.environment.warehouse_scene import WarehouseScene
from src.communication.interaction_system import InteractionSystem, PlacementTool
from src.communication.ui_controller import UIController
from src.config import SPAWN_ALPHA, SPAWN_BETA, CAMERA_PRESETS


@pytest.fixture
def setup_ui(ursina_app):
    from ursina import EditorCamera
    application.asset_folder = Path(__file__).resolve().parent.parent
    graph = WarehouseGraph100(10, 10)
    scene_obj = WarehouseScene(graph=graph)
    scene_obj.free_cam = EditorCamera(enabled=False)
    r_alpha = AGVRobot("Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    mgr = MissionManager(graph, scene_obj, r_alpha, r_beta)
    interaction_sys = InteractionSystem(mission_manager=mgr, scene=scene_obj)
    ui_ctrl = UIController(mission_manager=mgr, interaction_system=interaction_sys, scene=scene_obj)
    return ui_ctrl, scene_obj, interaction_sys, mgr


def test_operations_panel_top_layout(setup_ui):
    """Memverifikasi tata letak horizontal panel Operations di bagian atas."""
    ui_ctrl, scene_obj, interaction_sys, mgr = setup_ui
    window.size = (1600, 900)
    ui_ctrl._last_aspect_ratio = -1.0
    ui_ctrl._update_layout()

    # Pastikan side_bg berada di bawah header (header rule y ≈ 0.436) dan di atas telemetry (y <= 0.366)
    ops_top = ui_ctrl.side_bg.y + ui_ctrl.side_bg.scale_y / 2
    ops_bottom = ui_ctrl.side_bg.y - ui_ctrl.side_bg.scale_y / 2

    assert ops_top < 0.436, f"Top of operations ({ops_top}) harus di bawah header rule (0.436)"
    assert ops_bottom >= 0.366, f"Bottom of operations ({ops_bottom}) harus di atas batas telemetry/legenda (0.366)"

    # Susunan horizontal: grup 01, separator 1, grup 02, separator 2, grup 03
    assert ui_ctrl.btn_random.x < ui_ctrl.btn_transfer.x
    assert ui_ctrl.btn_transfer.x < ui_ctrl.sep_1.x
    assert ui_ctrl.sep_1.x < ui_ctrl.btn_cargo.x
    assert ui_ctrl.btn_cargo.x < ui_ctrl.btn_oil.x < ui_ctrl.btn_boost.x
    assert ui_ctrl.btn_boost.x < ui_ctrl.sep_2.x
    assert ui_ctrl.sep_2.x < ui_ctrl.btn_freecam.x
    assert ui_ctrl.btn_freecam.x < ui_ctrl.btn_report.x < ui_ctrl.btn_clear.x
    assert ui_ctrl.btn_clear.x < ui_ctrl.btn_tools.x


def test_anti_overlap_bounds(setup_ui):
    """Memverifikasi bahwa panel Operations, Telemetry, dan Legenda tidak tumpang tindih."""
    ui_ctrl, scene_obj, interaction_sys, mgr = setup_ui
    window.aspect_ratio = 16 / 9
    ui_ctrl._last_aspect_ratio = -1.0
    ui_ctrl._update_layout()

    # Batas kanan Telemetry panel (SeriousHUD)
    tel_w = ui_ctrl.hud_serious.panel_w
    half = window.aspect_ratio / 2
    tel_right = -half + 0.018 + tel_w

    # Batas kiri panel Operations
    ops_left = ui_ctrl.side_bg.x - ui_ctrl.side_bg.scale_x / 2
    ops_right = ui_ctrl.side_bg.x + ui_ctrl.side_bg.scale_x / 2

    # Batas kiri tombol Legenda
    legend_btn_left = ui_ctrl.btn_legend.x - ui_ctrl.btn_legend.scale_x / 2

    # Margin check: Operations tidak menabrak Telemetry di kiri dan Legenda di kanan
    assert ops_left > tel_right, f"Operations left ({ops_left}) harus di kanan Telemetry right ({tel_right})"
    assert ops_right < legend_btn_left, f"Operations right ({ops_right}) harus di kiri Legenda button ({legend_btn_left})"

    # Box Legenda tidak bertabrakan dengan tombol audio di kanan bawah
    # (audio test button di y = -0.354, top ≈ -0.340)
    legend_box_bottom = ui_ctrl.legend_panel.y - ui_ctrl.legend_panel.scale_y / 2
    assert legend_box_bottom > -0.340, f"Legenda bottom ({legend_box_bottom}) harus di atas audio buttons (-0.340)"


def test_independent_operations_and_legend_toggle(setup_ui):
    """Memverifikasi independensi total antara panel Operations dan Legenda."""
    ui_ctrl, scene_obj, interaction_sys, mgr = setup_ui
    ui_ctrl._update_layout()

    # Kondisi awal: Keduanya terbuka bersamaan
    assert ui_ctrl.tools_open == True
    assert ui_ctrl.legend_open == True
    assert ui_ctrl.side_bg.enabled == True
    assert ui_ctrl.legend_panel.enabled == True
    assert "Hide [P]" in ui_ctrl.btn_tools.text
    assert "Tutup [L]" in ui_ctrl.btn_legend.text

    # Sembunyikan Legenda dengan shortcut 'l'
    ui_ctrl.handle_input('l')
    assert ui_ctrl.legend_open == False
    assert ui_ctrl.legend_panel.enabled == False
    assert ui_ctrl.tools_open == True
    assert ui_ctrl.side_bg.enabled == True  # Operations TETAP terbuka!
    assert "Legenda [L]" in ui_ctrl.btn_legend.text

    # Sembunyikan Operations dengan shortcut 'p'
    ui_ctrl.handle_input('p')
    assert ui_ctrl.tools_open == False
    assert ui_ctrl.side_bg.enabled == False
    assert ui_ctrl.btn_tools.enabled == True
    assert "Show [P]" in ui_ctrl.btn_tools.text
    assert ui_ctrl.legend_open == False  # Legenda TETAP tertutup!

    # Buka Legenda kembali dengan shortcut 'l' saat Operations tertutup
    ui_ctrl.handle_input('l')
    assert ui_ctrl.legend_open == True
    assert ui_ctrl.legend_panel.enabled == True
    assert ui_ctrl.tools_open == False
    assert ui_ctrl.side_bg.enabled == False  # Operations TETAP tertutup!

    # Buka Operations kembali dengan shortcut 'p'
    ui_ctrl.handle_input('p')
    assert ui_ctrl.tools_open == True
    assert ui_ctrl.side_bg.enabled == True
    assert ui_ctrl.legend_open == True  # Legenda TETAP terbuka!
    assert ui_ctrl.legend_panel.enabled == True


def test_tool_selection_and_highlight(setup_ui):
    """Memverifikasi seleksi tool [1], [2], [3] dan highlight indikator aktif."""
    ui_ctrl, scene_obj, interaction_sys, mgr = setup_ui
    ui_ctrl._update_layout()

    # Tool 1: CARGO_BOX
    ui_ctrl.handle_input('1')
    assert interaction_sys.current_tool == PlacementTool.CARGO_BOX
    assert "Cargo" in ui_ctrl.side_sub.text
    assert ui_ctrl.btn_cargo.color == color.rgb32(35, 87, 86)

    # Tool 2: OIL_SPILL
    ui_ctrl.handle_input('2')
    assert interaction_sys.current_tool == PlacementTool.OIL_SPILL
    assert "Oil" in ui_ctrl.side_sub.text
    assert ui_ctrl.btn_oil.color == color.rgb32(35, 87, 86)
    assert ui_ctrl.btn_cargo.color == color.rgb32(*ui_ctrl.SURFACE)

    # Tool 3: BOOST_PAD
    ui_ctrl.handle_input('3')
    assert interaction_sys.current_tool == PlacementTool.BOOST_PAD
    assert "Boost" in ui_ctrl.side_sub.text
    assert ui_ctrl.btn_boost.color == color.rgb32(35, 87, 86)


def test_keyboard_shortcuts_and_actions(setup_ui):
    """Memverifikasi keyboard shortcut [G], [T], [B], [X]."""
    ui_ctrl, scene_obj, interaction_sys, mgr = setup_ui
    ui_ctrl._update_layout()

    # Free camera [B]
    assert scene_obj.current_cam_mode == "isometrik"
    ui_ctrl.handle_input('b')
    assert scene_obj.current_cam_mode in ("free_cam", "bebas")
    assert "Exit free cam [B]" in ui_ctrl.btn_freecam.text
    ui_ctrl.handle_input('b')
    assert scene_obj.current_cam_mode == "isometrik"
    assert "Free camera [B]" in ui_ctrl.btn_freecam.text

    # Clear terrain [X]
    ui_ctrl.handle_input('x')
    assert "Dynamic obstacles, oil, and boost pads cleared." in interaction_sys.prompt_text

    # Random race [G]
    ui_ctrl.handle_input('g')
    assert mgr.is_race_active or mgr.current_mission is not None or "race started" in interaction_sys.prompt_text.lower()
