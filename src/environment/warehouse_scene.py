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
    DEFAULT_GOAL,
    grid_to_world,
    COLOR_ALPHA_PRIMARY,
    COLOR_BETA_PRIMARY,
    COLOR_WALL,
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
    Warna dasar beton gelap dengan garis tepi lorong keselamatan presisi.
    """
    img = Image.new("RGBA", (resolution, resolution), color=(26, 30, 38, 255))
    border_col = (48, 56, 70, 255)

    for i in range(resolution):
        img.putpixel((i, 0), border_col)
        img.putpixel((i, resolution - 1), border_col)
        img.putpixel((0, i), border_col)
        img.putpixel((resolution - 1, i), border_col)

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
        self.cam_modes = ["isometrik", "topdown", "follow_alpha", "follow_beta", "bebas"]
        self.cam_mode_idx = 0

        # Kontainer static mesh combining
        self.static_racks_parent: Optional[Entity] = None
        self.static_walls_parent: Optional[Entity] = None
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

        # SATU plane raksasa untuk seluruh sel 35x25 (Shader-level Texture Tiling)
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

                # 1. Model visual statis
                vis_ent = Entity(
                    parent=self.static_racks_parent,
                    model=MODEL_PATH_SHELF_OCCUPIED if sdata.has_cargo else MODEL_PATH_SHELF_EMPTY,
                    position=world_pos,
                    scale=Vec3(0.88, 1.0, 0.88),
                )

                # 2. Separated Collider Box (InteractiveShelf untuk raycasting)
                shelf_ent = InteractiveShelf(shelf_data=sdata, visual_entity=vis_ent)
                self.interactive_shelves[sdata.coord] = shelf_ent

            pct = 0.20 + (0.50 * (min(i + batch_size, total_shelves) / max(total_shelves, 1)))
            self._update_progress(f"Menyusun Blok Rak Palet [{min(i + batch_size, total_shelves)}/{total_shelves}]...", pct)
            yield

        # =====================================================================
        # TAHAP 3: STATIC MESH COMBINING UNTUK RAK
        # =====================================================================
        self._update_progress("Menggabungkan Mesh Rak Statis (Combining Racks)...", 0.72)
        yield

        # =====================================================================
        # TAHAP 4: SPAWN RINTANGAN DINDING (WALL OBSTACLES) & PERIMETER
        # =====================================================================
        self._update_progress("Membangun Dinding Luar & Sekat Partisi Labirin...", 0.82)
        self.static_walls_parent = Entity()

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

        self._update_progress("Menggabungkan Mesh Dinding (Combining Walls)...", 0.90)
        yield
        self.static_walls_parent.combine(auto_destroy=True)
        yield

        # =====================================================================
        # TAHAP 5: STASIUN DOCKING (START) & TARGET GOAL
        # =====================================================================
        self._update_progress("Menyiapkan Stasiun Docking & Preset Kamera...", 0.95)
        self._build_dock_and_goal_stations()
        self._setup_camera()
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
        """Memajukan proses loading generator setiap frame render."""
        if self._async_loader:
            try:
                next(self._async_loader)
            except StopIteration:
                self._async_loader = None

    def _setup_lighting(self):
        """Pencahayaan 3D industrial terarah."""
        window.color = color.rgb32(18, 22, 28)
        AmbientLight(color=color.rgba(0.68, 0.68, 0.70, 1.0))
        sun = DirectionalLight(shadows=False)
        sun.look_at(Vec3(0.5, -1.2, 0.7))

    def _build_dock_and_goal_stations(self):
        """Membangun platform stasiun docking Start dan target Goal."""
        dock_model = AssetLoader.get_dock_model()

        # Dock Alpha (A* Search) di (1, 1)
        pos_a = grid_to_world(SPAWN_ALPHA[0], SPAWN_ALPHA[1], 0.0)
        Entity(
            model=dock_model,
            position=pos_a,
            scale=Vec3(0.65, 0.65, 0.65),
        )
        Text(
            text="DOCK ALPHA\n(A* Search)",
            position=pos_a + Vec3(0, 1.8, 0),
            scale=1.5,
            color=color.rgb32(*COLOR_ALPHA_PRIMARY),
            billboard=True,
            origin=(0, 0),
        )

        # Dock Beta (GBFS) di (1, 3)
        pos_b = grid_to_world(SPAWN_BETA[0], SPAWN_BETA[1], 0.0)
        Entity(
            model=dock_model,
            position=pos_b,
            scale=Vec3(0.65, 0.65, 0.65),
        )
        Text(
            text="DOCK BETA\n(GBFS)",
            position=pos_b + Vec3(0, 1.8, 0),
            scale=1.5,
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

    def _setup_camera(self):
        """Kamera multi-mode terpusat pada arena 35x25."""
        camera.fov = CAMERA_PRESETS["isometrik"]["fov"]
        self.free_cam = EditorCamera(enabled=False)
        self.apply_camera_mode("isometrik")

    def apply_camera_mode(self, mode: str):
        """Mengatur posisi dan sudut pandang kamera."""
        self.current_cam_mode = mode
        center_target = Vec3(0, 0, 0)

        if mode == "isometrik":
            self.free_cam.disable()
            cfg = CAMERA_PRESETS["isometrik"]
            camera.position = Vec3(*cfg["pos"])
            camera.fov = cfg["fov"]
            camera.look_at(center_target)

        elif mode == "topdown":
            self.free_cam.disable()
            cfg = CAMERA_PRESETS["topdown"]
            camera.position = Vec3(*cfg["pos"])
            camera.fov = cfg["fov"]
            camera.look_at(center_target)

        elif mode == "bebas":
            self.free_cam.enable()
            self.free_cam.position = camera.position
            self.free_cam.look_at(center_target)

    def cycle_camera_mode(self) -> str:
        """Siklus pergantian sudut kamera."""
        self.cam_mode_idx = (self.cam_mode_idx + 1) % len(self.cam_modes)
        mode = self.cam_modes[self.cam_mode_idx]
        self.apply_camera_mode(mode)
        return mode

    def update_follow_camera(self, target_pos: Vec3, offset: Tuple[float, float, float] = (0, 11.0, -13.0)):
        """Kamera mengekor posisi robot secara halus."""
        if "follow" in self.current_cam_mode:
            desired_pos = target_pos + Vec3(*offset)
            camera.position = Vec3(
                camera.position.x + (desired_pos.x - camera.position.x) * 0.1,
                desired_pos.y,
                camera.position.z + (desired_pos.z - camera.position.z) * 0.1,
            )
            camera.look_at(target_pos)
