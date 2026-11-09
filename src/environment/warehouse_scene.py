"""
warehouse_scene.py
==================
Konstruksi lingkungan 3D arena gudang 50x50 dengan 3 teknik optimasi ekstrem:
1. Floor Optimization (Procedural Texture Tiling pada 1 Single Plane raksasa).
2. Static Mesh Combining (Menggabungkan ratusan visual rak & dinding menjadi single mesh).
3. Asynchronous Loading (Generator coroutine dengan yield dan loading screen di tengah layar).
"""

from typing import Callable, Dict, List, Optional, Tuple
from PIL import Image
from ursina import (
    Entity,
    Vec3,
    Vec2,
    color,
    camera,
    window,
    EditorCamera,
    DirectionalLight,
    AmbientLight,
    Texture,
    Text,
    destroy,
)

from src.config import (
    GRID_WIDTH,
    GRID_HEIGHT,
    SPAWN_ALPHA,
    SPAWN_BETA,
    grid_to_world,
    COLOR_ALPHA_PRIMARY,
    COLOR_BETA_PRIMARY,
    COLOR_SHELF_FRAME,
    COLOR_SHELF_BEAM,
    COLOR_WALL,
    COLOR_WALL_TRIM,
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
    Pengelola lingkungan 3D gudang skala besar dengan pemuatan asinkron (generator coroutine)
    dan static mesh combining.
    """

    def __init__(self, graph: WarehouseGraph100, on_complete: Optional[Callable[[], None]] = None):
        super().__init__()
        self.graph = graph
        self.on_complete_callback = on_complete

        self.interactive_shelves: Dict[Coord, InteractiveShelf] = {}
        self.free_cam: Optional[EditorCamera] = None
        self.current_cam_mode = "isometrik"
        self.cam_modes = ["isometrik", "topdown", "follow_alpha", "follow_beta", "bebas"]
        self.cam_mode_idx = 0

        # Kontainer static mesh combining
        self.static_racks_parent: Optional[Entity] = None
        self.static_beams_parent: Optional[Entity] = None
        self.static_walls_parent: Optional[Entity] = None
        self.static_wall_trims_parent: Optional[Entity] = None
        self.floor: Optional[Entity] = None

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
            text="MEMUAT ARENA 50x50... MOHON TUNGGU",
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

        self._update_progress("Membangun Lantai Tiled 50x50 (Single-Plane Texture)...", 0.12)
        grid_tex = _create_procedural_grid_texture(64)

        # SATU plane raksasa untuk seluruh 10.000 sel (Shader-level Texture Tiling)
        self.floor = Entity(
            model='plane',
            position=Vec3(0, 0, 0),
            scale=Vec3(GRID_WIDTH, 1, GRID_HEIGHT),
            texture=grid_tex,
            texture_scale=Vec2(GRID_WIDTH, GRID_HEIGHT),
        )
        yield

        # =====================================================================
        # TAHAP 2: SPAWN VISUAL RAK & SEPARATED COLLIDERS SECARA BATCH
        # =====================================================================
        # =====================================================================
        # TAHAP 2: SPAWN VISUAL RAK 3D (.OBJ BERTEKSTUR) & COLLIDERS
        # =====================================================================
        self._update_progress("Menyiapkan Model 3D Rak & Aset...", 0.18)
        from src.config import MODEL_PATH_SHELF_EMPTY, MODEL_PATH_SHELF_OCCUPIED
        self.static_racks_parent = Entity()
        yield

        all_shelves: List[ShelfData] = list(self.graph.shelves.values())
        total_shelves = len(all_shelves)
        batch_size = 350

        for i in range(0, total_shelves, batch_size):
            batch = all_shelves[i:i + batch_size]
            for sdata in batch:
                world_pos = grid_to_world(sdata.x, sdata.y, 0.0)

                # 1. Model visual 3D bertekstur (empty vs occupied)
                vis_ent = Entity(
                    parent=self.static_racks_parent,
                    model=MODEL_PATH_SHELF_OCCUPIED if sdata.has_cargo else MODEL_PATH_SHELF_EMPTY,
                    position=world_pos,
                    scale=Vec3(0.88, 1.0, 0.88),
                )

                # 2. Separated Collider Box (InteractiveShelf murni untuk raycasting)
                shelf_ent = InteractiveShelf(shelf_data=sdata, visual_entity=vis_ent)
                self.interactive_shelves[sdata.coord] = shelf_ent

            pct = 0.20 + (0.50 * (min(i + batch_size, total_shelves) / total_shelves))
            self._update_progress(f"Menyusun Blok Rak Palet [{min(i + batch_size, total_shelves)}/{total_shelves}]...", pct)
            yield

        # =====================================================================
        # TAHAP 3: FINALISASI RAK
        # =====================================================================
        self._update_progress("Mengonfigurasi Pemandangan Rak 3D...", 0.75)
        yield

        # =====================================================================
        # TAHAP 4: SPAWN DINDING & COMBINE STATIS
        # =====================================================================
        self._update_progress("Membangun Dinding Luar & Sekat Partisi Labirin...", 0.82)
        self.static_walls_parent = Entity(color=color.rgb32(*COLOR_WALL))
        self.static_wall_trims_parent = Entity(color=color.rgb32(*COLOR_WALL_TRIM))

        # 4 Dinding Pembatas Luar
        arena_w = GRID_WIDTH + 2
        arena_h = GRID_HEIGHT + 2
        wall_h = 2.4
        wall_t = 0.5
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t))
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(0, wall_h / 2, -arena_h / 2), scale=Vec3(arena_w, wall_h, wall_t))
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h))
        Entity(parent=self.static_walls_parent, model='cube', position=Vec3(-arena_w / 2, wall_h / 2, 0), scale=Vec3(wall_t, wall_h, arena_h))

        # List Trim Kuning Keselamatan Atas Dinding Luar
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(0, wall_h + 0.05, arena_h / 2), scale=Vec3(arena_w, 0.1, wall_t * 1.05))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(0, wall_h + 0.05, -arena_h / 2), scale=Vec3(arena_w, 0.1, wall_t * 1.05))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(arena_w / 2, wall_h + 0.05, 0), scale=Vec3(wall_t * 1.05, 0.1, arena_h))
        Entity(parent=self.static_wall_trims_parent, model='cube', position=Vec3(-arena_w / 2, wall_h + 0.05, 0), scale=Vec3(wall_t * 1.05, 0.1, arena_h))

        # Sekat Partisi Labirin (Cul-de-Sacs)
        for y in range(self.graph.height):
            for x in range(self.graph.width):
                if self.graph.grid[y, x] == CellType.WALL:
                    pos = grid_to_world(x, y, 1.0)
                    Entity(
                        parent=self.static_walls_parent,
                        model='cube',
                        position=pos,
                        scale=Vec3(0.98, 2.0, 0.98),
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
        # TAHAP 5: STASIUN DOCKING STATIS & KAMERA
        # =====================================================================
        self._update_progress("Menyiapkan Stasiun Docking & Preset Kamera...", 0.95)
        self._build_dock_stations()
        self._setup_camera()
        yield

        # =====================================================================
        # TAHAP 6: SELESAI & HAPUS LOADING SCREEN
        # =====================================================================
        self._update_progress("Arena 50x50 Siap!", 1.0)
        yield

        destroy(self.loading_backdrop)

        if self.on_complete_callback:
            self.on_complete_callback()

    def update(self):
        """Memajukan proses loading generator setiap frame render."""
        if self._async_loader:
            try:
                next(self._async_loader)
            except StopIteration:
                self._async_loader = None

    def _setup_lighting(self):
        """Pencahayaan 3D industrial bergradasi dengan dual-directional highlight."""
        window.color = color.rgb32(20, 25, 34)
        AmbientLight(color=color.rgba(0.78, 0.80, 0.86, 1.0))

        # Key Light (Warm Sunlight)
        sun = DirectionalLight(shadows=False)
        sun.color = color.rgba(0.92, 0.90, 0.86, 1.0)
        sun.look_at(Vec3(0.6, -1.2, 0.7))

        # Fill Light (Cool Industrial Floodlight)
        fill = DirectionalLight(shadows=False)
        fill.color = color.rgba(0.40, 0.48, 0.62, 1.0)
        fill.look_at(Vec3(-0.6, -0.8, -0.6))

    def _build_dock_stations(self):
        """Stasiun pengisian dock pojok kiri bawah dengan aksen neon bergradasi."""
        dock_tower_model = AssetLoader.get_dock_model()

        # Dock Alpha (A*) di (1, 1)
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

    def _setup_camera(self):
        """Kamera multi-mode terpusat grid 50x50."""
        camera.fov = CAMERA_PRESETS["isometrik"]["fov"]
        self.free_cam = EditorCamera(enabled=False)
        self.apply_camera_mode("isometrik")

    def apply_camera_mode(self, mode: str, target_robot_pos: Optional[Vec3] = None):
        """Mengubah sudut pandang kamera dengan stabilisasi rotasi penuh (anti-gimbal lock)."""
        from ursina import scene
        self.current_cam_mode = mode

        # Selalu pastikan kamera terlepas dari free_cam saat beralih ke mode tetap
        if self.free_cam and mode != "bebas":
            self.free_cam.disable()
            camera.parent = scene

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

        elif mode == "bebas":
            if self.free_cam:
                self.free_cam.position = camera.position
                self.free_cam.rotation = camera.rotation
                self.free_cam.enable()

    def cycle_camera_mode(self, target_robot_pos: Optional[Vec3] = None) -> str:
        """Siklus pergantian sudut kamera."""
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
