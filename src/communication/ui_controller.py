"""
ui_controller.py
================
Pengendali UI Master & Keyboard / Mouse Input Handler.
Mengelola tombol kontrol di layar dengan desain modern glassmorphism Slate Gray,
peralihan mode HUD ganda (Serious vs Gamification), siklus kamera POV dashcam,
multi-tool terrain modifiers, transfer zona, dan integrasi siklus hidup simulator.
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
        self.scene.mission_mgr = mission_manager

        self.hud_serious = SeriousHUD()
        self.hud_gamification = GamificationHUD()
        self.is_serious_mode = True
        self._last_aspect_ratio: float = 0.0

        self._create_screen_buttons()
        self._update_dock_layout()

    def _create_screen_buttons(self):
        self.btn_y = -0.458
        self.btn_h = 0.045

        # Panel Bottom Dock Glassmorphism Modern Slate Gray
        self.dock_bg = Entity(
            parent=camera.ui,
            model='quad',
            position=Vec3(0, self.btn_y, 0.01),
            scale=Vec3(0.95, self.btn_h * 1.6, 1),
            color=color.rgba32(20, 26, 38, 230),
        )

        def make_btn(text, bg_color, text_color, on_click):
            return Button(
                text=text,
                scale=Vec3(0.1, self.btn_h, 1),
                color=color.rgb32(*bg_color),
                text_color=color.rgb32(*text_color),
                text_size=0.55,
                on_click=on_click,
                highlight_color=color.rgb32(min(255, bg_color[0] + 25), min(255, bg_color[1] + 25), min(255, bg_color[2] + 25)),
                font='assets/fonts/Roboto-Bold.ttf',
            )

        bg_dark = (30, 41, 59)

        # 1. Kontrol Mode & Algoritma
        self.btn_hud_mode = make_btn("SERIOUS", bg_dark, (56, 189, 248), self.toggle_hud_mode)
        self.btn_heuristic = make_btn("MANHATTAN", bg_dark, (52, 211, 153), self.cycle_heuristic)

        # 2. Misi & Zona
        self.btn_random = make_btn("RANDOM", bg_dark, (192, 132, 252), self.trigger_random_mission)
        self.btn_transfer = make_btn("ZONE", bg_dark, (0, 229, 255), self.trigger_zone_transfer)

        # 3. Terrain Modifier Multi-Tool ([1] Box / [2] Oil / [3] Boost)
        self.btn_tool = make_btn("[1] BOX", bg_dark, (245, 180, 20), self.cycle_tool)

        # 4. Kontrol Simulasi
        self.btn_pause = make_btn("PAUSE", bg_dark, (251, 146, 60), self.toggle_pause)
        self.btn_reset = make_btn("RESET", bg_dark, (248, 113, 113), self.reset_all)

        # 5. Sudut Pandang Kamera (POV Dashcam Alpha/Beta / Topdown / Isometric)
        self.btn_cam = make_btn("[C] Isometrik", bg_dark, (148, 163, 184), self.cycle_camera)

        # 6. Tombol Keluar
        self.btn_quit = make_btn("EXIT", (127, 29, 29), (255, 255, 255), application.quit)

        # --- Badge Kotak Pending Orders di Kanan Atas ---
        self.pending_bg = Entity(
            parent=camera.ui,
            model='quad',
            scale=Vec3(0.22, 0.05, 1),
            color=color.rgba32(20, 26, 38, 230),
        )
        self.pending_text = Text(
            parent=camera.ui,
            text="PENDING: 0",
            scale=1.0,
            color=color.rgb32(0, 255, 255),
            origin=(0, 0),
            font='assets/fonts/Roboto-Bold.ttf',
        )

    def _update_dock_layout(self):
        aspect = window.aspect_ratio
        if abs(aspect - self._last_aspect_ratio) < 0.01:
            return
        self._last_aspect_ratio = aspect

        self.hud_serious.update_layout()
        self.hud_gamification.update_layout()

        # Posisi Badge Kotak Kanan Atas
        pos_x = (aspect / 2.0) - 0.15
        pos_y = 0.44
        self.pending_bg.position = Vec3(pos_x, pos_y, 0)
        self.pending_text.position = Vec3(pos_x, pos_y, -0.01)

        # Layout Tombol Dock Terpusat
        btns = [
            (self.btn_hud_mode, 0.105),
            (self.btn_heuristic, 0.120),
            (self.btn_random, 0.090),
            (self.btn_transfer, 0.080),
            (self.btn_tool, 0.090),
            (self.btn_pause, 0.080),
            (self.btn_reset, 0.080),
            (self.btn_cam, 0.125),
            (self.btn_quit, 0.070),
        ]
        gap = 0.010
        total_w = sum(w for _, w in btns) + gap * (len(btns) - 1)

        self.dock_bg.scale = Vec3(total_w + 0.035, self.btn_h * 1.55, 1)

        cur_x = -total_w / 2.0
        for btn, w in btns:
            btn.position = Vec3(cur_x + w / 2.0, self.btn_y, 0)
            btn.scale = Vec3(w, self.btn_h, 1)
            cur_x += w + gap

    # =========================================================================
    # HANDLERS INTERAKSI & SIKLUS HIDUP SIMULATOR
    # =========================================================================
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

    def trigger_zone_transfer(self):
        """Memicu misi transfer kargo antar-zona (Fitur 2: Menuju Transfer Gate Zone B)."""
        self.interaction_sys.reset_interaction()
        if hasattr(self.mission_mgr, 'dispatch_zone_transfer'):
            success = self.mission_mgr.dispatch_zone_transfer()
        elif hasattr(self.mission_mgr, 'trigger_zone_transfer_mission'):
            success = self.mission_mgr.trigger_zone_transfer_mission()
        else:
            success = False
        if success:
            from src.communication.interaction_system import InteractionState
            self.interaction_sys.state = InteractionState.RACING
            self.interaction_sys.prompt_text = "Misi Aktif: Menuju Transfer Gate! Lewati gerbang untuk membuka Zone B."
        else:
            self.interaction_sys.prompt_text = "Gagal memicu misi Transfer Gate (pastikan kargo tersedia)."

    def cycle_tool(self):
        """Berganti tool penempatan medan secara berurutan: Box -> Oil Spill -> Boost Pad."""
        from src.communication.interaction_system import PlacementTool
        curr = getattr(self.interaction_sys, 'active_tool', PlacementTool.CARGO_BOX)
        if curr == PlacementTool.CARGO_BOX:
            nxt = PlacementTool.OIL_SPILL
        elif curr == PlacementTool.OIL_SPILL:
            nxt = PlacementTool.BOOST_PAD
        else:
            nxt = PlacementTool.CARGO_BOX
        self.set_tool(nxt)

    def set_tool(self, tool):
        """Mengatur tool interaksi dan memperbarui label serta aksen tombol dock."""
        from src.communication.interaction_system import PlacementTool
        self.interaction_sys.set_tool(tool)
        labels = {
            PlacementTool.CARGO_BOX: "[1] BOX",
            PlacementTool.OIL_SPILL: "[2] OIL",
            PlacementTool.BOOST_PAD: "[3] BOOST",
        }
        self.btn_tool.text = labels.get(tool, "[1] BOX")
        if tool == PlacementTool.OIL_SPILL:
            self.btn_tool.text_color = color.rgb32(245, 180, 20)
        elif tool == PlacementTool.BOOST_PAD:
            self.btn_tool.text_color = color.rgb32(0, 245, 140)
        else:
            self.btn_tool.text_color = color.rgb32(235, 145, 45)

    def toggle_pause(self):
        is_paused = self.mission_mgr.toggle_pause()
        self.btn_pause.text = "RESUME" if is_paused else "PAUSE"

    def reset_all(self):
        self.mission_mgr.reset_race()
        self.interaction_sys.reset_interaction()
        self.btn_pause.text = "PAUSE"

    def cycle_camera(self):
        """Mengganti mode kamera dalam siklus: Isometrik -> Top-Down -> POV Alpha (A*) -> POV Beta (GBFS) -> Isometrik."""
        new_mode = self.scene.cycle_camera_mode()
        self._update_camera_ui(new_mode)

    def set_camera(self, mode: str):
        """Mengatur mode kamera secara langsung dan memperbarui tampilan UI."""
        self.scene.apply_camera_mode(mode, mission_mgr=self.mission_mgr)
        self._update_camera_ui(mode)

    def cycle_pov_camera(self):
        """Pintasan pergantian sudut kamera POV Dashcam First-Person."""
        self.cycle_camera()

    def _update_camera_ui(self, mode: str):
        """Memperbarui teks tombol kamera dan prompt text indikator dramatis sesuai mode kamera aktif."""
        labels = {
            "isometrik": "[C] Isometrik",
            "topdown": "[C] Top-Down",
            "pov_alpha": "[C] POV Alpha",
            "pov_beta": "[C] POV Beta",
            "free_cam": "[C] Free-Cam",
            "bebas": "[C] Free-Cam",
        }
        self.btn_cam.text = labels.get(mode, f"[C] {mode.capitalize()}")

        if mode == "pov_alpha":
            self.btn_cam.color = color.rgb32(0, 160, 230)
            self.interaction_sys.prompt_text = "[CAM] DASHCAM AKTIF: AGV ALPHA (A*)"
        elif mode == "pov_beta":
            self.btn_cam.color = color.rgb32(235, 130, 20)
            self.interaction_sys.prompt_text = "[CAM] DASHCAM AKTIF: AGV BETA (GBFS)"
        elif mode == "topdown":
            self.btn_cam.color = color.rgb32(50, 70, 95)
            self.interaction_sys.prompt_text = "Mode Kamera: Top-Down (Pengawasan Udara 2D)."
        elif mode == "isometrik":
            self.btn_cam.color = color.rgb32(50, 70, 95)
            self.interaction_sys.prompt_text = "Mode Kamera: Isometrik."
        elif mode in ("free_cam", "bebas"):
            self.btn_cam.color = color.rgb32(80, 50, 110)
            self.interaction_sys.prompt_text = (
                "[FREE-CAM / GOD MODE] Tahan Klik Kanan Mouse untuk rotasi pandangan, "
                "WASD / Panah / Scroll untuk terbang melintasi seluruh gudang 3D!"
            )
        else:
            self.btn_cam.color = color.rgb32(50, 70, 95)
            self.interaction_sys.prompt_text = f"Mode Kamera: {mode.capitalize()}."

    def adjust_speed(self, delta: float):
        """Menyesuaikan kecepatan armada."""
        self.mission_mgr.adjust_speed(delta)

    def update(self):
        """Loop update per frame untuk layout dock, badge antrean, HUD aktif, dan kamera POV."""
        self._update_dock_layout()
        self.interaction_sys.update()

        q_count = len(self.mission_mgr.task_queue)
        self.pending_text.text = f"PENDING: {q_count}"
        if q_count > 0:
            self.pending_text.color = color.rgb32(251, 146, 60)
        else:
            self.pending_text.color = color.rgb32(0, 255, 255)

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
        elif key in ('c', 'f', 'k', 'v'):
            self.cycle_camera()
        elif key in ('x', 'delete', 'backspace'):
            self.scene.clear_all_dynamic_obstacles()
            self.scene.clear_all_terrain_modifiers()
            self.mission_mgr.graph.clear_dynamic_obstacles()
            self.mission_mgr.graph.clear_terrain_modifiers()
            if hasattr(self.scene, 'clear_exploration_heatmap'):
                self.scene.clear_exploration_heatmap()
            self.interaction_sys.prompt_text = "[Info] Seluruh rintangan dinamis, tumpahan oli, boost pad, dan heatmap telah dibersihkan."
        elif key in ('+', '='):
            self.adjust_speed(1.5)
        elif key == '-':
            self.adjust_speed(-1.5)
        elif key == '1':
            from src.communication.interaction_system import PlacementTool
            self.set_tool(PlacementTool.CARGO_BOX)
        elif key == '2':
            from src.communication.interaction_system import PlacementTool
            self.set_tool(PlacementTool.OIL_SPILL)
        elif key == '3':
            from src.communication.interaction_system import PlacementTool
            self.set_tool(PlacementTool.BOOST_PAD)
        elif key == 'escape':
            application.quit()
