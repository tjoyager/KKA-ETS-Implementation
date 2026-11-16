"""
hud_serious.py
==============
Panel HUD Mode Serius (Warehouse Management System / Industrial Telemetry).
Menampilkan metrik analitik profesional: tabel komparasi A* vs GBFS, total biaya rute,
jumlah simpul dieksplorasi, waktu eksekusi milidetik, serta analisis bottleneck jaringan gudang.
"""

import time
from ursina import Entity, Vec3, color, camera, Text, window
from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem

class SeriousHUD:
    def __init__(self):
        self.container = Entity(parent=camera.ui, enabled=True)
        self.panel_w, self.panel_h = 0.60, 0.48 
        
        self.BG_COLOR = color.rgba32(15, 23, 42, 240)
        self.LINE_COLOR = color.rgba32(50, 65, 85, 200)
        self.TEXT_COLOR = color.rgb32(226, 232, 240)
        self.HEADER_COLOR = color.rgb32(148, 163, 184)

        self.bg_panel = Entity(parent=self.container, model='quad', scale=Vec3(self.panel_w, self.panel_h, 1), color=self.BG_COLOR)
        self.accent_left = Entity(parent=self.container, model='quad', scale=Vec3(0.004, self.panel_h, 1), color=color.rgb32(56, 189, 248))
        
        self.title_text = Text(parent=self.container, text="WMS FLEET TELEMETRY", scale=0.85, color=color.white, font='assets/fonts/Roboto-Bold.ttf')
        self.subtitle_text = Text(parent=self.container, text="", scale=0.65, color=self.HEADER_COLOR, font='assets/fonts/Roboto-Bold.ttf')
        self.info_text = Text(parent=self.container, text="", scale=0.65, color=self.TEXT_COLOR, line_height=1.2, font='assets/fonts/Roboto-Bold.ttf')

        # Header Kolom (Rata Tengah)
        self.col_metric = Text(parent=self.container, text="METRIK", scale=0.65, color=self.HEADER_COLOR, font='assets/fonts/Roboto-Bold.ttf', origin=(-0.5, 0)) # Rata Kiri
        self.col_alpha = Text(parent=self.container, text="A* (CYAN)", scale=0.65, color=color.rgb32(56, 189, 248), font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0)) # Rata Tengah
        self.col_beta = Text(parent=self.container, text="GBFS (AMBER)", scale=0.65, color=color.rgb32(251, 146, 60), font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0)) # Rata Tengah

        self.rows = []
        labels = ["BATERAI", "BIAYA RUTE", "SIMPUL", "WAKTU", "PROGRES"]
        for lbl in labels:
            row = {
                "label": Text(parent=self.container, text=lbl, scale=0.65, color=self.TEXT_COLOR, font='assets/fonts/Roboto-Bold.ttf', origin=(-0.5, 0)),
                "val_a": Text(parent=self.container, text="-", scale=0.65, color=color.white, font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0)),
                "val_b": Text(parent=self.container, text="-", scale=0.65, color=color.white, font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0)),
                "line": Entity(parent=self.container, model='quad', color=self.LINE_COLOR)
            }
            self.rows.append(row)

        self.line_vert_1 = Entity(parent=self.container, model='quad', color=self.LINE_COLOR)
        self.line_vert_2 = Entity(parent=self.container, model='quad', color=self.LINE_COLOR)

        self.footer_text = Text(parent=self.container, text="", scale=0.65, color=self.TEXT_COLOR, line_height=1.2, font='assets/fonts/Roboto-Bold.ttf')

        self._last_update_time, self._last_aspect_ratio = 0.0, 0.0
        self.update_layout()

    def update_layout(self):
        aspect = window.aspect_ratio
        if abs(aspect - self._last_aspect_ratio) < 0.01: return
        self._last_aspect_ratio = aspect

        center_x = -aspect / 2.0 + 0.02 + (self.panel_w / 2.0)
        center_y = 0.22

        self.bg_panel.position = Vec3(center_x, center_y, 0)
        self.accent_left.position = Vec3(center_x - self.panel_w / 2.0, center_y, -0.005)

        start_x = center_x - self.panel_w / 2.0 + 0.03
        start_y = center_y + self.panel_h / 2.0 - 0.02

        self.title_text.position = Vec3(start_x, start_y, -0.01)
        self.subtitle_text.position = Vec3(start_x, start_y - 0.04, -0.01)
        self.info_text.position = Vec3(start_x, start_y - 0.09, -0.01)

        # Penataan Tabel
        table_start_y = start_y - 0.18
        row_h = 0.038
        
        # Titik Tengah Kolom (X)
        col1_x = start_x
        col2_x = start_x + 0.22  # Titik tengah untuk A*
        col3_x = start_x + 0.42  # Titik tengah untuk GBFS

        self.col_metric.position = Vec3(col1_x, table_start_y, -0.01)
        self.col_alpha.position = Vec3(col2_x, table_start_y, -0.01)
        self.col_beta.position = Vec3(col3_x, table_start_y, -0.01)

        total_table_h = row_h * (len(self.rows) + 1)
        v_line_y = table_start_y - (total_table_h / 2.0) + 0.01
        
        # Garis Vertikal
        self.line_vert_1.position = Vec3(col2_x - 0.08, v_line_y, -0.005)
        self.line_vert_1.scale = Vec3(0.002, total_table_h, 1)
        self.line_vert_2.position = Vec3(col3_x - 0.08, v_line_y, -0.005)
        self.line_vert_2.scale = Vec3(0.002, total_table_h, 1)

        # Baris Data
        for i, row in enumerate(self.rows):
            y_pos = table_start_y - (row_h * (i + 1))
            row["label"].position = Vec3(col1_x, y_pos, -0.01)
            row["val_a"].position = Vec3(col2_x, y_pos, -0.01) 
            row["val_b"].position = Vec3(col3_x, y_pos, -0.01)
            
            row["line"].position = Vec3(center_x, y_pos - 0.012, -0.005)
            row["line"].scale = Vec3(self.panel_w - 0.04, 0.002, 1)

        footer_y = table_start_y - (row_h * (len(self.rows) + 1)) - 0.01
        self.footer_text.position = Vec3(start_x, footer_y, -0.01)

    def set_visible(self, visible: bool):
        self.container.enabled = visible

    def update(self, mission_mgr: MissionManager, interaction_sys: InteractionSystem):
        if not self.container.enabled: return
        self.update_layout()

        now = time.perf_counter()
        if (now - self._last_update_time < 0.05) and not mission_mgr.race_finished: return
        self._last_update_time = now

        plan = mission_mgr.dual_plan
        robot_a, robot_b = mission_mgr.robot_alpha, mission_mgr.robot_beta

        if plan:
            row_data = [
                (f"{robot_a.battery:.0f}%", f"{robot_b.battery:.0f}%"),
                (f"{plan.alpha_plan.total_cost:.1f}", f"{plan.beta_plan.total_cost:.1f}"),
                (f"{plan.alpha_plan.total_nodes_explored}", f"{plan.beta_plan.total_nodes_explored}"),
                (f"{plan.alpha_plan.total_compute_time_ms:.2f} ms", f"{plan.beta_plan.total_compute_time_ms:.2f} ms"),
                (f"{robot_a.waypoint_idx}/{robot_a.total_mission_steps}", f"{robot_b.waypoint_idx}/{robot_b.total_mission_steps}"),
            ]
            shared_count, cong_pct = len(plan.shared_bottleneck_nodes), plan.congestion_index * 100.0
            risk_str = "LANCAR" if cong_pct < 25.0 else ("PADAT" if cong_pct < 60.0 else "BOTTLENECK")
        else:
            row_data = [("-", "-")] * 5
            shared_count, cong_pct, risk_str = 0, 0.0, "NORMAL"

        h_name = mission_mgr.current_heuristic_name.upper()
        self.subtitle_text.text = f"ZONA: {mission_mgr.current_zone}  |  HEURISTIK: {h_name}"

        p_id = mission_mgr.selected_pickup_shelf.shelf_data.shelf_id if mission_mgr.selected_pickup_shelf else "---"
        d_id = mission_mgr.selected_dropoff_shelf.shelf_data.shelf_id if mission_mgr.selected_dropoff_shelf else "---"
        self.info_text.text = f"PICKUP : {p_id}\nDROPOFF: {d_id}\nQUEUE  : {len(mission_mgr.task_queue)} Pesanan"

        for i, (val_a, val_b) in enumerate(row_data):
            self.rows[i]["val_a"].text = val_a
            self.rows[i]["val_b"].text = val_b

        self.footer_text.text = f"BOTTLENECK: {shared_count} sel ({cong_pct:.1f}%) - {risk_str}\nSIM SPEED : {mission_mgr.current_speed:.1f}x"