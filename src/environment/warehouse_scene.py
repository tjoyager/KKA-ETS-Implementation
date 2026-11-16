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

from typing import Callable, Dict, List, Optional, Set, Tuple
from PIL import Image
from ursina import (
    Entity,
    Vec3,
    Vec2,
    color,
    camera,
    window,
    scene,
    held_keys,
    time as utime,
    EditorCamera,
    DirectionalLight,
    AmbientLight,
    Texture,
    Text,
    destroy,
    curve,
)
from ursina.shaders import lit_with_shadows_shader

from src.config import (
    GRID_WIDTH,
    GRID_HEIGHT,
    SPAWN_ALPHA,
    SPAWN_BETA,
    DEFAULT_GOAL,
    grid_to_world,
    COLOR_ALPHA_PRIMARY,
    COLOR_BETA_PRIMARY,
    COLOR_SHELF_FRAME,
    COLOR_SHELF_BEAM,
    COLOR_WALL,
    COLOR_WALL_TRIM,
    COLOR_PERIMETER_WALL,
    COLOR_GOAL_PAD,
    WALL_HEIGHT,
    PERIMETER_WALL_HEIGHT,
    CAMERA_PRESETS,
)
from src.cognition.warehouse_graph import WarehouseGraph100, CellType, ShelfData
from src.environment.asset_loader import AssetLoader
from src.environment.interactive_shelf import InteractiveShelf

Coord = Tuple[int, int]


def _create_procedural_grid_texture(resolution: int = 64) -> Texture:
    """
    Membuat tekstur petak lantai gudang prosedural beresolusi tinggi menggunakan PIL.
    Warna dasar beton epoksi modern dengan garis tepi lorong keselamatan presisi.
    """
    img = Image.new("RGBA", (resolution, resolution), color=(30, 36, 46, 255))
    border_col = (62, 74, 94, 255)
    dot_col = (46, 54, 68, 255)

    for i in range(resolution):
        # 2px border for high-contrast crisp grid lines
        for w in (0, 1, resolution - 2, resolution - 1):
            img.putpixel((i, w), border_col)
            img.putpixel((w, i), border_col)

    # Subtle center crosshair guide marker
    mid = resolution // 2
    for d in (-2, -1, 0, 1, 2):
        img.putpixel((mid + d, mid), dot_col)
        img.putpixel((mid, mid + d), dot_col)

    return Texture(img)


class WarehouseScene(Entity):
    """
    Pengelola lingkungan 3D gudang skala 35x25 dengan pemuatan asinkron (generator coroutine),
    static mesh combining balok dinding beton dan rak, serta kontrol kamera.
    """

    def __init__(self, graph: WarehouseGraph100, on_complete: Optional[Callable[[], None]] = None):
        super().__init__()
        self.graph = graph
        self.on_complete_callback = on_complete

        self.interactive_shelves: Dict[Coord, InteractiveShelf] = {}
        self.free_cam: Optional[EditorCamera] = None
        self.current_cam_mode = "isometrik"
        self.cam_modes = ["isometrik", "topdown", "free_cam"]
        self.cam_mode_idx = 0

        # Kontainer static mesh combining
        self.static_racks_parent: Optional[Entity] = None
        self.static_beams_parent: Optional[Entity] = None
        self.static_walls_parent: Optional[Entity] = None
        self.static_wall_trims_parent: Optional[Entity] = None
        self.floor: Optional[Entity] = None

        # Kontainer visualisasi heatmap node exploration
        self.heatmap_parent: Optional[Entity] = None

        # Pencahayaan & Shadows
        self.sun: Optional[DirectionalLight] = None
        self.ambient: Optional[AmbientLight] = None

        # Kontainer rintangan dinamis (real-time user-placed obstacles)
        self.dynamic_obstacle_entities: Dict[Coord, Entity] = {}
        self.oil_spill_entities: Dict[Coord, Entity] = {}
        self.boost_pad_entities: Dict[Coord, Entity] = {}
        self.forklift = None

        # ---------------------------------------------------------------------
        # UI LOADING SCREEN DI TENGAH LAYAR
        # ---------------------------------------------------------------------
        self.loading_backdrop = Entity(
            parent=camera.ui,
            model='quad',
            scale=Vec3(2.5, 2.5, 1),
            color=color.rgba32(12, 15, 22, 245),
        )

        self.loading_title = Text(
            parent=self.loading_backdrop,
            text="MEMUAT ARENA 35x25... MOHON TUNGGU",
            position=Vec3(0, 0.08, -0.01),
            scale=1.5,
            color=color.rgb32(0, 229, 255),
            origin=(0, 0),
        )

        self.loading_status = Text(
            parent=self.loading_backdrop,
            text="Inisialisasi Sistem Renderer...",
            position=Vec3(0, -0.02, -0.01),
            scale=1.05,
            color=color.white,
            origin=(0, 0),
        )

        self.loading_bar_bg = Entity(
            parent=self.loading_backdrop,
            model='quad',
            position=Vec3(0, -0.10, -0.01),
            scale=Vec3(0.60, 0.03, 1),
            color=color.rgb32(35, 42, 54),
        )

        self.loading_bar_fill = Entity(
            parent=self.loading_bar_bg,
            model='quad',
            position=Vec3(-0.5, 0, -0.01),
            scale=Vec3(0.01, 1, 1),
            origin=(-0.5, 0),
            color=color.rgb32(46, 204, 113),
        )

        # Inisialisasi generator asinkron
        self._async_loader = self._build_scene_coroutine()

    def _update_progress(self, message: str, percent: float):
        """Memperbarui teks dan indikator progress bar pada loading screen."""
        self.loading_status.text = f"{message} ({int(percent * 100)}%)"
        self.loading_bar_fill.scale_x = max(0.01, min(1.0, percent))

    def _build_scene_coroutine(self):
        """
        Generator function pemuatan lingkungan gudang secara asinkron.
        Melakukan 'yield' di setiap tahapan agar jendela rendering tetap responsif.
        """
        # =====================================================================
        # TAHAP 1: PENCAHAYAAN & LANTAI PROSEDURAL TILED
        # =====================================================================
        self._update_progress("Menyiapkan Sistem Pencahayaan 3D...", 0.05)
        self._setup_lighting()
        yield

        self._update_progress("Membangun Lantai Tiled 35x25 (Single-Plane Texture)...", 0.12)
        grid_tex = _create_procedural_grid_texture(64)

        # SATU plane raksasa untuk seluruh sel 35x25 (Shader-level Texture Tiling & Shadows)
        self.floor = Entity(
            name='warehouse_floor',
            model='plane',
            position=Vec3(0, 0, 0),
            scale=Vec3(GRID_WIDTH, 1, GRID_HEIGHT),
            texture=grid_tex,
            texture_scale=Vec2(GRID_WIDTH, GRID_HEIGHT),
            collider='box',
            shader=lit_with_shadows_shader,
        )
        self.floor.receive_shadows = True
        if self.sun:
            self.sun.update_bounds(self.floor)
        yield

        # =====================================================================
        # TAHAP 2: SPAWN VISUAL RAK & SEPARATED COLLIDERS SECARA BATCH
        # =====================================================================
        # =====================================================================
        # TAHAP 2: SPAWN VISUAL RAK 3D (.OBJ BERTEKSTUR) & COLLIDERS
        # =====================================================================
        self._update_progress("Menyiapkan Model 3D Rak & Aset...", 0.18)
        shelf_empty_model = AssetLoader.get_shelf_empty_model()
        shelf_occupied_model = AssetLoader.get_shelf_occupied_model()
        self.static_racks_parent = Entity()
        yield

        all_shelves: List[ShelfData] = list(self.graph.shelves.values())
        total_shelves = len(all_shelves)
        batch_size = 150

        for i in range(0, total_shelves, batch_size):
            batch = all_shelves[i:i + batch_size]
            for sdata in batch:
                world_pos = grid_to_world(sdata.x, sdata.y, 0.0)

                # 1. Model visual 3D bertekstur (empty vs occupied) dengan bayangan
                vis_ent = Entity(
                    parent=self.static_racks_parent,
                    model=shelf_occupied_model if sdata.has_cargo else shelf_empty_model,
                    position=world_pos,
                    scale=Vec3(0.88, 1.0, 0.88),
                    shader=lit_with_shadows_shader,
                )
                vis_ent.cast_shadows = True

                # 2. Separated Collider Box (InteractiveShelf untuk raycasting)
                shelf_ent = InteractiveShelf(shelf_data=sdata, visual_entity=vis_ent)
                self.interactive_shelves[sdata.coord] = shelf_ent

            pct = 0.20 + (0.50 * (min(i + batch_size, total_shelves) / max(total_shelves, 1)))
            self._update_progress(f"Menyusun Blok Rak Palet [{min(i + batch_size, total_shelves)}/{total_shelves}]...", pct)
            yield

        # =====================================================================
        # TAHAP 3: FINALISASI RAK
        # =====================================================================
        self._update_progress("Mengonfigurasi Pemandangan Rak 3D...", 0.75)
        yield

        # =====================================================================
        # TAHAP 4: SPAWN RINTANGAN DINDING (WALL OBSTACLES) & PERIMETER
        # =====================================================================
        self._update_progress("Membangun Dinding Luar & Sekat Partisi Labirin...", 0.82)
        self.static_walls_parent = Entity(color=color.rgb32(*COLOR_WALL), shader=lit_with_shadows_shader)
        self.static_walls_parent.cast_shadows = True
        self.static_wall_trims_parent = Entity(color=color.rgb32(*COLOR_WALL_TRIM), shader=lit_with_shadows_shader)

        # 1. Empat Dinding Pembatas Luar Arena (Perimeter Walls)
        arena_w = GRID_WIDTH + 2
        arena_h = GRID_HEIGHT + 2
        wall_h = PERIMETER_WALL_HEIGHT
        wall_t = 0.5
        col_perim = color.rgb32(*COLOR_PERIMETER_WALL)

        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, -arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(-arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h), color=col_perim)

        # 2. Rintangan Dinding Internal (Wall Obstacles & Sekat Cul-de-Sac)
        # Menggunakan balok cube abu-abu beton kontras dan tinggi 2.0 (lebih tinggi dari rak ~1.0)
        col_wall = color.rgb32(*COLOR_WALL)
        internal_wall_h = WALL_HEIGHT

        # List Trim Kuning Keselamatan Atas Dinding Luar
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(0, wall_h + 0.05, arena_h / 2), scale=Vec3(arena_w, 0.1, wall_t * 1.05))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(0, wall_h + 0.05, -arena_h / 2), scale=Vec3(arena_w, 0.1, wall_t * 1.05))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(arena_w / 2, wall_h + 0.05, 0), scale=Vec3(wall_t * 1.05, 0.1, arena_h))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(-arena_w / 2, wall_h + 0.05, 0), scale=Vec3(wall_t * 1.05, 0.1, arena_h))

        # Sekat Partisi Labirin (Cul-de-Sacs)
        for y in range(self.graph.height):
            for x in range(self.graph.width):
                if self.graph.grid[y, x] == CellType.WALL:
                    pos = grid_to_world(x, y, internal_wall_h / 2.0)
                    Entity(
                        parent=self.static_walls_parent,
                        model='cube',
                        position=pos,
                        scale=Vec3(0.98, internal_wall_h, 0.98),
                        color=col_wall,
                    )
                    # Hazard yellow safety top cap
                    Entity(
                        parent=self.static_wall_trims_parent,
                        model='cube',
                        position=pos + Vec3(0, 1.05, 0),
                        scale=Vec3(0.98, 0.12, 0.98),
                    )

        self._update_progress("Menggabungkan Mesh Dinding (Combining Walls)...", 0.90)
        yield
        self.static_walls_parent.combine(auto_destroy=True)
        self.static_wall_trims_parent.combine(auto_destroy=True)
        yield

        # =====================================================================
        # TAHAP 5: STASIUN DOCKING (START) & TARGET GOAL
        # =====================================================================
        self._update_progress("Menyiapkan Stasiun Docking, Forklift & Kamera...", 0.95)
        self._build_dock_and_goal_stations()
        self._setup_camera()

        from src.behavior.forklift_controller import ForkliftController
        self.forklift = ForkliftController(graph=self.graph)
        yield

        # =====================================================================
        # TAHAP 6: SELESAI & HAPUS LOADING SCREEN
        # =====================================================================
        self._update_progress("Arena 35x25 Siap!", 1.0)
        yield

        destroy(self.loading_backdrop)

        if self.on_complete_callback:
            self.on_complete_callback()

    def update(self):
        """Memajukan proses loading generator setiap frame render dan menangani navigasi Free-Cam."""
        if self._async_loader:
            try:
                next(self._async_loader)
            except StopIteration:
                self._async_loader = None

        # Navigasi kamera bebas (God Mode)
        if self.current_cam_mode in ("free_cam", "bebas") and self.free_cam and self.free_cam.enabled:
            from ursina import held_keys, time as utime
            fly_speed = 18.0 * (2.2 if held_keys['shift'] else 1.0)
            if held_keys['up arrow']:
                self.free_cam.position += self.free_cam.forward * fly_speed * utime.dt
            if held_keys['down arrow']:
                self.free_cam.position -= self.free_cam.forward * fly_speed * utime.dt
            if held_keys['right arrow']:
                self.free_cam.position += self.free_cam.right * fly_speed * utime.dt
            if held_keys['left arrow']:
                self.free_cam.position -= self.free_cam.right * fly_speed * utime.dt
            if held_keys['page up'] or held_keys['e']:
                self.free_cam.position += Vec3(0, 1, 0) * fly_speed * utime.dt
            if held_keys['page down'] or held_keys['q']:
                self.free_cam.position -= Vec3(0, 1, 0) * fly_speed * utime.dt

    def _setup_lighting(self):
        """Pencahayaan 3D industrial dengan spotlight lampu sorot gudang & bayangan tajam."""
        window.color = color.rgb32(20, 25, 34)

        # Ambient light terkalibrasi agar area berbayang tidak menjadi hitam pekat
        self.ambient = AmbientLight(color=color.rgba(0.42, 0.44, 0.50, 1.0))

        # Spotlight utama gudang dari langit-langit (rotasi & posisi sudut sorot realistis)
        self.sun = DirectionalLight(shadow_map_resolution=Vec2(2048, 2048), shadows=True)
        self.sun.color = color.rgba(0.96, 0.94, 0.90, 1.0)
        self.sun.position = Vec3(-12, 28, -14)
        self.sun.look_at(Vec3(0, 0, 0))

        # Cahaya pengisi lembut (fill light) aksen industrial
        fill = DirectionalLight(shadows=False)
        fill.color = color.rgba(0.20, 0.24, 0.32, 1.0)
        fill.look_at(Vec3(0.6, -0.8, 0.6))

        # Konfigurasi bias bayangan lembut & warna bayangan realistis
        lit_with_shadows_shader.default_input['shadow_bias'] = 0.002
        lit_with_shadows_shader.default_input['shadow_color'] = color.rgba(0.10, 0.12, 0.18, 0.60)
        lit_with_shadows_shader.default_input['shadow_blur'] = 0.004

    def _build_dock_and_goal_stations(self):
        """Stasiun pengisian dock pojok kiri bawah dengan aksen neon bergradasi dan platform target Goal."""
        dock_tower_model = AssetLoader.get_dock_model()

        # Dock Alpha (A* Search) di (1, 1)
        pos_a = grid_to_world(SPAWN_ALPHA[0], SPAWN_ALPHA[1], 0.0)
        # Pad lantai parkir pengisian daya robot Alpha
        Entity(
            model='cube',
            position=pos_a - Vec3(0, 0.02, 0),
            scale=Vec3(1.4, 0.05, 1.4),
            color=color.rgba32(0, 195, 255, 160),
        )
        # Menara charger terminal di tepi dinding barat (belakang robot)
        Entity(
            model=dock_tower_model,
            position=pos_a + Vec3(-1.0, 0, 0),
            rotation=Vec3(0, 90, 0),
            scale=Vec3(0.55, 0.65, 0.55),
        )
        Text(
            text="DOCK ALPHA\n[A* Search]",
            position=pos_a + Vec3(-1.0, 1.8, 0),
            scale=1.3,
            color=color.rgb32(*COLOR_ALPHA_PRIMARY),
            billboard=True,
            origin=(0, 0),
        )

        # Dock Beta (GBFS) di (1, 3)
        pos_b = grid_to_world(SPAWN_BETA[0], SPAWN_BETA[1], 0.0)
        # Pad lantai parkir pengisian daya robot Beta
        Entity(
            model='cube',
            position=pos_b - Vec3(0, 0.02, 0),
            scale=Vec3(1.4, 0.05, 1.4),
            color=color.rgba32(255, 140, 0, 160),
        )
        # Menara charger terminal di tepi dinding barat (belakang robot)
        Entity(
            model=dock_tower_model,
            position=pos_b + Vec3(-1.0, 0, 0),
            rotation=Vec3(0, 90, 0),
            scale=Vec3(0.55, 0.65, 0.55),
        )
        Text(
            text="DOCK BETA\n[GBFS]",
            position=pos_b + Vec3(-1.0, 1.8, 0),
            scale=1.3,
            color=color.rgb32(*COLOR_BETA_PRIMARY),
            billboard=True,
            origin=(0, 0),
        )

        # Platform Target Goal di pojok kanan atas (32, 21)
        pos_g = grid_to_world(DEFAULT_GOAL[0], DEFAULT_GOAL[1], 0.0)
        Entity(
            model='cube',
            position=pos_g + Vec3(0, 0.05, 0),
            scale=Vec3(0.94, 0.10, 0.94),
            color=color.rgb32(*COLOR_GOAL_PAD),
        )
        Entity(
            model='cube',
            position=pos_g + Vec3(0, 0.02, 0),
            scale=Vec3(1.10, 0.04, 1.10),
            color=color.rgb32(30, 40, 50),
        )
        Text(
            text="GOAL STATION\n(Delivery Point)",
            position=pos_g + Vec3(0, 1.8, 0),
            scale=1.5,
            color=color.rgb32(*COLOR_GOAL_PAD),
            billboard=True,
            origin=(0, 0),
        )

        # 3. Gerbang Transfer Antar-Zona (Fitur 2: Zone Transfer Gate)
        self._build_transfer_gate()

    def _build_transfer_gate(self):
        """Membangun visual Transfer Gate antar-zona (Fitur 2) di x=34, y=12..14."""
        pos_gate = grid_to_world(34, 13, 0.0)

        # Pad lantai gerbang bercahaya cyan
        Entity(
            model='cube',
            position=pos_gate + Vec3(0, 0.04, 0),
            scale=Vec3(1.2, 0.07, 3.4),
            color=color.rgba32(0, 229, 255, 200),
        )

        # Pilar Selatan
        Entity(
            model='cube',
            position=pos_gate + Vec3(0.25, 1.8, -1.75),
            scale=Vec3(0.6, 3.6, 0.6),
            color=color.rgb32(28, 38, 54),
            shader=lit_with_shadows_shader,
        )
        # Pilar Utara
        Entity(
            model='cube',
            position=pos_gate + Vec3(0.25, 1.8, 1.75),
            scale=Vec3(0.6, 3.6, 0.6),
            color=color.rgb32(28, 38, 54),
            shader=lit_with_shadows_shader,
        )
        # Balok Kusen Atas Portal
        Entity(
            model='cube',
            position=pos_gate + Vec3(0.25, 3.6, 0),
            scale=Vec3(0.7, 0.6, 4.1),
            color=color.rgb32(0, 229, 255),
        )
        # Efek Tirai Energi Portal Semi-Transparan
        Entity(
            model='cube',
            position=pos_gate + Vec3(0.25, 1.8, 0),
            scale=Vec3(0.08, 3.2, 3.1),
            color=color.rgba32(0, 229, 255, 95),
        )

        # Label Billboard Penunjuk Arah Transfer Gate
        Text(
            text="TRANSFER GATE\n>>> ZONE B >>>",
            position=pos_gate + Vec3(0, 4.4, 0),
            scale=1.5,
            color=color.rgb32(0, 229, 255),
            billboard=True,
            origin=(0, 0),
        )

    _build_dock_stations = _build_dock_and_goal_stations

    def _setup_camera(self):
        """Kamera multi-mode terpusat pada arena 35x25."""
        camera.fov = CAMERA_PRESETS["isometrik"]["fov"]
        self.free_cam = EditorCamera(enabled=False)
        self.apply_camera_mode("isometrik")

    def apply_camera_mode(self, mode: str, target_robot_pos: Optional[Vec3] = None):
        """Mengubah sudut pandang kamera dengan stabilisasi rotasi penuh (anti-gimbal lock)."""
        from ursina import scene
        self.current_cam_mode = mode
        is_free = (mode in ("free_cam", "bebas"))

        # Selalu pastikan kamera terlepas dari free_cam saat beralih ke mode tetap
        if self.free_cam and not is_free:
            self.free_cam.disable()
            camera.parent = scene
            # Aktifkan kembali kontrol WASD Forklift saat keluar dari Free-Cam
            if self.forklift:
                self.forklift.set_control_enabled(True)

        if mode == "isometrik":
            cfg = CAMERA_PRESETS["isometrik"]
            camera.rotation = Vec3(0, 0, 0)
            camera.position = Vec3(*cfg["pos"])
            camera.fov = cfg["fov"]
            camera.look_at(Vec3(*cfg["target"]))
            camera.rotation_z = 0.0

        elif mode == "topdown":
            cfg = CAMERA_PRESETS["topdown"]
            camera.position = Vec3(*cfg["pos"])
            camera.rotation = Vec3(90, 0, 0)
            camera.fov = cfg["fov"]
            camera.rotation_z = 0.0

        elif mode in ("follow_alpha", "follow_beta"):
            cfg = CAMERA_PRESETS.get(mode, {"offset": (0.0, 16.0, -14.0), "fov": 55})
            camera.fov = cfg.get("fov", 55)
            camera.rotation_z = 0.0
            if target_robot_pos is not None:
                offset = cfg.get("offset", (0.0, 16.0, -14.0))
                desired = target_robot_pos + Vec3(*offset)
                camera.position = Vec3(
                    max(-23.5, min(23.5, desired.x)),
                    desired.y,
                    max(-23.5, min(23.5, desired.z)),
                )
                camera.look_at(target_robot_pos)
                camera.rotation_z = 0.0

        elif mode in ("pov_alpha", "pov_beta"):
            camera.fov = 68
            camera.rotation_z = 0.0

        elif is_free:
            if self.free_cam:
                self.free_cam.position = camera.position
                self.free_cam.rotation = camera.rotation
                self.free_cam.enable()
            # Nonaktifkan kontrol WASD Forklift saat presenter menggunakan Free-Cam
            if self.forklift:
                self.forklift.set_control_enabled(False)

    def cycle_camera_mode(self, target_robot_pos: Optional[Vec3] = None) -> str:
        """Siklus pergantian sudut kamera (Isometrik -> Topdown -> Free-Cam)."""
        self.cam_mode_idx = (self.cam_mode_idx + 1) % len(self.cam_modes)
        mode = self.cam_modes[self.cam_mode_idx]
        self.apply_camera_mode(mode, target_robot_pos=target_robot_pos)
        return mode

    def update_follow_camera(self, target_pos: Vec3, offset: Tuple[float, float, float] = (0.0, 16.0, -14.0)):
        """Kamera mengekor posisi robot secara halus tanpa deviasi roll dan anti-tembus dinding."""
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
        """Kamera First-Person / Close Hood Chase Cam mengikuti kap robot AGV secara imersif."""
        if not robot:
            return
        target_ent = getattr(robot, 'visual_body', robot)
        if not target_ent:
            return

        cam_offset = -(target_ent.forward * 1.55) + Vec3(0, 0.95, 0)
        desired_pos = target_ent.position + cam_offset
        desired_look = target_ent.position + (target_ent.forward * 4.2) + Vec3(0, 0.35, 0)

        from ursina import time as utime
        camera.position = Vec3(
            camera.position.x + (desired_pos.x - camera.position.x) * min(1.0, utime.dt * 14.0),
            camera.position.y + (desired_pos.y - camera.position.y) * min(1.0, utime.dt * 14.0),
            camera.position.z + (desired_pos.z - camera.position.z) * min(1.0, utime.dt * 14.0),
        )
        camera.look_at(desired_look)
        camera.rotation_z = 0.0

    # =========================================================================
    # VISUALISASI HEATMAP KOMPUTASI EKSPLORASI NODE (A* VS GBFS)
    # =========================================================================
    def render_exploration_heatmap(
        self,
        alpha_nodes: Optional[Set[Coord]] = None,
        beta_nodes: Optional[Set[Coord]] = None,
    ):
        """
        Merender visualisasi lantai overlay eksplorasi node komputasi A* vs GBFS.
        - Merah/Pink transparan: Node yang dieksplorasi oleh A* (Robot Alpha).
        - Biru/Cyan transparan: Node yang dieksplorasi oleh GBFS (Robot Beta).
        - Ungu/Magenta transparan: Node yang dieksplorasi oleh KEDUA algoritma (Shared).
        Menggunakan batching combine(auto_destroy=True) untuk memadukan ratusan mesh quad
        menjadi 1-3 draw calls efisien, mempertahankan FPS rendering Ursina 60 FPS.
        """
        self.clear_exploration_heatmap()

        nodes_a = alpha_nodes or set()
        nodes_b = beta_nodes or set()

        if not nodes_a and not nodes_b:
            return

        shared_nodes = nodes_a & nodes_b
        alpha_only = nodes_a - shared_nodes
        beta_only = nodes_b - shared_nodes

        self.heatmap_parent = Entity(name="exploration_heatmap")

        # 1. Overlay Node Eksklusif A* (Merah/Pink Transparan)
        if alpha_only:
            p_alpha = Entity(
                parent=self.heatmap_parent,
                color=color.rgba32(245, 65, 120, 95),
            )
            for x, y in alpha_only:
                pos = grid_to_world(x, y, 0.015)
                Entity(
                    parent=p_alpha,
                    model='quad',
                    rotation_x=90,
                    position=pos,
                    scale=Vec3(0.92, 0.92, 1),
                )
            p_alpha.combine(auto_destroy=True)

        # 2. Overlay Node Eksklusif GBFS (Biru/Cyan Transparan)
        if beta_only:
            p_beta = Entity(
                parent=self.heatmap_parent,
                color=color.rgba32(0, 205, 255, 95),
            )
            for x, y in beta_only:
                pos = grid_to_world(x, y, 0.015)
                Entity(
                    parent=p_beta,
                    model='quad',
                    rotation_x=90,
                    position=pos,
                    scale=Vec3(0.92, 0.92, 1),
                )
            p_beta.combine(auto_destroy=True)

        # 3. Overlay Node Irisan Keduanya (Ungu/Magenta Transparan)
        if shared_nodes:
            p_shared = Entity(
                parent=self.heatmap_parent,
                color=color.rgba32(195, 75, 255, 125),
            )
            for x, y in shared_nodes:
                pos = grid_to_world(x, y, 0.016)
                Entity(
                    parent=p_shared,
                    model='quad',
                    rotation_x=90,
                    position=pos,
                    scale=Vec3(0.92, 0.92, 1),
                )
            p_shared.combine(auto_destroy=True)

    def clear_exploration_heatmap(self):
        """Menghapus dan melepaskan seluruh mesh entitas visual heatmap dari scene."""
        if hasattr(self, 'heatmap_parent') and self.heatmap_parent:
            destroy(self.heatmap_parent)
            self.heatmap_parent = None

    # =========================================================================
    # PENGELOLAAN RINTANGAN DINAMIS (DYNAMIC OBSTACLE PLACEMENT)
    # =========================================================================
    def spawn_dynamic_obstacle(self, x: int, y: int) -> Entity:
        """
        Membuat entitas 3D rintangan kotak kargo dinamis dengan animasi jatuh (drop bounce),
        efek bayangan (shadow casting), dan collider raycast.
        """
        target_pos = grid_to_world(x, y, 0.35)
        # Posisi awal mengambang di udara sebelum dijatuhkan
        spawn_pos = Vec3(target_pos.x, 2.6, target_pos.z)

        cargo_ent = Entity(
            parent=self,
            model=AssetLoader.get_cargo_model(),
            position=spawn_pos,
            scale=Vec3(0.82, 0.70, 0.82),
            color=color.rgb32(235, 145, 45),
            collider='box',
            shader=lit_with_shadows_shader,
        )
        cargo_ent.cast_shadows = True
        cargo_ent.receive_shadows = True
        cargo_ent.interactive_type = "dynamic_obstacle"
        cargo_ent.grid_coord = (x, y)

        # Animasi kargo dijatuhkan secara fisik ke lantai
        cargo_ent.animate_y(target_pos.y, duration=0.28, curve=curve.out_bounce)

        self.dynamic_obstacle_entities[(x, y)] = cargo_ent
        return cargo_ent

    def remove_dynamic_obstacle(self, x: int, y: int) -> bool:
        """Menghapus visual rintangan dinamis dari scene."""
        if (x, y) in self.dynamic_obstacle_entities:
            ent = self.dynamic_obstacle_entities.pop((x, y))
            destroy(ent)
            return True
        return False

    def clear_all_dynamic_obstacles(self):
        """Menghapus seluruh entitas rintangan dinamis di scene."""
        for ent in self.dynamic_obstacle_entities.values():
            destroy(ent)
        self.dynamic_obstacle_entities.clear()

    # =========================================================================
    # VISUALISASI MEDAN BERBOBOT (HAZARD OIL & SPEED BOOST PAD)
    # =========================================================================
    def spawn_hazard_oil(self, x: int, y: int) -> Entity:
        """Membuat visual genangan tumpahan oli kuning/emas mengkilap di lantai."""
        pos = grid_to_world(x, y, 0.02)
        oil_ent = Entity(
            parent=self,
            model='circle',
            rotation_x=90,
            position=pos,
            scale=Vec3(0.88, 0.88, 1),
            color=color.rgba32(235, 170, 20, 215),
            collider='box',
        )
        oil_ent.interactive_type = "hazard_oil"
        oil_ent.grid_coord = (x, y)
        self.oil_spill_entities[(x, y)] = oil_ent
        return oil_ent

    def remove_hazard_oil(self, x: int, y: int) -> bool:
        """Menghapus entitas visual tumpahan oli dari scene."""
        if (x, y) in self.oil_spill_entities:
            ent = self.oil_spill_entities.pop((x, y))
            destroy(ent)
            return True
        return False

    def spawn_boost_pad(self, x: int, y: int) -> Entity:
        """Membuat visual speed boost pad hijau neon bercahaya dengan tanda chevron di lantai."""
        pos = grid_to_world(x, y, 0.02)
        pad_ent = Entity(
            parent=self,
            model='quad',
            rotation_x=90,
            position=pos,
            scale=Vec3(0.90, 0.90, 1),
            color=color.rgba32(0, 245, 140, 220),
            collider='box',
        )
        pad_ent.interactive_type = "boost_pad"
        pad_ent.grid_coord = (x, y)
        # Indikator chevron visual arah cepat
        Text(
            parent=pad_ent,
            text=">>",
            position=Vec3(0, 0, -0.01),
            scale=2.8,
            color=color.rgb32(10, 45, 25),
            origin=(0, 0),
        )
        self.boost_pad_entities[(x, y)] = pad_ent
        return pad_ent

    def remove_boost_pad(self, x: int, y: int) -> bool:
        """Menghapus entitas visual boost pad dari scene."""
        if (x, y) in self.boost_pad_entities:
            ent = self.boost_pad_entities.pop((x, y))
            destroy(ent)
            return True
        return False

    def clear_all_terrain_modifiers(self):
        """Menghapus seluruh entitas tumpahan oli dan speed boost pad di scene."""
        for ent in self.oil_spill_entities.values():
            destroy(ent)
        self.oil_spill_entities.clear()
        for ent in self.boost_pad_entities.values():
            destroy(ent)
        self.boost_pad_entities.clear()

    # =========================================================================
    # REGENERASI PANGGUNG ANTAR-ZONA (ZONE TRANSFER REBUILD)
    # =========================================================================
    def rebuild_for_new_zone(self, new_graph: WarehouseGraph100):
        """
        Meregenerasi lingkungan 3D gudang secara instan untuk stage baru (Zone Transfer).
        Menghapus rak lama, membangun denah rintangan baru, dan menyinkronkan interaktivitas.
        """
        from src.config import MODEL_PATH_SHELF_EMPTY, MODEL_PATH_SHELF_OCCUPIED
        from src.environment.interactive_shelf import InteractiveShelf

        # 1. Bersihkan seluruh rak interaktif lama
        for shelf in list(self.interactive_shelves.values()):
            if shelf.visual_entity:
                destroy(shelf.visual_entity)
            destroy(shelf)
        self.interactive_shelves.clear()

        if self.static_racks_parent:
            destroy(self.static_racks_parent)
        self.static_racks_parent = Entity()

        # 2. Bersihkan sekat dinding internal lama
        if self.static_walls_parent:
            destroy(self.static_walls_parent)
        if self.static_wall_trims_parent:
            destroy(self.static_wall_trims_parent)

        # 3. Bersihkan rintangan dinamis kargo, modifier medan & heatmap eksplorasi
        self.clear_all_dynamic_obstacles()
        self.clear_all_terrain_modifiers()
        self.clear_exploration_heatmap()

        # 4. Terapkan graf baru & sinkronkan Forklift
        self.graph = new_graph
        if self.forklift:
            self.forklift.graph = new_graph
            self.forklift.reset_position((17, 11))

        # 5. Bangun rak-rak baru
        for sdata in self.graph.shelves.values():
            world_pos = grid_to_world(sdata.x, sdata.y, 0.0)
            vis_ent = Entity(
                parent=self.static_racks_parent,
                model=MODEL_PATH_SHELF_OCCUPIED if sdata.has_cargo else MODEL_PATH_SHELF_EMPTY,
                position=world_pos,
                scale=Vec3(0.88, 1.0, 0.88),
                shader=lit_with_shadows_shader,
            )
            vis_ent.cast_shadows = True
            shelf_ent = InteractiveShelf(shelf_data=sdata, visual_entity=vis_ent)
            self.interactive_shelves[sdata.coord] = shelf_ent

        # 6. Bangun dinding perimeter & partisi baru
        self.static_walls_parent = Entity(color=color.rgb32(*COLOR_WALL), shader=lit_with_shadows_shader)
        self.static_walls_parent.cast_shadows = True
        self.static_wall_trims_parent = Entity(color=color.rgb32(*COLOR_WALL_TRIM), shader=lit_with_shadows_shader)

        arena_w = GRID_WIDTH + 2
        arena_h = GRID_HEIGHT + 2
        wall_h = PERIMETER_WALL_HEIGHT
        wall_t = 0.5
        col_perim = color.rgb32(*COLOR_PERIMETER_WALL)
        col_wall = color.rgb32(*COLOR_WALL)
        internal_wall_h = WALL_HEIGHT

        # Perimeter luar
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, -arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h), color=col_perim)
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(-arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h), color=col_perim)

        # Partisi dinding baru sesuai graf
        for y in range(self.graph.height):
            for x in range(self.graph.width):
                if self.graph.grid[y, x] == CellType.WALL:
                    pos = grid_to_world(x, y, internal_wall_h / 2.0)
                    Entity(parent=self.static_walls_parent, model='cube', position=pos, scale=Vec3(0.98, internal_wall_h, 0.98), color=col_wall)
                    Entity(parent=self.static_wall_trims_parent, model='cube', position=pos + Vec3(0, 1.05, 0), scale=Vec3(0.98, 0.12, 0.98))

        self.static_walls_parent.combine(auto_destroy=True)
        self.static_wall_trims_parent.combine(auto_destroy=True)

        if self.sun and self.floor:
            self.sun.update_bounds(self.floor)
