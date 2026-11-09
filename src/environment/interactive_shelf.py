"""
interactive_shelf.py
====================
Entitas 3D Rak Penyimpanan Gudang Interaktif berbasis Ursina Engine.
Dioptimasi ekstrem dengan:
1. Model visual rak dilebur ke dalam static combined mesh di level scene.
2. InteractiveShelf hanya bertindak sebagai invisible Collider Box yang sangat ringan (zero-draw-call).
3. Menggunakan Singleton Selection Indicators (3 entitas global untuk seluruh 608 rak,
   menghemat 1.200+ scene graph entities).
4. Kargo tanpa collider terpisah (menghemat 340 raycast collision checks per frame).
"""

from typing import Optional
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
from src.config import MODEL_PATH_SHELF_EMPTY, MODEL_PATH_SHELF_OCCUPIED


class InteractiveShelf(Entity):
    """
    Entitas Collider Box Interaktif untuk Rak Gudang.
    Model visual rangka rak utama dilebur (combined) pada scene,
    sehingga entitas ini murni menangani raycasting dan visual seleksi/kargo tanpa membebani GPU.
    """
    _shared_hover_box: Optional[Entity] = None
    _shared_pickup_ring: Optional[Entity] = None
    _shared_dropoff_ring: Optional[Entity] = None
    _active_pickup_shelf: Optional["InteractiveShelf"] = None
    _active_dropoff_shelf: Optional["InteractiveShelf"] = None
    _active_hover_shelf: Optional["InteractiveShelf"] = None

    @classmethod
    def _get_hover_box(cls) -> Entity:
        if cls._shared_hover_box is None:
            cls._shared_hover_box = Entity(
                model='cube',
                scale=Vec3(0.92, 1.15, 0.92),
                color=color.rgba32(255, 235, 59, 100),
                enabled=False,
            )
        return cls._shared_hover_box

    @classmethod
    def _get_pickup_ring(cls) -> Entity:
        if cls._shared_pickup_ring is None:
            cls._shared_pickup_ring = Entity(
                model=Cylinder(resolution=16),
                scale=Vec3(1.15, 0.08, 1.15),
                color=color.rgb32(*COLOR_SHELF_PICKUP),
                enabled=False,
            )
        return cls._shared_pickup_ring

    @classmethod
    def _get_dropoff_ring(cls) -> Entity:
        if cls._shared_dropoff_ring is None:
            cls._shared_dropoff_ring = Entity(
                model=Cylinder(resolution=16),
                scale=Vec3(1.15, 0.08, 1.15),
                color=color.rgb32(*COLOR_SHELF_DROPOFF),
                enabled=False,
            )
        return cls._shared_dropoff_ring

    def __init__(self, shelf_data: ShelfData, **kwargs):
        self.shelf_data = shelf_data

        # Posisi di tengah-tengah volume rak (tinggi 1.4m -> y=0.7)
        world_pos = grid_to_world(shelf_data.x, shelf_data.y, 0.55)

        super().__init__(
            position=world_pos,
            scale=Vec3(0.88, 1.1, 0.88),
            collider='box',
            visible=False,  # Invisible collider: 0 draw-calls untuk rangka statis!
            **kwargs,
        )

        self.interactive_type = "shelf"

        # Kargo aktif di atas rak (jika rak memiliki barang)
        self.visual_entity = kwargs.get('visual_entity', None)
        self.cargo_entity: Optional[Entity] = None
        if shelf_data.has_cargo:
            self._create_cargo_visual()

        # Status seleksi
        self.is_selected_pickup: bool = False
        self.is_selected_dropoff: bool = False
        self.is_hovered: bool = False

    def _create_cargo_visual(self):
        """Membuat model kargo individual tanpa collider tambahan (collider rak sudah mencakup kargo)."""
        cargo_col = color.rgb32(*COLOR_CARGO_PRIORITY) if "Lithium" in self.shelf_data.cargo_item else color.rgb32(*COLOR_CARGO_BOX)
        self.cargo_entity = Entity(
            parent=self,
            model=AssetLoader.get_cargo_model(),
            position=Vec3(0, -0.22, 0),
            scale=Vec3(0.65, 0.45, 0.65),
            color=cargo_col,
            # Tanpa collider terpisah: menghemat 340 collider raycast checks per-frame!
        )
        self.cargo_entity.interactive_type = "cargo"
        self.cargo_entity.shelf_owner = self

    def set_hover(self, hovered: bool):
        """Menampilkan atau menyembunyikan efek sorot saat mouse melintas via Singleton Indicator."""
        if self.is_selected_pickup or self.is_selected_dropoff:
            return

        self.is_hovered = hovered
        box = self._get_hover_box()
        if hovered:
            box.position = self.position
            box.enabled = True
            InteractiveShelf._active_hover_shelf = self
        else:
            if InteractiveShelf._active_hover_shelf is self:
                box.enabled = False
                InteractiveShelf._active_hover_shelf = None

    def mark_as_pickup(self, active: bool = True):
        """Menandai rak ini sebagai titik jemput kargo (Pick-up Node)."""
        self.is_selected_pickup = active
        self.is_selected_dropoff = False
        ring = self._get_pickup_ring()
        if active:
            ring.position = self.position + Vec3(0, 0.60, 0)
            ring.enabled = True
            InteractiveShelf._active_pickup_shelf = self
            if InteractiveShelf._active_hover_shelf is self:
                self._get_hover_box().enabled = False
                InteractiveShelf._active_hover_shelf = None
        else:
            if InteractiveShelf._active_pickup_shelf is self:
                ring.enabled = False
                InteractiveShelf._active_pickup_shelf = None

    def mark_as_dropoff(self, active: bool = True):
        """Menandai rak ini sebagai titik antar tujuan kargo (Drop-off Node)."""
        self.is_selected_dropoff = active
        self.is_selected_pickup = False
        ring = self._get_dropoff_ring()
        if active:
            ring.position = self.position + Vec3(0, 0.60, 0)
            ring.enabled = True
            InteractiveShelf._active_dropoff_shelf = self
            if InteractiveShelf._active_hover_shelf is self:
                self._get_hover_box().enabled = False
                InteractiveShelf._active_hover_shelf = None
        else:
            if InteractiveShelf._active_dropoff_shelf is self:
                ring.enabled = False
                InteractiveShelf._active_dropoff_shelf = None

    def clear_selection(self):
        """Mereset seluruh penanda seleksi."""
        self.is_selected_pickup = False
        self.is_selected_dropoff = False
        self.is_hovered = False
        if InteractiveShelf._active_pickup_shelf is self:
            self._get_pickup_ring().enabled = False
            InteractiveShelf._active_pickup_shelf = None
        if InteractiveShelf._active_dropoff_shelf is self:
            self._get_dropoff_ring().enabled = False
            InteractiveShelf._active_dropoff_shelf = None
        if InteractiveShelf._active_hover_shelf is self:
            self._get_hover_box().enabled = False
            InteractiveShelf._active_hover_shelf = None

    def remove_cargo(self) -> str:
        """Mengambil kargo dari rak (saat AGV tiba untuk pick-up)."""
        item_name = self.shelf_data.cargo_item
        self.shelf_data.has_cargo = False
        self.shelf_data.cargo_item = ""
        if self.visual_entity:
            self.visual_entity.model = MODEL_PATH_SHELF_EMPTY
        if self.cargo_entity:
            self.cargo_entity.enabled = False
        return item_name

    def place_cargo(self, item_name: str = "Delivered Package"):
        """Menaruh kargo ke rak (saat AGV tiba untuk drop-off)."""
        self.shelf_data.has_cargo = True
        self.shelf_data.cargo_item = item_name
        if self.visual_entity:
            self.visual_entity.model = MODEL_PATH_SHELF_OCCUPIED
        if self.cargo_entity:
            self.cargo_entity.enabled = True
