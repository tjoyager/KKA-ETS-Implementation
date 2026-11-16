"""
test_full_suite.py
==================
Pengujian Komprehensif Seluruh Fitur Overhaul (Tahap 1, Tahap 2, Tahap 3).
"""

from unittest.mock import MagicMock
from src.cognition.warehouse_graph import WarehouseGraph100, CellType
from src.behavior.robot_controller import AGVRobot, RobotState
from src.behavior.mission_manager import MissionManager, MissionType
from src.config import SPAWN_ALPHA, SPAWN_BETA

import pytest

pytestmark = pytest.mark.usefixtures("ursina_app")


def run_full_suite():
    print("==================================================")
    print("MEMULAI PENGUJIAN KOMPREHENSIF FULL OVERHAUL")
    print("==================================================")
    
    # 1. SETUP GRAPH & ROBOT
    graph = WarehouseGraph100.generate_complex_warehouse()
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    scene_mock = MagicMock()
    scene_mock.interactive_shelves = {}
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)
    
    # --- PENGUJIAN FITUR 1: SISTEM BATERAI ---
    print("\n[UJI 1] Sistem Manajemen Baterai:")
    assert r_alpha.battery == 100.0
    r_alpha.state = RobotState.MOVING_TO_PICKUP
    for _ in range(40):
        r_alpha.consume_battery(0.5)
    assert r_alpha.battery == 80.0
    print(f"  ✓ Baterai terkuras normal: {r_alpha.battery}%")
    
    # Uji baterai kritis dan dead
    for _ in range(120):
        r_alpha.consume_battery(0.5)
    assert r_alpha.battery == 20.0
    print(f"  ✓ Baterai mencapai batas kritis: {r_alpha.battery}%")
    
    for _ in range(40):
        r_alpha.consume_battery(0.5)
    assert r_alpha.battery == 0.0
    assert r_alpha.state == RobotState.DEAD
    print(f"  ✓ Robot mati saat baterai habis: State = {r_alpha.state.value}")
    
    # Uji intervensi user Force Return to Dock & Recharge
    r_alpha.recharge_full()
    assert r_alpha.battery == 100.0
    assert r_alpha.visual_body.color == r_alpha.primary_col
    print(f"  ✓ Intervensi User Force Return to Dock berhasil merestorasi baterai ke {r_alpha.battery}%")

    # --- PENGUJIAN FITUR 2: TRANSFER ZONA MULTI-STAGE ---
    print("\n[UJI 2] Multi-Stage Zone Transfer:")
    assert mgr.current_zone == "Zone A"
    zone_b_graph = WarehouseGraph100.generate_zone_b_warehouse()
    assert len(zone_b_graph.shelves) > 0
    print(f"  ✓ Generator Zone B berhasil dengan {len(zone_b_graph.shelves)} rak palet")

    # --- PENGUJIAN FITUR 3: FORKLIFT DYNAMIC OBSTACLE ---
    print("\n[UJI 3] Forklift Controller & Sub-millisecond Graph Update:")
    f_coord = (17, 11)
    graph.update_forklift_cell(None, f_coord)
    assert not graph.is_walkable(f_coord[0], f_coord[1])
    assert graph.grid[f_coord[1], f_coord[0]] == CellType.FORKLIFT
    print(f"  ✓ Sel ({f_coord[0]}, {f_coord[1]}) ditandai sebagai CellType.FORKLIFT")
    
    # Pindahkan ke sel sebelah
    f_next = (16, 11)
    graph.update_forklift_cell(f_coord, f_next)
    assert graph.is_walkable(f_coord[0], f_coord[1])
    assert not graph.is_walkable(f_next[0], f_next[1])
    print(f"  ✓ Sel lama ({f_coord[0]}, {f_coord[1]}) dilepas kembali walkable, sel baru ({f_next[0]}, {f_next[1]}) diblokir")

    # --- PENGUJIAN FITUR 4: DYNAMIC REPLANNING TRIGGER ---
    print("\n[UJI 4] Dynamic Collision Avoidance & Replanning:")
    shelves = list(graph.shelves.values())
    s_pickup = MagicMock(); s_pickup.shelf_data = shelves[0]
    s_dropoff = MagicMock(); s_dropoff.shelf_data = shelves[1]
    
    mgr.dispatch_race(s_pickup, s_dropoff)
    assert mgr.is_race_active
    
    # Ambil titik tengah jalur Alpha
    blocked_node = r_alpha.active_grid_path[len(r_alpha.active_grid_path) // 2]
    forklift_mock = MagicMock()
    forklift_mock.get_threatened_coords.return_value = {blocked_node}
    mgr.set_forklift(forklift_mock)
    graph.update_forklift_cell(None, blocked_node)
    
    old_replan = r_alpha.replan_count
    mgr._check_forklift_collision_threats()
    assert r_alpha.replan_count > old_replan
    assert blocked_node not in r_alpha.active_grid_path[r_alpha.waypoint_idx:]
    print(f"  ✓ Replanning A* berhasil menghindari ancaman Forklift di {blocked_node}!")

    # --- PENGUJIAN FITUR 5: ORDER TASK QUEUE (FIFO) ---
    print("\n[UJI 5] Order Task Queue & Auto-Dispatch:")
    s_a = MagicMock(); s_a.shelf_data = shelves[2]
    s_b = MagicMock(); s_b.shelf_data = shelves[3]
    s_c = MagicMock(); s_c.shelf_data = shelves[4]
    s_d = MagicMock(); s_d.shelf_data = shelves[5]
    
    id1 = mgr.enqueue_order(s_a, s_b)
    id2 = mgr.enqueue_order(s_c, s_d)
    assert len(mgr.task_queue) == 2
    print(f"  ✓ Task queue menampung {len(mgr.task_queue)} pesanan secara FIFO")
    
    # Selesaikan balapan aktif
    r_alpha.state = RobotState.FINISHED
    r_beta.state = RobotState.FINISHED
    mgr.race_finished = True
    
    mgr.update()
    assert len(mgr.task_queue) == 1
    assert mgr.selected_pickup_shelf == s_a
    print("  ✓ Pesanan #1 berhasil di-pop dan di-dispatch secara otomatis")
    
    r_alpha.state = RobotState.FINISHED
    r_beta.state = RobotState.FINISHED
    mgr.race_finished = True
    
    mgr.update()
    assert len(mgr.task_queue) == 0
    assert mgr.selected_pickup_shelf == s_c
    print("  ✓ Pesanan #2 berhasil di-pop dan di-dispatch secara otomatis")

    # --- PENGUJIAN FITUR 6: HEATMAP EKSPLORASI NODE (TAHAP 4) ---
    print("\n[UJI 6] Visualisasi Heatmap Komputasi (Node Exploration):")
    plan = mgr.dual_plan
    assert plan is not None
    assert len(plan.alpha_visited_nodes) > 0
    assert len(plan.beta_visited_nodes) > 0
    print(f"  ✓ DualPlan visited nodes: A*={len(plan.alpha_visited_nodes)}, GBFS={len(plan.beta_visited_nodes)}")

    # --- PENGUJIAN FITUR 7: MODE KAMERA BEBAS & TOGGLE FORKLIFT (TAHAP 4) ---
    print("\n[UJI 7] Mode Kamera Bebas (Free-Cam / God Mode):")
    from src.behavior.forklift_controller import ForkliftController
    fl = ForkliftController(graph=graph, start_coord=(17, 11))
    assert fl.enabled_control == True
    fl.set_control_enabled(False)
    assert fl.enabled_control == False
    fl.set_control_enabled(True)
    assert fl.enabled_control == True
    fl.on_destroy()
    print("  ✓ Proteksi kendali input Forklift saat Free-Cam aktif berjalan sempurna!")

    # --- PENGUJIAN FITUR 8: WEIGHTED TERRAIN AI & FITUR TAHAP 5 ---
    print("\n[UJI 8] Weighted Terrain AI: Oil Spill vs Speed Boost Pad (Tahap 5):")
    from src.cognition.pathfinding import a_star_search, greedy_best_first_search
    from src.communication.interaction_system import PlacementTool

    test_g = WarehouseGraph100(10, 10)
    # 1. Uji Registrasi Terrain Modifier
    oil_coord = (3, 2)
    test_g.add_hazard_oil(oil_coord[0], oil_coord[1])
    assert test_g.grid[oil_coord[1], oil_coord[0]] == CellType.HAZARD_OIL
    assert test_g.is_walkable(oil_coord[0], oil_coord[1])
    assert test_g.terrain_weights[oil_coord] == 5.0
    assert test_g.get_movement_cost((2, 2), oil_coord) == 5.0
    print(f"  ✓ Registrasi Hazard Oil di {oil_coord}: Walkable, Cost = 5.0")

    # 2. Uji Trade-Off Teoretis A* vs GBFS:
    # A* mengevaluasi f(n) = g(n) + h(n) sehingga memutar menghindari oli (Cost = 6.0).
    # GBFS mengevaluasi f(n) = h(n) sehingga buta terhadap g(n) dan menerobos oli (Cost = 8.0)!
    res_a = a_star_search(test_g, (1, 2), (5, 2))
    res_b = greedy_best_first_search(test_g, (1, 2), (5, 2))
    assert oil_coord not in res_a.path
    assert oil_coord in res_b.path
    assert res_a.cost < res_b.cost
    print(f"  ✓ Trade-Off AI Terbukti: A* memutar (Cost {res_a.cost}), GBFS menerobos oli (Cost {res_b.cost})")

    # 3. Uji Boost Pad
    boost_coord = (3, 2)
    test_g.remove_terrain_modifier(oil_coord[0], oil_coord[1])
    test_g.add_boost_pad(boost_coord[0], boost_coord[1])
    assert test_g.grid[boost_coord[1], boost_coord[0]] == CellType.BOOST_PAD
    assert test_g.terrain_weights[boost_coord] == 0.35
    assert test_g.get_movement_cost((2, 2), boost_coord) == 0.35
    res_boost = a_star_search(test_g, (1, 2), (5, 2))
    assert boost_coord in res_boost.path
    assert res_boost.cost < 4.0
    print(f"  ✓ Speed Boost Pad: A* memprioritaskan pad cepat (Cost {res_boost.cost})")

    # 4. Uji Multi-Tool Enum
    assert PlacementTool.CARGO_BOX == 1
    assert PlacementTool.OIL_SPILL == 2
    assert PlacementTool.BOOST_PAD == 3
    print("  ✓ Multi-Tool Placement [1], [2], [3] tervalidasi")

    # 5. Uji Visual FX & Kamera POV
    r_alpha.trigger_radar_pulse()
    r_alpha.spawn_floating_text("+TEST FX+")
    print("  ✓ Visual FX Radar Pulse & 3D Floating Popup terpicu sukses")

    # --- PENGUJIAN FITUR 9: AUTO-RETURN TO BASE (MISI LEG 3) ---
    print("\n[UJI 9] Auto-Return to Base (Misi Leg 3 - Unified Twin Dock):")
    # Dispatch misi baru untuk menguji 3-leg cycle
    s_p = MagicMock(); s_p.shelf_data = shelves[6]
    s_d = MagicMock(); s_d.shelf_data = shelves[7]
    mgr.dispatch_race(s_p, s_d)
    
    assert mgr.dual_plan is not None
    assert mgr.dual_plan.alpha_plan.leg3 is not None, "Leg 3 Alpha (Return to Dock) harus terencana"
    assert mgr.dual_plan.beta_plan.leg3 is not None, "Leg 3 Beta (Return to Dock) harus terencana"
    assert mgr.dual_plan.alpha_plan.leg3.path[-1] == SPAWN_ALPHA, f"Leg 3 Alpha harus berakhir di {SPAWN_ALPHA}"
    assert mgr.dual_plan.beta_plan.leg3.path[-1] == SPAWN_BETA, f"Leg 3 Beta harus berakhir di {SPAWN_BETA}"
    print(f"  ✓ Leg 3 Terencana Sempurna: Alpha -> {SPAWN_ALPHA}, Beta -> {SPAWN_BETA}")
    
    # Simulasikan robot menyelesaikan Leg 1 (Pickup)
    r_alpha.state = RobotState.LOADING_CARGO
    r_alpha._resume_after_action()
    assert r_alpha.state == RobotState.MOVING_TO_DROPOFF
    assert r_alpha.deck_cargo.enabled == True
    
    # Simulasikan robot menyelesaikan Leg 2 (Dropoff)
    r_alpha.state = RobotState.UNLOADING_CARGO
    # Di Tahap Akhir Overhaul, setelah unloading, robot TIDAK boleh FINISHED!
    r_alpha._resume_after_action()
    assert r_alpha.state == RobotState.RETURNING_TO_DOCK, f"State robot harus RETURNING_TO_DOCK, got {r_alpha.state}"
    assert r_alpha.deck_cargo.enabled == False
    assert len(r_alpha.active_grid_path) > 0
    assert r_alpha.active_grid_path[-1] == SPAWN_ALPHA
    print(f"  ✓ Leg 2 Selesai -> Transisi Otomatis ke RETURNING_TO_DOCK (Menuju Dock {SPAWN_ALPHA})")
    
    # Simulasikan robot tiba di Dock asalnya (Leg 3 selesai)
    r_alpha.waypoint_idx = len(r_alpha.active_waypoints)
    r_alpha._handle_leg_completion()
    assert r_alpha.state == RobotState.FINISHED, "Robot harus FINISHED setelah menyentuh Dock asalnya"
    assert r_alpha.finish_time is not None
    assert r_alpha.battery == 100.0, "Baterai otomatis terisi penuh (recharge) di docking station"
    print("  ✓ Leg 3 Selesai -> Robot FINISHED, docked & fully recharged!")

    # --- PENGUJIAN FITUR 10: UNIFIED TWIN DOCK & MULTI-FORKLIFT (3 UNITS) ---
    print("\n[UJI 10] Unified Twin Docking Station & Multi-Forklift (3 Unit):")
    assert SPAWN_ALPHA == (17, 1), f"SPAWN_ALPHA harus (17, 1), got {SPAWN_ALPHA}"
    assert SPAWN_BETA == (18, 1), f"SPAWN_BETA harus (18, 1), got {SPAWN_BETA}"
    assert graph.grid[1, 17] == CellType.DOCK
    assert graph.grid[1, 18] == CellType.DOCK
    print(f"  ✓ Unified Twin Dock terkonfirmasi di grid {SPAWN_ALPHA} & {SPAWN_BETA}")

    # Inisialisasi 3 Forklift dengan kontrol independen
    fl_center = ForkliftController(graph=graph, start_coord=(17, 11), control_scheme="wasd", name="Forklift Tengah")
    fl_left = ForkliftController(graph=graph, start_coord=(5, 7), control_scheme="arrows", name="Forklift Kiri")
    fl_top = ForkliftController(graph=graph, start_coord=(23, 20), control_scheme="ijkl", name="Forklift Atas")
    
    assert fl_center.control_scheme == "wasd"
    assert fl_left.control_scheme == "arrows"
    assert fl_top.control_scheme == "ijkl"
    
    # Registrasi ke MissionManager
    mgr.set_forklifts([fl_center, fl_left, fl_top])
    assert len(mgr.forklifts) == 3
    print("  ✓ 3 Forklift (WASD, Arrows, IJKL) berhasil diinstansiasi dan didaftarkan ke MissionManager")

    # Uji pergerakan multiset cell di graph
    assert not graph.is_walkable(5, 7)
    assert not graph.is_walkable(23, 20)
    
    # Forklift kiri bergerak dari (5, 7) ke (5, 8)
    graph.update_forklift_cell((5, 7), (5, 8), forklift_id=id(fl_left))
    assert graph.is_walkable(5, 7), "Sel lama (5, 7) harus kembali walkable"
    assert not graph.is_walkable(5, 8), "Sel baru (5, 8) harus non-walkable"
    assert not graph.is_walkable(23, 20), "Sel forklift lain (23, 20) tetap aman terisolasi"
    print("  ✓ Multiset grid tracking untuk 3 Forklift berjalan independen tanpa bentrok")

    # --- PENGUJIAN AI PATROL (AUTONOMOUS MOVING OBSTACLES) ---
    assert fl_center.is_moving == False
    assert fl_center.move_speed == 1.5
    assert fl_center.current_coord == (17, 11)
    
    old_c = fl_center.current_coord
    chosen_c = fl_center.think_next_move()
    assert chosen_c is not None
    assert fl_center.is_moving == True
    assert fl_center.current_coord == chosen_c
    assert not graph.is_walkable(chosen_c[0], chosen_c[1]), "Sel tujuan AI harus diblokir di graf"
    assert graph.is_walkable(old_c[0], old_c[1]), "Sel lama harus langsung dibebaskan"
    assert chosen_c in fl_center.get_threatened_coords()
    print(f"  ✓ Autonomous Patrol: think_next_move({old_c}) -> {chosen_c}, graf terblokir & is_moving aktif")

    # Uji 25 langkah wandering acak bebas tabrakan
    fl_center.is_moving = False
    for step_i in range(25):
        cur = fl_center.current_coord
        nxt = fl_center.think_next_move()
        assert nxt is not None, f"Langkah {step_i}: AI Forklift harus selalu menemukan petak valid"
        assert graph.grid[nxt[1], nxt[0]] == CellType.FORKLIFT
        assert not graph.is_walkable(nxt[0], nxt[1])
        fl_center.is_moving = False  # Simulasikan gerakan selesai
    print(f"  ✓ 25 langkah AI Random Wandering berhasil tanpa collision rak/dinding (Posisi akhir: {fl_center.current_coord})")

    print("\n" + "=" * 50)
    print("SELURUH TEST SUITE OVERHAUL (TAHAP 1-5 + TAHAP AKHIR) LOLOS 100%!")
    print("==================================================")


def test_full_suite():
    run_full_suite()


if __name__ == "__main__":
    run_full_suite()
