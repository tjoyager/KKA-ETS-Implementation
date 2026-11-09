"""
hud_gamification.py
===================
Panel HUD Mode Gamifikasi (Arcade Style / Logistics Rush).
Menampilkan elemen Time-Attack (timer stopwatch), akumulasi skor efisiensi,
combo multiplier, serta sistem rating bintang 1-5 berdasarkan rasio keoptimalan rute.
"""

import time
from ursina import Entity, Vec3, color, camera, Text

from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem


class GamificationHUD:
    """
    HUD Bergaya Video Game Arcade dengan sistem skor, time-attack, dan rating bintang
    teroptimasi (Throttle render mesh font untuk framerate stabil).
    """

    def __init__(self):
        # Root container unscaled (scale=Vec3(1,1,1)) - mencegah distorsi teks font
        self.container = Entity(parent=camera.ui, enabled=False)

        # 1. Panel banner atas bergaya arcade
        top_pos = Vec3(0, 0.435, 0)
        top_w = 0.98
        top_h = 0.088
        self.top_bg = Entity(
            parent=self.container,
            model='quad',
            position=top_pos,
            scale=Vec3(top_w, top_h, 1),
            color=color.rgba32(18, 14, 30, 235),
        )
        Entity(
            parent=self.container,
            model='quad',
            position=top_pos + Vec3(0, top_h / 2 - 0.003, -0.005),
            scale=Vec3(top_w, 0.006, 1),
            color=color.rgb32(255, 215, 0),
        )
        self.top_text = Text(
            parent=self.container,
            text="",
            position=Vec3(-0.47, 0.468, -0.01),
            scale=0.74,
            color=color.rgb32(255, 230, 40),
        )

        # 2. Panel samping kiri untuk papan skor & rincian balapan
        side_pos = Vec3(-0.52, 0.16, 0)
        side_w = 0.66
        side_h = 0.42
        self.side_bg = Entity(
            parent=self.container,
            model='quad',
            position=side_pos,
            scale=Vec3(side_w, side_h, 1),
            color=color.rgba32(20, 16, 34, 225),
        )
        Entity(
            parent=self.container,
            model='quad',
            position=side_pos + Vec3(0, side_h / 2 - 0.003, -0.005),
            scale=Vec3(side_w, 0.006, 1),
            color=color.rgb32(233, 30, 99),
        )
        self.side_text = Text(
            parent=self.container,
            text="",
            position=Vec3(-0.83, 0.35, -0.01),
            scale=0.72,
            color=color.white,
        )

        self._last_update_time: float = 0.0
        self._last_top_text: str = ""
        self._last_side_text: str = ""

    def set_visible(self, visible: bool):
        """Menampilkan atau menyembunyikan elemen HUD Gamifikasi."""
        self.container.enabled = visible
        if visible:
            self._last_top_text = ""
            self._last_side_text = ""

    def update(self, mission_mgr: MissionManager, interaction_sys: InteractionSystem):
        """Memperbarui visual skor, bintang, dan waktu balapan dengan dirty-checking dan rate-limiting."""
        if not self.container.enabled:
            return

        now = time.perf_counter()
        if (now - self._last_update_time < 0.05) and not mission_mgr.race_finished:
            return
        self._last_update_time = now

        # Format Stopwatch Time-Attack
        elapsed = mission_mgr.race_elapsed_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        millis = int((elapsed * 100) % 100)
        timer_str = f"{mins:02d}:{secs:02d}.{millis:02d}"

        # Bintang visual
        stars = "[*]" * mission_mgr.star_rating

        # Teks Banner Atas
        h_tag = mission_mgr.current_heuristic_name.upper()
        new_top = (
            f"[LOGISTICS RUSH] A* (CYAN) vs GBFS (ORANGE) | HEURISTIK: {h_tag} [H]\n"
            f"TIME-ATTACK: {timer_str} | SCORE: {mission_mgr.score:,} PTS | COMBO: x{mission_mgr.combo_multiplier}\n"
            f"RATING MISI: {stars} ({mission_mgr.star_rating}/5) | {mission_mgr.rating_explanation}"
        )
        if new_top != self._last_top_text:
            self.top_text.text = new_top
            self._last_top_text = new_top

        # Teks Panel Samping
        plan = mission_mgr.dual_plan
        if plan:
            cost_a = f"{plan.alpha_plan.total_cost:.1f}"
            cost_b = f"{plan.beta_plan.total_cost:.1f}"
            nodes_a = f"{plan.alpha_plan.total_nodes_explored}"
            nodes_b = f"{plan.beta_plan.total_nodes_explored}"
            step_a = f"{mission_mgr.robot_alpha.waypoint_idx}/{mission_mgr.robot_alpha.total_mission_steps}"
            step_b = f"{mission_mgr.robot_beta.waypoint_idx}/{mission_mgr.robot_beta.total_mission_steps}"
        else:
            cost_a, cost_b, nodes_a, nodes_b, step_a, step_b = "-", "-", "-", "-", "-", "-"

        first_arrived = mission_mgr.first_to_arrive if mission_mgr.first_to_arrive else "Menuju Target..."
        efficiency_champ = mission_mgr.overall_efficiency_winner if mission_mgr.race_finished else "Menghitung..."

        new_side = (
            f"STATUS MISI: {interaction_sys.prompt_text}\n"
            f"Misi Terselesaikan: {mission_mgr.missions_completed} Pengiriman\n"
            f"----------------------------------------------------\n"
            f"STANDING BALAPAN REAL-TIME:\n"
            f"  [CYAN] AGV Alpha (A*)   : Langkah {step_a} | Cost: {cost_a}\n"
            f"  [AMBER] AGV Beta (GBFS) : Langkah {step_b} | Cost: {cost_b}\n"
            f"----------------------------------------------------\n"
            f"Tiba Pertama di Target: {first_arrived}\n"
            f"Juara Efisiensi Energi : {efficiency_champ}\n"
            f"Hint: Tekan [G] untuk Balapan Acak Instan!"
        )
        if new_side != self._last_side_text:
            self.side_text.text = new_side
            self._last_side_text = new_side
