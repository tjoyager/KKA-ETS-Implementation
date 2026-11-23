"""AGV COMMAND CENTER V14 — industrial polish, warmer palette, and warehouse facelift.

Focus: make speed controls readable and push the warehouse look further.
Keeps all search, mission, POV and Free Cam behavior intact.
"""

import math
from src.communication.visual_theme import rounded_surface
from ursina.shaders import unlit_shader

from ursina import Button, Entity, Text, Vec3, application, camera, color, held_keys, mouse, time as ursina_time, window

from src.behavior.mission_manager import MissionManager
from src.communication.hud_gamification import GamificationHUD
from src.communication.hud_serious import SeriousHUD
from src.communication.interaction_system import InteractionState, InteractionSystem, PlacementTool
from src.environment.warehouse_scene import WarehouseScene
from src.environment.industrial_facelift import IndustrialFacelift


class UIController:
    V12_MARKER = "AGV COMMAND CENTER V13"
    FONT = "assets/fonts/Roboto-Regular.ttf"
    FONT_BOLD = "assets/fonts/Roboto-Bold.ttf"
    BG = (19, 28, 35)
    SURFACE = (40, 54, 64)
    SURFACE_ALT = (29, 42, 51)
    SURFACE_HOVER = (57, 78, 88)
    MUTED = (151, 171, 181)
    CYAN = (93, 201, 189)
    AMBER = (231, 177, 101)
    GREEN = (130, 198, 156)
    TEXT = (234, 242, 243)
    DANGER = (132, 78, 70)

    def __init__(self, mission_manager: MissionManager, interaction_system: InteractionSystem, scene: WarehouseScene):
        self.mission_mgr = mission_manager
        self.interaction_sys = interaction_system
        self.scene = scene
        from src.communication.warehouse_audio import WarehouseAudio
        self.warehouse_audio = WarehouseAudio(mission_manager)
        self.scene.mission_mgr = mission_manager
        self.hud_serious = SeriousHUD()
        self.hud_gamification = GamificationHUD()
        self.is_serious_mode = True
        self.hud_visible = True
        self.report_open = False
        self.tools_open = True
        self.legend_open = True
        self._tools_user_toggled = False
        self._last_aspect_ratio = -1.0
        self._speed_toast_until = 0.0
        self._build_ui()
        self.industrial_facelift = IndustrialFacelift(scene)
        self._update_layout()
        self._refresh_tool_buttons()
        self._refresh_controls()
        self._apply_tools_visibility()
        self._apply_hud_visibility()

    @staticmethod
    def _set(widget, value):
        value = str(value)
        if widget.text != value:
            widget.text = value

    @staticmethod
    def _clip(value, limit):
        value = " ".join(str(value).split())
        return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."

    def _button(self, label, on_click, width=0.10, tint=None):
        tint = tint or self.SURFACE
        return Button(
            parent=camera.ui,
            shader=unlit_shader,
            text=label,
            texture=rounded_surface(width, 0.048),
            scale=Vec3(width, 0.048, 1),
            color=color.rgb32(*tint),
            text_color=color.rgb32(*self.TEXT),
            text_size=0.70,
            highlight_color=color.rgb32(*tuple(min(255, k + 16) for k in tint)),
            pressed_scale=1.0,
            font=self.FONT,
            on_click=on_click,
        )

    def _text(self, label, scale=0.64, tint=None, bold=False, origin=(-0.5, 0)):
        return Text(
            parent=camera.ui,
            text=label,
            scale=scale,
            origin=origin,
            color=color.rgb32(*(tint or self.TEXT)),
            font=self.FONT_BOLD if bold else self.FONT,
        )

    def _panel(self, width, height, fill=None, collider=True):
        return Entity(
            parent=camera.ui,
            model="quad",
            shader=unlit_shader,
            texture=rounded_surface(width, height) if height > 0.02 else None,
            collider="box" if collider else None,
            scale=Vec3(width, height, 1),
            color=color.rgba32(*((fill or self.BG) + (245,) if len(fill or self.BG) == 3 else (fill or self.BG))),
        )

    def _build_ui(self):
        # Top bar
        self.top_bg = self._panel(0.9, 0.058, (19, 28, 35, 242))
        self.top_rule = self._panel(0.9, 0.0016, (74, 139, 141, 155), collider=False)
        self.top_title = self._text("WAREHOUSE  /  Command", 0.78, self.TEXT, True)
        self.top_status = self._text("Zone A · Ready · 00:00", 0.58, self.MUTED, origin=(0, 0))
        self.pending_bg = self._panel(0.12, 0.038, (32, 57, 63, 230))
        self.pending_text = self._text("Queue 0", 0.56, self.CYAN, True, origin=(0, 0))

        # Right sidebar
        self.side_bg = self._panel(0.34, 0.68, (19, 28, 35, 242))
        self.side_rule = self._panel(0.074, 0.003, (74, 139, 141, 255), collider=False)
        self.side_title = self._text("Operations", 0.83, self.TEXT, True)
        self.side_sub = self._text("Selected: Cargo", 0.57, self.MUTED)
        self.btn_tools = self._button("Hide [P]", self.toggle_tools, 0.094)
        self.btn_legend = self._button("Tutup [L]", self.toggle_legend, 0.12, (39, 79, 78))
        self.legend_panel = Entity(parent=camera.ui, model="quad", shader=unlit_shader,
                                  texture="assets/ui/warehouse_legend_id.png", collider="box")

        self.run_label = self._text("01  /  DISPATCH", 0.53, self.MUTED, True)
        self.terrain_label = self._text("02  /  ENVIRONMENT", 0.53, self.MUTED, True)
        self.view_label = self._text("03  /  WORKSPACE", 0.53, self.MUTED, True)
        self.sep_1 = self._panel(0.28, 0.0015, (63, 81, 104, 145), collider=False)
        self.sep_2 = self._panel(0.28, 0.0015, (63, 81, 104, 145), collider=False)
        self.tools_hint = self._text("Cargo block selected", 0.55, self.MUTED)
        self.tools_footer = self._text("Right-click robot: return to dock", 0.51, self.MUTED)

        self.btn_random = self._button("Random race [G]", self.trigger_random_mission, 0.29, (36, 108, 104))
        self.btn_transfer = self._button("Transfer zone [T]", self.trigger_zone_transfer, 0.29)
        self.btn_cargo = self._button("Cargo block [1]", lambda: self.select_tool(PlacementTool.CARGO_BOX), 0.29)
        self.btn_oil = self._button("Oil spill [2]", lambda: self.select_tool(PlacementTool.OIL_SPILL), 0.29)
        self.btn_boost = self._button("Speed boost [3]", lambda: self.select_tool(PlacementTool.BOOST_PAD), 0.29)
        self.btn_freecam = self._button("Free camera [B]", self.toggle_free_camera, 0.29)
        self.btn_report = self._button("View analysis [J]", self.toggle_report, 0.29)
        self.btn_clear = self._button("Clear terrain [X]", self.clear_terrain, 0.29, (92, 56, 56))
        self._tool_panel_items = [
            self.side_bg, self.side_rule, self.side_title, self.side_sub,
            self.run_label, self.terrain_label, self.view_label,
            self.sep_1, self.sep_2, self.tools_hint, self.tools_footer,
            self.btn_random, self.btn_transfer, self.btn_cargo, self.btn_oil,
            self.btn_boost, self.btn_freecam, self.btn_report, self.btn_clear,
        ]

        # Center overlays
        self.result_bg = self._panel(0.60, 0.056, (19, 28, 35, 228))
        self.result_title = self._text("Race complete", 0.60, self.TEXT, True, origin=(0, 0))
        self.result_detail = self._text("", 0.50, self.MUTED, origin=(0, 0))

        self.message_bg = self._panel(0.76, 0.044, (19, 28, 35, 224))
        self.message_text = self._text("Choose pickup and drop-off shelves", 0.56, self.TEXT, origin=(0, 0))

        # Bottom dock
        self.dock_bg = self._panel(0.70, 0.062, (19, 28, 35, 246))
        self.dock_rule = self._panel(0.66, 0.0014, (74, 139, 141, 145), collider=False)
        self.btn_hud_mode = self._button("Serious [M]", self.toggle_hud_mode, 0.102)
        self.btn_heuristic = self._button("Manhattan [H]", self.cycle_heuristic, 0.122)
        self.btn_pause = self._button("Pause [Space]", self.toggle_pause, 0.120, (36, 108, 104))
        self.btn_reset = self._button("Reset [R]", self.reset_all, 0.085)
        self.btn_cam = self._button("Camera [C]", self.cycle_camera, 0.110)
        self.btn_slower = self._button(" ", lambda: self.adjust_speed(-1.5), 0.052)
        self.btn_faster = self._button(" ", lambda: self.adjust_speed(1.5), 0.052)
        # Separate glyphs avoid Ursina Button text-size overflow.
        self.speed_minus_glyph = self._text("-", 1.05, self.TEXT, True, origin=(0, 0))
        self.speed_plus_glyph = self._text("+", 1.05, self.TEXT, True, origin=(0, 0))
        # Current speed is always visible between the two adjustment buttons.
        self.speed_chip_bg = self._panel(0.092, 0.043, (32, 50, 59, 255))
        self.speed_chip_text = self._text("6.0", 0.72, self.TEXT, True, origin=(0, 0))
        self.speed_chip_caption = self._text("SPEED", 0.43, self.MUTED, True, origin=(0, 0))
        # Small, short-lived toast directly above the dock after adjustment.
        self.speed_toast_bg = self._panel(0.18, 0.044, (32, 71, 72, 250), collider=False)
        self.speed_toast_text = self._text("Speed 6.0", 0.58, self.TEXT, True, origin=(0, 0))
        self.speed_toast_bg.enabled = False
        self.speed_toast_text.enabled = False
        self.btn_quit = self._button("Exit", application.quit, 0.060, (90, 41, 41))
        self._dock_buttons = [
            (self.btn_hud_mode, 0.102), (self.btn_heuristic, 0.122),
            (self.btn_pause, 0.120), (self.btn_reset, 0.085),
            (self.btn_cam, 0.110), (self.btn_slower, 0.052),
            (self.speed_chip_bg, 0.094), (self.btn_faster, 0.052),
            (self.btn_quit, 0.060),
        ]

        # V10 ANALYSIS VIEW: fully opaque matte surface. No blurred, glowing,
        # or semi-transparent center: the world is entirely obscured while open.
        # All elements are flat-colored quads and text, independent of 3D light.
        self.report_dim = self._panel(2.5, 1.04, (12, 19, 25, 255))
        self.report_edge = self._panel(0.95, 0.80, (60, 86, 96, 255), collider=False)
        self.report_bg = self._panel(0.95, 0.80, (19, 28, 35, 255))
        self.report_accent = self._panel(0.05, 0.004, (74, 139, 141, 255), collider=False)
        self.report_kicker = self._text("SIMULATION  /  PERFORMANCE", 0.54, self.MUTED, True)
        self.report_title = self._text("Race analysis", 1.02, self.TEXT, True)
        self.report_subtitle = self._text("Comparing the latest A* and GBFS routes", 0.60, self.MUTED)
        self.report_divider = self._panel(0.87, 0.0015, (55, 72, 91, 255), collider=False)

        # Two takeaways above the detailed metrics.
        self.report_summary_a = self._panel(0.38, 0.098, (29, 43, 53, 255), collider=False)
        self.report_summary_b = self._panel(0.38, 0.098, (29, 43, 53, 255), collider=False)
        self.report_arrival_label = self._text("FIRST TO ARRIVE", 0.53, self.MUTED, True)
        self.report_outcome = self._text("Pending", 0.87, self.TEXT, True)
        self.report_cost_label = self._text("LOWEST ROUTE COST", 0.53, self.MUTED, True)
        self.report_cost_value = self._text("Pending", 0.87, self.TEXT, True)
        self.report_summary_accents = [
            self._panel(0.004, 0.064, (93, 201, 189, 255), collider=False),
            self._panel(0.004, 0.064, (231, 177, 101, 255), collider=False),
        ]

        self.report_section_text = self._text("METRIC COMPARISON", 0.55, self.MUTED, True)
        self.report_columns = [
            self._text("METRIC", 0.53, self.MUTED, True),
            self._text("ALPHA  /  A*", 0.56, self.CYAN, True, origin=(0, 0)),
            self._text("BETA  /  GBFS", 0.56, self.AMBER, True, origin=(0, 0)),
            self._text("BEST", 0.53, self.MUTED, True, origin=(0, 0)),
        ]
        self.report_rows = []
        self.report_row_bgs = []
        self.report_row_accents = []
        self.report_lead_bgs = []
        for idx, label in enumerate(("Route cost", "Nodes explored", "Compute time")):
            surface = (31, 46, 57, 255) if idx % 2 == 0 else (26, 39, 49, 255)
            self.report_row_bgs.append(self._panel(0.85, 0.087, surface, collider=False))
            self.report_row_accents.append(self._panel(0.003, 0.043, (78, 100, 122, 255), collider=False))
            self.report_lead_bgs.append(self._panel(0.095, 0.034, (36, 51, 68, 255), collider=False))
            self.report_rows.append([
                self._text(label, 0.68, self.TEXT, True),
                self._text("—", 0.81, self.TEXT, True, origin=(0, 0)),
                self._text("—", 0.81, self.TEXT, True, origin=(0, 0)),
                self._text("—", 0.61, self.TEXT, True, origin=(0, 0)),
            ])

        self.report_bottom_rule = self._panel(0.87, 0.0016, (55, 72, 91, 255), collider=False)
        self.report_note = self._text("Lower is better  ·  Search time excludes robot movement", 0.56, self.MUTED, origin=(0, 0))
        self.report_hint = self._text("Different start docks  ·  Latest plan only  ·  J / Esc to close", 0.50, self.MUTED, origin=(0, 0))
        self.btn_close_report = self._button("Close  [J]", self.toggle_report, 0.12, (35, 52, 72))

        self._report_elements = [
            self.report_dim, self.report_edge, self.report_bg, self.report_accent,
            self.report_kicker, self.report_title, self.report_subtitle,
            self.report_divider, self.report_summary_a, self.report_summary_b,
            *self.report_summary_accents, self.report_arrival_label,
            self.report_outcome, self.report_cost_label, self.report_cost_value,
            self.report_section_text, *self.report_columns,
            *self.report_row_bgs, *self.report_row_accents,
            *self.report_lead_bgs,
            *(item for row in self.report_rows for item in row),
            self.report_bottom_rule, self.report_note, self.report_hint,
            self.btn_close_report,
        ]

    def _update_layout(self):
        aspect = max(1.0, float(window.aspect_ratio))
        if abs(aspect - self._last_aspect_ratio) < 0.01:
            return
        self._last_aspect_ratio = aspect
        half = aspect / 2
        self.hud_serious.update_layout()
        self.hud_gamification.update_layout()

        # Top bar
        self.top_bg.position = Vec3(0, 0.464, 0.022)
        self.top_bg.scale = Vec3(aspect - 0.026, 0.056, 1)
        self.top_rule.position = Vec3(0, 0.436, 0.017)
        self.top_rule.scale = Vec3(aspect - 0.040, 0.0014, 1)
        self.top_title.position = Vec3(-half + 0.036, 0.462, 0.010)
        self.top_status.position = Vec3(0.04, 0.462, 0.010)
        self.top_status.scale = 0.55 if aspect >= 1.45 else 0.50
        self.pending_bg.position = Vec3(half - 0.095, 0.462, 0.014)
        self.pending_bg.scale = Vec3(0.12, 0.036, 1)
        self.pending_text.position = Vec3(half - 0.095, 0.462, 0.010)
        self.pending_bg.enabled = aspect >= 1.38
        self.pending_text.enabled = aspect >= 1.38

        # Right sidebar: every button has its own row, and all text stays inside.
        panel_w = 0.34 if aspect >= 1.52 else (0.31 if aspect >= 1.32 else 0.28)
        right = half - 0.016
        legend_w = min(0.32, aspect * 0.28)
        self.legend_panel.scale = Vec3(legend_w, 0.370, 1)
        self.legend_panel.position = Vec3(-half + 0.018 + legend_w / 2, -0.398 + self.legend_panel.scale_y / 2, 0.016)
        center = right - panel_w / 2
        left = right - panel_w + 0.022
        self.side_bg.position = Vec3(center, 0.040, 0.032)
        self.side_bg.scale = Vec3(panel_w, 0.664, 1)
        self.side_rule.position = Vec3(left + 0.042, 0.364, 0.015)
        self.side_rule.scale = Vec3(0.084, 0.003, 1)
        self.side_title.position = Vec3(left, 0.330, 0.010)
        self.side_sub.position = Vec3(left, 0.297, 0.010)
        self.btn_tools.position = Vec3(right - 0.062, 0.330, 0.008)
        self.btn_tools.scale = Vec3(0.096, 0.032, 1)

        self.run_label.position = Vec3(left, 0.261, 0.010)
        self.sep_1.position = Vec3(center, 0.132, 0.014)
        self.sep_1.scale = Vec3(panel_w - 0.044, 0.0015, 1)
        self.terrain_label.position = Vec3(left, 0.104, 0.010)
        self.sep_2.position = Vec3(center, -0.069, 0.014)
        self.sep_2.scale = Vec3(panel_w - 0.044, 0.0015, 1)
        self.view_label.position = Vec3(left, -0.096, 0.010)

        # Controls are deliberately 0.051 apart for 0.043-height buttons.
        for button, y in (
            (self.btn_random, 0.220), (self.btn_transfer, 0.170),
            (self.btn_cargo, 0.064), (self.btn_oil, 0.013),
            (self.btn_boost, -0.038), (self.btn_freecam, -0.135),
            (self.btn_report, -0.186), (self.btn_clear, -0.237),
        ):
            button.position = Vec3(center, y, 0.010)
            button.scale = Vec3(panel_w - 0.048, 0.043, 1)
            button.text_size = 0.68 if aspect >= 1.42 else 0.61

        # No extra tiny text below the last button; it used to overlap the menu.
        self.tools_hint.enabled = False
        self.tools_footer.enabled = False

        # Notification cards don't collide with the prompt or bottom controls.
        self.message_bg.position = Vec3(0, -0.365, 0.024)
        self.message_bg.scale = Vec3(min(0.78, max(0.40, aspect - 0.96)), 0.044, 1)
        self.message_text.position = Vec3(0, -0.365, 0.010)
        self.message_text.scale = 0.57

        self.result_bg.position = Vec3(0, -0.284, 0.024)
        self.result_bg.scale = Vec3(min(0.65, max(0.42, aspect - 1.02)), 0.071, 1)
        self.result_title.position = Vec3(0, -0.267, 0.010)
        self.result_detail.position = Vec3(0, -0.306, 0.010)
        self.result_title.scale = 0.67
        self.result_detail.scale = 0.59

        # The dock sits above the bottom edge, with room for the text glyphs.
        gap = 0.008
        widths = sum(w for _, w in self._dock_buttons)
        total_width = widths + gap * (len(self._dock_buttons) - 1)
        shrink = min(1.0, (aspect - 0.080) / total_width)
        total = total_width * shrink
        self.dock_bg.position = Vec3(0, -0.440, 0.024)
        self.dock_bg.scale = Vec3(total + 0.030, 0.062, 1)
        self.dock_rule.position = Vec3(0, -0.411, 0.017)
        self.dock_rule.scale = Vec3(total + 0.018, 0.0014, 1)
        pos = -total / 2
        for button, w in self._dock_buttons:
            scaled = w * shrink
            button.position = Vec3(pos + scaled / 2, -0.440, 0.010)
            button.scale = Vec3(scaled, 0.043, 1)
            if button is not self.speed_chip_bg:
                button.text_size = 0.65 if scaled >= 0.085 else 0.72
            pos += scaled + gap * shrink
        # Camera UI text is decoupled from Button text autoscaling.
        for button, glyph in ((self.btn_slower, self.speed_minus_glyph),
                              (self.btn_faster, self.speed_plus_glyph)):
            button.color = color.rgb32(*self.SURFACE_ALT)
            glyph.position = Vec3(button.x, button.y, 0.003)
            glyph.scale = 1.05
            glyph.color = color.rgb32(*self.TEXT)
        self.speed_chip_bg.scale = Vec3(0.094 * shrink, 0.043, 1)
        self.speed_chip_text.position = Vec3(self.speed_chip_bg.x, -0.448, 0.003)
        self.speed_chip_text.scale = 0.70 if shrink >= 0.8 else 0.62
        self.speed_chip_caption.position = Vec3(self.speed_chip_bg.x, -0.427, 0.003)
        self.speed_chip_caption.scale = 0.39 if shrink >= 0.8 else 0.34
        self.speed_toast_bg.position = Vec3(self.speed_chip_bg.x, -0.365, 0.019)
        self.speed_toast_text.position = Vec3(self.speed_chip_bg.x, -0.365, 0.009)
        self.speed_toast_bg.scale = Vec3(0.18, 0.044, 1)

        # V10: large centered solid workspace. Fit naturally from 4:3 to 16:9.
        rw = min(0.98, max(0.74, aspect - 0.08))
        panel_top = 0.39
        self.report_dim.position = Vec3(0, 0, -0.035)
        self.report_dim.scale = Vec3(aspect + 0.04, 1.04, 1)
        self.report_edge.position = Vec3(0, 0, -0.054)
        self.report_edge.scale = Vec3(rw + 0.003, 0.795, 1)
        self.report_bg.position = Vec3(0, 0, -0.056)
        self.report_bg.scale = Vec3(rw, 0.792, 1)
        left = -rw / 2 + 0.042
        right = rw / 2 - 0.042

        # Header / Close. Text never shares a position with other elements.
        self.report_accent.position = Vec3(left + 0.029, 0.347, -0.065)
        self.report_accent.scale = Vec3(0.058, 0.0032, 1)
        self.report_kicker.position = Vec3(left, 0.320, -0.078)
        self.report_title.position = Vec3(left, 0.280, -0.078)
        self.report_subtitle.position = Vec3(left, 0.242, -0.078)
        self.btn_close_report.position = Vec3(right - 0.060, 0.303, -0.089)
        self.btn_close_report.scale = Vec3(0.112, 0.041, 1)
        self.btn_close_report.text_size = 0.69
        self.report_divider.position = Vec3(0, 0.218, -0.066)
        self.report_divider.scale = Vec3(rw - 0.083, 0.0016, 1)

        # Summary cards are two equal-width, aligned blocks.
        card_w = (rw - 0.113) / 2
        card_x = (card_w + 0.017) / 2
        for card, cx in ((self.report_summary_a, -card_x), (self.report_summary_b, card_x)):
            card.position = Vec3(cx, 0.151, -0.064)
            card.scale = Vec3(card_w, 0.105, 1)
        al = -card_x - card_w / 2 + 0.023
        bl = card_x - card_w / 2 + 0.023
        for accent, cx in zip(self.report_summary_accents, (-card_x, card_x)):
            accent.position = Vec3(cx - card_w / 2 + 0.008, 0.151, -0.069)
            accent.scale = Vec3(0.0035, 0.062, 1)
        self.report_arrival_label.position = Vec3(al, 0.169, -0.080)
        self.report_outcome.position = Vec3(al, 0.127, -0.080)
        self.report_cost_label.position = Vec3(bl, 0.169, -0.080)
        self.report_cost_value.position = Vec3(bl, 0.127, -0.080)

        # Metrics: uniform row rhythm, aligned numbers and a small lead badge.
        self.report_section_text.position = Vec3(left, 0.069, -0.080)
        metric_x = left + 0.010
        alpha_x = -rw * 0.080
        beta_x = rw * 0.139
        winner_x = rw * 0.340
        cols = (metric_x, alpha_x, beta_x, winner_x)
        for item, cx in zip(self.report_columns, cols):
            item.position = Vec3(cx, 0.033, -0.080)

        for idx, row in enumerate(self.report_rows):
            cy = -0.021 - idx * 0.104
            bg = self.report_row_bgs[idx]
            bg.position = Vec3(0, cy, -0.066)
            bg.scale = Vec3(rw - 0.083, 0.090, 1)
            a = self.report_row_accents[idx]
            a.position = Vec3(-rw / 2 + 0.045, cy, -0.070)
            a.scale = Vec3(0.0030, 0.044, 1)
            lead = self.report_lead_bgs[idx]
            lead.position = Vec3(winner_x, cy, -0.071)
            lead.scale = Vec3(0.092, 0.034, 1)
            for item, cx in zip(row, cols):
                item.position = Vec3(cx, cy, -0.081)

        self.report_bottom_rule.position = Vec3(0, -0.284, -0.066)
        self.report_bottom_rule.scale = Vec3(rw - 0.083, 0.0016, 1)
        self.report_note.position = Vec3(0, -0.323, -0.081)
        self.report_hint.position = Vec3(0, -0.361, -0.081)

        if not self._tools_user_toggled:
            self.tools_open = aspect >= 1.42
        self._apply_tools_visibility()
        self._sync_overlay_visibility()

    def _sync_overlay_visibility(self):
        for el in (self.top_bg, self.top_rule, self.top_title, self.top_status, self.pending_bg, self.pending_text):
            el.enabled = True if el not in (self.pending_bg, self.pending_text) else el.enabled
        # Results live in the telemetry footer / arcade HUD and the J report.
        # Never cover the warehouse view with a second floating banner.
        for el in (self.result_bg, self.result_title, self.result_detail):
            el.enabled = False

        # Contextual instructions are useful during mission selection only.
        # In Free Cam, instructions move to the action rail to keep the view clean.
        prompt_visible = (
            not self.report_open
            and not self._free_cam_mode(self.scene.current_cam_mode)
            and not self.mission_mgr.race_finished
        )
        self.message_bg.enabled = prompt_visible and not self.speed_toast_bg.enabled
        self.message_text.enabled = prompt_visible and not self.speed_toast_bg.enabled
        if not self._report_has_plan():
            self.report_open = False
        if self.report_open != getattr(self, "_report_widgets_visible", None):
            for el in self._report_elements:
                el.enabled = self.report_open
            self._report_widgets_visible = self.report_open
        self.speed_chip_bg.enabled = not self.report_open
        self.speed_chip_text.enabled = not self.report_open
        self.speed_chip_caption.enabled = not self.report_open
        if self.report_open:
            self.speed_toast_bg.enabled = False
            self.speed_toast_text.enabled = False
        self.btn_legend.enabled = not self.report_open
        self.legend_panel.enabled = self.legend_open and not self.report_open
        self.btn_tools.enabled = not self.report_open
        self.btn_report.color = color.rgb32(*((34, 76, 85) if self.report_open else self.SURFACE))
        self.btn_report.text_color = color.rgb32(*(self.CYAN if self.report_open else self.TEXT))

    def _apply_tools_visibility(self):
        show_tools = self.tools_open
        for item in self._tool_panel_items:
            item.enabled = show_tools and item is not self.tools_hint and item is not self.tools_footer
        # A single short help line sits *inside* the sidebar, under the last button.
        self.tools_footer.enabled = show_tools and self._free_cam_mode(self.scene.current_cam_mode)
        self.tools_footer.position = Vec3(self.side_title.position.x, -0.278, 0.010)
        self.tools_footer.scale = 0.49
        self._set(self.tools_footer, "WASD move  ·  RMB look  ·  Q/E height")
        self._set(self.btn_tools, "Hide [P]" if show_tools else "Operasi [P]")
        self.btn_tools.y = 0.330 if show_tools else 0.399
        self.btn_tools.scale_x = 0.096 if show_tools else 0.118
        right = max(1.0, float(window.aspect_ratio)) / 2 - 0.016
        self.btn_tools.x = right - self.btn_tools.scale_x / 2
        self.btn_legend.position = Vec3(right - (0.060 if show_tools else 0.188), 0.399, 0.008)
        self.btn_legend.scale = Vec3(0.120, 0.041, 1)
        self._set(self.btn_legend, "Tutup [L]" if self.legend_open else "Legenda [L]")
        self._sync_overlay_visibility()
        self.btn_tools.color = color.rgb32(*((34, 76, 85) if self.tools_open else self.SURFACE))
        self.btn_tools.text_color = color.rgb32(*(self.CYAN if self.tools_open else self.TEXT))

    def toggle_legend(self):
        if not self.report_open:
            self.legend_open = not self.legend_open
            self._apply_tools_visibility()

    def toggle_tools(self):
        self.tools_open = not self.tools_open
        self._tools_user_toggled = True
        self._apply_tools_visibility()

    def _report_has_plan(self):
        plan = getattr(self.mission_mgr, "dual_plan", None)
        return bool(plan is not None and (self.mission_mgr.is_race_active or self.mission_mgr.race_finished))

    def toggle_report(self):
        if not self.report_open and not self._report_has_plan():
            self.interaction_sys.prompt_text = "Start a race first to open analysis."
            return
        self.report_open = not self.report_open
        self._apply_hud_visibility()
        if self.report_open:
            self._refresh_report()

    @staticmethod
    def _lead(alpha: float, beta: float) -> str:
        if abs(alpha - beta) <= 1e-9:
            return "Tie"
        return "Alpha" if alpha < beta else "Beta"

    def _refresh_report(self):
        plan = getattr(self.mission_mgr, "dual_plan", None)
        if plan is None:
            return
        alpha = getattr(plan, "alpha_plan", None)
        beta = getattr(plan, "beta_plan", None)
        if alpha is None or beta is None:
            return

        metric_specs = (
            ("total_cost", ".2f", ""),
            ("total_nodes_explored", ".0f", ""),
            ("total_compute_time_ms", ".2f", " ms"),
        )
        cost_leader = "Pending"
        for index, ((label, a_text, b_text, better), (field, fmt, suffix)) in enumerate(zip(self.report_rows, metric_specs)):
            try:
                a = float(getattr(alpha, field))
                b = float(getattr(beta, field))
                if not all(math.isfinite(v) for v in (a, b)):
                    raise ValueError("non-finite metric")
            except (AttributeError, TypeError, ValueError):
                self._set(a_text, "—")
                self._set(b_text, "—")
                self._set(better, "—")
                self.report_lead_bgs[index].color = color.rgb32(38, 54, 71)
                self.report_row_accents[index].color = color.rgb32(65, 83, 103)
                continue
            self._set(a_text, format(a, fmt) + suffix)
            self._set(b_text, format(b, fmt) + suffix)
            lead = self._lead(a, b)
            self._set(better, lead)
            lead_color = self.CYAN if lead == "Alpha" else (self.AMBER if lead == "Beta" else self.MUTED)
            bg = (24, 67, 83) if lead == "Alpha" else ((78, 58, 37) if lead == "Beta" else (44, 57, 75))
            self.report_lead_bgs[index].color = color.rgb32(*bg)
            self.report_row_accents[index].color = color.rgb32(*lead_color)
            better.color = color.rgb32(*lead_color)
            if field == "total_cost":
                cost_leader = lead

        arrived = str(getattr(self.mission_mgr, "first_to_arrive", "") or "")
        if "alpha" in arrived.lower():
            arrival_label = "Alpha / A*"
            self.report_outcome.color = color.rgb32(*self.CYAN)
        elif "beta" in arrived.lower():
            arrival_label = "Beta / GBFS"
            self.report_outcome.color = color.rgb32(*self.AMBER)
        elif self.mission_mgr.race_finished:
            arrival_label = self._clip(arrived or "Not recorded", 21)
            self.report_outcome.color = color.rgb32(*self.TEXT)
        else:
            arrival_label = "Not finished"
            self.report_outcome.color = color.rgb32(*self.MUTED)
        self._set(self.report_outcome, arrival_label)
        self._set(self.report_cost_value, "Tie" if cost_leader == "Tie" else (cost_leader if cost_leader in ("Alpha", "Beta") else "Pending"))
        self.report_cost_value.color = color.rgb32(*(
            self.CYAN if cost_leader == "Alpha" else self.AMBER if cost_leader == "Beta" else self.TEXT
        ))

    def toggle_hud_mode(self):
        self.is_serious_mode = not self.is_serious_mode
        self._apply_hud_visibility()
        self._refresh_controls()

    def toggle_hud_visibility(self):
        self.hud_visible = not self.hud_visible
        self._apply_hud_visibility()

    def _apply_hud_visibility(self):
        self.hud_serious.set_visible(self.hud_visible and self.is_serious_mode and not self.report_open)
        self.hud_gamification.set_visible(self.hud_visible and not self.is_serious_mode and not self.report_open)
        self._sync_overlay_visibility()

    def select_tool(self, tool: PlacementTool):
        self.interaction_sys.set_tool(tool)
        self._refresh_tool_buttons()

    def _refresh_tool_buttons(self):
        active = self.interaction_sys.current_tool
        configs = [
            (PlacementTool.CARGO_BOX, self.btn_cargo, self.CYAN),
            (PlacementTool.OIL_SPILL, self.btn_oil, self.AMBER),
            (PlacementTool.BOOST_PAD, self.btn_boost, self.GREEN),
        ]
        for tool, button, tint in configs:
            button.color = color.rgb32(*((35, 87, 86) if tool == active else self.SURFACE))
            button.text_color = color.rgb32(*(tint if tool == active else self.TEXT))
        descriptions = {
            PlacementTool.CARGO_BOX: "Cargo block · fully blocks the corridor",
            PlacementTool.OIL_SPILL: "Oil spill · slows down traversal",
            PlacementTool.BOOST_PAD: "Speed boost · faster traversal",
        }
        self._set(self.tools_hint, self._clip(descriptions.get(active, "Choose a terrain tool"), 32))
        tool_names = {PlacementTool.CARGO_BOX: "Cargo", PlacementTool.OIL_SPILL: "Oil", PlacementTool.BOOST_PAD: "Boost"}
        self._set(self.side_sub, f"Selected tool · {tool_names.get(active, '-')}")

    def cycle_heuristic(self):
        new_h = self.mission_mgr.cycle_heuristic()
        self._set(self.btn_heuristic, f"{new_h.title()} [H]")
        self.interaction_sys.prompt_text = f"Heuristic changed to {new_h}."

    def trigger_random_mission(self):
        self.interaction_sys.reset_interaction()
        if self.mission_mgr.trigger_random_mission():
            self.interaction_sys.state = InteractionState.RACING
            self.interaction_sys.prompt_text = "Random A* vs GBFS race started."
        else:
            self.interaction_sys.prompt_text = "Could not start a random mission."

    def trigger_zone_transfer(self):
        if self.mission_mgr.is_race_active and not self.mission_mgr.race_finished:
            self.interaction_sys.prompt_text = "Finish or reset the current race before changing zones."
            return
        self.interaction_sys.reset_interaction()
        if self.mission_mgr.dispatch_zone_transfer():
            self.interaction_sys.state = InteractionState.RACING
            self.interaction_sys.prompt_text = "Zone transfer started."
        else:
            self.interaction_sys.prompt_text = "Could not start zone transfer."

    def toggle_pause(self):
        self.mission_mgr.toggle_pause()
        self._refresh_controls()

    def reset_all(self):
        self.report_open = False
        self.mission_mgr.reset_race()
        self.interaction_sys.reset_interaction()
        if self.mission_mgr.is_paused:
            self.mission_mgr.toggle_pause()
        self._refresh_controls()
        self._apply_hud_visibility()

    @staticmethod
    def _free_cam_mode(mode: str) -> bool:
        return mode in ("free_cam", "bebas")

    def toggle_free_camera(self):
        if self._free_cam_mode(self.scene.current_cam_mode):
            self.set_camera("isometrik")
        elif getattr(self.scene, "free_cam", None) is None:
            self.interaction_sys.prompt_text = "Free cam not ready yet. Wait until the arena finishes loading."
        else:
            self.set_camera("free_cam")

    def _refresh_freecam_button(self):
        active = self._free_cam_mode(self.scene.current_cam_mode)
        self._set(self.btn_freecam, "Exit free cam [B]" if active else "Free camera [B]")
        self.btn_freecam.color = color.rgb32(*((34, 76, 85) if active else self.SURFACE))
        self.btn_freecam.text_color = color.rgb32(*(self.CYAN if active else self.TEXT))
        footer = "WASD move · RMB drag · Q/E height" if active else "Right-click robot: return to dock"
        self._set(self.tools_footer, self._clip(footer, 34))

    def _update_free_camera_motion(self):
        if not self._free_cam_mode(self.scene.current_cam_mode):
            return
        free_cam = getattr(self.scene, "free_cam", None)
        if free_cam is None or not free_cam.enabled:
            return
        direction = Vec3(0, 0, 0)
        if held_keys["w"]:
            direction += free_cam.forward
        if held_keys["s"]:
            direction -= free_cam.forward
        if held_keys["d"]:
            direction += free_cam.right
        if held_keys["a"]:
            direction -= free_cam.right
        if direction.length() > 0.0001:
            dt = max(0.0, min(float(ursina_time.dt), 0.1))
            speed = 40.0 if held_keys["shift"] else 18.0
            free_cam.position += direction.normalized() * speed * dt

    def cycle_camera(self):
        new_mode = self.scene.cycle_camera_mode()
        self._update_camera_ui(new_mode)

    def set_camera(self, mode: str):
        self.scene.apply_camera_mode(mode, mission_mgr=self.mission_mgr)
        self._update_camera_ui(mode)

    def _update_camera_ui(self, mode: str):
        labels = {
            "isometrik": "Camera [C]",
            "topdown": "Top-down [C]",
            "pov_alpha": "POV Alpha [C]",
            "pov_beta": "POV Beta [C]",
            "free_cam": "Next view [C]",
            "bebas": "Next view [C]",
        }
        self._set(self.btn_cam, labels.get(mode, "Camera [C]"))
        if mode == "pov_alpha":
            self.btn_cam.color = color.rgb32(*self.CYAN)
            self.interaction_sys.prompt_text = "Dashcam active: AGV Alpha"
        elif mode == "pov_beta":
            self.btn_cam.color = color.rgb32(*self.AMBER)
            self.interaction_sys.prompt_text = "Dashcam active: AGV Beta"
        elif mode == "topdown":
            self.btn_cam.color = color.rgb32(*self.SURFACE)
            self.interaction_sys.prompt_text = "Top-down camera mode."
        elif mode == "isometrik":
            self.btn_cam.color = color.rgb32(*self.SURFACE)
            self.interaction_sys.prompt_text = "Isometric camera mode."
        elif mode in ("free_cam", "bebas"):
            self.btn_cam.color = color.rgb32(*self.CYAN)
            self.interaction_sys.prompt_text = "Free cam active."
        else:
            self.btn_cam.color = color.rgb32(*self.SURFACE)
            self.interaction_sys.prompt_text = f"Camera mode: {mode}."
        self._refresh_freecam_button()
        self._apply_tools_visibility()

    def _refresh_speed_indicator(self):
        speed = float(getattr(self.mission_mgr, "current_speed", 0.0))
        self._set(self.speed_chip_text, f"{speed:.1f}")
        # Make the chip informative without attaching a multiplier to a value
        # that represents actual simulation speed, not a time-scale factor.

    def adjust_speed(self, delta):
        speed = float(self.mission_mgr.adjust_speed(delta))
        self._refresh_speed_indicator()
        message = f"Robot speed: {speed:.1f}"
        self.interaction_sys.prompt_text = message
        self._set(self.speed_toast_text, message)
        self._speed_toast_until = float(ursina_time.time()) + 1.6
        self.speed_toast_bg.enabled = True
        self.speed_toast_text.enabled = True

    def clear_terrain(self):
        self.scene.clear_all_dynamic_obstacles()
        self.scene.clear_all_terrain_modifiers()
        self.mission_mgr.graph.clear_dynamic_obstacles()
        self.mission_mgr.graph.clear_terrain_modifiers()
        if hasattr(self.scene, "clear_exploration_heatmap"):
            self.scene.clear_exploration_heatmap()
        self.interaction_sys.prompt_text = "Dynamic obstacles, oil, and boost pads cleared."

    def _refresh_controls(self):
        self._set(self.btn_hud_mode, "Serious [M]" if self.is_serious_mode else "Arcade [M]")
        self._set(self.btn_pause, "Resume [Space]" if self.mission_mgr.is_paused else "Pause [Space]")
        self.btn_pause.color = color.rgb32(*((74, 88, 76) if self.mission_mgr.is_paused else (36, 108, 104)))
        self.btn_pause.text_color = color.rgb32(*(self.GREEN if self.mission_mgr.is_paused else self.TEXT))
        mode = self.scene.current_cam_mode
        labels = {
            "isometrik": "Camera [C]",
            "topdown": "Top-down [C]",
            "pov_alpha": "POV Alpha [C]",
            "pov_beta": "POV Beta [C]",
            "free_cam": "Next view [C]",
            "bebas": "Next view [C]",
        }
        self._set(self.btn_cam, labels.get(mode, "Camera [C]"))
        self._refresh_freecam_button()
        self._refresh_speed_indicator()

    @staticmethod
    def _is_pointer_over_ui():
        entity = mouse.hovered_entity
        while entity is not None:
            if entity is camera.ui:
                return True
            entity = getattr(entity, "parent", None)
        return False

    @staticmethod
    def _first_arrival_label(value):
        value = str(value or "-")
        lowered = value.lower()
        if "alpha" in lowered:
            return "Alpha"
        if "beta" in lowered:
            return "Beta"
        return UIController._clip(value, 15)

    @staticmethod
    def _lowest_cost_label(plan):
        if plan is None:
            return "-"
        try:
            a = float(plan.alpha_plan.total_cost)
            b = float(plan.beta_plan.total_cost)
        except (AttributeError, TypeError, ValueError):
            return "-"
        if abs(a - b) <= 1e-7:
            return "Tie"
        return "Alpha" if a < b else "Beta"

    def _refresh_result(self):
        if not self.mission_mgr.race_finished:
            return
        first = self._first_arrival_label(getattr(self.mission_mgr, "first_to_arrive", None))
        route = self._lowest_cost_label(getattr(self.mission_mgr, "dual_plan", None))
        self._set(self.result_detail, f"First arrival: {first}    ·    Lowest route cost: {route}")

    def update(self):
        self._update_layout()
        self.interaction_sys.update()
        self.industrial_facelift.refresh()
        self._refresh_speed_indicator()
        toast_active = (not self.report_open and float(ursina_time.time()) < self._speed_toast_until)
        self.speed_toast_bg.enabled = toast_active
        self.speed_toast_text.enabled = toast_active
        self._sync_overlay_visibility()
        if self.report_open:
            self._refresh_report()
        if not self.report_open and not (self.hud_serious.container.enabled or self.hud_gamification.container.enabled):
            self._apply_hud_visibility()

        queue = len(self.mission_mgr.task_queue)
        self._set(self.pending_text, f"Queue {queue}")
        self.pending_text.color = color.rgb32(*(self.AMBER if queue else self.CYAN))

        elapsed = self.mission_mgr.race_elapsed_time
        clock = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        if self.mission_mgr.is_paused:
            status = "Paused"
        elif self.mission_mgr.race_finished:
            status = "Finished"
        elif self.mission_mgr.is_race_active:
            status = "Racing"
        else:
            status = "Ready"
        if self._free_cam_mode(self.scene.current_cam_mode):
            status = f"Free cam · {status}"
        self._set(self.top_status, self._clip(f"{self.mission_mgr.current_zone} · {status} · {clock}", 40))

        if self.result_bg.enabled:
            self._refresh_result()

        if self._free_cam_mode(self.scene.current_cam_mode):
            prompt = "Free cam  ·  WASD move  ·  Right-click drag to look  ·  B exit"
        else:
            prompt = self.interaction_sys.prompt_text
        self._set(self.message_text, self._clip(prompt, 68 if self._last_aspect_ratio >= 1.50 else 44))

        if self.hud_visible:
            if self.is_serious_mode:
                self.hud_serious.update(self.mission_mgr, self.interaction_sys)
            else:
                self.hud_gamification.update(self.mission_mgr, self.interaction_sys)

        self._update_free_camera_motion()
        if self.scene.current_cam_mode == "follow_alpha":
            self.scene.update_follow_camera(self.mission_mgr.robot_alpha.position)
        elif self.scene.current_cam_mode == "follow_beta":
            self.scene.update_follow_camera(self.mission_mgr.robot_beta.position)
        elif self.scene.current_cam_mode == "pov_alpha":
            self.scene.update_pov_camera(self.mission_mgr.robot_alpha)
        elif self.scene.current_cam_mode == "pov_beta":
            self.scene.update_pov_camera(self.mission_mgr.robot_beta)

    def handle_input(self, key: str):
        # Modal behaves modally: the simulation underneath cannot be edited.
        if self.report_open and key not in ("j", "escape", "left mouse down"):
            return
        if key == "left mouse down":
            if self.report_open and mouse.hovered_entity is self.report_dim:
                self.toggle_report()
            elif not self.report_open and not self._is_pointer_over_ui():
                self.interaction_sys.handle_click()
        elif key == "right mouse down":
            if not self._is_pointer_over_ui() and self.scene.current_cam_mode not in ("free_cam", "bebas"):
                self.interaction_sys.handle_right_click()
        elif key == "m":
            self.toggle_hud_mode()
        elif key == "u":
            self.toggle_hud_visibility()
        elif key == "l":
            self.toggle_legend()
        elif key == "p":
            self.toggle_tools()
        elif key == "j":
            self.toggle_report()
        elif key == "b":
            self.toggle_free_camera()
        elif key == "h":
            self.cycle_heuristic()
        elif key == "g":
            self.trigger_random_mission()
        elif key == "t":
            self.trigger_zone_transfer()
        elif key == "space":
            self.toggle_pause()
        elif key == "r":
            self.reset_all()
        elif key in ("c", "f", "k", "v"):
            self.cycle_camera()
        elif key in ("+", "="):
            self.adjust_speed(1.5)
        elif key == "-":
            self.adjust_speed(-1.5)
        elif key in ("x", "delete", "backspace"):
            self.clear_terrain()
        elif key == "1":
            self.select_tool(PlacementTool.CARGO_BOX)
        elif key == "2":
            self.select_tool(PlacementTool.OIL_SPILL)
        elif key == "3":
            self.select_tool(PlacementTool.BOOST_PAD)
        elif key == "f11":
            window.fullscreen = not window.fullscreen
            self._last_aspect_ratio = -1.0
        elif key == "escape":
            if self.report_open:
                self.toggle_report()
            else:
                application.quit()
