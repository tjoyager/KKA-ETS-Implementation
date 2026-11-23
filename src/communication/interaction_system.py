"""
interaction_system.py
=====================
Sistem Raycasting Mouse (Point-and-Click), State-Machine Seleksi Misi,
dan Penempatan Rintangan Dinamis Real-Time (Dynamic Obstacle Placement).

Fitur Interaktif:
1. Klik Rak Kargo (Pick-up Node) -> Klik Rak Kosong (Drop-off Node) untuk peluncuran balapan dual-AGV.
2. Klik Kiri pada sel lorong kosong (walkable) untuk menjatuhkan kotak kargo dinamis real-time.
3. Otomatis memperbarui matriks WarehouseGraph100 dan memicu kalkulasi ulang rute (dynamic replanning)
   bagi AGV Alpha (A*) dan/atau AGV Beta (GBFS) jika jalur yang sedang ditempuh terhalang.
4. Klik Kiri pada kotak rintangan yang sudah ada untuk mengangkat/menghapusnya dari peta.
5. Indikator kursor petak lantai dinamis (Grid Cursor Indicator).
"""

from enum import Enum, IntEnum
from typing import Optional, Tuple
from ursina import mouse, Text, Vec3, color, Entity, destroy

from src.environment.interactive_shelf import InteractiveShelf
from src.environment.warehouse_scene import WarehouseScene
from src.behavior.traffic_clearance import carton_bounds, forklift_bounds, touches_robot
from src.behavior.mission_manager import MissionManager
from src.behavior.robot_controller import RobotState
from src.config import world_to_grid, grid_to_world, GRID_WIDTH, GRID_HEIGHT, CHARGING_STATIONS

Coord = Tuple[int, int]


class PlacementTool(IntEnum):
    CARGO_BOX = 1      # [1] Rintangan kargo blokir penuh (Dynamic Obstacle)
    OIL_SPILL = 2      # [2] Tumpahan oli licin (Cost 5.0, robot slowdown 0.4x)
    BOOST_PAD = 3      # [3] Speed Boost Pad konveyor (Cost 0.35, robot speed 1.75x)


class InteractionState(Enum):
    SELECT_PICKUP = "PILIH RAK KARGO (PICK-UP)"
    SELECT_DROPOFF = "PILIH RAK KOSONG (DROP-OFF)"
    RACING = "BALAPAN DUAL-ROBOT BERLANGSUNG"
    COMPLETED = "PENGANTARAN SELESAI"


class InteractionSystem:
    """
    Mengelola deteksi kursor mouse pada entitas ber-collider, penempatan rintangan dinamis,
    multi-tool medan berbobot (Oli vs Boost Pad), dan alur state-machine seleksi misi.
    """

    def __init__(self, mission_manager: MissionManager, scene: Optional[WarehouseScene] = None):
        self.mission_mgr = mission_manager
        self.scene: WarehouseScene = scene or mission_manager.scene
        # The active graph is provided by the mission manager after each zone switch.
        self.state = InteractionState.SELECT_PICKUP
        self.current_tool = PlacementTool.CARGO_BOX

        self.hovered_shelf: Optional[InteractiveShelf] = None
        self.selected_pickup_shelf: Optional[InteractiveShelf] = None
        self.selected_dropoff_shelf: Optional[InteractiveShelf] = None
        self._queue_pickup_shelf: Optional[InteractiveShelf] = None
        self._observed_race_finished: bool = False

        # Banner Instruksi Dinamis Mengambang di Atas Layar
        self.prompt_text = "KLIK 1: Klik RAK DENGAN KARGO untuk titik jemput, atau gunakan Tool [1/2/3] di lantai"

        # Indikator visual kursor petak lantai (Hover Placement Marker)
        self.cursor_marker = Entity(
            model='cube',
            scale=Vec3(0.96, 0.04, 0.96),
            color=color.rgba32(0, 230, 255, 120),
            position=Vec3(0, -10, 0),
            enabled=False,
        )

    @property
    def graph(self):
        return self.mission_mgr.graph

    def set_tool(self, tool: PlacementTool):
        """Mengganti kuas/tool penempatan lantai yang aktif."""
        self.current_tool = tool
        names = {
            PlacementTool.CARGO_BOX: "KOTAK KARGO [1] (BLOKIR PENUH)",
            PlacementTool.OIL_SPILL: "TUMPAHAN OLI [2] (COST 5.0 / SLOW 0.4x)",
            PlacementTool.BOOST_PAD: "SPEED BOOST PAD [3] (COST 0.35 / SPEED 1.75x)",
        }
        self.prompt_text = f"Tool Aktif: {names.get(tool, '')}. Klik petak lantai lorong kosong untuk menempatkannya."

    def update(self):
        """Mendeteksi entitas yang sedang disorot kursor mouse (Raycast hover) dan memperbarui cursor marker."""
        hovered_ent = mouse.hovered_entity

        current_shelf = None
        if hovered_ent:
            if isinstance(hovered_ent, InteractiveShelf):
                current_shelf = hovered_ent
            elif hasattr(hovered_ent, "shelf_owner"):
                current_shelf = hovered_ent.shelf_owner

        # Update status hover rak
        if current_shelf != self.hovered_shelf:
            if self.hovered_shelf:
                self.hovered_shelf.set_hover(False)
            self.hovered_shelf = current_shelf
            if self.hovered_shelf:
                self.hovered_shelf.set_hover(True)

        # Update visual petak kursor pada lantai jika tidak sedang mengarahkan ke rak
        if not self.hovered_shelf and mouse.world_point is not None:
            gx, gy = world_to_grid(mouse.world_point)
            if 0 <= gx < GRID_WIDTH and 0 <= gy < GRID_HEIGHT:
                self.cursor_marker.position = grid_to_world(gx, gy, 0.04)
                self.cursor_marker.enabled = True

                coord = (gx, gy)
                if coord in self.scene.dynamic_obstacle_entities:
                    # Rintangan kargo -> Warna Merah (klik untuk menghapus)
                    self.cursor_marker.color = color.rgba32(245, 60, 60, 160)
                elif coord in self.scene.oil_spill_entities:
                    # Tumpahan oli -> Warna Kuning/Emas (klik untuk menghapus)
                    self.cursor_marker.color = color.rgba32(245, 175, 20, 190)
                elif coord in self.scene.boost_pad_entities:
                    # Speed boost pad -> Warna Hijau Neon (klik untuk menghapus)
                    self.cursor_marker.color = color.rgba32(0, 245, 140, 190)
                elif self.graph.is_walkable(gx, gy):
                    # Sel kosong walkable -> Tampilkan warna sesuai tool aktif
                    if self.current_tool == PlacementTool.OIL_SPILL:
                        self.cursor_marker.color = color.rgba32(245, 175, 20, 150)
                    elif self.current_tool == PlacementTool.BOOST_PAD:
                        self.cursor_marker.color = color.rgba32(0, 245, 140, 150)
                    else:
                        self.cursor_marker.color = color.rgba32(0, 230, 255, 130)
                else:
                    # Dinding/rak permanen -> Dimmed
                    self.cursor_marker.color = color.rgba32(100, 110, 130, 60)
            else:
                self.cursor_marker.enabled = False
        else:
            self.cursor_marker.enabled = False

        # Deteksi transisi otomatis saat balapan selesai
        if self.mission_mgr.is_race_active and not self.mission_mgr.race_finished:
            self._observed_race_finished = False
        elif self.mission_mgr.race_finished and not self._observed_race_finished:
            self._observed_race_finished = True
            if len(self.mission_mgr.task_queue) > 0:
                self.prompt_text = f"PENGANTARAN SELESAI! Mempersiapkan pesanan dari antrean ({len(self.mission_mgr.task_queue)} pesanan tersisa)..."
            elif self.state == InteractionState.RACING:
                self.state = InteractionState.COMPLETED
                self.prompt_text = "PENGANTARAN SELESAI! Klik rak kargo baru untuk misi berikutnya, atau tekan [G] Misi Acak."
            elif self.state == InteractionState.SELECT_DROPOFF and self._queue_pickup_shelf is not None:
                self.prompt_text = (
                    f"Balapan sebelumnya selesai! Pilih RAK KOSONG untuk langsung menjalankan "
                    f"{self._queue_pickup_shelf.shelf_data.shelf_id}."
                )

    def _is_race_busy(self) -> bool:
        return bool(
            self.mission_mgr.is_race_active
            and not self.mission_mgr.race_finished
            and (
                self.mission_mgr.robot_alpha.state not in (RobotState.IDLE_DOCK, RobotState.FINISHED)
                or self.mission_mgr.robot_beta.state not in (RobotState.IDLE_DOCK, RobotState.FINISHED)
            )
        )

    def handle_click(self):
        """
        Memproses klik kiri mouse:
        1. Jika klik pada rak: Menjalankan state machine pemilihan Pick-up / Drop-off,
           dan otomatis menambahkan ke antrean FIFO (Task Queue) jika robot sedang bertugas.
        2. Jika klik pada rintangan dinamis: Mengangkat/menghapus rintangan tersebut.
        3. Jika klik pada sel lorong kosong (walkable): Menjatuhkan rintangan kargo baru
           dan memicu kalkulasi ulang rute (dynamic replanning) jika memotong rute aktif.
        """
        from src.behavior.robot_controller import RobotState

        # ---------------------------------------------------------------------
        # KASUS 1: INTERAKSI DENGAN RAK (POINT-AND-CLICK SELECTION / TASK QUEUE)
        # ---------------------------------------------------------------------
        if self.hovered_shelf:
            shelf = self.hovered_shelf

            # State 1: Seleksi Titik Jemput (Pick-up)
            if self.state in (InteractionState.SELECT_PICKUP, InteractionState.COMPLETED, InteractionState.RACING):
                if not shelf.shelf_data.has_cargo:
                    self.prompt_text = f"[Peringatan] Rak {shelf.shelf_data.shelf_id} Kosong! Pilih rak yang memiliki kargo."
                    return

                # Validasi Cegah Double-Booking Antrean Kargo
                if self.mission_mgr.is_pickup_booked(shelf.shelf_data.x, shelf.shelf_data.y):
                    self.prompt_text = "[Peringatan] Kargo ini sudah di-booking oleh antrean sebelumnya!"
                    return

                is_busy = self._is_race_busy()
                if is_busy:
                    if self._queue_pickup_shelf and self._queue_pickup_shelf is not shelf:
                        self._queue_pickup_shelf.clear_selection()
                    self._queue_pickup_shelf = shelf
                else:
                    # Bersihkan seleksi lama jika ada
                    if self.selected_pickup_shelf:
                        self.selected_pickup_shelf.clear_selection()
                    if self.selected_dropoff_shelf:
                        self.selected_dropoff_shelf.clear_selection()
                    self._queue_pickup_shelf = None
                    self.selected_dropoff_shelf = None

                self.selected_pickup_shelf = shelf
                shelf.mark_as_pickup(True)
                self.state = InteractionState.SELECT_DROPOFF

                if is_busy:
                    self.prompt_text = (
                        f"[ANTREAN PESANAN] Titik Jemput: {shelf.shelf_data.shelf_id}. "
                        f"Sekarang klik RAK KOSONG untuk menambahkan tiket ke antrean!"
                    )
                else:
                    self.prompt_text = (
                        f"TITIK JEMPUT: {shelf.shelf_data.shelf_id} ({shelf.shelf_data.cargo_item}). "
                        f"KLIK 2: Sekarang klik RAK KOSONG untuk tujuan (Drop-off)!"
                    )
                return

            # State 2: Seleksi Titik Antar (Drop-off) -> Dispatch Langsung atau Enqueue FIFO
            elif self.state == InteractionState.SELECT_DROPOFF:
                if shelf == self.selected_pickup_shelf:
                    self.prompt_text = "[Peringatan] Titik antar tidak boleh sama dengan titik jemput!"
                    return

                if shelf.shelf_data.has_cargo:
                    self.prompt_text = f"[Peringatan] Rak {shelf.shelf_data.shelf_id} sudah terisi kargo! Pilih rak kosong."
                    return

                if self.mission_mgr.is_dropoff_booked(shelf.shelf_data.x, shelf.shelf_data.y):
                    self.prompt_text = f"[Peringatan] Rak {shelf.shelf_data.shelf_id} sudah di-booking sebagai tujuan antrean!"
                    return

                # Cek apakah robot sedang sibuk menjalankan misi
                if self._is_race_busy():
                    # Masukkan pesanan ke antrean FIFO tanpa mengganggu balapan berjalan
                    order_id = self.mission_mgr.enqueue_order(
                        self.selected_pickup_shelf,
                        shelf,
                    )
                    q_len = len(self.mission_mgr.task_queue)
                    p_id = self.selected_pickup_shelf.shelf_data.shelf_id
                    d_id = shelf.shelf_data.shelf_id
                    self.prompt_text = (
                        f"[ANTREAN TERSIMPAN] Pesanan #{order_id} ({p_id} -> {d_id}) "
                        f"ditambahkan ke antrean! (Total Antrean: {q_len}). Dikerjakan otomatis saat idle."
                    )
                    # Bersihkan seleksi sementara antrean dan pulihkan penanda misi aktif
                    self.selected_pickup_shelf.clear_selection()
                    self._queue_pickup_shelf = None
                    self.selected_pickup_shelf = self.mission_mgr.selected_pickup_shelf
                    self.selected_dropoff_shelf = self.mission_mgr.selected_dropoff_shelf
                    if self.selected_pickup_shelf:
                        self.selected_pickup_shelf.mark_as_pickup(True)
                    if self.selected_dropoff_shelf:
                        self.selected_dropoff_shelf.mark_as_dropoff(True)
                    self.state = InteractionState.RACING
                    return
                else:
                    # Jalankan balapan segera jika robot sedang menganggur
                    if self.mission_mgr.selected_pickup_shelf and self.mission_mgr.selected_pickup_shelf is not self.selected_pickup_shelf:
                        self.mission_mgr.selected_pickup_shelf.clear_selection()
                    if self.mission_mgr.selected_dropoff_shelf and self.mission_mgr.selected_dropoff_shelf is not shelf:
                        self.mission_mgr.selected_dropoff_shelf.clear_selection()
                    self._queue_pickup_shelf = None
                    self.selected_dropoff_shelf = shelf
                    shelf.mark_as_dropoff(True)
                    self.state = InteractionState.RACING

                    success = self.mission_mgr.dispatch_race(
                        self.selected_pickup_shelf,
                        self.selected_dropoff_shelf,
                    )

                    if success:
                        self.prompt_text = (
                            f"BALAPAN DIMULAI! A* vs GBFS menuju {shelf.shelf_data.shelf_id}. "
                            f"Gunakan WASD untuk Forklift atau klik lantai untuk rintangan!"
                        )
                    else:
                        self.prompt_text = "Gagal menemukan rute ke rak tersebut. Silakan pilih rak lain."
                        self.state = InteractionState.SELECT_DROPOFF
                    return

        # ---------------------------------------------------------------------
        # KASUS 2: INTERAKSI DENGAN LANTAI / RINTANGAN DINAMIS (RAYCAST)
        # ---------------------------------------------------------------------
        if mouse.world_point is not None:
            gx, gy = world_to_grid(mouse.world_point)
            if not (0 <= gx < self.graph.width and 0 <= gy < self.graph.height):
                return

            coord = (gx, gy)

            # Subkasus A: Klik pada rintangan dinamis yang sudah ada -> Hapus / Angkat
            if coord in self.scene.dynamic_obstacle_entities:
                self.scene.remove_dynamic_obstacle(gx, gy)
                self.graph.remove_dynamic_obstacle(gx, gy)
                self.mission_mgr.handle_dynamic_obstacle_removed(coord)
                self.prompt_text = f"[Rintangan Dihapus] Kotak kargo di ({gx}, {gy}) diangkat! Jalur lorong dibuka kembali."
                return

            # Subkasus B: Klik pada tumpahan oli yang sudah ada -> Bersihkan
            if coord in self.scene.oil_spill_entities:
                self.scene.remove_hazard_oil(gx, gy)
                self.graph.remove_terrain_modifier(gx, gy)
                self.mission_mgr.handle_terrain_modified(coord)
                self.prompt_text = f"[Tumpahan Oli Dihapus] Genangan oli di ({gx}, {gy}) dibersihkan! Jalur lorong kembali normal."
                return

            # Subkasus C: Klik pada speed boost pad yang sudah ada -> Lepas
            if coord in self.scene.boost_pad_entities:
                self.scene.remove_boost_pad(gx, gy)
                self.graph.remove_terrain_modifier(gx, gy)
                self.mission_mgr.handle_terrain_modified(coord)
                self.prompt_text = f"[Speed Pad Dihapus] Konveyor boost pad di ({gx}, {gy}) dilepas!"
                return

            # Subkasus D: Klik pada sel kosong yang walkable -> Tempatkan Tool Aktif
            if self.graph.is_walkable(gx, gy):
                # Cegah menjatuhkan rintangan pada posisi aktual robot
                alpha_pos = self.mission_mgr.robot_alpha.get_current_grid_coord()
                beta_pos = self.mission_mgr.robot_beta.get_current_grid_coord()
                if coord in (alpha_pos, beta_pos):
                    self.prompt_text = f"[Peringatan] Tidak dapat menempatkan tool di sel robot ({gx}, {gy})!"
                    return

                # Cegah menjatuhkan rintangan di docking stasiun, charger interior, goal, dan transfer gate
                protected_cells = (
                    set(self.graph.get_charging_docks())
                    | set(CHARGING_STATIONS)
                    | {self.graph.dock_alpha, self.graph.dock_beta, self.graph.goal}
                    | set(self.graph.transfer_gate_coords)
                )
                if coord in protected_cells:
                    self.prompt_text = f"[Peringatan] Tidak dapat menempatkan tool di sel fasilitas/stasiun ({gx}, {gy})!"
                    return

                # Eksekusi sesuai jenis tool yang dipilih
                if self.current_tool == PlacementTool.CARGO_BOX:
                    bounds = carton_bounds(coord)
                    if (touches_robot(bounds, self.mission_mgr)
                            or any(bounds.overlaps(forklift_bounds(f)) for f in self.mission_mgr.forklifts if f)):
                        self.prompt_text = "Belum bisa taruh kardus di sini. Tunggu kendaraan lewat."
                        return
                    if not self.graph.add_dynamic_obstacle(gx, gy):
                        return
                    self.scene.spawn_dynamic_obstacle(gx, gy)
                    alpha_rep, beta_rep = self.mission_mgr.handle_dynamic_obstacle(coord)

                    if alpha_rep or beta_rep:
                        replan_names = []
                        if alpha_rep:
                            replan_names.append("Alpha (A*)")
                        if beta_rep:
                            replan_names.append("Beta (GBFS)")
                        self.prompt_text = (
                            f"[RINTANGAN DINAMIS] Kotak di ({gx}, {gy}) memotong rute! "
                            f"{' & '.join(replan_names)} menghitung rute alternatif!"
                        )
                    else:
                        if self.mission_mgr.is_race_active:
                            self.prompt_text = f"[Rintangan Dinamis] Kotak dijatuhkan di ({gx}, {gy}). Robot akan memeriksa jalur sebelum bergerak."
                        else:
                            self.prompt_text = f"[Rintangan Dinamis] Kotak ditempatkan di ({gx}, {gy}). Matriks graf diperbarui."

                elif self.current_tool == PlacementTool.OIL_SPILL:
                    self.graph.add_hazard_oil(gx, gy)
                    self.scene.spawn_hazard_oil(gx, gy)
                    self.mission_mgr.handle_terrain_modified(coord)
                    self.prompt_text = (
                        f"[TUMPAHAN OLI] Genangan diletakkan di ({gx}, {gy})! "
                        f"Biaya langkah g(n) = 5.0. A* mengevaluasi rute memutar, GBFS menerobos!"
                    )

                elif self.current_tool == PlacementTool.BOOST_PAD:
                    self.graph.add_boost_pad(gx, gy)
                    self.scene.spawn_boost_pad(gx, gy)
                    self.mission_mgr.handle_terrain_modified(coord)
                    self.prompt_text = (
                        f"[SPEED BOOST PAD] Konveyor cepat dipasang di ({gx}, {gy})! "
                        f"Biaya langkah g(n) = 0.35. A* memprioritaskan pad cepat ini!"
                    )
            else:
                self.prompt_text = f"[Info] Sel ({gx}, {gy}) bukan lorong kosong yang dapat dilintasi."

    def handle_right_click(self):
        """
        Memproses klik kanan mouse:
        Intervensi Pengguna (Fitur 1) untuk memerintahkan robot AGV yang kehabisan baterai
        atau kritis agar melakukan Force Return to Dock & Recharge ke 100%.
        """
        target_robot = None
        hovered = mouse.hovered_entity

        # 1. Cek langsung via collider visual_body robot
        if hovered:
            if hasattr(hovered, "robot_owner"):
                target_robot = hovered.robot_owner
            elif hovered == self.mission_mgr.robot_alpha.visual_body:
                target_robot = self.mission_mgr.robot_alpha
            elif hovered == self.mission_mgr.robot_beta.visual_body:
                target_robot = self.mission_mgr.robot_beta

        # 2. Cek via koordinat lantai raycast terdekat ke posisi robot
        if not target_robot and mouse.world_point is not None:
            gx, gy = world_to_grid(mouse.world_point)
            alpha_coord = self.mission_mgr.robot_alpha.get_current_grid_coord()
            beta_coord = self.mission_mgr.robot_beta.get_current_grid_coord()
            if abs(gx - alpha_coord[0]) <= 1 and abs(gy - alpha_coord[1]) <= 1:
                target_robot = self.mission_mgr.robot_alpha
            elif abs(gx - beta_coord[0]) <= 1 and abs(gy - beta_coord[1]) <= 1:
                target_robot = self.mission_mgr.robot_beta

        if target_robot:
            success = target_robot.force_return_to_dock(
                graph=self.graph,
                heuristic_fn=self.mission_mgr.current_heuristic_fn,
            )
            if success:
                self.prompt_text = (
                    f"[INTERVENSI USER] {target_robot.robot_name} menerima perintah "
                    f"FORCE RETURN TO DOCK! Menuju dock untuk mengisi daya 100%."
                )
            else:
                self.prompt_text = f"[{target_robot.robot_name}] Gagal menemukan rute pulang ke stasiun dock!"
        else:
            self.prompt_text = "[Info] Klik Kanan pada robot untuk perintah Force Return to Dock & Recharge."

    def reset_interaction(self):
        """Mereset state seleksi klik kembali ke awal."""
        self.state = InteractionState.SELECT_PICKUP
        self._observed_race_finished = False
        if self._queue_pickup_shelf:
            self._queue_pickup_shelf.clear_selection()
            self._queue_pickup_shelf = None
        if self.selected_pickup_shelf:
            self.selected_pickup_shelf.clear_selection()
            self.selected_pickup_shelf = None
        if self.selected_dropoff_shelf:
            self.selected_dropoff_shelf.clear_selection()
            self.selected_dropoff_shelf = None
        self.prompt_text = "KLIK 1: Klik RAK DENGAN KARGO untuk titik jemput (Pick-up), atau klik lantai untuk rintangan"

    def on_destroy(self):
        """Membersihkan indikator kursor visual saat interaction system dihancurkan."""
        if hasattr(self, 'cursor_marker') and self.cursor_marker:
            destroy(self.cursor_marker)
