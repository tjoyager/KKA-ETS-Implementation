"""
interactive_shelf.py
====================
Entitas 3D Rak Penyimpanan Gudang Interaktif berbasis Ursina Engine.
Dioptimasi dengan pemisahan komponen:
1. Model visual rak dilebur ke dalam static combined mesh di level scene.
2. InteractiveShelf hanya bertindak sebagai invisible Collider Box yang sangat ringan (zero-draw-call).
3. Mendukung raycasting point-and-click, hover aura, marker seleksi dinamis, dan kargo aktif.
"""

from ursina import Entity, Vec3, color, Cylinder
from src.config import (
    grid_to_world,
    COLOR_SHELF_PICKUP,
    COLOR_SHELF_DROPOFF,
    COLOR_CARGO_BOX,
    COLOR_CARGO_PRIORITY,
)
from src.cognition.warehouse_graph import ShelfData
from src.environment.asset_loader import AssetLoader


class InteractiveShelf(Entity):
    """
    Entitas Collider Box Interaktif untuk Rak Gudang.
    Model visual rangka rak utama dilebur (combined) pada scene,
    sehingga entitas ini murni menangani raycasting dan visual seleksi/kargo tanpa membebani GPU.
    """

    def __init__(self, shelf_data: ShelfData, **kwargs):
        self.shelf_data = shelf_data

        # Posisi di tengah-tengah volume rak (tinggi 1.4m -> y=0.7)
        world_pos = grid_to_world(shelf_data.x, shelf_data.y, 0.7)

        super().__init__(
            position=world_pos,
            scale=Vec3(0.92, 1.4, 0.92),
            collider='box',
            visible=False,  # Invisible collider: 0 draw-calls untuk rangka statis!
            **kwargs,
        )

        self.interactive_type = "shelf"

        # 1. Kotak sorot hover semi-transparan kuning terang
        self.highlight_box = Entity(
            parent=self,
            model='cube',
            position=Vec3(0, 0, 0),
            scale=Vec3(1.04, 1.04, 1.04),
            color=color.rgba32(255, 235, 59, 100),
            enabled=False,
        )

        # 2. Cincin visual seleksi di atas rak (Cyan untuk Pick-up, Magenta untuk Drop-off)
        self.selection_ring = Entity(
            parent=self,
            model=Cylinder(resolution=16),
            position=Vec3(0, 0.52, 0),
            scale=Vec3(1.15, 0.08, 1.15),
            color=color.rgb32(*COLOR_SHELF_PICKUP),
            enabled=False,
        )

        # 3. Kargo aktif di atas rak (jika rak memiliki barang)
        self.cargo_entity: Entity = None
        if shelf_data.has_cargo:
            self._create_cargo_visual()

        # Status seleksi
        self.is_selected_pickup: bool = False
        self.is_selected_dropoff: bool = False
        self.is_hovered: bool = False

    def _create_cargo_visual(self):
        """Membuat model kargo individual dengan collider agar dapat dideteksi kursor."""
        cargo_col = color.rgb32(*COLOR_CARGO_PRIORITY) if "Lithium" in self.shelf_data.cargo_item else color.rgb32(*COLOR_CARGO_BOX)
        self.cargo_entity = Entity(
            parent=self,
            model=AssetLoader.get_cargo_model(),
            position=Vec3(0, -0.22, 0),
            scale=Vec3(0.65, 0.45, 0.65),
            color=cargo_col,
            collider='box',
        )
        self.cargo_entity.interactive_type = "cargo"
        self.cargo_entity.shelf_owner = self

    def set_hover(self, hovered: bool):
        """Menampilkan atau menyembunyikan efek sorot saat mouse melintas."""
        if self.is_selected_pickup or self.is_selected_dropoff:
            return

        self.is_hovered = hovered
        self.highlight_box.enabled = hovered

    def mark_as_pickup(self, active: bool = True):
        """Menandai rak ini sebagai titik jemput kargo (Pick-up Node)."""
        self.is_selected_pickup = active
        self.is_selected_dropoff = False
        if active:
            self.selection_ring.enabled = True
            self.selection_ring.color = color.rgb32(*COLOR_SHELF_PICKUP)
            self.highlight_box.enabled = True
            self.highlight_box.color = color.rgba32(0, 229, 255, 90)
        else:
            self.selection_ring.enabled = False
            self.highlight_box.enabled = False
            self.highlight_box.color = color.rgba32(255, 235, 59, 100)

    def mark_as_dropoff(self, active: bool = True):
        """Menandai rak ini sebagai titik antar tujuan kargo (Drop-off Node)."""
        self.is_selected_dropoff = active
        self.is_selected_pickup = False
        if active:
            self.selection_ring.enabled = True
            self.selection_ring.color = color.rgb32(*COLOR_SHELF_DROPOFF)
            self.highlight_box.enabled = True
            self.highlight_box.color = color.rgba32(224, 64, 251, 90)
        else:
            self.selection_ring.enabled = False
            self.highlight_box.enabled = False
            self.highlight_box.color = color.rgba32(255, 235, 59, 100)

    def clear_selection(self):
        """Mereset seluruh penanda seleksi."""
        self.is_selected_pickup = False
        self.is_selected_dropoff = False
        self.is_hovered = False
        self.selection_ring.enabled = False
        self.highlight_box.enabled = False
        self.highlight_box.color = color.rgba32(255, 235, 59, 100)

    def remove_cargo(self) -> str:
        """Mengambil kargo dari rak (saat AGV tiba untuk pick-up)."""
        item_name = self.shelf_data.cargo_item
        self.shelf_data.has_cargo = False
        self.shelf_data.cargo_item = ""
        if self.cargo_entity:
            self.cargo_entity.enabled = False
        return item_name

    def place_cargo(self, item_name: str = "Delivered Package"):
        """Menaruh kargo ke rak (saat AGV tiba untuk drop-off)."""
        self.shelf_data.has_cargo = True
        self.shelf_data.cargo_item = item_name
        if self.cargo_entity:
            self.cargo_entity.enabled = True
        else:
            self._create_cargo_visual()
