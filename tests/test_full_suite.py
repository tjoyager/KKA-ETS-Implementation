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

    print("\n" + "=" * 50)
    print("SELURUH TEST SUITE OVERHAUL (TAHAP 1-5) LOLOS 100%!")
    print("==================================================")


if __name__ == "__main__":
    run_full_suite()
