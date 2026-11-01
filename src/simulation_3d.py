"""
simulation_3d.py
================
Visualisasi 3D simulasi robot gudang (Warehouse AGV) berbasis Ursina Engine.

Fitur Unggulan:
- Multi-Algorithm Live Switch: Beralih rute A* Search dan Greedy Best-First Search (GBFS)
  secara langsung di dalam jendela 3D tanpa perlu me-restart program.
- Kontrol Interaktif Ganda: Tombol UI di layar (klik mouse) dan Shortcut Keyboard.
- Model 3D Realistis: Denah rak gudang bertingkat, lantai grid, platform docking Start,
  target kargo Goal, dan robot AGV lengkap dengan LIDAR & lampu LED.
- Manajemen Kamera: Isometrik, Tampak Atas (Top-Down), dan Kamera Bebas Orbit (Klik Kanan drag).
- HUD Interaktif: Menampilkan metrik perbandingan kinerja (biaya rute, simpul dieksplorasi,
  kecepatan, dan progres langkah) secara real-time.
"""

import math
from typing import Dict, List, Optional, Tuple, Union

from src.algorithms import SearchResult

Coord = Tuple[int, int]


def run_3d_simulation(
    grid_map,
    results_or_path: Union[Dict[str, SearchResult], List[Coord]],
    active_algo: str = "A* Search",
    auto_start: bool = True,
):
    """
    Meluncurkan visualisasi 3D interaktif menggunakan Ursina Engine.
    
    Args:
        grid_map: Objek WarehouseGrid.
        results_or_path: Dictionary berisi SearchResult (misal: {"A* Search": res_a, "Greedy Best-First Search": res_g})
                         atau List koordinat rute untuk mode backward-compatibility.
        active_algo: Nama algoritma awal yang ingin ditampilkan.
        auto_start: Apakah robot langsung bergerak otomatis saat dibuka.
    """
    try:
        from ursina import (
            Ursina,
            Entity,
            Vec3,
            color,
            camera,
            window,
            Text,
            Button,
            EditorCamera,
            destroy,
            time,
            application,
        )
        from ursina.models.procedural.cylinder import Cylinder
    except ImportError:
        print("\n" + "=" * 65)
        print("[PERINGATAN] Pustaka 'ursina' belum terinstal di lingkungan Python ini.")
        print("Silakan ikuti langkah berikut untuk menginstalnya:")
        print("  1. Aktifkan virtual environment (jika menggunakan venv):")
        print("     - Linux/Ubuntu : source venv/bin/activate")
        print("     - Windows      : .\\venv\\Scripts\\activate")
        print("  2. Jalankan instalasi dependensi:")
        print("     pip install -r requirements.txt")
        print("=" * 65 + "\n")
        return

    # Normalisasi data input agar mendukung dictionary multi-algoritma
    results_dict: Dict[str, SearchResult] = {}
    if isinstance(results_or_path, dict):
        results_dict = results_or_path
    else:
        # Jika hanya list path yang dipassing
        dummy_res = SearchResult(
            algorithm_name=active_algo,
            success=True,
            path=results_or_path,
            cost=float(len(results_or_path) - 1) if results_or_path else 0.0,
            nodes_explored=len(results_or_path),
            execution_time_ms=0.0,
        )
        results_dict[active_algo] = dummy_res

    # Pastikan active_algo ada di dalam dictionary
    algo_keys = list(results_dict.keys())
    if active_algo not in results_dict and algo_keys:
        active_algo = algo_keys[0]

    # Inisialisasi jendela Ursina
    app = Ursina(
        title="Simulasi Robot Gudang 3D - KKA (A* vs GBFS)",
        borderless=False,
        fullscreen=False,
        size=(1280, 720),
    )

    # Konfigurasi jendela
    window.color = color.rgb(18, 22, 28)
    window.fps_counter.enabled = True
    window.exit_button.visible = False

    # Konversi koordinat grid (x, y) ke koordinat dunia 3D Ursina (X, Y, Z)
    center_offset_x = (grid_map.width - 1) / 2.0
    center_offset_z = (grid_map.height - 1) / 2.0

    def grid_to_world(x: float, y: float, y_elevation: float = 0.0) -> Vec3:
        wx = x - center_offset_x
        wz = y - center_offset_z
        return Vec3(wx, y_elevation, wz)

    # =========================================================================
    # LINGKUNGAN GUDANG (LANTAI, DINDING, & RAK PENYIMPANAN)
    # =========================================================================

    floor_w = grid_map.width + 2
    floor_h = grid_map.height + 2

    # Lantai dasar
    Entity(
        model='cube',
        position=Vec3(0, -0.25, 0),
        scale=Vec3(floor_w, 0.5, floor_h),
        color=color.rgb(32, 36, 44),
    )

    # Petak-petak lantai grid
    for x in range(grid_map.width):
        for y in range(grid_map.height):
            pos = grid_to_world(x, y, 0.01)
            tile_col = color.rgb(46, 52, 62) if (x + y) % 2 == 0 else color.rgb(40, 45, 54)
            Entity(
                model='plane',
                position=pos,
                scale=Vec3(0.96, 1, 0.96),
                color=tile_col,
            )

    # Dinding pembatas luar gudang
    wall_col = color.rgb(65, 72, 85)
    wall_h = 1.3
    wall_t = 0.35
    Entity(model='cube', position=Vec3(0, wall_h / 2, floor_h / 2), scale=Vec3(floor_w, wall_h, wall_t), color=wall_col)
    Entity(model='cube', position=Vec3(0, wall_h / 2, -floor_h / 2), scale=Vec3(floor_w, wall_h, wall_t), color=wall_col)
    Entity(model='cube', position=Vec3(floor_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, floor_h), color=wall_col)
    Entity(model='cube', position=Vec3(-floor_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, floor_h), color=wall_col)

    # Rak gudang (Storage Racks)
    shelf_frame_col = color.rgb(45, 60, 80)      # Rangka baja biru
    shelf_beam_col = color.rgb(235, 125, 35)     # Balok rak oranye industrial
    cargo_box_col = color.rgb(175, 130, 85)      # Kotak kargo karton

    for y in range(grid_map.height):
        for x in range(grid_map.width):
            if grid_map.grid[y, x] == 1:  # CellType.OBSTACLE
                pos = grid_to_world(x, y, 0.7)
                rack = Entity(
                    model='cube',
                    position=pos,
                    scale=Vec3(0.88, 1.4, 0.88),
                    color=shelf_frame_col,
                )
                # Batang aksen penahan rak
                Entity(parent=rack, model='cube', position=Vec3(0, 0.1, 0), scale=Vec3(1.02, 0.12, 1.02), color=shelf_beam_col)
                # Kardus barang di atas rak
                Entity(parent=rack, model='cube', position=Vec3(0, 0.45, 0), scale=Vec3(0.65, 0.45, 0.65), color=cargo_box_col)

    # =========================================================================
    # DOCKING START & TARGET GOAL
    # =========================================================================

    start_pos = grid_to_world(grid_map.start[0], grid_map.start[1], 0.05)
    goal_pos = grid_to_world(grid_map.goal[0], grid_map.goal[1], 0.05)

    # Titik Start (Charging Station Hijau)
    Entity(model=Cylinder(resolution=16), position=start_pos, scale=Vec3(0.92, 0.1, 0.92), color=color.rgb(46, 204, 113))
    Text(text="START", position=start_pos + Vec3(0, 1.3, 0), scale=1.4, color=color.rgb(46, 204, 113), billboard=True, origin=(0, 0))

    # Titik Goal (Target Kargo Emas/Merah)
    Entity(model=Cylinder(resolution=16), position=goal_pos, scale=Vec3(0.92, 0.1, 0.92), color=color.rgb(231, 76, 60))
    Entity(model='cube', position=goal_pos + Vec3(0, 0.4, 0), scale=Vec3(0.62, 0.62, 0.62), color=color.rgb(241, 196, 15))
    Text(text="GOAL", position=goal_pos + Vec3(0, 1.4, 0), scale=1.4, color=color.rgb(231, 76, 60), billboard=True, origin=(0, 0))

    # =========================================================================
    # MODEL 3D ROBOT GUDANG (AGV)
    # =========================================================================

    robot_root = Entity(
        position=grid_to_world(grid_map.start[0], grid_map.start[1], 0.18),
        scale=Vec3(1, 1, 1),
    )

    # Bodi utama AGV (Safety Yellow)
    Entity(parent=robot_root, model='cube', position=Vec3(0, 0, 0), scale=Vec3(0.72, 0.28, 0.72), color=color.rgb(245, 170, 20))
    # Bumper pelindung benturan
    Entity(parent=robot_root, model='cube', position=Vec3(0, -0.08, 0), scale=Vec3(0.78, 0.1, 0.78), color=color.rgb(25, 25, 28))
    # Sensor LIDAR scanner
    lidar_sensor = Entity(parent=robot_root, model=Cylinder(resolution=16), position=Vec3(0, 0.22, 0.18), scale=Vec3(0.24, 0.18, 0.24), color=color.rgb(30, 200, 180))
    # Lampu depan LED kembar
    Entity(parent=robot_root, model='sphere', position=Vec3(0.22, 0.02, 0.36), scale=Vec3(0.11, 0.08, 0.08), color=color.white)
    Entity(parent=robot_root, model='sphere', position=Vec3(-0.22, 0.02, 0.36), scale=Vec3(0.11, 0.08, 0.08), color=color.white)
    # Muatan paket kargo di atas robot
    Entity(parent=robot_root, model='cube', position=Vec3(0, 0.24, -0.12), scale=Vec3(0.42, 0.28, 0.42), color=color.rgb(150, 105, 65))

    # =========================================================================
    # SISTEM KAMERA
    # =========================================================================

    free_cam = EditorCamera(enabled=False)
    cam_modes = ["isometrik", "topdown", "bebas"]
    cam_state = {"mode_idx": 0}

    def apply_camera_mode(mode: str):
        if mode == "isometrik":
            free_cam.disable()
            camera.position = Vec3(0, 21.0, -17.5)
            camera.rotation = Vec3(50, 0, 0)
        elif mode == "topdown":
            free_cam.disable()
            camera.position = Vec3(0, 23.0, 0.01)
            camera.rotation = Vec3(90, 0, 0)
        elif mode == "bebas":
            free_cam.enable()

    apply_camera_mode("isometrik")

    # =========================================================================
    # STATE SIMULASI & JALUR
    # =========================================================================

    current_algo = {"name": active_algo}
    path_entities: List[Entity] = []
    waypoints: List[Vec3] = []

    sim_state = {
        "current_idx": 0,
        "is_moving": auto_start,
        "speed": 3.4,
        "finished": False,
    }

    # =========================================================================
    # HUD & TEKS STATUS
    # =========================================================================

    hud_panel = Entity(
        parent=camera.ui,
        model='quad',
        position=Vec3(-0.54, 0.35, 0),
        scale=Vec3(0.66, 0.26, 1),
        color=color.rgba(15, 20, 28, 0.85),
    )

    hud_text = Text(
        parent=hud_panel,
        text="",
        position=Vec3(-0.48, 0.45, -0.01),
        scale=1.05,
        color=color.white,
    )

    def refresh_hud(status_override: Optional[str] = None):
        """Memperbarui informasi pada panel HUD."""
        algo = current_algo["name"]
        res = results_dict.get(algo)
        path = res.path if res else []
        cost_str = f"{res.cost:.1f}" if res else f"{len(path) - 1}"
        nodes_str = f"{res.nodes_explored}" if res else "-"
        time_str = f"{res.execution_time_ms:.2f} ms" if res else "-"

        # Keterangan analisis teoritis singkat
        if "A*" in algo:
            teori_str = "Optimal (Rute Terpendek)"
        else:
            teori_str = "Suboptimal (Greedy / Memutar)"

        if status_override:
            status_str = status_override
        elif sim_state["finished"]:
            status_str = "SELESAI (Sampai di Tujuan)"
        elif sim_state["is_moving"]:
            status_str = "Sedang Bergerak..."
        else:
            status_str = "DIJEDA (Paused)"

        hud_text.text = (
            f"SIMULASI ROBOT GUDANG 3D (KKA)\n"
            f"Algoritma Aktif   : {algo} [{teori_str}]\n"
            f"Panjang Jalur     : {len(path)} sel (Cost: {cost_str})\n"
            f"Simpul Eksplorasi : {nodes_str} simpul | Waktu: {time_str}\n"
            f"Status Robot      : {status_str}\n"
            f"Langkah           : {sim_state['current_idx'] + 1} / {len(path)} (Kecepatan: {sim_state['speed']:.1f}x)"
        )

    # =========================================================================
    # PENGELOLAAN JALUR (PATH GENERATION & SWITCHING)
    # =========================================================================

    def reset_robot():
        """Mereset posisi robot ke titik awal rute."""
        sim_state["current_idx"] = 0
        sim_state["finished"] = False
        sim_state["is_moving"] = True
        if waypoints:
            robot_root.position = waypoints[0]
            robot_root.rotation_y = 0.0
            for dot in path_entities:
                dot.color = color.rgb(41, 128, 185)
        refresh_hud("Mulai Ulang...")

    def load_algorithm_path(algo_name: str):
        """Memuat rute dari algoritma yang dipilih ke dunia 3D."""
        nonlocal waypoints, path_entities
        current_algo["name"] = algo_name

        # Hapus penanda rute lama
        for e in path_entities:
            destroy(e)
        path_entities.clear()

        res = results_dict.get(algo_name)
        active_path = res.path if res else []

        # Buat penanda titik jalur baru
        for pt in active_path:
            p_pos = grid_to_world(pt[0], pt[1], 0.08)
            dot = Entity(
                model='sphere',
                position=p_pos,
                scale=Vec3(0.24, 0.24, 0.24),
                color=color.rgb(41, 128, 185),  # Biru laut
            )
            path_entities.append(dot)

        # Siapkan koordinat waypoint 3D
        waypoints = [grid_to_world(pt[0], pt[1], 0.18) for pt in active_path]

        # Reset posisi robot
        reset_robot()
        refresh_hud()

        # Update teks tombol beralih algoritma
        other_algo = "Greedy Best-First Search" if "A*" in algo_name else "A* Search"
        btn_switch_algo.text = f"Ganti: {other_algo}"

    def toggle_play_pause():
        """Mengaktifkan / menonaktifkan pergerakan robot."""
        if not sim_state["finished"]:
            sim_state["is_moving"] = not sim_state["is_moving"]
            btn_play_pause.text = "Lanjut (Spasi)" if not sim_state["is_moving"] else "Jeda (Spasi)"
            btn_play_pause.color = color.rgb(39, 174, 96) if not sim_state["is_moving"] else color.rgb(230, 126, 34)
            refresh_hud()

    def toggle_algorithm():
        """Beralih antara A* Search dan Greedy Best-First Search."""
        if len(algo_keys) < 2:
            return
        current = current_algo["name"]
        next_algo = [k for k in algo_keys if k != current][0]
        load_algorithm_path(next_algo)

    def cycle_camera():
        """Berganti sudut pandang kamera."""
        cam_state["mode_idx"] = (cam_state["mode_idx"] + 1) % len(cam_modes)
        mode = cam_modes[cam_state["mode_idx"]]
        apply_camera_mode(mode)
        btn_cam.text = f"Kamera: {mode.capitalize()}"

    def adjust_speed(delta: float):
        """Menyesuaikan kecepatan pergerakan robot."""
        sim_state["speed"] = max(0.8, min(10.0, sim_state["speed"] + delta))
        refresh_hud()

    # =========================================================================
    # TOMBOL INTERAKTIF DI LAYAR (SCREEN UI BUTTONS)
    # =========================================================================

    btn_y = -0.44
    btn_h = 0.052

    # 1. Tombol Ganti Algoritma
    btn_switch_algo = Button(
        text="Ganti Algoritma",
        position=Vec3(-0.62, btn_y, 0),
        scale=Vec3(0.25, btn_h, 1),
        color=color.rgb(142, 68, 173),  # Ungu
        text_size=0.85,
        on_click=toggle_algorithm,
    )

    # 2. Tombol Jeda / Lanjut
    btn_play_pause = Button(
        text="Jeda (Spasi)",
        position=Vec3(-0.35, btn_y, 0),
        scale=Vec3(0.18, btn_h, 1),
        color=color.rgb(230, 126, 34),  # Oranye
        text_size=0.85,
        on_click=toggle_play_pause,
    )

    # 3. Tombol Reset
    Button(
        text="Reset (R)",
        position=Vec3(-0.15, btn_y, 0),
        scale=Vec3(0.14, btn_h, 1),
        color=color.rgb(192, 57, 43),   # Merah
        text_size=0.85,
        on_click=reset_robot,
    )

    # 4. Tombol Kamera
    btn_cam = Button(
        text="Kamera: Isometrik",
        position=Vec3(0.06, btn_y, 0),
        scale=Vec3(0.20, btn_h, 1),
        color=color.rgb(52, 73, 94),    # Slate
        text_size=0.85,
        on_click=cycle_camera,
    )

    # 5. Tombol Pengatur Kecepatan
    Button(
        text="Lambat (-)",
        position=Vec3(0.25, btn_y, 0),
        scale=Vec3(0.12, btn_h, 1),
        color=color.rgb(44, 62, 80),
        text_size=0.8,
        on_click=lambda: adjust_speed(-0.8),
    )
    Button(
        text="Cepat (+)",
        position=Vec3(0.39, btn_y, 0),
        scale=Vec3(0.12, btn_h, 1),
        color=color.rgb(44, 62, 80),
        text_size=0.8,
        on_click=lambda: adjust_speed(0.8),
    )

    # 6. Tombol Keluar
    Button(
        text="Keluar (Esc)",
        position=Vec3(0.60, btn_y, 0),
        scale=Vec3(0.15, btn_h, 1),
        color=color.rgb(35, 40, 50),
        text_size=0.8,
        on_click=application.quit,
    )

    # Muat algoritma awal
    load_algorithm_path(active_algo)

    # =========================================================================
    # LOGIKA FRAME PER FRAME (UPDATE & INPUT)
    # =========================================================================

    def update():
        # Putar sensor LIDAR agar tampak aktif
        lidar_sensor.rotation_y += 360 * time.dt

        if not sim_state["is_moving"] or sim_state["finished"]:
            return

        if len(waypoints) <= 1:
            sim_state["finished"] = True
            refresh_hud()
            return

        target_idx = sim_state["current_idx"] + 1
        if target_idx >= len(waypoints):
            sim_state["finished"] = True
            sim_state["is_moving"] = False
            btn_play_pause.text = "Selesai!"
            refresh_hud("SELESAI (Sampai di Tujuan!)")
            return

        target_pos = waypoints[target_idx]
        current_pos = robot_root.position

        dir_vec = target_pos - current_pos
        dist = math.sqrt(dir_vec.x ** 2 + dir_vec.z ** 2)

        # Rotasi robot menghadap ke waypoint berikutnya
        if dist > 0.01:
            target_angle = math.degrees(math.atan2(dir_vec.x, dir_vec.z))
            robot_root.rotation_y = target_angle

        # Langkah pergerakan robot
        step = sim_state["speed"] * time.dt
        if dist <= step:
            robot_root.position = target_pos
            sim_state["current_idx"] = target_idx

            # Tandai titik jalur yang telah dilewati menjadi hijau
            if target_idx < len(path_entities):
                path_entities[target_idx].color = color.rgb(46, 204, 113)

            refresh_hud()
        else:
            # Gerak translasi linier
            robot_root.position += Vec3(dir_vec.x / dist, 0, dir_vec.z / dist) * step

    def input(key):
        if key == 'space':
            toggle_play_pause()
        elif key == 'r':
            reset_robot()
        elif key == 'tab':
            toggle_algorithm()
        elif key == 'v':
            cycle_camera()
        elif key in ('+', '=', 'up arrow'):
            adjust_speed(0.8)
        elif key in ('-', 'down arrow'):
            adjust_speed(-0.8)
        elif key == 'escape':
            application.quit()

    app.update = update
    app.input = input

    # Jalankan loop aplikasi Ursina
    app.run()
