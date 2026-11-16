"""
ui_controller.py
================
Pengendali UI Master & Keyboard / Mouse Input Handler.
Mengelola tombol kontrol di layar, peralihan mode HUD ganda (Serious vs Gamification),
serta integrasi siklus hidup simulator.
"""

from ursina import Button, Vec3, color, application, Entity, camera, Text, window
from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem
from src.communication.hud_serious import SeriousHUD
from src.communication.hud_gamification import GamificationHUD
from src.environment.warehouse_scene import WarehouseScene

class UIController:
    def __init__(self, mission_manager: MissionManager, interaction_system: InteractionSystem, scene: WarehouseScene):
        self.mission_mgr = mission_manager
        self.interaction_sys = interaction_system
        self.scene = scene

        self.hud_serious = SeriousHUD()
        self.hud_gamification = GamificationHUD()
        self.is_serious_mode = True
        self._last_aspect_ratio: float = 0.0

        self._create_screen_buttons()
        self._update_dock_layout()

    def _create_screen_buttons(self):
        self.btn_y = -0.458
        self.btn_h = 0.045

        self.dock_bg = Entity(parent=camera.ui, model='quad', position=Vec3(0, self.btn_y, 0.01), scale=Vec3(0.95, self.btn_h * 1.6, 1), color=color.rgba32(20, 26, 38, 230))

        def make_btn(text, bg_color, text_color, on_click):
            return Button(
                text=text, scale=Vec3(0.1, self.btn_h, 1),
                color=color.rgb32(*bg_color), text_color=color.rgb32(*text_color),
                text_size=0.55, on_click=on_click,
                highlight_color=color.rgb32(bg_color[0]+20, bg_color[1]+20, bg_color[2]+20),
                font='assets/fonts/Roboto-Bold.ttf'
            )

        bg_dark = (30, 41, 59)
        self.btn_hud_mode = make_btn("SERIOUS", bg_dark, (56, 189, 248), self.toggle_hud_mode)
        self.btn_heuristic = make_btn("MANHATTAN", bg_dark, (52, 211, 153), self.cycle_heuristic)
        self.btn_random = make_btn("RANDOM", bg_dark, (192, 132, 252), self.trigger_random_mission)
        self.btn_pause = make_btn("PAUSE", bg_dark, (251, 146, 60), self.toggle_pause)
        self.btn_reset = make_btn("RESET", bg_dark, (248, 113, 113), self.reset_all)
        self.btn_cam = make_btn("ISO", bg_dark, (148, 163, 184), self.cycle_camera)
        self.btn_quit = make_btn("EXIT", (127, 29, 29), (255, 255, 255), application.quit)

        # --- KOTAK PENDING YANG SUDAH PASTI RAPI ---
        self.pending_bg = Entity(parent=camera.ui, model='quad', scale=Vec3(0.22, 0.05, 1), color=color.rgba32(20, 26, 38, 230))
        self.pending_text = Text(
            parent=camera.ui, 
            text="PENDING: 0", 
            scale=1.0, 
            color=color.rgb32(0, 255, 255), 
            origin=(0, 0), 
            font='assets/fonts/Roboto-Bold.ttf'
        )

    def _update_dock_layout(self):
        aspect = window.aspect_ratio
        if abs(aspect - self._last_aspect_ratio) < 0.01: return
        self._last_aspect_ratio = aspect

        self.hud_serious.update_layout()
        self.hud_gamification.update_layout()

        # Posisi Kotak Kanan Atas (Disamakan persis)
        pos_x = (aspect / 2.0) - 0.15
        pos_y = 0.44
        self.pending_bg.position = Vec3(pos_x, pos_y, 0)
        self.pending_text.position = Vec3(pos_x, pos_y, -0.01)

        # Tombol Bawah
        btns = [
            (self.btn_hud_mode, 0.12), (self.btn_heuristic, 0.13), (self.btn_random, 0.10),
            (self.btn_pause, 0.09), (self.btn_reset, 0.09),
            (self.btn_cam, 0.08), (self.btn_quit, 0.08),
        ]
        gap = 0.015
        total_w = sum(w for _, w in btns) + gap * (len(btns) - 1)

        self.dock_bg.scale = Vec3(total_w + 0.04, self.btn_h * 1.6, 1)

        cur_x = -total_w / 2.0
        for btn, w in btns:
            btn.position = Vec3(cur_x + w / 2.0, self.btn_y, 0)
            btn.scale = Vec3(w, self.btn_h, 1)
            cur_x += w + gap

    # --- Handlers ---
    def toggle_hud_mode(self):
        self.is_serious_mode = not self.is_serious_mode
        self.hud_serious.set_visible(self.is_serious_mode)
        self.hud_gamification.set_visible(not self.is_serious_mode)
        self.btn_hud_mode.text = "SERIOUS" if self.is_serious_mode else "ARCADE"

    def cycle_heuristic(self):
        new_h = self.mission_mgr.cycle_heuristic()
        self.btn_heuristic.text = new_h.upper()

    def trigger_random_mission(self):
        self.interaction_sys.reset_interaction()
        if self.mission_mgr.trigger_random_mission():
            from src.communication.interaction_system import InteractionState
            self.interaction_sys.state = InteractionState.RACING

    def toggle_pause(self):
        is_paused = self.mission_mgr.toggle_pause()
        self.btn_pause.text = "RESUME" if is_paused else "PAUSE"

    def reset_all(self):
        self.mission_mgr.reset_race()
        self.interaction_sys.reset_interaction()
        self.btn_pause.text = "PAUSE"

    def cycle_camera(self):
        new_mode = self.scene.cycle_camera_mode()
        labels = {"isometrik": "ISO", "topdown": "TOP", "free_cam": "FREE", "bebas": "FREE"}
        self.btn_cam.text = labels.get(new_mode, "ISO")

    def adjust_speed(self, delta): self.mission_mgr.adjust_speed(delta)

    def update(self):
        self._update_dock_layout()
        self.interaction_sys.update()
        q_count = len(self.mission_mgr.task_queue)
        self.pending_text.text = f"PENDING: {q_count}"
        
        if self.is_serious_mode: self.hud_serious.update(self.mission_mgr, self.interaction_sys)
        else: self.hud_gamification.update(self.mission_mgr, self.interaction_sys)

    def handle_input(self, key: str):
        if key == 'left mouse down': self.interaction_sys.handle_click()
        elif key == 'right mouse down' and self.scene.current_cam_mode not in ("free_cam", "bebas"): self.interaction_sys.handle_right_click()
        elif key == 'm': self.toggle_hud_mode()
        elif key == 'h': self.cycle_heuristic()
        elif key == 'g': self.trigger_random_mission()
        elif key == 'space': self.toggle_pause()
        elif key == 'r': self.reset_all()
        elif key in ('k', 'v'): self.cycle_camera()
        elif key in ('+', '='): self.adjust_speed(1.5)
        elif key == '-': self.adjust_speed(-1.5)
        elif key == 'escape': application.quit()