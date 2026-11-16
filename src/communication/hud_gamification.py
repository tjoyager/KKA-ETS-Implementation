"""
hud_gamification.py
===================
Panel HUD Mode Gamifikasi (Arcade Style / Logistics Rush).
Menampilkan elemen Time-Attack (timer stopwatch), akumulasi skor efisiensi,
combo multiplier, serta sistem rating bintang 1-5 berdasarkan rasio keoptimalan rute.
"""

import time
import textwrap
from ursina import Entity, Vec3, color, camera, Text, window
from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem

class GamificationHUD:
    def __init__(self):
        self.container = Entity(parent=camera.ui, enabled=False)
        
        self.panel_w, self.panel_h = 0.60, 0.52 
        
        self.BG_COLOR = color.rgba32(40, 20, 60, 240)
        self.LINE_COLOR = color.rgba32(80, 60, 100, 200)
        self.TEXT_COLOR = color.rgb32(255, 230, 240)
        self.HEADER_COLOR = color.rgb32(255, 215, 0)

        # Background Panel
        self.bg_panel = Entity(parent=self.container, model='quad', scale=Vec3(self.panel_w, self.panel_h, 1), color=self.BG_COLOR)
        self.accent_left = Entity(parent=self.container, model='quad', scale=Vec3(0.004, self.panel_h, 1), color=color.rgb32(255, 215, 0))

        # Header
        self.title_text = Text(parent=self.container, text="ARCADE LOGISTICS RUSH", scale=0.85, color=self.HEADER_COLOR, font='assets/fonts/Roboto-Bold.ttf')
        self.status_text = Text(parent=self.container, text="", scale=0.65, color=self.TEXT_COLOR, line_height=1.2, font='assets/fonts/Roboto-Bold.ttf')
        
        # Top Banner Info
        self.top_info_text = Text(parent=self.container, text="", scale=0.65, color=color.rgb32(255, 255, 255), line_height=1.2, font='assets/fonts/Roboto-Bold.ttf')

        # --- STRUKTUR TABEL ---
        self.col_robot = Text(parent=self.container, text="ROBOT", scale=0.6, color=self.HEADER_COLOR, font='assets/fonts/Roboto-Bold.ttf', origin=(-0.5, 0))
        self.col_bat = Text(parent=self.container, text="BAT", scale=0.6, color=self.HEADER_COLOR, font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0))
        self.col_step = Text(parent=self.container, text="STEP", scale=0.6, color=self.HEADER_COLOR, font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0))
        self.col_cost = Text(parent=self.container, text="COST", scale=0.6, color=self.HEADER_COLOR, font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0))

        self.rows = []
        for i in range(2):
            row = {
                "robot": Text(parent=self.container, text="", scale=0.65, color=color.white, font='assets/fonts/Roboto-Bold.ttf', origin=(-0.5, 0)),
                "bat": Text(parent=self.container, text="-", scale=0.65, color=color.white, font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0)),
                "step": Text(parent=self.container, text="-", scale=0.65, color=color.white, font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0)),
                "cost": Text(parent=self.container, text="-", scale=0.65, color=color.white, font='assets/fonts/Roboto-Bold.ttf', origin=(0, 0)),
            }
            self.rows.append(row)

        # Garis Tabel
        self.line_vert_1 = Entity(parent=self.container, model='quad', color=self.LINE_COLOR)
        self.line_vert_2 = Entity(parent=self.container, model='quad', color=self.LINE_COLOR)
        self.line_vert_3 = Entity(parent=self.container, model='quad', color=self.LINE_COLOR)
        self.line_h1 = Entity(parent=self.container, model='quad', color=self.LINE_COLOR)
        self.line_h2 = Entity(parent=self.container, model='quad', color=self.LINE_COLOR)

        # Footer
        self.footer_text = Text(parent=self.container, text="", scale=0.65, color=self.TEXT_COLOR, line_height=1.2, font='assets/fonts/Roboto-Bold.ttf')

        self._last_update_time, self._last_aspect_ratio = 0.0, 0.0
        self.update_layout()

    def update_layout(self):
        aspect = window.aspect_ratio
        if abs(aspect - self._last_aspect_ratio) < 0.01: return
        self._last_aspect_ratio = aspect

        # Posisi dasar panel
        center_x = -aspect / 2.0 + 0.02 + (self.panel_w / 2.0)
        center_y = 0.22

        self.bg_panel.position = Vec3(center_x, center_y, 0)
        self.accent_left.position = Vec3(center_x - self.panel_w / 2.0, center_y, -0.005)

        # Titik Start (Atas Kiri)
        start_x = center_x - self.panel_w / 2.0 + 0.03
        start_y = center_y + self.panel_h / 2.0 - 0.02

        # ==========================================
        # PENATAAN VERTIKAL (Y-OFFSET)
        # ==========================================
        self.title_text.position = Vec3(start_x, start_y, -0.01)
        self.status_text.position = Vec3(start_x, start_y - 0.05, -0.01)
        self.top_info_text.position = Vec3(start_x, start_y - 0.13, -0.01)

        table_start_y = start_y - 0.23
        row_h = 0.045  # Jarak antar baris diperlebar
        
        # ==========================================
        # PENATAAN HORIZONTAL TABEL (MATEMATIKA PRESISI)
        # ==========================================
        # Pembagian area X:
        # Robot: start_x s/d start_x + 0.16 (Lebar 0.16)
        # BAT:   start_x + 0.16 s/d start_x + 0.29 (Lebar 0.13)
        # STEP:  start_x + 0.29 s/d start_x + 0.42 (Lebar 0.13)
        # COST:  start_x + 0.42 s/d start_x + 0.54 (Lebar 0.12)

        col1_x = start_x                  # Rata kiri (origin -0.5)
        col2_x = start_x + 0.225          # Titik tengah BAT
        col3_x = start_x + 0.355          # Titik tengah STEP
        col4_x = start_x + 0.48           # Titik tengah COST

        self.col_robot.position = Vec3(col1_x, table_start_y, -0.01)
        self.col_bat.position = Vec3(col2_x, table_start_y, -0.01)
        self.col_step.position = Vec3(col3_x, table_start_y, -0.01)
        self.col_cost.position = Vec3(col4_x, table_start_y, -0.01)

        total_table_h = row_h * 2
        v_line_y = table_start_y - (total_table_h / 2.0)
        
        # Garis Vertikal Tabel (Diletakkan di antara teks)
        self.line_vert_1.position = Vec3(start_x + 0.16, v_line_y, -0.005)
        self.line_vert_1.scale = Vec3(0.002, total_table_h + 0.03, 1)
        
        self.line_vert_2.position = Vec3(start_x + 0.29, v_line_y, -0.005)
        self.line_vert_2.scale = Vec3(0.002, total_table_h + 0.03, 1)
        
        self.line_vert_3.position = Vec3(start_x + 0.42, v_line_y, -0.005)
        self.line_vert_3.scale = Vec3(0.002, total_table_h + 0.03, 1)

        # Garis Horizontal
        self.line_h1.position = Vec3(center_x, table_start_y - (row_h / 2.0), -0.005)
        self.line_h1.scale = Vec3(self.panel_w - 0.04, 0.002, 1)
        
        self.line_h2.position = Vec3(center_x, table_start_y - (row_h * 2.5), -0.005)
        self.line_h2.scale = Vec3(self.panel_w - 0.04, 0.002, 1)

        # Baris Data
        for i, row in enumerate(self.rows):
            y_pos = table_start_y - (row_h * (i + 1))
            row["robot"].position = Vec3(col1_x, y_pos, -0.01)
            row["bat"].position = Vec3(col2_x, y_pos, -0.01)
            row["step"].position = Vec3(col3_x, y_pos, -0.01)
            row["cost"].position = Vec3(col4_x, y_pos, -0.01)

        # Footer
        footer_y = table_start_y - (row_h * 3.2)
        self.footer_text.position = Vec3(start_x, footer_y, -0.01)

    def set_visible(self, visible: bool):
        self.container.enabled = visible

    def update(self, mission_mgr: MissionManager, interaction_sys: InteractionSystem):
        if not self.container.enabled: return
        self.update_layout()

        now = time.perf_counter()
        if (now - self._last_update_time < 0.05) and not mission_mgr.race_finished: return
        self._last_update_time = now

        raw_status = f"STATUS: {interaction_sys.prompt_text}"
        wrapped_status = textwrap.fill(raw_status, width=55)
        self.status_text.text = wrapped_status

        elapsed = mission_mgr.race_elapsed_time
        timer_str = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}.{int((elapsed * 100) % 100):02d}"
        stars_str = f"{mission_mgr.star_rating}/5"

        self.top_info_text.text = (
            f"TIME: {timer_str}\n"
            f"SCORE: {mission_mgr.score:,} PTS\n"
            f"COMBO: x{mission_mgr.combo_multiplier}\n"
            f"RATING MISI: {stars_str}"
        )

        plan = mission_mgr.dual_plan
        if plan:
            cost_a, cost_b = f"{plan.alpha_plan.total_cost:.1f}", f"{plan.beta_plan.total_cost:.1f}"
            step_a, step_b = f"{mission_mgr.robot_alpha.waypoint_idx}/{mission_mgr.robot_alpha.total_mission_steps}", f"{mission_mgr.robot_beta.waypoint_idx}/{mission_mgr.robot_beta.total_mission_steps}"
            bat_a, bat_b = f"{mission_mgr.robot_alpha.battery:.0f}%", f"{mission_mgr.robot_beta.battery:.0f}%"
        else:
            cost_a, cost_b, step_a, step_b, bat_a, bat_b = "-", "-", "-", "-", "-", "-"

        self.rows[0]["robot"].text = "A* (Alpha)"
        self.rows[0]["robot"].color = color.rgb32(56, 189, 248) 
        self.rows[0]["bat"].text = bat_a
        self.rows[0]["step"].text = step_a
        self.rows[0]["cost"].text = cost_a

        self.rows[1]["robot"].text = "GBFS (Beta)"
        self.rows[1]["robot"].color = color.rgb32(251, 146, 60) 
        self.rows[1]["bat"].text = bat_b
        self.rows[1]["step"].text = step_b
        self.rows[1]["cost"].text = cost_b

        first_arrived = mission_mgr.first_to_arrive if mission_mgr.first_to_arrive else "Menuju Target..."
        efficiency_champ = mission_mgr.overall_efficiency_winner if mission_mgr.race_finished else "Menghitung..."

        self.footer_text.text = (
            f"Tiba Pertama: {first_arrived}\n"
            f"Juara Efisiensi: {efficiency_champ}\n"
            f"Hint: Tekan [G] untuk Balapan Acak!"
        )