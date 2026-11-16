"""
test_phase3_integration.py
===========================
Pengujian Headless Integrasi Fitur Tahap 3:
1. ForkliftController & Real-time Graph Update (Sub-millisecond update).
2. Dynamic Collision Avoidance & Replanning Trigger (A* & GBFS).
3. Order Task Queue (FIFO Auto-Dispatch saat robot idle).
"""

import time
from unittest.mock import MagicMock
from src.cognition.warehouse_graph import WarehouseGraph100, CellType
from src.cognition.heuristics import manhattan_distance
from src.behavior.robot_controller import AGVRobot, RobotState
from src.behavior.mission_manager import MissionManager, DeliveryOrder
from src.behavior.forklift_controller import ForkliftController
from src.config import SPAWN_ALPHA, SPAWN_BETA
from statistics import median

import pytest


pytestmark = pytest.mark.usefixtures("ursina_app")

def test_forklift_and_graph_integration():
    print("=== TEST 1: FORKLIFT & GRAPH INTEGRATION ===")
    graph = WarehouseGraph100.generate_complex_warehouse()
    
    # Koordinat awal
    start_c = (17, 11)
    assert graph.is_walkable(start_c[0], start_c[1]), f"Sel {start_c} harus walkable di awal"
    
    # Mocking Ursina Entity untuk Forklift di lingkungan headless
    t0 = time.perf_counter()
    graph.update_forklift_cell(None, start_c)
    dt1 = (time.perf_counter() - t0) * 1000.0
    print(f"-> Graph update sel forklift awal: {dt1:.4f} ms")
    
    assert not graph.is_walkable(start_c[0], start_c[1]), "Sel forklift harus non-walkable"
    assert graph.grid[start_c[1], start_c[0]] == CellType.FORKLIFT
    
    # Pindahkan forklift ke sel baru
    next_c = (16, 11)
    t0 = time.perf_counter()
    graph.update_forklift_cell(start_c, next_c)
    dt2 = (time.perf_counter() - t0) * 1000.0
    print(f"-> Perpindahan forklift (17,11) -> (16,11): {dt2:.4f} ms")
    
    assert graph.is_walkable(start_c[0], start_c[1]), "Sel lama (17, 12) harus kembali walkable"
    assert not graph.is_walkable(next_c[0], next_c[1]), "Sel baru (17, 13) harus non-walkable"
    samples = []

    for _ in range(50):
        graph.update_forklift_cell(next_c, start_c)

        t0 = time.perf_counter()
        graph.update_forklift_cell(start_c, next_c)

        samples.append((time.perf_counter() - t0) * 1000)

    median_ms = median(samples)
    print(f"Median forklift update: {median_ms:.4f} ms")

    assert median_ms < 0.5, (
        f"Median update {median_ms:.4f} ms melebihi 0.5 ms"
)
    print("✓ TEST 1 PASSED: Integrasi Forklift & Graf ultra-cepat dan presisi!\n")


def test_forklift_collision_threat_and_replanning():
    print("=== TEST 2: DYNAMIC REPLANNING TRIGGER OLEH FORKLIFT ===")
    graph = WarehouseGraph100.generate_complex_warehouse()
    
    # Ambil 2 rak untuk rute uji coba
    shelves = list(graph.shelves.values())
    pickup_shelf_data = [s for s in shelves if s.has_cargo][0]
    dropoff_shelf_data = [s for s in shelves if not s.has_cargo][0]
    
    pickup_mock = MagicMock()
    pickup_mock.shelf_data = pickup_shelf_data
    dropoff_mock = MagicMock()
    dropoff_mock.shelf_data = dropoff_shelf_data
    
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    
    scene_mock = MagicMock()
    scene_mock.interactive_shelves = {}
    
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)
    
    # Dispatch balapan awal
    success = mgr.dispatch_race(pickup_mock, dropoff_mock)
    assert success, "Dispatch balapan harus berhasil"
    assert mgr.is_race_active, "Balapan harus aktif"
    
    # Ambil jalur aktif Alpha
    alpha_path = list(r_alpha.active_grid_path)
    assert len(alpha_path) > 3, "Jalur Alpha harus memiliki beberapa titik"
    
    target_block = alpha_path[len(alpha_path) // 2]
    print(f"-> Menempatkan Forklift mengancam jalur Alpha di sel: {target_block}")
    
    # Buat forklift mock yang mengancam sel target_block
    forklift_mock = MagicMock()
    forklift_mock.get_threatened_coords.return_value = {target_block}
    mgr.set_forklift(forklift_mock)
    
    # Update sel graf agar sel target_block benar-benar diblokir oleh Forklift
    graph.update_forklift_cell(None, target_block)
    
    # Jalankan pengecekan ancaman di manager
    old_replan_count = r_alpha.replan_count
    mgr._check_forklift_collision_threats()
    
    print(f"-> Alpha replan count sebelum: {old_replan_count}, sesudah: {r_alpha.replan_count}")
    assert r_alpha.replan_count > old_replan_count, "Alpha harus berhasil menghitung ulang rute saat jalurnya terancam Forklift!"
    
    # Pastikan rute baru Alpha tidak melewati sel target_block yang diblokir
    new_remaining_path = r_alpha.active_grid_path[r_alpha.waypoint_idx:]
    assert target_block not in new_remaining_path, "Rute baru Alpha tidak boleh melewati sel yang diblokir Forklift!"
    print("✓ TEST 2 PASSED: Dynamic Replanning A* aktif dan berhasil menghindari Forklift!\n")


def test_order_task_queue_and_auto_dispatch():
    print("=== TEST 3: ORDER TASK QUEUE (FIFO) & AUTO-DISPATCH ===")
    graph = WarehouseGraph100.generate_complex_warehouse()
    
    shelves = list(graph.shelves.values())
    s1 = MagicMock(); s1.shelf_data = shelves[0]
    s2 = MagicMock(); s2.shelf_data = shelves[1]
    s3 = MagicMock(); s3.shelf_data = shelves[2]
    s4 = MagicMock(); s4.shelf_data = shelves[3]
    s5 = MagicMock(); s5.shelf_data = shelves[4]
    s6 = MagicMock(); s6.shelf_data = shelves[5]
    
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    scene_mock = MagicMock()
    
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)
    
    # 1. Jalankan misi awal (Balapan Aktif)
    mgr.dispatch_race(s1, s2)
    assert mgr.is_race_active
    assert len(mgr.task_queue) == 0
    
    # 2. Tambahkan 2 pesanan ke antrean saat robot sedang sibuk
    id1 = mgr.enqueue_order(s3, s4)
    id2 = mgr.enqueue_order(s5, s6)
    assert id1 == 1
    assert id2 == 2
    assert len(mgr.task_queue) == 2, "Task queue harus berisi 2 pesanan"
    print(f"-> Berhasil memasukkan Pesanan #{id1} dan #{id2} ke dalam antrean (Total: {len(mgr.task_queue)})")
    
    # 3. Simulasikan robot menyelesaikan misi pertama
    r_alpha.state = RobotState.FINISHED
    r_beta.state = RobotState.FINISHED
    mgr.race_finished = True
    
    # 4. Panggil update manager: harus otomatis auto-dispatch pesanan pertama (FIFO: Pesanan #1)
    mgr.update()
    
    assert len(mgr.task_queue) == 1, "Pesanan #1 harus di-pop, tersisa 1 pesanan di queue"
    assert mgr.selected_pickup_shelf == s3, "Misi baru harus memproses pickup s3"
    assert mgr.selected_dropoff_shelf == s4, "Misi baru harus memproses dropoff s4"
    assert mgr.is_race_active, "Balapan untuk pesanan #1 harus langsung aktif"
    print(f"-> Auto-dispatch Pesanan #{id1} berhasil! Sisa antrean: {len(mgr.task_queue)}")
    
    # 5. Simulasikan robot menyelesaikan misi kedua
    r_alpha.state = RobotState.FINISHED
    r_beta.state = RobotState.FINISHED
    mgr.race_finished = True
    
    # 6. Panggil update manager lagi: harus auto-dispatch pesanan terakhir (Pesanan #2)
    mgr.update()
    assert len(mgr.task_queue) == 0, "Semua pesanan di antrean harus sudah habis"
    assert mgr.selected_pickup_shelf == s5
    assert mgr.selected_dropoff_shelf == s6
    print(f"-> Auto-dispatch Pesanan #{id2} berhasil! Sisa antrean: {len(mgr.task_queue)}")
    
    print("✓ TEST 3 PASSED: Sistem Antrean FIFO & Auto-dispatch berjalan 100% sempurna!\n")


if __name__ == "__main__":
    test_forklift_and_graph_integration()
    test_forklift_collision_threat_and_replanning()
    test_order_task_queue_and_auto_dispatch()
    print("==================================================")
    print("SEMUA PENGUJIAN INTEGRASI TAHAP 3 LOLOS 100% (NO REGRESSION)!")
    print("==================================================")
