"""
ui_controller.py
================
Pengendali UI Master & Keyboard / Mouse Input Handler.
Mengelola tombol kontrol di layar, peralihan mode HUD ganda (Serious vs Gamification),
serta integrasi siklus hidup simulator.
"""

from ursina import (
    Button,
    Vec3,
    color,
    application,
    Entity,
    camera,
    Text,
    window,
)

from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem
from src.communication.hud_serious import SeriousHUD
from src.communication.hud_gamification import GamificationHUD
from src.environment.warehouse_scene import WarehouseScene


class UIController:
    """
    Mengelola interaksi UI tombol layar, hotkey keyboard, dan render HUD.
    """

    def __init__(
        self,
        mission_manager: MissionManager,
        interaction_system: InteractionSystem,
        scene: WarehouseScene,
    ):
        self.mission_mgr = mission_manager
        self.interaction_sys = interaction_system
        self.scene = scene

        # Instansiasi kedua sistem HUD
        self.hud_serious = SeriousHUD()
        self.hud_gamification = GamificationHUD()
        self.is_serious_mode = True
        self._last_aspect_ratio: float = 0.0

        # Buat tombol-tombol interaktif di bagian bawah layar
        self._create_screen_buttons()
        self._update_dock_layout()

    def _create_screen_buttons(self):
        """Menempatkan deretan tombol aksi modern di dermaga kontrol bagian bawah layar."""
        btn_y = -0.458
        btn_h = 0.050

        # Latar belakang dock bar kontrol modern
        self.dock_bg = Entity(
            parent=camera.ui,
            model='quad',
            position=Vec3(0, btn_y, 0.01),
            scale=Vec3(0.95, btn_h * 1.35, 1),
            color=color.rgba32(14, 18, 26, 230),
        )

        # 1. Tombol Ganti Mode HUD (Serious vs Gamifikasi)
        self.btn_hud_mode = Button(
            text="[M] Serious",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.125, btn_h, 1),
            color=color.rgb32(35, 95, 155),
            text_size=0.76,
            on_click=self.toggle_hud_mode,
        )

        # 2. Tombol Pemilih Heuristik Dinamis
        self.btn_heuristic = Button(
            text="[H] Manhattan",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.135, btn_h, 1),
            color=color.rgb32(20, 140, 120),
            text_size=0.74,
            on_click=self.cycle_heuristic,
        )

        # 3. Tombol Misi Acak (Random Race)
        self.btn_random = Button(
            text="[G] Acak",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.095, btn_h, 1),
            color=color.rgb32(125, 65, 160),
            text_size=0.76,
            on_click=self.trigger_random_mission,
        )

        # 3b. Tombol Transfer Zona (Fitur 2: Zone Transfer)
        self.btn_transfer = Button(
            text="[T] Zone",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.095, btn_h, 1),
            color=color.rgb32(0, 150, 185),
            text_size=0.76,
            on_click=self.trigger_zone_transfer,
        )

        # 4. Tombol Jeda / Lanjut
        self.btn_pause = Button(
            text="[Space] Jeda",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.100, btn_h, 1),
            color=color.rgb32(195, 105, 30),
            text_size=0.76,
            on_click=self.toggle_pause,
        )

        # 5. Tombol Reset
        self.btn_reset = Button(
            text="[R] Reset",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.085, btn_h, 1),
            color=color.rgb32(175, 45, 40),
            text_size=0.76,
            on_click=self.reset_all,
        )

        # 6. Tombol Kamera
        self.btn_cam = Button(
            text="[K] Isometrik",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.125, btn_h, 1),
            color=color.rgb32(50, 70, 95),
            text_size=0.76,
            on_click=self.cycle_camera,
        )

        # 7. Tombol Pengatur Kecepatan
        self.btn_slower = Button(
            text="[-]",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.050, btn_h, 1),
            color=color.rgb32(45, 58, 75),
            text_size=0.82,
            on_click=lambda: self.adjust_speed(-1.5),
        )
        self.btn_faster = Button(
            text="[+]",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.050, btn_h, 1),
            color=color.rgb32(45, 58, 75),
            text_size=0.82,
            on_click=lambda: self.adjust_speed(1.5),
        )

        # 8. Tombol Keluar
        self.btn_quit = Button(
            text="[Esc] Keluar",
            position=Vec3(0, btn_y, 0),
            scale=Vec3(0.100, btn_h, 1),
            color=color.rgb32(32, 38, 48),
            text_size=0.76,
            on_click=application.quit,
        )

        # 9. Badge UI Indikator Antrean Pesanan (Pending Orders Task Queue)
        self.pending_orders_bg = Entity(
            parent=camera.ui,
            model='quad',
            position=Vec3(0.55, 0.44, 0),
            scale=Vec3(0.25, 0.046, 1),
            color=color.rgba32(14, 18, 28, 225),
        )
        self.pending_orders_accent = Entity(
            parent=self.pending_orders_bg,
            model='quad',
            position=Vec3(0, 0.46, -0.005),
            scale=Vec3(1.0, 0.08, 1),
            color=color.rgb32(0, 229, 255),
        )
        self.pending_orders_text = Text(
            parent=self.pending_orders_bg,
            text="Pending Orders: 0",
            position=Vec3(0, -0.05, -0.01),
            scale=1.05,
            color=color.rgb32(0, 229, 255),
            origin=(0, 0),
        )

    def _update_dock_layout(self):
        """Menyesuaikan posisi dock kontrol bawah secara responsif mengikuti aspect ratio layar."""
        from ursina import window
        aspect = window.aspect_ratio
        if abs(aspect - self._last_aspect_ratio) < 0.01:
            return
        self._last_aspect_ratio = aspect

        # Beritahu kedua HUD untuk memperbarui penjangkarannya ke tepi kiri layar
        self.hud_serious.update_layout()
        self.hud_gamification.update_layout()

        # Posisikan badge antrean pesanan di pojok kanan atas
        screen_right = aspect / 2.0
        badge_w = 0.25
        badge_margin = 0.02
        self.pending_orders_bg.position = Vec3(screen_right - badge_margin - (badge_w / 2.0), 0.44, 0)

        btn_y = -0.458
        btn_h = 0.050

        if aspect >= 1.15:
            # Mode 1-Baris Kompak (Standar Widescreen & Normal)
            btns = [
                (self.btn_hud_mode, 0.115),
                (self.btn_heuristic, 0.125),
                (self.btn_random, 0.085),
                (self.btn_transfer, 0.085),
                (self.btn_pause, 0.090),
                (self.btn_reset, 0.075),
                (self.btn_cam, 0.110),
                (self.btn_slower, 0.045),
                (self.btn_faster, 0.045),
                (self.btn_quit, 0.090),
            ]
            gap = 0.006
            total_w = sum(w for _, w in btns) + gap * (len(btns) - 1)

            self.dock_bg.position = Vec3(0, btn_y, 0.01)
            self.dock_bg.scale = Vec3(total_w + 0.03, btn_h * 1.35, 1)

            cur_x = -total_w / 2.0
            for btn, w in btns:
                btn.position = Vec3(cur_x + w / 2.0, btn_y, 0)
                btn.scale = Vec3(w, btn_h, 1)
                cur_x += w + gap
        else:
            # Mode 2-Baris Responsif (Tiling Window Manager / Layar Vertikal / Separuh Layar)
            row1_y = -0.425
            row2_y = -0.472
            row_h = 0.042

            row1 = [
                (self.btn_hud_mode, 0.120),
                (self.btn_heuristic, 0.130),
                (self.btn_cam, 0.120),
                (self.btn_slower, 0.050),
                (self.btn_faster, 0.050),
            ]
            row2 = [
                (self.btn_random, 0.090),
                (self.btn_transfer, 0.090),
                (self.btn_pause, 0.100),
                (self.btn_reset, 0.080),
                (self.btn_quit, 0.100),
            ]
            gap = 0.007
            w1 = sum(w for _, w in row1) + gap * (len(row1) - 1)
            w2 = sum(w for _, w in row2) + gap * (len(row2) - 1)
            max_w = max(w1, w2)

            self.dock_bg.position = Vec3(0, (row1_y + row2_y) / 2.0, 0.01)
            self.dock_bg.scale = Vec3(max_w + 0.03, 0.098, 1)

            cur_x = -w1 / 2.0
            for btn, w in row1:
                btn.position = Vec3(cur_x + w / 2.0, row1_y, 0)
                btn.scale = Vec3(w, row_h, 1)
                cur_x += w + gap

            cur_x = -w2 / 2.0
            for btn, w in row2:
                btn.position = Vec3(cur_x + w / 2.0, row2_y, 0)
                btn.scale = Vec3(w, row_h, 1)
                cur_x += w + gap

    def toggle_hud_mode(self):
        """Beralih antara Mode Serius (WMS Analytics) dan Mode Gamifikasi (Arcade)."""
        self.is_serious_mode = not self.is_serious_mode
        self.hud_serious.set_visible(self.is_serious_mode)
        self.hud_gamification.set_visible(not self.is_serious_mode)

        if self.is_serious_mode:
            self.btn_hud_mode.text = "[M] Serious"
            self.btn_hud_mode.color = color.rgb32(35, 95, 155)
        else:
            self.btn_hud_mode.text = "[M] Arcade"
            self.btn_hud_mode.color = color.rgb32(233, 30, 99)

    def cycle_heuristic(self):
        """Beralih ke heuristik berikutnya dan perbarui teks tombol."""
        new_h = self.mission_mgr.cycle_heuristic()
        self.btn_heuristic.text = f"[H] {new_h}"
        self.interaction_sys.prompt_text = f"Heuristik: {new_h.upper()}. Rute dihitung ulang."

    def trigger_random_mission(self):
        """Menjalankan balapan acak otomatis."""
        self.interaction_sys.reset_interaction()
        success = self.mission_mgr.trigger_random_mission()
        if success:
            from src.communication.interaction_system import InteractionState
            self.interaction_sys.state = InteractionState.RACING
            p_id = self.mission_mgr.selected_pickup_shelf.shelf_data.shelf_id
            d_id = self.mission_mgr.selected_dropoff_shelf.shelf_data.shelf_id
            self.interaction_sys.prompt_text = f"MISI ACAK DIMULAI! A* vs GBFS: Rak {p_id} -> {d_id}"

    def trigger_zone_transfer(self):
        """Meluncurkan balapan transfer antar-zona menuju Transfer Gate (Fitur 2)."""
        self.interaction_sys.reset_interaction()
        success = self.mission_mgr.dispatch_zone_transfer()
        if success:
            from src.communication.interaction_system import InteractionState
            self.interaction_sys.state = InteractionState.RACING
            dest_zone = "Zone B" if self.mission_mgr.current_zone == "Zone A" else "Zone A"
            self.interaction_sys.prompt_text = (
                f"MISI TRANSFER ZONA! A* vs GBFS meluncur menuju Gerbang (x=34, y=13) "
                f"untuk transisi ke {dest_zone}!"
            )

    def toggle_pause(self):
        """Menjeda / melanjutkan pergerakan robot."""
        is_paused = self.mission_mgr.toggle_pause()
        if is_paused:
            self.btn_pause.text = "[Space] Lanjut"
            self.btn_pause.color = color.rgb32(39, 174, 96)
        else:
            self.btn_pause.text = "[Space] Jeda"
            self.btn_pause.color = color.rgb32(230, 126, 34)

    def reset_all(self):
        """Mereset posisi robot dan seleksi interaksi."""
        self.mission_mgr.reset_race()
        self.interaction_sys.reset_interaction()
        self.btn_pause.text = "[Space] Jeda"
        self.btn_pause.color = color.rgb32(230, 126, 34)

    def cycle_camera(self):
        """Mengganti mode kamera dalam siklus: Isometrik -> Top-Down -> Free-Cam."""
        new_mode = self.scene.cycle_camera_mode()
        labels = {
            "isometrik": "Isometrik",
            "topdown": "Top-Down",
            "free_cam": "Free-Cam",
            "bebas": "Free-Cam",
        }
        cam_label = labels.get(new_mode, new_mode.capitalize())
        self.btn_cam.text = f"[K] {cam_label}"

        if new_mode in ("free_cam", "bebas"):
            self.interaction_sys.prompt_text = (
                "[FREE-CAM / GOD MODE] Tahan Klik Kanan Mouse untuk rotasi pandangan, "
                "WASD / Panah / Scroll untuk terbang melintasi seluruh gudang 3D!"
            )
        else:
            self.interaction_sys.prompt_text = f"Mode Kamera: {cam_label}."

    def adjust_speed(self, delta: float):
        """Menyesuaikan kecepatan armada."""
        self.mission_mgr.adjust_speed(delta)

    def update(self):
        """Sinkronisasi HUD per frame."""
        self._update_dock_layout()
        self.interaction_sys.update()

        # Update teks dan warna badge antrean pesanan
        q_count = len(self.mission_mgr.task_queue)
        self.pending_orders_text.text = f"Pending Orders: {q_count}"
        if q_count > 0:
            self.pending_orders_text.color = color.rgb32(243, 156, 18)
            self.pending_orders_accent.color = color.rgb32(243, 156, 18)
        else:
            self.pending_orders_text.color = color.rgb32(0, 229, 255)
            self.pending_orders_accent.color = color.rgb32(0, 229, 255)

        # Update HUD yang sedang aktif
        if self.is_serious_mode:
            self.hud_serious.update(self.mission_mgr, self.interaction_sys)
        else:
            self.hud_gamification.update(self.mission_mgr, self.interaction_sys)

        # Update follow camera atau POV camera jika aktif
        if self.scene.current_cam_mode == "follow_alpha":
            self.scene.update_follow_camera(self.mission_mgr.robot_alpha.position)
        elif self.scene.current_cam_mode == "follow_beta":
            self.scene.update_follow_camera(self.mission_mgr.robot_beta.position)
        elif self.scene.current_cam_mode == "pov_alpha":
            self.scene.update_pov_camera(self.mission_mgr.robot_alpha)
        elif self.scene.current_cam_mode == "pov_beta":
            self.scene.update_pov_camera(self.mission_mgr.robot_beta)

    def cycle_pov_camera(self):
        """Beralih ke mode kamera POV Cockpit / Chase Cam: POV Alpha -> POV Beta -> Isometrik."""
        if self.scene.current_cam_mode != "pov_alpha" and self.scene.current_cam_mode != "pov_beta":
            self.scene.apply_camera_mode("pov_alpha")
            self.btn_cam.text = "[F] POV Alpha"
            self.interaction_sys.prompt_text = "[POV CAM] Sudut Pandang Kokpit AGV Alpha (A*) Aktif!"
        elif self.scene.current_cam_mode == "pov_alpha":
            self.scene.apply_camera_mode("pov_beta")
            self.btn_cam.text = "[F] POV Beta"
            self.interaction_sys.prompt_text = "[POV CAM] Sudut Pandang Kokpit AGV Beta (GBFS) Aktif!"
        else:
            self.scene.apply_camera_mode("isometrik")
            self.btn_cam.text = "[K] Isometrik"
            self.interaction_sys.prompt_text = "Mode Kamera: Isometrik."

    def handle_input(self, key: str):
        """Menangani penekanan tombol keyboard & klik mouse raycast."""
        if key == 'left mouse down':
            self.interaction_sys.handle_click()
        elif key == 'right mouse down':
            # Hanya proses intervensi klik kanan pada robot jika bukan mode free_cam
            if self.scene.current_cam_mode not in ("free_cam", "bebas"):
                self.interaction_sys.handle_right_click()
        elif key == 'm':
            self.toggle_hud_mode()
        elif key == 'h':
            self.cycle_heuristic()
        elif key == 'g':
            self.trigger_random_mission()
        elif key == 't':
            self.trigger_zone_transfer()
        elif key == 'space':
            self.toggle_pause()
        elif key == 'r':
            self.reset_all()
        elif key == 'c':
            self.scene.clear_all_dynamic_obstacles()
            self.scene.clear_all_terrain_modifiers()
            self.mission_mgr.graph.clear_dynamic_obstacles()
            self.mission_mgr.graph.clear_terrain_modifiers()
            if hasattr(self.scene, 'clear_exploration_heatmap'):
                self.scene.clear_exploration_heatmap()
            self.interaction_sys.prompt_text = "[Info] Seluruh rintangan dinamis, tumpahan oli, boost pad, dan heatmap telah dibersihkan."
        elif key in ('k', 'v'):
            self.cycle_camera()
        elif key == 'f':
            self.cycle_pov_camera()
        elif key in ('+', '='):
            self.adjust_speed(1.5)
        elif key == '-':
            self.adjust_speed(-1.5)
        elif key == '1':
            from src.communication.interaction_system import PlacementTool
            self.interaction_sys.set_tool(PlacementTool.CARGO_BOX)
        elif key == '2':
            from src.communication.interaction_system import PlacementTool
            self.interaction_sys.set_tool(PlacementTool.OIL_SPILL)
        elif key == '3':
            from src.communication.interaction_system import PlacementTool
            self.interaction_sys.set_tool(PlacementTool.BOOST_PAD)
        elif key == 'escape':
            application.quit()
