"""V12 serious HUD.

Cleaner typography, shorter labels, larger spacing, and safer text clipping.
"""
import time
from src.communication.visual_theme import rounded_surface
from ursina.shaders import unlit_shader

from ursina import Entity, Text, Vec3, camera, color, window


class SeriousHUD:
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
        self.container = Entity(parent=camera.ui, scale=1, enabled=True)
        self.panel_w = 0.320
        self.panel_h = 0.365
        self._last_aspect = -1.0
        self._last_update = 0.0

        self.bg = self._box(self.BG, 0.01)
        self.edge = self._box(self.EDGE, 0.012)
        self.top_rule = self._box(self.CYAN, 0.004)
        self.eyebrow = self._text("RACE TELEMETRY", 0.42, self.MUTED, True)
        self.title = self._text("A* vs GBFS", 0.62, self.TEXT, True)
        self.subtitle = self._text("Waiting for mission", 0.44, self.MUTED)
        self.sep = self._box(self.LINE, 0.0018)

        self.header_metric = self._text("Metric", 0.41, self.MUTED, True)
        self.header_a = self._text("Alpha", 0.45, self.CYAN, True, origin=(0, 0))
        self.header_b = self._text("Beta", 0.45, self.AMBER, True, origin=(0, 0))

        self.rows = []
        for label in ("Battery", "Route cost", "Nodes", "Search time", "Path progress"):
            self.rows.append({
                "label": self._text(label, 0.43, self.MUTED),
                "a": self._text("--", 0.47, self.TEXT, True, origin=(0, 0)),
                "b": self._text("--", 0.47, self.TEXT, True, origin=(0, 0)),
                "line": self._box(self.LINE, 0.0012),
            })

        self.footer_sep = self._box(self.LINE, 0.0018)
        self.route_k = self._text("Mission", 0.41, self.MUTED, True)
        self.route_v = self._text("Choose pickup and drop-off", 0.43, self.TEXT)
        self.bneck_k = self._text("Traffic", 0.41, self.MUTED, True)
        self.bneck_v = self._text("No route yet", 0.43, self.GREEN, True)
        self.meta_v = self._text("", 0.42, self.MUTED)
        self.result_v = self._text("", 0.42, self.MUTED)

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
        col_a = left + inner * 0.62
        col_b = left + inner * 0.88

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
        self.sep.position = Vec3(w / 2, -0.080, 0.018)
        self.sep.scale = Vec3(inner, 0.0012, 1)

        head_y = -0.100
        self.header_metric.position = Vec3(left, head_y, 0.012)
        self.header_a.position = Vec3(col_a, head_y, 0.012)
        self.header_b.position = Vec3(col_b, head_y, 0.012)

        row_start_y = -0.123
        row_step = 0.026
        for i, row in enumerate(self.rows):
            yy = row_start_y - i * row_step
            row["label"].position = Vec3(left, yy, 0.012)
            row["a"].position = Vec3(col_a, yy, 0.012)
            row["b"].position = Vec3(col_b, yy, 0.012)
            row["line"].position = Vec3(w / 2, yy - 0.012, 0.018)
            row["line"].scale = Vec3(inner, 0.001, 1)

        fy = -0.252
        self.footer_sep.position = Vec3(w / 2, fy, 0.018)
        self.footer_sep.scale = Vec3(inner, 0.0012, 1)
        self.route_k.position = Vec3(left, fy - 0.017, 0.012)
        self.route_v.position = Vec3(left + 0.054, fy - 0.017, 0.012)
        self.bneck_k.position = Vec3(left, fy - 0.039, 0.012)
        self.bneck_v.position = Vec3(left + 0.054, fy - 0.039, 0.012)
        self.meta_v.position = Vec3(left, fy - 0.061, 0.012)
        self.result_v.position = Vec3(left, fy - 0.082, 0.012)

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

        plan = getattr(mission_mgr, "dual_plan", None)
        a, b = mission_mgr.robot_alpha, mission_mgr.robot_beta
        if plan is not None:
            pa, pb = plan.alpha_plan, plan.beta_plan
            values = (
                (f"{a.battery:.0f}%", f"{b.battery:.0f}%"),
                (f"{pa.total_cost:.1f}", f"{pb.total_cost:.1f}"),
                (str(pa.total_nodes_explored), str(pb.total_nodes_explored)),
                (f"{pa.total_compute_time_ms:.1f} ms", f"{pb.total_compute_time_ms:.1f} ms"),
                (("Done" if mission_mgr.race_finished else
                  f"{min(a.total_steps_executed, a.total_mission_steps)}/{a.total_mission_steps}"),
                 ("Done" if mission_mgr.race_finished else
                  f"{min(b.total_steps_executed, b.total_mission_steps)}/{b.total_mission_steps}")),
            )
            n = len(plan.shared_bottleneck_nodes)
            congestion = plan.congestion_index * 100.0
            level = "Low" if congestion < 25 else ("Medium" if congestion < 60 else "High")
            self._set(self.bneck_v, f"{level} · {n} cells")
            self.bneck_v.color = self.GREEN if congestion < 25 else self.AMBER
        else:
            values = (("--", "--"),) * 5
            self._set(self.bneck_v, "No route yet")
            self.bneck_v.color = self.MUTED

        for row, (va, vb) in zip(self.rows, values):
            self._set(row["a"], va)
            self._set(row["b"], vb)

        self._set(self.subtitle, f"{mission_mgr.current_zone} · {mission_mgr.current_heuristic_name}")
        pickup = mission_mgr.selected_pickup_shelf
        dropoff = mission_mgr.selected_dropoff_shelf
        p = pickup.shelf_data.shelf_id if pickup else "--"
        d = dropoff.shelf_data.shelf_id if dropoff else "--"
        if mission_mgr.race_finished and p == "--" and d == "--":
            self._set(self.route_v, "Delivery complete")
        else:
            self._set(self.route_v, self._clip(f"{p} -> {d}", 26))

        if mission_mgr.race_finished:
            arrived = str(getattr(mission_mgr, "first_to_arrive", "") or "").lower()
            first = "Alpha" if "alpha" in arrived else ("Beta" if "beta" in arrived else "N/A")
            winner = "N/A"
            if plan is not None:
                cost_a, cost_b = plan.alpha_plan.total_cost, plan.beta_plan.total_cost
                if abs(cost_a - cost_b) < 1e-7:
                    winner = "Tie"
                else:
                    winner = "Alpha" if cost_a < cost_b else "Beta"
            self._set(self.meta_v, f"First arrival    {first}")
            self._set(self.result_v, f"Best route cost    {winner}")
            self.meta_v.color = self.TEXT
            self.result_v.color = self.CYAN if winner == "Alpha" else (self.AMBER if winner == "Beta" else self.GREEN)
        else:
            self._set(self.meta_v, f"Robot speed {mission_mgr.current_speed:.1f}")
            self._set(self.result_v, "")
            self.meta_v.color = self.MUTED
