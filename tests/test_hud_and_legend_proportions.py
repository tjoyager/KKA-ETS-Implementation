"""Unit and regression tests for HUD Telemetry and Warehouse Legend layout and proportions."""

import pytest
from ursina import Vec3, window
from src.behavior.mission_manager import MissionManager
from src.behavior.robot_controller import AGVRobot
from src.cognition.warehouse_graph import WarehouseGraph100
from src.communication.hud_gamification import GamificationHUD
from src.communication.hud_serious import SeriousHUD
from src.communication.interaction_system import InteractionSystem
from src.communication.ui_controller import UIController
from src.communication.warehouse_legend import WarehouseLegend
from src.environment.warehouse_scene import WarehouseScene
from src.config import SPAWN_ALPHA, SPAWN_BETA

pytestmark = pytest.mark.usefixtures("ursina_app")


@pytest.fixture
def setup_ui_controller():
    graph = WarehouseGraph100.generate_complex_warehouse()
    scene = WarehouseScene(graph=graph)
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    mgr = MissionManager(graph, scene, r_alpha, r_beta)
    isys = InteractionSystem(mgr, scene)
    ui = UIController(mgr, isys, scene)
    ui._last_aspect_ratio = -1.0
    ui._update_layout()
    return ui, mgr


def test_serious_hud_proportions_and_container(setup_ui_controller):
    """Verifies that SeriousHUD root container has scale 1:1 and metrics columns are spaced."""
    ui, _ = setup_ui_controller
    hud = ui.hud_serious

    # 1. Root container must have scale 1:1
    assert hud.container.scale == Vec3(1, 1, 1), "SeriousHUD container scale must be 1:1"

    # 2. Text and icons must be children of container, not children of bg
    assert hud.title.parent == hud.container
    assert hud.eyebrow.parent == hud.container
    assert hud.header_metric.parent == hud.container
    assert hud.bg.parent == hud.container

    # 3. Background quad must be behind text in z
    assert hud.bg.z > hud.title.z, "bg must be positioned behind text in z"

    # 4. Metric columns distance: Alpha to Beta
    col_dist = hud.header_b.x - hud.header_a.x
    assert col_dist >= 0.07, f"Alpha to Beta distance ({col_dist:.3f}) must be >= 0.07"

    # 5. Panel bounds
    assert hud.panel_w <= 0.35, f"Panel width ({hud.panel_w}) should leave space for arena"
    assert hud.panel_h <= 0.40, f"Panel height ({hud.panel_h}) should leave space for legend"


def test_gamification_hud_proportions_and_container(setup_ui_controller):
    """Verifies that GamificationHUD root container has scale 1:1 and matching bounds."""
    ui, _ = setup_ui_controller
    hud = ui.hud_gamification

    # 1. Root container must have scale 1:1
    assert hud.container.scale == Vec3(1, 1, 1), "GamificationHUD container scale must be 1:1"

    # 2. Text and cards must be children of container
    assert hud.title.parent == hud.container
    assert hud.bg.parent == hud.container
    assert hud.bg.z > hud.title.z

    # 3. Bounds match SeriousHUD for seamless mode toggle
    assert abs(hud.panel_w - ui.hud_serious.panel_w) < 0.01
    assert abs(hud.panel_h - ui.hud_serious.panel_h) < 0.01


def test_warehouse_legend_proportions_and_layout(setup_ui_controller):
    """Verifies that WarehouseLegend has scale 1:1, natural icon aspects, and clean layout."""
    ui, _ = setup_ui_controller
    legend = ui.legend

    # 1. Root container must have scale 1:1
    assert legend.container.scale == Vec3(1, 1, 1), "WarehouseLegend container scale must be 1:1"
    assert legend.bg.parent == legend.container
    assert legend.bg.z > legend.title.z, "bg must be positioned behind text in z"

    # 2. 12 Legend rows + 4 section titles + 3 swatches exist
    assert len(legend.item_entities) == 12
    assert legend.sec1_title.text == "Kendaraan"
    assert legend.sec2_title.text == "Medan & rintangan"
    assert legend.sec3_title.text == "Lokasi"
    assert legend.sec4_title.text == "Petak yang dieksplorasi"

    # 3. Icon scales maintain natural aspect ratios
    for icon_ent, _, _, name in legend.item_entities:
        expected_aspect = legend.ICON_ASPECTS[name]
        actual_aspect = icon_ent.scale_x / icon_ent.scale_y
        assert abs(actual_aspect - expected_aspect) < 0.05, (
            f"Icon {name} aspect ratio distorted: expected {expected_aspect}, got {actual_aspect}"
        )

    # 4. No vertical collision with Telemetry panel
    tel_bottom = ui.hud_serious.container.y - ui.hud_serious.panel_h
    legend_top = legend.container.y
    legend_bottom = legend.container.y - legend.panel_h

    assert tel_bottom > legend_top, (
        f"Vertical collision: Telemetry bottom ({tel_bottom:.3f}) <= Legend top ({legend_top:.3f})"
    )
    assert tel_bottom - legend_top >= 0.010, "Gap between Telemetry and Legend should be >= 0.01"

    # 5. Legend stays within screen bottom
    assert legend_bottom > -0.485, f"Legend bottom ({legend_bottom:.3f}) must be above screen bottom"


def test_legend_toggle_and_mode_switching(setup_ui_controller):
    """Verifies [L] toggle button and [M] mode switching."""
    ui, _ = setup_ui_controller

    # Initial state
    assert ui.legend_open is True
    assert ui.legend.container.enabled is True
    assert "Tutup [L]" in ui.btn_legend.text

    # Toggle legend OFF with [L]
    ui.handle_input("l")
    assert ui.legend_open is False
    assert ui.legend.container.enabled is False
    assert "Legenda [L]" in ui.btn_legend.text

    # Toggle legend ON with [L]
    ui.handle_input("l")
    assert ui.legend_open is True
    assert ui.legend.container.enabled is True
    assert "Tutup [L]" in ui.btn_legend.text

    # Mode switch [M]: Serious -> Gamification
    assert ui.is_serious_mode is True
    assert ui.hud_serious.container.enabled is True
    assert ui.hud_gamification.container.enabled is False

    ui.handle_input("m")
    assert ui.is_serious_mode is False
    assert ui.hud_serious.container.enabled is False
    assert ui.hud_gamification.container.enabled is True
    assert ui.legend.container.enabled is True  # Legend remains open

    # Switch back to Serious mode
    ui.handle_input("m")
    assert ui.is_serious_mode is True
    assert ui.hud_serious.container.enabled is True
    assert ui.hud_gamification.container.enabled is False
    assert ui.legend.container.enabled is True
