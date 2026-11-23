"""
test_smart_rerouting.py
=======================
Pengujian Headless Fitur Smart Re-routing Baterai Kritis pada Leg 3:
1. Kondisi Baterai Cukup (> 20%): Robot pulang ke dock asalnya di (17, 1).
2. Kondisi Baterai Kritis (<= 20%): Robot membatalkan pulang ke dock asal,
   mencari docking terdekat di arena via find_nearest_dock,
   mengeksekusi recalculate_route menuju dock darurat,
   dan memunculkan notifikasi UI floating text.
3. Memastikan tidak ada AttributeError saat eksekusi.
"""

from unittest.mock import MagicMock
import pytest
from src.cognition.warehouse_graph import WarehouseGraph100
from src.cognition.pathfinding import find_nearest_dock
from src.behavior.robot_controller import AGVRobot, RobotState
from src.behavior.mission_manager import MissionManager
from src.config import SPAWN_ALPHA, SPAWN_BETA, grid_to_world

pytestmark = pytest.mark.usefixtures("ursina_app")


def test_smart_rerouting_battery_sufficient():
    print("\n=== TEST 1: BATERAI CUKUP (> 20%) -> PULANG KE DOCK ASAL ===")
    graph = WarehouseGraph100.generate_complex_warehouse()
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    
    scene_mock = MagicMock()
    scene_mock.interactive_shelves = {}
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)
    
    # Simulasikan robot Alpha sedang di rak drop-off (misal koordinat (30, 20))
    dropoff_coord = (30, 20)
    r_alpha.position = grid_to_world(dropoff_coord[0], dropoff_coord[1], 0.0)
    r_alpha.state = RobotState.UNLOADING_CARGO
    r_alpha.battery = 65.0  # Baterai cukup (> 20%)
    
    # Jalur lama Leg 3 yang sudah direncanakan menuju spawn_coord (17, 1)
    old_leg3 = [(30, 20), (25, 20), (17, 1)]
    r_alpha.leg3_grid_path = list(old_leg3)
    r_alpha.leg3_waypoints = [grid_to_world(p[0], p[1], 0.0) for p in old_leg3]
    
    # Jalankan _resume_after_action (transisi dari UNLOADING_CARGO ke RETURNING_TO_DOCK)
    r_alpha._resume_after_action()
    
    assert r_alpha.state == RobotState.RETURNING_TO_DOCK
    assert not r_alpha.is_critical_battery
    assert r_alpha.emergency_dock is None
    # Robot harus tetap menggunakan jalur lama menuju spawn_coord
    assert r_alpha.active_grid_path == old_leg3
    print(f"  ✓ Robot state: {r_alpha.state.value}")
    print(f"  ✓ Baterai: {r_alpha.battery}% -> Tetap menuju dock asal: {r_alpha.spawn_coord}")


def test_smart_rerouting_battery_critical():
    print("\n=== TEST 2: BATERAI KRITIS (<= 20%) -> SMART RE-ROUTING KE DOCK TERDEKAT ===")
    graph = WarehouseGraph100.generate_complex_warehouse()
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    
    scene_mock = MagicMock()
    scene_mock.interactive_shelves = {}
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)
    
    # Ambil salah satu charging dock di arena (misal dekat (22, 15) atau (30, 19))
    charging_docks = graph.get_charging_docks()
    assert len(charging_docks) > 2, "Harus ada stasiun pengisian daya arena"
    
    # Posisikan robot Alpha di dekat stasiun pengisian daya arena (misal di (21, 15))
    dropoff_coord = (21, 15)
    r_alpha.position = grid_to_world(dropoff_coord[0], dropoff_coord[1], 0.0)
    r_alpha.state = RobotState.UNLOADING_CARGO
    r_alpha.battery = 15.0  # Baterai kritis (<= 20%)
    
    # Jalur lama Leg 3 yang jauh menuju spawn_coord (17, 1)
    old_leg3 = [(21, 15), (20, 10), (17, 1)]
    r_alpha.leg3_grid_path = list(old_leg3)
    r_alpha.leg3_waypoints = [grid_to_world(p[0], p[1], 0.0) for p in old_leg3]
    
    # Jalankan _resume_after_action (transisi dari UNLOADING_CARGO ke RETURNING_TO_DOCK)
    r_alpha._resume_after_action()
    
    # Verifikasi Smart Re-routing:
    assert r_alpha.state == RobotState.TO_CHARGER
    assert r_alpha._resume_state == RobotState.RETURNING_TO_DOCK
    assert r_alpha.is_critical_battery == True
    assert r_alpha.emergency_dock is not None
    # Dock darurat tidak boleh dock asal (17, 1) karena ada charger yang jauh lebih dekat di (22, 15)
    assert r_alpha.emergency_dock != r_alpha.spawn_coord
    print(f"  ✓ Emergency Dock terpilih: {r_alpha.emergency_dock} (Dock asal: {r_alpha.spawn_coord})")
    
    # Rute aktif robot harus menuju emergency dock
    assert len(r_alpha.active_grid_path) > 0
    assert r_alpha.active_grid_path[-1] == r_alpha.emergency_dock
    print(f"  ✓ Rute aktif di-replan ke: {r_alpha.active_grid_path[-1]}")
    print(f"  ✓ Label tag robot: {r_alpha.label_tag.text}")
    assert "charger" in r_alpha.label_tag.text.lower()


def test_smart_rerouting_for_beta_gbfs():
    print("\n=== TEST 3: SMART RE-ROUTING UNTUK ROBOT BETA (GBFS) ===")
    graph = WarehouseGraph100.generate_complex_warehouse()
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    
    scene_mock = MagicMock()
    scene_mock.interactive_shelves = {}
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)
    
    dropoff_coord = (31, 19)
    r_beta.position = grid_to_world(dropoff_coord[0], dropoff_coord[1], 0.0)
    r_beta.state = RobotState.UNLOADING_CARGO
    r_beta.battery = 18.0  # Baterai kritis (<= 20%)
    
    r_beta._resume_after_action()
    
    assert r_beta.state == RobotState.TO_CHARGER
    assert r_beta._resume_state == RobotState.RETURNING_TO_DOCK
    assert r_beta.is_critical_battery == True
    assert r_beta.emergency_dock is not None
    assert r_beta.emergency_dock != r_beta.spawn_coord
    assert r_beta.active_grid_path[-1] == r_beta.emergency_dock
    print(f"  ✓ AGV Beta (GBFS) Emergency Dock: {r_beta.emergency_dock}")
    print(f"  ✓ Rute aktif Beta berakhir di: {r_beta.active_grid_path[-1]}")


def test_dock_arrival_and_recharge():
    print("\n=== TEST 4: KEDATANGAN DI CHARGER & RECHARGE PENUH ===")
    graph = WarehouseGraph100.generate_complex_warehouse()
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    
    scene_mock = MagicMock()
    scene_mock.interactive_shelves = {}
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)
    
    # Tahap A: Tiba di charging station interior (22, 15) -> isi daya -> lanjut Leg 3 ke dock asal
    r_alpha.position = grid_to_world(22, 15, 0.0)
    r_alpha.state = RobotState.TO_CHARGER
    r_alpha._resume_state = RobotState.RETURNING_TO_DOCK
    r_alpha.battery = 10.0
    r_alpha.is_critical_battery = True
    r_alpha.emergency_dock = (22, 15)
    
    r_alpha._start_charging()
    assert r_alpha.state == RobotState.CHARGING
    r_alpha.recharge_full()
    r_alpha._finish_charging()
    assert r_alpha.state == RobotState.RETURNING_TO_DOCK
    assert r_alpha.battery == 100.0
    assert not r_alpha.is_critical_battery
    assert r_alpha.emergency_dock is None
    assert r_alpha.active_grid_path[-1] == SPAWN_ALPHA

    # Tahap B: Tiba di dock asal (17, 1) -> selesai misi (FINISHED), sisa baterai dipertahankan sampai recharge manual
    r_alpha.position = grid_to_world(SPAWN_ALPHA[0], SPAWN_ALPHA[1], 0.0)
    r_alpha.battery = 85.0
    r_alpha._handle_leg_completion()
    
    assert r_alpha.state == RobotState.FINISHED
    assert r_alpha.battery == 85.0
    assert "85%" in r_alpha.label_tag.text
    assert not r_alpha.is_critical_battery
    assert r_alpha.emergency_dock is None
    assert r_alpha.force_return_to_dock(graph, mgr.current_heuristic_fn)
    assert r_alpha.battery == 100.0
    print(f"  ✓ Selesai docking: State = {r_alpha.state.value}, Baterai setelah recharge = {r_alpha.battery}%")
