"""
ui_controller.py
================
Pengendali UI Master & Keyboard / Mouse Input Handler.
Mengelola tombol kontrol di layar, peralihan mode HUD ganda (Serious vs Gamification),
serta integrasi siklus hidup simulator.
"""

from ursina import Button, Vec3, color, application

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

        # Buat tombol-tombol interaktif di bagian bawah layar
        self._create_screen_buttons()

    def _create_screen_buttons(self):
        """Menempatkan deretan tombol aksi di bagian bawah layar."""
        btn_y = -0.45
        btn_h = 0.054

        # 1. Tombol Ganti Mode HUD (Serious vs Gamifikasi)
        self.btn_hud_mode = Button(
            text="Mode HUD: Serious [M]",
            position=Vec3(-0.64, btn_y, 0),
            scale=Vec3(0.24, btn_h, 1),
            color=color.rgb32(41, 128, 185),
            text_size=0.82,
            on_click=self.toggle_hud_mode,
        )

        # 2. Tombol Misi Acak (Random Race)
        Button(
            text="Misi Acak [G]",
            position=Vec3(-0.41, btn_y, 0),
            scale=Vec3(0.18, btn_h, 1),
            color=color.rgb32(142, 68, 173),
            text_size=0.82,
            on_click=self.trigger_random_mission,
        )

        # 3. Tombol Jeda / Lanjut
        self.btn_pause = Button(
            text="Jeda [Spasi]",
            position=Vec3(-0.23, btn_y, 0),
            scale=Vec3(0.15, btn_h, 1),
            color=color.rgb32(230, 126, 34),
            text_size=0.82,
            on_click=self.toggle_pause,
        )

        # 4. Tombol Reset
        Button(
            text="Reset [R]",
            position=Vec3(-0.08, btn_y, 0),
            scale=Vec3(0.13, btn_h, 1),
            color=color.rgb32(192, 57, 43),
            text_size=0.82,
            on_click=self.reset_all,
        )

        # 5. Tombol Kamera
        self.btn_cam = Button(
            text="Kamera: Isometrik [V]",
            position=Vec3(0.11, btn_y, 0),
            scale=Vec3(0.22, btn_h, 1),
            color=color.rgb32(52, 73, 94),
            text_size=0.82,
            on_click=self.cycle_camera,
        )

        # 6. Tombol Pengatur Kecepatan
        Button(
            text="Lambat [-]",
            position=Vec3(0.29, btn_y, 0),
            scale=Vec3(0.12, btn_h, 1),
            color=color.rgb32(44, 62, 80),
            text_size=0.78,
            on_click=lambda: self.adjust_speed(-1.5),
        )
        Button(
            text="Cepat [+]",
            position=Vec3(0.42, btn_y, 0),
            scale=Vec3(0.12, btn_h, 1),
            color=color.rgb32(44, 62, 80),
            text_size=0.78,
            on_click=lambda: self.adjust_speed(1.5),
        )

        # 7. Tombol Keluar
        Button(
            text="Keluar [Esc]",
            position=Vec3(0.59, btn_y, 0),
            scale=Vec3(0.15, btn_h, 1),
            color=color.rgb32(35, 40, 50),
            text_size=0.8,
            on_click=application.quit,
        )

    def toggle_hud_mode(self):
        """Beralih antara Mode Serius (WMS Analytics) dan Mode Gamifikasi (Arcade)."""
        self.is_serious_mode = not self.is_serious_mode
        self.hud_serious.set_visible(self.is_serious_mode)
        self.hud_gamification.set_visible(not self.is_serious_mode)

        if self.is_serious_mode:
            self.btn_hud_mode.text = "Mode HUD: Serious [M]"
            self.btn_hud_mode.color = color.rgb32(41, 128, 185)
        else:
            self.btn_hud_mode.text = "Mode HUD: Game [M]"
            self.btn_hud_mode.color = color.rgb32(233, 30, 99)

    def trigger_random_mission(self):
        """Menjalankan balapan acak otomatis."""
        self.interaction_sys.reset_interaction()
        success = self.mission_mgr.trigger_random_mission()
        if success:
            self.interaction_sys.prompt_text = "MISI ACAK DILUNCURKAN! A* vs GBFS sedang balapan."

    def toggle_pause(self):
        """Menjeda / melanjutkan pergerakan robot."""
        is_paused = self.mission_mgr.toggle_pause()
        if is_paused:
            self.btn_pause.text = "Lanjut [Spasi]"
            self.btn_pause.color = color.rgb32(39, 174, 96)
        else:
            self.btn_pause.text = "Jeda [Spasi]"
            self.btn_pause.color = color.rgb32(230, 126, 34)

    def reset_all(self):
        """Mereset posisi robot dan seleksi interaksi."""
        self.mission_mgr.reset_race()
        self.interaction_sys.reset_interaction()
        self.btn_pause.text = "Jeda [Spasi]"
        self.btn_pause.color = color.rgb32(230, 126, 34)

    def cycle_camera(self):
        """Mengganti mode kamera."""
        new_mode = self.scene.cycle_camera_mode()
        self.btn_cam.text = f"Kamera: {new_mode.capitalize()} [V]"

    def adjust_speed(self, delta: float):
        """Menyesuaikan kecepatan armada."""
        self.mission_mgr.adjust_speed(delta)

    def update(self):
        """Sinkronisasi HUD per frame."""
        self.interaction_sys.update()

        # Update HUD yang sedang aktif
        if self.is_serious_mode:
            self.hud_serious.update(self.mission_mgr, self.interaction_sys)
        else:
            self.hud_gamification.update(self.mission_mgr, self.interaction_sys)

        # Update follow camera jika mode kamera mengekor
        if self.scene.current_cam_mode == "follow_alpha":
            self.scene.update_follow_camera(self.mission_mgr.robot_alpha.position)
        elif self.scene.current_cam_mode == "follow_beta":
            self.scene.update_follow_camera(self.mission_mgr.robot_beta.position)

    def handle_input(self, key: str):
        """Menangani penekanan tombol keyboard & klik mouse raycast."""
        if key == 'left mouse down':
            self.interaction_sys.handle_click()
        elif key == 'm':
            self.toggle_hud_mode()
        elif key == 'g':
            self.trigger_random_mission()
        elif key == 'space':
            self.toggle_pause()
        elif key == 'r':
            self.reset_all()
        elif key == 'v':
            self.cycle_camera()
        elif key in ('+', '=', 'up arrow'):
            self.adjust_speed(1.5)
        elif key in ('-', 'down arrow'):
            self.adjust_speed(-1.5)
        elif key == '1':
            self.scene.apply_camera_mode("follow_alpha")
            self.btn_cam.text = "Kamera: Follow Alpha [V]"
        elif key == '2':
            self.scene.apply_camera_mode("follow_beta")
            self.btn_cam.text = "Kamera: Follow Beta [V]"
        elif key == 'escape':
            application.quit()
