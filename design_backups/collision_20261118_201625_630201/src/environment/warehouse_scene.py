"""
warehouse_scene.py
==================
Konstruksi lingkungan 3D arena gudang 35x25 dengan 3 teknik optimasi ekstrem:
1. Floor Optimization (Procedural Texture Tiling pada 1 Single Plane raksasa 35x25).
2. Static Mesh Combining (Menggabungkan visual rak & balok dinding beton menjadi single mesh).
3. Asynchronous Loading (Generator coroutine dengan yield dan loading screen di tengah layar).
Menyediakan visualisasi rintangan dinding (Wall Obstacles) abu-abu beton kontras,
stasiun docking Start, target Goal, dan penyesuaian kamera terpusat.
"""

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from PIL import Image
from ursina import (
    Entity, Vec3, Vec2, color, camera, window, scene, held_keys, 
    time as utime, EditorCamera, DirectionalLight, AmbientLight, 
    Texture, Text, destroy, curve,
)
from ursina.shaders import lit_with_shadows_shader

from src.config import (
    GRID_WIDTH, GRID_HEIGHT, SPAWN_ALPHA, SPAWN_BETA, DEFAULT_GOAL,
    grid_to_world, COLOR_ALPHA_PRIMARY, COLOR_BETA_PRIMARY,
    COLOR_SHELF_FRAME, COLOR_SHELF_BEAM, COLOR_WALL, COLOR_WALL_TRIM,
    COLOR_PERIMETER_WALL, COLOR_GOAL_PAD, WALL_HEIGHT,
    PERIMETER_WALL_HEIGHT, CAMERA_PRESETS,
)
from src.cognition.warehouse_graph import WarehouseGraph100, CellType, ShelfData
from src.environment.asset_loader import AssetLoader
from src.environment.interactive_shelf import InteractiveShelf

Coord = Tuple[int, int]

def _create_procedural_grid_texture(resolution: int = 128) -> Texture:
    """
    Tekstur lantai futuristik: Dasar gelap (Dark Slate) dengan garis grid Cyan neon tipis.
    """
    img = Image.new("RGBA", (resolution, resolution), color=(64, 62, 58, 255)) # Dark Slate 900
    border_col = (96, 92, 84, 235) # Cyan neon transparan

    for i in range(resolution):
        for w in (0, 1, resolution - 2, resolution - 1):
            img.putpixel((i, w), border_col)
            img.putpixel((w, i), border_col)
    return Texture(img)


class WarehouseScene(Entity):
    def __init__(self, graph: WarehouseGraph100, on_complete: Optional[Callable[[], None]] = None):
        super().__init__()
        self.graph = graph
        self.on_complete_callback = on_complete

        self.interactive_shelves: Dict[Coord, InteractiveShelf] = {}
        self.free_cam: Optional[EditorCamera] = None
        self.current_cam_mode = "isometrik"
        self.cam_modes = ["isometrik", "topdown", "pov_alpha", "pov_beta"]
        self.cam_mode_idx = 0
        self.mission_mgr: Optional[Any] = None

        self.static_racks_parent: Optional[Entity] = None
        self.static_beams_parent: Optional[Entity] = None
        self.static_walls_parent: Optional[Entity] = None
        self.static_wall_trims_parent: Optional[Entity] = None
        self.floor: Optional[Entity] = None
        self.heatmap_parent: Optional[Entity] = None

        self.sun: Optional[DirectionalLight] = None
        self.ambient: Optional[AmbientLight] = None

        self.dynamic_obstacle_entities: Dict[Coord, Entity] = {}
        self.oil_spill_entities: Dict[Coord, Entity] = {}
        self.boost_pad_entities: Dict[Coord, Entity] = {}
        self.forklifts: List[Any] = []
        self.forklift = None

        # ---------------------------------------------------------------------
        # UI LOADING SCREEN
        # ---------------------------------------------------------------------
        self.loading_backdrop = Entity(
            parent=camera.ui, model='quad', scale=Vec3(2.5, 2.5, 1), color=color.rgba32(12, 15, 22, 245),
        )
        self.loading_title = Text(
            parent=self.loading_backdrop, text="MEMUAT ARENA 35x25...", position=Vec3(0, 0.08, -0.01),
            scale=1.5, color=color.rgb32(110, 149, 144), origin=(0, 0), font='assets/fonts/Roboto-Bold.ttf'
        )
        self.loading_status = Text(
            parent=self.loading_backdrop, text="Inisialisasi Sistem Renderer...", position=Vec3(0, -0.02, -0.01),
            scale=1.05, color=color.white, origin=(0, 0), font='assets/fonts/Roboto-Regular.ttf'
        )
        self.loading_bar_bg = Entity(
            parent=self.loading_backdrop, model='quad', position=Vec3(0, -0.10, -0.01),
            scale=Vec3(0.60, 0.03, 1), color=color.rgb32(35, 42, 54),
        )
        self.loading_bar_fill = Entity(
            parent=self.loading_bar_bg, model='quad', position=Vec3(-0.5, 0, -0.01),
            scale=Vec3(0.01, 1, 1), origin=(-0.5, 0), color=color.rgb32(110, 149, 144),
        )

        self._async_loader = self._build_scene_coroutine()

    def _update_progress(self, message: str, percent: float):
        self.loading_status.text = f"{message} ({int(percent * 100)}%)"
        self.loading_bar_fill.scale_x = max(0.01, min(1.0, percent))

    def _build_scene_coroutine(self):
        # =====================================================================
        # TAHAP 1: PENCAHAYAAN & LANTAI
        # =====================================================================
        self._update_progress("Menyiapkan Sistem Pencahayaan 3D...", 0.05)
        self._setup_lighting() 
        yield

        self._update_progress("Membangun Lantai Tiled 35x25...", 0.12)
        grid_tex = _create_procedural_grid_texture(128)

        self.floor = Entity(
            name='warehouse_floor', model='plane', position=Vec3(0, 0, 0),
            scale=Vec3(GRID_WIDTH, 1, GRID_HEIGHT), texture=grid_tex,
            texture_scale=Vec2(GRID_WIDTH, GRID_HEIGHT), collider='box',
            shader=lit_with_shadows_shader,
        )
        self.floor.receive_shadows = True
        if self.sun: self.sun.update_bounds(self.floor)
        yield

        # =====================================================================
        # TAHAP 2: SPAWN VISUAL RAK
        # =====================================================================
        self._update_progress("Menyiapkan Model 3D Rak & Aset...", 0.18)
        from src.config import MODEL_PATH_SHELF_EMPTY, MODEL_PATH_SHELF_OCCUPIED
        self.static_racks_parent = Entity()
        yield

        all_shelves: List[ShelfData] = list(self.graph.shelves.values())
        total_shelves = len(all_shelves)
        batch_size = 150

        for i in range(0, total_shelves, batch_size):
            batch = all_shelves[i:i + batch_size]
            for sdata in batch:
                world_pos = grid_to_world(sdata.x, sdata.y, 0.0)
                vis_ent = Entity(
                    parent=self.static_racks_parent,
                    model=MODEL_PATH_SHELF_OCCUPIED if sdata.has_cargo else MODEL_PATH_SHELF_EMPTY,
                    position=world_pos, scale=Vec3(0.88, 1.0, 0.88), shader=lit_with_shadows_shader,
                )
                vis_ent.cast_shadows = True
                shelf_ent = InteractiveShelf(shelf_data=sdata, visual_entity=vis_ent)
                self.interactive_shelves[sdata.coord] = shelf_ent

            pct = 0.20 + (0.50 * (min(i + batch_size, total_shelves) / max(total_shelves, 1)))
            self._update_progress(f"Menyusun Blok Rak [{min(i + batch_size, total_shelves)}/{total_shelves}]...", pct)
            yield

        self._update_progress("Mengonfigurasi Pemandangan Rak 3D...", 0.75)
        yield

        # =====================================================================
        # TAHAP 4: SPAWN RINTANGAN DINDING (WALL OBSTACLES) & PERIMETER
        # =====================================================================
        self._update_progress("Membangun Dinding Luar & Sekat Partisi...", 0.82)
        
        # Warna Dinding Modern: Abu-abu Beton Gelap
        wall_color_modern = color.rgb32(53, 69, 77) 
        trim_color_modern = color.rgb32(80, 90, 110)

        self.static_walls_parent = Entity(color=wall_color_modern, shader=lit_with_shadows_shader)
        self.static_walls_parent.cast_shadows = True
        self.static_wall_trims_parent = Entity(color=trim_color_modern, shader=lit_with_shadows_shader)

        arena_w = GRID_WIDTH + 2
        arena_h = GRID_HEIGHT + 2
        wall_h = PERIMETER_WALL_HEIGHT
        wall_t = 0.5
        col_perim = color.rgb32(46, 60, 67) # Dinding perimeter lebih gelap

        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, -arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(-arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h), color=col_perim)

        internal_wall_h = WALL_HEIGHT
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(0, wall_h + 0.05, arena_h / 2), scale=Vec3(arena_w, 0.1, wall_t * 1.05))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(0, wall_h + 0.05, -arena_h / 2), scale=Vec3(arena_w, 0.1, wall_t * 1.05))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(arena_w / 2, wall_h + 0.05, 0), scale=Vec3(wall_t * 1.05, 0.1, arena_h))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(-arena_w / 2, wall_h + 0.05, 0), scale=Vec3(wall_t * 1.05, 0.1, arena_h))

        for y in range(self.graph.height):
            for x in range(self.graph.width):
                if self.graph.grid[y, x] == CellType.WALL:
                    pos = grid_to_world(x, y, internal_wall_h / 2.0)
                    Entity(parent=self.static_walls_parent, model='cube', position=pos, scale=Vec3(0.98, internal_wall_h, 0.98), color=wall_color_modern)
                    Entity(parent=self.static_wall_trims_parent, model='cube', position=pos + Vec3(0, 1.05, 0), scale=Vec3(0.98, 0.12, 0.98))

        self._update_progress("Menggabungkan Mesh Dinding...", 0.90)
        yield
        self.static_walls_parent.combine(auto_destroy=True)
        self.static_wall_trims_parent.combine(auto_destroy=True)
        yield

        # =====================================================================
        # TAHAP 5: STASIUN DOCKING (START) & TARGET GOAL
        # =====================================================================
        self._update_progress("Menyiapkan Stasiun Docking...", 0.95)
        self._build_dock_and_goal_stations()
        self._setup_camera()

        from src.behavior.forklift_controller import ForkliftController
        # 3 Forklift Industri di 3 Zona Berbeda (Tengah: WASD, Kiri: Arrows, Atas: IJKL)
        fl_center = ForkliftController(
            graph=self.graph,
            start_coord=(17, 11),
            control_scheme="wasd",
            name="FORKLIFT 1",
            chassis_color=(235, 125, 25),
        )
        fl_left = ForkliftController(
            graph=self.graph,
            start_coord=(5, 7),
            control_scheme="arrows",
            name="FORKLIFT 2",
            chassis_color=(240, 195, 20),
        )
        fl_top = ForkliftController(
            graph=self.graph,
            start_coord=(23, 20),
            control_scheme="ijkl",
            name="FORKLIFT 3",
            chassis_color=(220, 50, 45),
        )
        self.forklifts = [fl_center, fl_left, fl_top]
        self.forklift = fl_center
        yield

        self._update_progress("Arena 35x25 Siap!", 1.0)
        yield
        destroy(self.loading_backdrop)
        if self.on_complete_callback: self.on_complete_callback()

    def update(self):
        """Memajukan proses loading generator dan navigasi Free-Cam."""
        if self._async_loader:
            try: next(self._async_loader)
            except StopIteration: self._async_loader = None

        if self.current_cam_mode in ("free_cam", "bebas") and self.free_cam and self.free_cam.enabled:
            from ursina import held_keys, time as utime
            fly_speed = 18.0 * (2.2 if held_keys['shift'] else 1.0)
            if held_keys['up arrow']: self.free_cam.position += self.free_cam.forward * fly_speed * utime.dt
            if held_keys['down arrow']: self.free_cam.position -= self.free_cam.forward * fly_speed * utime.dt
            if held_keys['right arrow']: self.free_cam.position += self.free_cam.right * fly_speed * utime.dt
            if held_keys['left arrow']: self.free_cam.position -= self.free_cam.right * fly_speed * utime.dt
            if held_keys['page up'] or held_keys['e']: self.free_cam.position += Vec3(0, 1, 0) * fly_speed * utime.dt
            if held_keys['page down'] or held_keys['q']: self.free_cam.position -= Vec3(0, 1, 0) * fly_speed * utime.dt

    # =========================================================================
    # FUNGSI INI SEKARANG SUDAH BERADA DI POSISI YANG BENAR (DI DALAM KELAS)
    # =========================================================================
    def _setup_lighting(self):
        """Pencahayaan 3D industrial modern."""
        window.color = color.rgb32(24, 34, 40)  # Background luar sangat gelap

        # Cahaya ambient biru redup (membuat bayangan tidak hitam pekat)
        self.ambient = AmbientLight(color=color.rgba(0.43, 0.46, 0.48, 1.0))

        # Cahaya utama putih bersih (seperti lampu sorot pabrik modern)
        self.sun = DirectionalLight(shadow_map_resolution=Vec2(2048, 2048), shadows=True)
        self.sun.color = color.rgba(0.98, 0.95, 0.90, 1.0)
        self.sun.position = Vec3(-20, 40, -20)
        self.sun.look_at(Vec3(0, 0, 0))

        # Fill light lembut
        fill = DirectionalLight(shadows=False)
        fill.color = color.rgba(0.25, 0.30, 0.34, 1.0)
        fill.look_at(Vec3(0.6, -0.8, 0.6))

        lit_with_shadows_shader.default_input['shadow_bias'] = 0.001
        lit_with_shadows_shader.default_input['shadow_color'] = color.rgba(0.0, 0.0, 0.0, 0.7)

    def _build_dock_and_goal_stations(self):
        """Unified Twin Docking Station di area bawah/tengah arena (x=17, 18, y=1) & Platform Target Goal."""
<<<<<<< Updated upstream
        dock_tower_model = AssetLoader.get_dock_model()

        pos_a = grid_to_world(SPAWN_ALPHA[0], SPAWN_ALPHA[1], 0.0)
        pos_b = grid_to_world(SPAWN_BETA[0], SPAWN_BETA[1], 0.0)
        mid_pos = (pos_a + pos_b) / 2.0

        # 1. Platform Terpadu Raksasa (Unified Docking Platform)
        Entity(
            model='cube',
            position=mid_pos - Vec3(0, 0.025, 0),
            scale=Vec3(3.2, 0.06, 1.8),
            color=color.rgba32(18, 24, 34, 230),
        )

        # 2. Pad Lantai Parkir Alpha (A* Search) - Cyan Neon
        Entity(
            model='cube',
            position=pos_a - Vec3(0, 0.015, 0),
            scale=Vec3(1.35, 0.065, 1.5),
            color=color.rgba32(110, 149, 144, 165),
        )
        # Menara charger stasiun Alpha di belakang robot
        Entity(
            model=dock_tower_model,
            position=pos_a + Vec3(0, 0, -0.75),
            rotation=Vec3(0, 0, 0),
            scale=Vec3(0.55, 0.65, 0.55),
        )

        # 3. Pad Lantai Parkir Beta (GBFS) - Orange Neon
        Entity(
            model='cube',
            position=pos_b - Vec3(0, 0.015, 0),
            scale=Vec3(1.35, 0.065, 1.5),
            color=color.rgba32(176, 132, 84, 165),
        )
        # Menara charger stasiun Beta di belakang robot
        Entity(
            model=dock_tower_model,
            position=pos_b + Vec3(0, 0, -0.75),
            rotation=Vec3(0, 0, 0),
            scale=Vec3(0.55, 0.65, 0.55),
        )

        # 4. Header Billboard Terpadu
        Text(
            text="UNIFIED TWIN DOCK\n[ A* SEARCH  |  GBFS ]",
            position=mid_pos + Vec3(0, 2.1, -0.75),
            scale=1.45,
            color=color.rgb32(110, 149, 144),
            billboard=True,
            origin=(0, 0),
            font='assets/fonts/Roboto-Bold.ttf',
        )
        offset_text = 0.35 if SPAWN_ALPHA == SPAWN_BETA else 0.0
        Text(
            text="ALPHA (A*)",
            position=pos_a + Vec3(-offset_text, 1.55, -0.75),
            scale=1.1,
            color=color.rgb32(*COLOR_ALPHA_PRIMARY),
            billboard=True,
            origin=(0, 0),
            font='assets/fonts/Roboto-Bold.ttf',
        )
        Text(
            text="BETA (GBFS)",
            position=pos_b + Vec3(offset_text, 1.55, -0.75),
            scale=1.1,
            color=color.rgb32(*COLOR_BETA_PRIMARY),
            billboard=True,
            origin=(0, 0),
            font='assets/fonts/Roboto-Bold.ttf',
        )
=======
        from src.environment.charging_station import build_charging_station
        build_charging_station(self)
>>>>>>> Stashed changes

        # Goal
        pos_g = grid_to_world(DEFAULT_GOAL[0], DEFAULT_GOAL[1], 0.0)
        Entity(model='cube', position=pos_g + Vec3(0, 0.05, 0), scale=Vec3(0.94, 0.10, 0.94), color=color.rgb32(*COLOR_GOAL_PAD))
        Entity(model='cube', position=pos_g + Vec3(0, 0.02, 0), scale=Vec3(1.10, 0.04, 1.10), color=color.rgb32(30, 40, 50))
        Text(text="GOAL STATION\n(Delivery Point)", position=pos_g + Vec3(0, 1.8, 0), scale=1.5, color=color.rgb32(*COLOR_GOAL_PAD), billboard=True, origin=(0, 0), font='assets/fonts/Roboto-Bold.ttf')

        self._build_transfer_gate()

    def _build_transfer_gate(self):
        pos_gate = grid_to_world(34, 13, 0.0)
        Entity(model='cube', position=pos_gate + Vec3(0, 0.04, 0), scale=Vec3(1.2, 0.07, 3.4), color=color.rgba32(110, 149, 144, 175))
        Entity(model='cube', position=pos_gate + Vec3(0.25, 1.8, -1.75), scale=Vec3(0.6, 3.6, 0.6), color=color.rgb32(28, 38, 54), shader=lit_with_shadows_shader)
        Entity(model='cube', position=pos_gate + Vec3(0.25, 1.8, 1.75), scale=Vec3(0.6, 3.6, 0.6), color=color.rgb32(28, 38, 54), shader=lit_with_shadows_shader)
        Entity(model='cube', position=pos_gate + Vec3(0.25, 3.6, 0), scale=Vec3(0.7, 0.6, 4.1), color=color.rgb32(110, 149, 144))
        Entity(model='cube', position=pos_gate + Vec3(0.25, 1.8, 0), scale=Vec3(0.08, 3.2, 3.1), color=color.rgba32(110, 149, 144, 74))
        Text(text="TRANSFER GATE\n>>> ZONE B >>>", position=pos_gate + Vec3(0, 4.4, 0), scale=1.5, color=color.rgb32(110, 149, 144), billboard=True, origin=(0, 0), font='assets/fonts/Roboto-Bold.ttf')

    def _setup_camera(self):
        camera.fov = CAMERA_PRESETS["isometrik"]["fov"]
        self.free_cam = EditorCamera(enabled=False)
        self.apply_camera_mode("isometrik")

    def apply_camera_mode(
        self,
        mode: str,
        target_robot_pos: Optional[Vec3] = None,
        mission_mgr: Optional[Any] = None,
    ):
        """
        Mengubah sudut pandang kamera dengan stabilisasi rotasi penuh (anti-gimbal lock).
        Mode yang didukung:
        - 'isometrik': Tampilan arena 35x25 dari sudut atas miring statis.
        - 'topdown': Tampilan 2D top-down dari atas arena.
        - 'pov_alpha': Dashcam First-Person view menempel pada visual_body AGV Alpha (A*).
        - 'pov_beta': Dashcam First-Person view menempel pada visual_body AGV Beta (GBFS).
        - 'free_cam' / 'bebas': Navigasi kamera bebas melayang.
        """
        from ursina import scene
        if mission_mgr is not None:
            self.mission_mgr = mission_mgr
        mgr = self.mission_mgr

        self.current_cam_mode = mode
        is_free = (mode in ("free_cam", "bebas"))

        # Pastikan EditorCamera dimatikan jika bukan mode bebas
        if self.free_cam and not is_free:
            self.free_cam.disable()
            camera.parent = scene
            if hasattr(self, 'forklifts') and self.forklifts:
                for fl in self.forklifts:
                    fl.set_control_enabled(True)
            elif self.forklift:
                self.forklift.set_control_enabled(True)

        # Kelola visibilitas label billboard agar tidak menghalangi pandangan dashcam
        if mgr:
            if hasattr(mgr, 'robot_alpha') and mgr.robot_alpha:
                if hasattr(mgr.robot_alpha, 'label_tag'):
                    mgr.robot_alpha.label_tag.enabled = (mode != "pov_alpha")
                if hasattr(mgr.robot_alpha, 'battery_bar_bg'):
                    mgr.robot_alpha.battery_bar_bg.enabled = (mode != "pov_alpha")
            if hasattr(mgr, 'robot_beta') and mgr.robot_beta:
                if hasattr(mgr.robot_beta, 'label_tag'):
                    mgr.robot_beta.label_tag.enabled = (mode != "pov_beta")
                if hasattr(mgr.robot_beta, 'battery_bar_bg'):
                    mgr.robot_beta.battery_bar_bg.enabled = (mode != "pov_beta")

        # 1. Mode POV Alpha (First-Person Dashcam A*)
        if mode == "pov_alpha":
            target = None
            if mgr and hasattr(mgr, 'robot_alpha') and mgr.robot_alpha:
                target = getattr(mgr.robot_alpha, 'visual_body', mgr.robot_alpha)
            if target:
                camera.parent = target
                camera.position = Vec3(0, 1.5, 0.5)
                camera.rotation = Vec3(10, 0, 0)
                camera.fov = 68

        # 2. Mode POV Beta (First-Person Dashcam GBFS)
        elif mode == "pov_beta":
            target = None
            if mgr and hasattr(mgr, 'robot_beta') and mgr.robot_beta:
                target = getattr(mgr.robot_beta, 'visual_body', mgr.robot_beta)
            if target:
                camera.parent = target
                camera.position = Vec3(0, 1.5, 0.5)
                camera.rotation = Vec3(10, 0, 0)
                camera.fov = 68

        # 3. Mode Isometrik Arena Statis
        elif mode == "isometrik":
            camera.parent = scene
            cfg = CAMERA_PRESETS["isometrik"]
            camera.rotation = Vec3(0, 0, 0)
            camera.position = Vec3(*cfg["pos"])
            camera.fov = cfg["fov"]
            camera.look_at(Vec3(*cfg["target"]))
            camera.rotation_z = 0.0
        # 4. Mode Top-Down Arena Statis
        elif mode == "topdown":
            camera.parent = scene
            cfg = CAMERA_PRESETS["topdown"]
            camera.position = Vec3(*cfg["pos"])
            camera.rotation = Vec3(90, 0, 0)
            camera.fov = cfg["fov"]
            camera.rotation_z = 0.0

        # 5. Follow Mode (Opsional)
        elif mode in ("follow_alpha", "follow_beta"):
            camera.parent = scene
            cfg = CAMERA_PRESETS.get(mode, {"offset": (0.0, 16.0, -14.0), "fov": 55})
            camera.fov = cfg.get("fov", 55)
            camera.rotation_z = 0.0
            if target_robot_pos is not None:
                offset = cfg.get("offset", (0.0, 16.0, -14.0))
                desired = target_robot_pos + Vec3(*offset)
                camera.position = Vec3(max(-23.5, min(23.5, desired.x)), desired.y, max(-23.5, min(23.5, desired.z)))
                camera.look_at(target_robot_pos)
                camera.rotation_z = 0.0

        # 6. Mode Bebas (Free-Cam)
        elif is_free:
            camera.parent = scene
            if self.free_cam:
                cfg = CAMERA_PRESETS["isometrik"]
                camera.rotation = Vec3(0, 0, 0)
                camera.position = Vec3(*cfg["pos"])
                camera.fov = cfg["fov"]
                camera.look_at(Vec3(*cfg["target"]))
                camera.rotation_z = 0.0
                
                self.free_cam.position = camera.position
                self.free_cam.rotation = camera.rotation
                self.free_cam.fov = camera.fov

                self.free_cam.clip_plane_far = 5000
                self.free_cam.clip_plane_near = 0.1

                self.free_cam.enable()
            if hasattr(self, 'forklifts') and self.forklifts:
                for fl in self.forklifts:
                    fl.set_control_enabled(False)
            elif self.forklift:
                self.forklift.set_control_enabled(False)

    def cycle_camera_mode(self, target_robot_pos: Optional[Vec3] = None) -> str:
        """Siklus pergantian sudut kamera: Isometrik -> Top-Down -> POV Alpha (A*) -> POV Beta (GBFS) -> Isometrik."""
        if self.current_cam_mode in self.cam_modes:
            self.cam_mode_idx = self.cam_modes.index(self.current_cam_mode)
        self.cam_mode_idx = (self.cam_mode_idx + 1) % len(self.cam_modes)
        mode = self.cam_modes[self.cam_mode_idx]
        self.apply_camera_mode(mode, target_robot_pos=target_robot_pos)
        return mode

    def update_follow_camera(self, target_pos: Vec3, offset: Tuple[float, float, float] = (0.0, 16.0, -14.0)):
        if "follow" in self.current_cam_mode:
            desired_pos = target_pos + Vec3(*offset)
            clamped_x = max(-23.5, min(23.5, desired_pos.x))
            clamped_z = max(-23.5, min(23.5, desired_pos.z))
            target_cam = Vec3(clamped_x, desired_pos.y, clamped_z)

            camera.position = Vec3(
                camera.position.x + (target_cam.x - camera.position.x) * 0.15,
                camera.position.y + (target_cam.y - camera.position.y) * 0.15,
                camera.position.z + (target_cam.z - camera.position.z) * 0.15,
            )
            camera.look_at(target_pos)
            camera.rotation_z = 0.0

    def update_pov_camera(self, robot):
        """Menjaga kamera First-Person Dashcam POV tetap terpasang pada visual_body robot."""
        if not robot:
            return
        target_ent = getattr(robot, 'visual_body', robot)
        if not target_ent:
            return
        if camera.parent != target_ent:
            camera.parent = target_ent
            camera.position = Vec3(0, 1.5, 0.5)
            camera.rotation = Vec3(10, 0, 0)

    def render_exploration_heatmap(self, alpha_nodes=None, beta_nodes=None):
        self.clear_exploration_heatmap()
        nodes_a = alpha_nodes or set()
        nodes_b = beta_nodes or set()
        if not nodes_a and not nodes_b: return

        shared_nodes = nodes_a & nodes_b
        alpha_only = nodes_a - shared_nodes
        beta_only = nodes_b - shared_nodes

        self.heatmap_parent = Entity(name="exploration_heatmap")

        if alpha_only:
            p_alpha = Entity(parent=self.heatmap_parent, color=color.rgba32(245, 65, 120, 95))
            for x, y in alpha_only:
                Entity(parent=p_alpha, model='quad', rotation_x=90, position=grid_to_world(x, y, 0.015), scale=Vec3(0.92, 0.92, 1))
            p_alpha.combine(auto_destroy=True)

        if beta_only:
            p_beta = Entity(parent=self.heatmap_parent, color=color.rgba32(0, 205, 255, 95))
            for x, y in beta_only:
                Entity(parent=p_beta, model='quad', rotation_x=90, position=grid_to_world(x, y, 0.015), scale=Vec3(0.92, 0.92, 1))
            p_beta.combine(auto_destroy=True)

        if shared_nodes:
            p_shared = Entity(parent=self.heatmap_parent, color=color.rgba32(195, 75, 255, 125))
            for x, y in shared_nodes:
                Entity(parent=p_shared, model='quad', rotation_x=90, position=grid_to_world(x, y, 0.016), scale=Vec3(0.92, 0.92, 1))
            p_shared.combine(auto_destroy=True)

    def clear_exploration_heatmap(self):
        if hasattr(self, 'heatmap_parent') and self.heatmap_parent:
            destroy(self.heatmap_parent)
            self.heatmap_parent = None

    def spawn_dynamic_obstacle(self, x: int, y: int) -> Entity:
        target_pos = grid_to_world(x, y, 0.35)
        spawn_pos = Vec3(target_pos.x, 2.6, target_pos.z)
        from src.environment.cardboard_box import make_cardboard_box
        cargo_ent = make_cardboard_box(self, spawn_pos)
        cargo_ent.cast_shadows = True
        cargo_ent.receive_shadows = True
        cargo_ent.interactive_type = "dynamic_obstacle"
        cargo_ent.grid_coord = (x, y)
        cargo_ent.animate_y(target_pos.y, duration=0.28, curve=curve.out_bounce)
        self.dynamic_obstacle_entities[(x, y)] = cargo_ent
        return cargo_ent

    def remove_dynamic_obstacle(self, x: int, y: int) -> bool:
        if (x, y) in self.dynamic_obstacle_entities:
            destroy(self.dynamic_obstacle_entities.pop((x, y)))
            return True
        return False

    def clear_all_dynamic_obstacles(self):
        for ent in self.dynamic_obstacle_entities.values(): destroy(ent)
        self.dynamic_obstacle_entities.clear()

    def spawn_hazard_oil(self, x: int, y: int) -> Entity:
        pos = grid_to_world(x, y, 0.02)
        oil_ent = Entity(parent=self, model='circle', rotation_x=90, position=pos, scale=Vec3(0.88, 0.88, 1), color=color.rgba32(235, 170, 20, 215), collider='box')
        oil_ent.interactive_type = "hazard_oil"
        oil_ent.grid_coord = (x, y)
        self.oil_spill_entities[(x, y)] = oil_ent
        return oil_ent

    def remove_hazard_oil(self, x: int, y: int) -> bool:
        if (x, y) in self.oil_spill_entities:
            destroy(self.oil_spill_entities.pop((x, y)))
            return True
        return False

    def spawn_boost_pad(self, x: int, y: int) -> Entity:
        pos = grid_to_world(x, y, 0.02)
        pad_ent = Entity(parent=self, model='quad', rotation_x=90, position=pos, scale=Vec3(0.90, 0.90, 1), color=color.rgba32(0, 245, 140, 220), collider='box')
        pad_ent.interactive_type = "boost_pad"
        pad_ent.grid_coord = (x, y)
        Text(parent=pad_ent, text=">>", position=Vec3(0, 0, -0.01), scale=2.8, color=color.rgb32(10, 45, 25), origin=(0, 0))
        self.boost_pad_entities[(x, y)] = pad_ent
        return pad_ent

    def remove_boost_pad(self, x: int, y: int) -> bool:
        if (x, y) in self.boost_pad_entities:
            destroy(self.boost_pad_entities.pop((x, y)))
            return True
        return False

    def clear_all_terrain_modifiers(self):
        for ent in self.oil_spill_entities.values(): destroy(ent)
        self.oil_spill_entities.clear()
        for ent in self.boost_pad_entities.values(): destroy(ent)
        self.boost_pad_entities.clear()

    def rebuild_for_new_zone(self, new_graph: WarehouseGraph100):
        from src.config import MODEL_PATH_SHELF_EMPTY, MODEL_PATH_SHELF_OCCUPIED
        from src.environment.interactive_shelf import InteractiveShelf

        for shelf in list(self.interactive_shelves.values()):
            if shelf.visual_entity: destroy(shelf.visual_entity)
            destroy(shelf)
        self.interactive_shelves.clear()

        if self.static_racks_parent: destroy(self.static_racks_parent)
        self.static_racks_parent = Entity()

        if self.static_walls_parent: destroy(self.static_walls_parent)
        if self.static_wall_trims_parent: destroy(self.static_wall_trims_parent)

        self.clear_all_dynamic_obstacles()
        self.clear_all_terrain_modifiers()
        self.clear_exploration_heatmap()

        # 4. Terapkan graf baru & sinkronkan 3 Forklift
        self.graph = new_graph
        if hasattr(self, 'forklifts') and self.forklifts:
            spawn_coords = [(17, 11), (5, 7), (23, 20)]
            for i, fl in enumerate(self.forklifts):
                fl.graph = new_graph
                fl.reset_position(spawn_coords[i % len(spawn_coords)])
        elif self.forklift:
            self.forklift.graph = new_graph
            self.forklift.reset_position((17, 11))

        for sdata in self.graph.shelves.values():
            world_pos = grid_to_world(sdata.x, sdata.y, 0.0)
            vis_ent = Entity(parent=self.static_racks_parent, model=MODEL_PATH_SHELF_OCCUPIED if sdata.has_cargo else MODEL_PATH_SHELF_EMPTY, position=world_pos, scale=Vec3(0.88, 1.0, 0.88), shader=lit_with_shadows_shader)
            vis_ent.cast_shadows = True
            shelf_ent = InteractiveShelf(shelf_data=sdata, visual_entity=vis_ent)
            self.interactive_shelves[sdata.coord] = shelf_ent

        wall_color_modern = color.rgb32(53, 69, 77) 
        trim_color_modern = color.rgb32(143, 161, 166)

        self.static_walls_parent = Entity(color=wall_color_modern, shader=lit_with_shadows_shader)
        self.static_walls_parent.cast_shadows = True
        self.static_wall_trims_parent = Entity(color=trim_color_modern, shader=lit_with_shadows_shader)

        arena_w, arena_h = GRID_WIDTH + 2, GRID_HEIGHT + 2
        wall_h, wall_t = PERIMETER_WALL_HEIGHT, 0.5
        col_perim = color.rgb32(46, 60, 67)
        internal_wall_h = WALL_HEIGHT

        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, -arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(-arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h), color=col_perim)

        for y in range(self.graph.height):
            for x in range(self.graph.width):
                if self.graph.grid[y, x] == CellType.WALL:
                    pos = grid_to_world(x, y, internal_wall_h / 2.0)
                    Entity(parent=self.static_walls_parent, model='cube', position=pos, scale=Vec3(0.98, internal_wall_h, 0.98), color=wall_color_modern)
                    Entity(parent=self.static_wall_trims_parent, model='cube', position=pos + Vec3(0, 1.05, 0), scale=Vec3(0.98, 0.12, 0.98))

        self.static_walls_parent.combine(auto_destroy=True)
        self.static_wall_trims_parent.combine(auto_destroy=True)

        if self.sun and self.floor:
            self.sun.update_bounds(self.floor)