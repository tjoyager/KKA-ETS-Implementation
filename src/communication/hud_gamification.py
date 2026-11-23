"""V8 arcade HUD.

Cleaner and more elegant than V6, with less clutter and safer text bounds.
"""
import time
from src.communication.visual_theme import rounded_surface
from ursina.shaders import unlit_shader

from ursina import Entity, Text, Vec3, camera, color, window


class GamificationHUD:
    BG = color.rgba32(19, 28, 35, 248)
    EDGE = color.rgba32(67, 92, 103, 220)
    LINE = color.rgba32(66, 86, 97, 150)
    TEXT = color.rgb32(234, 242, 243)
    MUTED = color.rgb32(151, 171, 181)
    CYAN = color.rgb32(93, 201, 189)
    AMBER = color.rgb32(231, 177, 101)
    GREEN = color.rgb32(130, 198, 156)
    REG = "assets/fonts/Roboto-Regular.ttf"
    BOLD = "assets/fonts/Roboto-Bold.ttf"

    def __init__(self):
        self.container = Entity(parent=camera.ui, scale=1, enabled=False)
        self.panel_w = 0.320
        self.panel_h = 0.365
        self._last_aspect = -1.0
        self._last_update = 0.0

        self.bg = self._box(self.BG, 0.01)
        self.edge = self._box(self.EDGE, 0.012)
        self.top_rule = self._box(self.AMBER, 0.004)
        self.eyebrow = self._text("ARCADE MODE", 0.42, self.MUTED, True)
        self.title = self._text("Logistics rush", 0.62, self.TEXT, True)
        self.subtitle = self._text("Fast comparison run", 0.44, self.MUTED)

        self.score_k = self._text("Score", 0.41, self.MUTED, True)
        self.score_v = self._text("0", 0.68, self.TEXT, True)
        self.score_u = self._text("pts", 0.41, self.AMBER, True)
        self.sep_a = self._box(self.LINE, 0.0018)

        self.stats = []
        for label in ("Elapsed", "Combo", "Rating"):
            self.stats.append((
                self._text(label, 0.41, self.MUTED, True),
                self._text("--", 0.50, self.TEXT, True),
            ))

        self.sep_b = self._box(self.LINE, 0.0018)
        self.match_k = self._text("Head to head", 0.41, self.MUTED, True)
        self.cards = []
        for title, tint in (("Alpha / A*", self.CYAN), ("Beta / GBFS", self.AMBER)):
            card = self._box(color.rgba32(24, 34, 48, 228), 0.042)
            accent = self._box(tint, 0.042)
            t = self._text(title, 0.44, tint, True)
            line1 = self._text("Battery --   Cost --", 0.40, self.TEXT)
            line2 = self._text("Steps --", 0.37, self.MUTED)
            self.cards.append((card, accent, t, line1, line2))

        self.sep_c = self._box(self.LINE, 0.0018)
        self.outcome = self._text("Race not started", 0.44, self.TEXT)
        self.hint = self._text("G random race  ·  J analysis", 0.39, self.MUTED)

        self.update_layout()

    def _box(self, tint, height):
        return Entity(parent=self.container, model="quad", shader=unlit_shader, texture=rounded_surface(0.320, height) if height > 0.02 else None, scale=Vec3(0.02, height, 1), color=tint)

    def _text(self, text, scale, tint, bold=False, origin=(-0.5, 0)):
        return Text(parent=self.container, text=text, origin=origin, scale=scale,
                    color=tint, font=self.BOLD if bold else self.REG)

    @staticmethod
    def _set(widget, value):
        value = str(value)
        if widget.text != value:
            widget.text = value

    @staticmethod
    def _clip(value, limit):
        value = str(value)
        return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."

    def update_layout(self):
        aspect = max(1.0, float(window.aspect_ratio))
        if abs(aspect - self._last_aspect) < 0.01:
            return
        self._last_aspect = aspect
        w = 0.320 if aspect >= 1.55 else (0.295 if aspect >= 1.25 else 0.270)
        self.panel_w = w
        self.container.scale = Vec3(1, 1, 1)
        self.container.position = Vec3(-aspect / 2 + 0.018, 0.420, 0)
        h = self.panel_h

        left = 0.014
        inner = w - 0.028

        self.bg.position = Vec3(w / 2, -h / 2, 0.036)
        self.bg.scale = Vec3(w, h, 1)
        self.bg.texture = rounded_surface(w, h)

        self.edge.position = Vec3(w / 2, -h / 2, 0.037)
        self.edge.scale = Vec3(w + 0.003, h + 0.003, 1)
        self.edge.texture = rounded_surface(w + 0.003, h + 0.003)

        self.top_rule.position = Vec3(left + 0.030, -0.006, 0.018)
        self.top_rule.scale = Vec3(0.060, 0.0022, 1)
        self.eyebrow.position = Vec3(left, -0.021, 0.012)
        self.title.position = Vec3(left, -0.044, 0.012)
        self.subtitle.position = Vec3(left, -0.065, 0.012)

        self.score_k.position = Vec3(left, -0.088, 0.012)
        self.score_v.position = Vec3(left + 0.052, -0.088, 0.012)
        self.score_u.position = Vec3(left + 0.138, -0.088, 0.012)
        self.sep_a.position = Vec3(w / 2, -0.108, 0.018)
        self.sep_a.scale = Vec3(inner, 0.0012, 1)

        stat_w = inner / 3
        for i, (k, v) in enumerate(self.stats):
            sx = left + stat_w * i
            k.position = Vec3(sx, -0.124, 0.012)
            v.position = Vec3(sx, -0.142, 0.012)

        self.sep_b.position = Vec3(w / 2, -0.162, 0.018)
        self.sep_b.scale = Vec3(inner, 0.0012, 1)
        self.match_k.position = Vec3(left, -0.179, 0.012)

        card_h = 0.042
        cy_base = -0.214
        for i, (card, accent, t, line1, line2) in enumerate(self.cards):
            cy = cy_base - i * 0.048
            card.position = Vec3(w / 2, cy, 0.018)
            card.scale = Vec3(inner, card_h, 1)
            accent.position = Vec3(left + 0.002, cy, 0.019)
            accent.scale = Vec3(0.003, card_h, 1)
            t.position = Vec3(left + 0.012, cy + 0.010, 0.012)
            line1.position = Vec3(left + 0.012, cy - 0.002, 0.012)
            line2.position = Vec3(left + 0.012, cy - 0.013, 0.012)

        self.sep_c.position = Vec3(w / 2, -0.294, 0.018)
        self.sep_c.scale = Vec3(inner, 0.0012, 1)
        self.outcome.position = Vec3(left, -0.312, 0.012)
        self.hint.position = Vec3(left, -0.334, 0.012)

    def set_visible(self, visible: bool):
        self.container.enabled = visible

    def update(self, mission_mgr, interaction_sys):
        if not self.container.enabled:
            return
        self.update_layout()
        now = time.perf_counter()
        if now - self._last_update < 0.10:
            return
        self._last_update = now

        elapsed = mission_mgr.race_elapsed_time
        self._set(self.score_v, f"{mission_mgr.score:,}")
        stat_values = (
            f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}",
            f"x{mission_mgr.combo_multiplier}",
            f"{mission_mgr.star_rating}/5",
        )
        for (_, value), content in zip(self.stats, stat_values):
            self._set(value, content)

        plan = getattr(mission_mgr, "dual_plan", None)
        robots = (mission_mgr.robot_alpha, mission_mgr.robot_beta)
        costs = (plan.alpha_plan.total_cost, plan.beta_plan.total_cost) if plan else (None, None)
        for (_, _, _, line1, line2), robot, cost in zip(self.cards, robots, costs):
            c = f"{cost:.1f}" if cost is not None else "--"
            self._set(line1, self._clip(f"Battery {robot.battery:.0f}%   ·   Cost {c}", 26))
            steps_txt = (
                f"Steps {min(robot.total_steps_executed, robot.total_mission_steps)}/{robot.total_mission_steps}"
                if robot.total_mission_steps > 0
                else "Steps --"
            )
            self._set(line2, self._clip(steps_txt, 26))

        first = mission_mgr.first_to_arrive
        if first:
            outcome = f"First arrival: {first}"
        elif mission_mgr.is_race_active:
            outcome = "Race in progress"
        else:
            outcome = "Race not started"
        self._set(self.outcome, self._clip(outcome, 32))
