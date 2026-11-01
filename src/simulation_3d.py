"""
simulation_3d.py
================
Visualisasi 3D simulasi robot gudang (Warehouse AGV) berbasis Ursina Engine.

Fitur Unggulan:
- Multi-Algorithm Live Switch: Beralih rute A* Search dan Greedy Best-First Search (GBFS)
  secara langsung di dalam jendela 3D tanpa perlu me-restart program.
- Animated Trajectory Trail: Robot meninggalkan jejak bercahaya dinamis di lantai
  (Hijau Neon untuk rute optimal A*, Oranye Api untuk rute suboptimal GBFS).
- Dynamic Smooth Movement & Rotation: Robot bergerak mulus antar koordinat grid dan berputar
  menghadap arah belokan (heading) menggunakan interpolasi sudut (lerp_angle).
- Pencahayaan 3D Nyata: Menggunakan DirectionalLight dan AmbientLight dengan kontras warna
  akurat (color.rgb32) sehingga lingkungan gudang terlihat hidup dan tidak putih polos.
- Kamera Terpusat Grid 30x20: Sudut pandang Isometrik, Tampak Atas (Top-Down), dan Kamera Bebas Orbit.
- HUD Interaktif & Tombol UI: Menampilkan metrik perbandingan kinerja (biaya rute, simpul dieksplorasi,
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
            DirectionalLight,
            AmbientLight,
            lerp_angle,
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

    # Konfigurasi jendela & latar belakang gelap elegan
    window.color = color.rgb32(20, 24, 32)
    window.fps_counter.enabled = True
    window.exit_button.visible = False

    # =========================================================================
    # PENCAHAYAAN (LIGHTING SYSTEM)
    # =========================================================================
    AmbientLight(color=color.rgba(0.65, 0.65, 0.65, 1.0))
    sun_light = DirectionalLight(shadows=False)
    sun_light.look_at(Vec3(0.6, -1.2, 0.8))

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

    # Lantai dasar gudang
    Entity(
        model='cube',
        position=Vec3(0, -0.25, 0),
        scale=Vec3(floor_w, 0.5, floor_h),
        color=color.rgb32(30, 34, 42),
    )

    # Petak-petak lantai grid
    for x in range(grid_map.width):
        for y in range(grid_map.height):
            pos = grid_to_world(x, y, 0.01)
            tile_col = color.rgb32(46, 52, 64) if (x + y) % 2 == 0 else color.rgb32(38, 43, 52)
            Entity(
                model='plane',
                position=pos,
                scale=Vec3(0.96, 1, 0.96),
                color=tile_col,
            )

    # Dinding pembatas luar gudang
    wall_col = color.rgb32(65, 74, 88)
    wall_h = 1.3
    wall_t = 0.35
    Entity(model='cube', position=Vec3(0, wall_h / 2, floor_h / 2), scale=Vec3(floor_w, wall_h, wall_t), color=wall_col)
    Entity(model='cube', position=Vec3(0, wall_h / 2, -floor_h / 2), scale=Vec3(floor_w, wall_h, wall_t), color=wall_col)
    Entity(model='cube', position=Vec3(floor_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, floor_h), color=wall_col)
    Entity(model='cube', position=Vec3(-floor_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, floor_h), color=wall_col)

    # Rak gudang (Storage Racks)
    shelf_frame_col = color.rgb32(45, 65, 90)      # Rangka baja biru industrial
    shelf_beam_col = color.rgb32(235, 125, 35)     # Balok rak oranye keselamatan
    cargo_box_col = color.rgb32(180, 135, 90)      # Kotak kargo karton cokelat

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
                # Balok rak oranye
                Entity(parent=rack, model='cube', position=Vec3(0, 0.1, 0), scale=Vec3(1.02, 0.12, 1.02), color=shelf_beam_col)
                # Kardus barang di atas rak
                Entity(parent=rack, model='cube', position=Vec3(0, 0.45, 0), scale=Vec3(0.65, 0.45, 0.65), color=cargo_box_col)

    # =========================================================================
    # DOCKING START & TARGET GOAL
    # =========================================================================

    start_pos = grid_to_world(grid_map.start[0], grid_map.start[1], 0.05)
    goal_pos = grid_to_world(grid_map.goal[0], grid_map.goal[1], 0.05)

    # Titik Start (Platform Docking Hijau Terang)
    Entity(model=Cylinder(resolution=16), position=start_pos, scale=Vec3(0.92, 0.1, 0.92), color=color.rgb32(46, 204, 113))
    Text(text="START", position=start_pos + Vec3(0, 1.3, 0), scale=1.4, color=color.rgb32(46, 204, 113), billboard=True, origin=(0, 0))

    # Titik Goal (Target Kargo Emas/Merah)
    Entity(model=Cylinder(resolution=16), position=goal_pos, scale=Vec3(0.92, 0.1, 0.92), color=color.rgb32(231, 76, 60))
    Entity(model='cube', position=goal_pos + Vec3(0, 0.4, 0), scale=Vec3(0.65, 0.65, 0.65), color=color.rgb32(241, 196, 15))
    Text(text="GOAL", position=goal_pos + Vec3(0, 1.4, 0), scale=1.4, color=color.rgb32(231, 76, 60), billboard=True, origin=(0, 0))

    # =========================================================================
    # MODEL 3D ROBOT GUDANG (AGV)
    # =========================================================================

    robot_root = Entity(
        position=grid_to_world(grid_map.start[0], grid_map.start[1], 0.18),
        scale=Vec3(1, 1, 1),
    )

    # Bodi utama AGV (Kuning Oranye Keselamatan)
    Entity(parent=robot_root, model='cube', position=Vec3(0, 0, 0), scale=Vec3(0.74, 0.28, 0.74), color=color.rgb32(245, 170, 20))
    # Bumper pelindung benturan hitam
    Entity(parent=robot_root, model='cube', position=Vec3(0, -0.08, 0), scale=Vec3(0.80, 0.1, 0.80), color=color.rgb32(28, 28, 32))
    # Sensor LIDAR scanner biru toska
    lidar_sensor = Entity(parent=robot_root, model=Cylinder(resolution=16), position=Vec3(0, 0.22, 0.18), scale=Vec3(0.24, 0.18, 0.24), color=color.rgb32(26, 188, 156))
    # Lampu depan LED kembar
    Entity(parent=robot_root, model='sphere', position=Vec3(0.22, 0.02, 0.38), scale=Vec3(0.11, 0.08, 0.08), color=color.white)
    Entity(parent=robot_root, model='sphere', position=Vec3(-0.22, 0.02, 0.38), scale=Vec3(0.11, 0.08, 0.08), color=color.white)
    # Muatan paket kargo di atas robot
    Entity(parent=robot_root, model='cube', position=Vec3(0, 0.24, -0.12), scale=Vec3(0.44, 0.28, 0.44), color=color.rgb32(150, 105, 65))

    # =========================================================================
    # SISTEM KAMERA TERPUSAT (DISESUAIKAN UNTUK GRID 30x20)
    # =========================================================================

    camera.fov = 54
    free_cam = EditorCamera(enabled=False)
    cam_modes = ["isometrik", "topdown", "bebas"]
    cam_state = {"mode_idx": 0}

    def apply_camera_mode(mode: str):
        """Mengarahkan kamera secara presisi ke titik tengah gudang Vec3(0, 0, 0)."""
        center_target = Vec3(0, 0, 0)
        if mode == "isometrik":
            free_cam.disable()
            camera.position = Vec3(0, 27.0, -22.5)
            camera.look_at(center_target)
        elif mode == "topdown":
            free_cam.disable()
            camera.position = Vec3(0, 31.0, 0.001)
            camera.look_at(center_target)
        elif mode == "bebas":
            free_cam.enable()
            free_cam.position = camera.position
            free_cam.look_at(center_target)

    # Aktifkan kamera isometrik default
    apply_camera_mode("isometrik")

    # =========================================================================
    # STATE SIMULASI & JALUR
    # =========================================================================

    current_algo = {"name": active_algo}
    preview_entities: List[Entity] = []   # Titik-titik penanda rute yang belum dilewati
    trail_entities: List[Entity] = []     # Jejak bercahaya yang ditinggalkan robot
    waypoints: List[Vec3] = []

    sim_state = {
        "current_idx": 0,
        "is_moving": auto_start,
        "speed": 3.8,
        "finished": False,
    }

    # =========================================================================
    # HUD / PANEL INFORMASI REAL-TIME
    # =========================================================================

    hud_panel = Entity(
        parent=camera.ui,
        model='quad',
        position=Vec3(-0.52, 0.33, 0),
        scale=Vec3(0.70, 0.28, 1),
        color=color.rgba32(15, 20, 28, 225),
    )

    hud_text = Text(
        parent=hud_panel,
        text="",
        position=Vec3(-0.48, 0.44, -0.01),
        scale=1.05,
        color=color.white,
    )

    def refresh_hud(status_override: Optional[str] = None):
        """Memperbarui teks informasi kinerja dan status robot secara real-time."""
        algo = current_algo["name"]
        res = results_dict.get(algo)
        path = res.path if res else []
        cost_str = f"{res.cost:.1f}" if res else f"{len(path) - 1}"
        nodes_str = f"{res.nodes_explored}" if res else "-"
        time_str = f"{res.execution_time_ms:.2f} ms" if res else "-"

        # Label status keoptimalan
        if "A*" in algo:
            badge = "[JALUR OPTIMAL - TERPENDEK]"
            trail_name = "Hijau Neon"
        else:
            badge = "[RUTE SUBOPTIMAL - GREEDY]"
            trail_name = "Oranye Api"

        if status_override:
            status_str = status_override
        elif sim_state["finished"]:
            status_str = "SELESAI (Sampai di Titik Tujuan!)"
        elif sim_state["is_moving"]:
            status_str = "Sedang Menavigasi Lorong..."
        else:
            status_str = "DIJEDA (Paused)"

        total_steps = len(path)
        cur_step = min(sim_state["current_idx"] + 1, total_steps)
        pct = (cur_step / total_steps * 100.0) if total_steps > 0 else 0.0

        hud_text.text = (
            f"SIMULASI ROBOT GUDANG 3D (KKA)\n"
            f"Algoritma Aktif   : {algo} {badge}\n"
            f"Panjang Rute      : {total_steps} sel (Total Cost: {cost_str})\n"
            f"Simpul Eksplorasi : {nodes_str} simpul | Waktu Hitung: {time_str}\n"
            f"Status Robot      : {status_str}\n"
            f"Progres Langkah   : {cur_step} / {total_steps} ({pct:.1f}%) | Speed: {sim_state['speed']:.1f}x\n"
            f"Warna Jejak Trail : {trail_name}"
        )

    # =========================================================================
    # PENGELOLAAN JALUR & ANIMASI TRAIL
    # =========================================================================

    def get_trail_color() -> color.Color:
        """Menghasilkan warna jejak khusus untuk tiap algoritma."""
        if "A*" in current_algo["name"]:
            return color.rgb32(46, 204, 113)  # Hijau neon (optimal)
        return color.rgb32(230, 126, 34)      # Oranye api (greedy)

    def spawn_trail_marker(pos: Vec3):
        """Membuat jejak bercahaya di lantai saat robot melintasi koordinat."""
        t_col = get_trail_color()
        # Plat balok jejak di lantai
        trail_tile = Entity(
            model='cube',
            position=Vec3(pos.x, 0.03, pos.z),
            scale=Vec3(0.58, 0.03, 0.58),
            color=t_col,
        )
        # Titik cahaya terang di tengah
        trail_core = Entity(
            parent=trail_tile,
            model='sphere',
            position=Vec3(0, 0.5, 0),
            scale=Vec3(0.35, 0.35, 0.35),
            color=color.white,
        )
        trail_entities.append(trail_tile)

    def reset_robot():
        """Mereset posisi robot ke titik awal dan membersihkan jejak lama."""
        sim_state["current_idx"] = 0
        sim_state["finished"] = False
        sim_state["is_moving"] = True

        # Hapus seluruh jejak trail
        for t in trail_entities:
            destroy(t)
        trail_entities.clear()

        # Kembalikan penanda preview rute
        for p in preview_entities:
            p.visible = True

        if waypoints:
            robot_root.position = waypoints[0]
            robot_root.rotation_y = 0.0
            spawn_trail_marker(waypoints[0])
            if preview_entities:
                preview_entities[0].visible = False

        refresh_hud("Mulai Ulang...")

    def load_algorithm_path(algo_name: str):
        """Memuat rute dari algoritma yang dipilih dan menyegarkan tampilan jalur."""
        nonlocal waypoints, preview_entities, trail_entities
        current_algo["name"] = algo_name

        # Bersihkan elemen penanda rute lama
        for e in preview_entities:
            destroy(e)
        preview_entities.clear()

        for t in trail_entities:
            destroy(t)
        trail_entities.clear()

        res = results_dict.get(algo_name)
        active_path = res.path if res else []

        # Buat penanda preview titik rute di lantai
        preview_color = color.rgb32(55, 75, 105)
        for pt in active_path:
            p_pos = grid_to_world(pt[0], pt[1], 0.07)
            dot = Entity(
                model='sphere',
                position=p_pos,
                scale=Vec3(0.20, 0.20, 0.20),
                color=preview_color,
            )
            preview_entities.append(dot)

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
            btn_play_pause.color = color.rgb32(39, 174, 96) if not sim_state["is_moving"] else color.rgb32(230, 126, 34)
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
        sim_state["speed"] = max(1.0, min(12.0, sim_state["speed"] + delta))
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
        color=color.rgb32(142, 68, 173),  # Ungu
        text_size=0.85,
        on_click=toggle_algorithm,
    )

    # 2. Tombol Jeda / Lanjut
    btn_play_pause = Button(
        text="Jeda (Spasi)",
        position=Vec3(-0.35, btn_y, 0),
        scale=Vec3(0.18, btn_h, 1),
        color=color.rgb32(230, 126, 34),  # Oranye
        text_size=0.85,
        on_click=toggle_play_pause,
    )

    # 3. Tombol Reset
    Button(
        text="Reset (R)",
        position=Vec3(-0.15, btn_y, 0),
        scale=Vec3(0.14, btn_h, 1),
        color=color.rgb32(192, 57, 43),   # Merah
        text_size=0.85,
        on_click=reset_robot,
    )

    # 4. Tombol Kamera
    btn_cam = Button(
        text="Kamera: Isometrik",
        position=Vec3(0.06, btn_y, 0),
        scale=Vec3(0.20, btn_h, 1),
        color=color.rgb32(52, 73, 94),    # Slate
        text_size=0.85,
        on_click=cycle_camera,
    )

    # 5. Tombol Pengatur Kecepatan
    Button(
        text="Lambat (-)",
        position=Vec3(0.25, btn_y, 0),
        scale=Vec3(0.12, btn_h, 1),
        color=color.rgb32(44, 62, 80),
        text_size=0.8,
        on_click=lambda: adjust_speed(-1.0),
    )
    Button(
        text="Cepat (+)",
        position=Vec3(0.39, btn_y, 0),
        scale=Vec3(0.12, btn_h, 1),
        color=color.rgb32(44, 62, 80),
        text_size=0.8,
        on_click=lambda: adjust_speed(1.0),
    )

    # 6. Tombol Keluar
    Button(
        text="Keluar (Esc)",
        position=Vec3(0.60, btn_y, 0),
        scale=Vec3(0.15, btn_h, 1),
        color=color.rgb32(35, 40, 50),
        text_size=0.8,
        on_click=application.quit,
    )

    # Muat algoritma awal
    load_algorithm_path(active_algo)

    # =========================================================================
    # LOGIKA FRAME PER FRAME (UPDATE & SMOOTH INTERPOLATION)
    # =========================================================================

    def update():
        # Sensor LIDAR scanner berputar terus
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
            refresh_hud("SELESAI (Sampai di Titik Tujuan!)")
            return

        target_pos = waypoints[target_idx]
        current_pos = robot_root.position

        dir_vec = target_pos - current_pos
        dist = math.sqrt(dir_vec.x ** 2 + dir_vec.z ** 2)

        # Rotasi halus robot menghadap ke waypoint berikutnya (lerp_angle)
        if dist > 0.01:
            target_angle = math.degrees(math.atan2(dir_vec.x, dir_vec.z))
            robot_root.rotation_y = lerp_angle(robot_root.rotation_y, target_angle, time.dt * 12.0)

        # Translasi pergerakan robot
        step = sim_state["speed"] * time.dt
        if dist <= step:
            # Robot mencapai titik waypoint saat ini
            robot_root.position = target_pos
            sim_state["current_idx"] = target_idx

            # Sembunyikan titik preview dan tinggalkan jejak bercahaya di lantai
            if target_idx < len(preview_entities):
                preview_entities[target_idx].visible = False
            spawn_trail_marker(target_pos)

            refresh_hud()
        else:
            # Interpolasi linier menuju waypoint
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
            adjust_speed(1.0)
        elif key in ('-', 'down arrow'):
            adjust_speed(-1.0)
        elif key == 'escape':
            application.quit()

    app.update = update
    app.input = input

    # Jalankan loop aplikasi Ursina
    app.run()
