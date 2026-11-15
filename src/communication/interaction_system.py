"""
interaction_system.py
=====================
Sistem Raycasting Mouse (Point-and-Click) dan State-Machine Seleksi Misi.
Mengeliminasi seluruh input terminal dan menangani interaktivitas 3D langsung:
Klik 1: Memilih rak kargo (Pick-up Node).
Klik 2: Memilih rak kosong (Drop-off Node) -> Otomatis meluncurkan balapan dual-AGV.
"""

from enum import Enum
from typing import Optional
from ursina import mouse, Text, Vec3, color

from src.environment.interactive_shelf import InteractiveShelf
from src.behavior.mission_manager import MissionManager


class InteractionState(Enum):
    SELECT_PICKUP = "PILIH RAK KARGO (PICK-UP)"
    SELECT_DROPOFF = "PILIH RAK KOSONG (DROP-OFF)"
    RACING = "BALAPAN DUAL-ROBOT BERLANGSUNG"
    COMPLETED = "PENGANTARAN SELESAI"


class InteractionSystem:
    """
    Mengelola deteksi kursor mouse pada entitas ber-collider dan alur state-machine klik.
    """

    def __init__(self, mission_manager: MissionManager):
        self.mission_mgr = mission_manager
        self.state = InteractionState.SELECT_PICKUP

        self.hovered_shelf: Optional[InteractiveShelf] = None
        self.selected_pickup_shelf: Optional[InteractiveShelf] = None
        self.selected_dropoff_shelf: Optional[InteractiveShelf] = None

        # Banner Instruksi Dinamis Mengambang di Atas Layar
        self.prompt_text = "KLIK 1: Klik RAK DENGAN KARGO untuk titik jemput (Pick-up)"

    def update(self):
        """Mendeteksi entitas yang sedang disorot kursor mouse (Raycast hover)."""
        hovered_ent = mouse.hovered_entity

        current_shelf = None
        if hovered_ent:
            if isinstance(hovered_ent, InteractiveShelf):
                current_shelf = hovered_ent
            elif hasattr(hovered_ent, "shelf_owner"):
                current_shelf = hovered_ent.shelf_owner

        # Update status hover
        if current_shelf != self.hovered_shelf:
            if self.hovered_shelf:
                self.hovered_shelf.set_hover(False)
            self.hovered_shelf = current_shelf
            if self.hovered_shelf:
                self.hovered_shelf.set_hover(True)

        # Deteksi transisi otomatis saat balapan selesai
        if self.state == InteractionState.RACING and self.mission_mgr.race_finished:
            self.state = InteractionState.COMPLETED
            self.prompt_text = "PENGANTARAN SELESAI! Klik rak kargo baru untuk misi berikutnya, atau tekan [G] Misi Acak."

    def handle_click(self):
        """Memproses klik kiri mouse pada rak atau kargo."""
        if not self.hovered_shelf:
            return

        shelf = self.hovered_shelf

        # ---------------------------------------------------------------------
        # STATE 1: SELEKSI TITIK JEMPUT (PICK-UP)
        # ---------------------------------------------------------------------
        if self.state in (InteractionState.SELECT_PICKUP, InteractionState.COMPLETED):
            if not shelf.shelf_data.has_cargo:
                self.prompt_text = f"[Peringatan] Rak {shelf.shelf_data.shelf_id} Kosong! Pilih rak yang memiliki kargo."
                return

            # Bersihkan seleksi lama jika ada
            if self.selected_pickup_shelf:
                self.selected_pickup_shelf.clear_selection()
            if self.selected_dropoff_shelf:
                self.selected_dropoff_shelf.clear_selection()

            self.selected_pickup_shelf = shelf
            shelf.mark_as_pickup(True)
            self.state = InteractionState.SELECT_DROPOFF
            self.prompt_text = (
                f"TITIK JEMPUT: {shelf.shelf_data.shelf_id} ({shelf.shelf_data.cargo_item}). "
                f"KLIK 2: Sekarang klik RAK KOSONG untuk tujuan (Drop-off)!"
            )

        # ---------------------------------------------------------------------
        # STATE 2: SELEKSI TITIK ANTAR (DROP-OFF)
        # ---------------------------------------------------------------------
        elif self.state == InteractionState.SELECT_DROPOFF:
            if shelf == self.selected_pickup_shelf:
                self.prompt_text = "[Peringatan] Titik antar tidak boleh sama dengan titik jemput!"
                return

            self.selected_dropoff_shelf = shelf
            shelf.mark_as_dropoff(True)
            self.state = InteractionState.RACING

            # Trigger Peluncuran Balapan Konkuren Dual-Robot!
            success = self.mission_mgr.dispatch_race(
                self.selected_pickup_shelf,
                self.selected_dropoff_shelf,
            )

            if success:
                self.prompt_text = (
                    f"BALAPAN DIMULAI! A* vs GBFS menuju {shelf.shelf_data.shelf_id}. "
                    f"Tekan [Spasi] untuk Jeda, [V] Ganti Kamera, [R] Reset."
                )
            else:
                self.prompt_text = "Gagal menemukan rute ke rak tersebut. Silakan pilih rak lain."
                self.state = InteractionState.SELECT_DROPOFF

    def reset_interaction(self):
        """Mereset state seleksi klik kembali ke awal."""
        self.state = InteractionState.SELECT_PICKUP
        if self.selected_pickup_shelf:
            self.selected_pickup_shelf.clear_selection()
            self.selected_pickup_shelf = None
        if self.selected_dropoff_shelf:
            self.selected_dropoff_shelf.clear_selection()
            self.selected_dropoff_shelf = None
        self.prompt_text = "KLIK 1: Klik RAK DENGAN KARGO untuk titik jemput (Pick-up)"
