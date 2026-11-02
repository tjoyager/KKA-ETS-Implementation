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
        # Panel atas bergaya arcade
        self.top_banner = Entity(
            parent=camera.ui,
            model='quad',
            position=Vec3(0, 0.40, 0),
            scale=Vec3(0.96, 0.14, 1),
            color=color.rgba32(20, 15, 35, 235),
            enabled=False,
        )

        self.top_text = Text(
            parent=self.top_banner,
            text="",
            position=Vec3(-0.48, 0.35, -0.01),
            scale=1.1,
            color=color.rgb32(255, 230, 0),
        )

        # Panel samping kiri untuk papan skor & rincian balapan
        self.side_panel = Entity(
            parent=camera.ui,
            model='quad',
            position=Vec3(-0.52, 0.16, 0),
            scale=Vec3(0.68, 0.32, 1),
            color=color.rgba32(22, 18, 38, 230),
            enabled=False,
        )

        self.side_text = Text(
            parent=self.side_panel,
            text="",
            position=Vec3(-0.46, 0.42, -0.01),
            scale=0.95,
            color=color.white,
        )

        self._last_update_time: float = 0.0
        self._last_top_text: str = ""
        self._last_side_text: str = ""

    def set_visible(self, visible: bool):
        """Menampilkan atau menyembunyikan elemen HUD Gamifikasi."""
        self.top_banner.enabled = visible
        self.side_panel.enabled = visible
        if visible:
            self._last_top_text = ""
            self._last_side_text = ""

    def update(self, mission_mgr: MissionManager, interaction_sys: InteractionSystem):
        """Memperbarui visual skor, bintang, dan waktu balapan dengan dirty-checking dan rate-limiting."""
        if not self.top_banner.enabled:
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
        new_top = (
            f"[WAREHOUSE SHOWDOWN] A* SEARCH (CYAN) vs GBFS (ORANGE)\n"
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
