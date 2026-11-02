"""
hud_serious.py
==============
Panel HUD Mode Serius (Warehouse Management System / Industrial Telemetry).
Menampilkan metrik analitik profesional: tabel komparasi A* vs GBFS, total biaya rute,
jumlah simpul dieksplorasi, waktu eksekusi milidetik, serta analisis bottleneck jaringan gudang.
"""

from typing import Optional
from ursina import Entity, Vec3, color, camera, Text

from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem


class SeriousHUD:
    """
    HUD Telemetri Industri WMS dengan visual tabel data presisi tinggi.
    """

    def __init__(self):
        # Panel dasar gelap transparan di kiri atas layar
        self.panel = Entity(
            parent=camera.ui,
            model='quad',
            position=Vec3(-0.48, 0.25, 0),
            scale=Vec3(0.78, 0.44, 1),
            color=color.rgba32(14, 18, 26, 235),
            enabled=True,
        )

        self.text_display = Text(
            parent=self.panel,
            text="",
            position=Vec3(-0.48, 0.46, -0.01),
            scale=0.92,
            color=color.white,
        )

    def set_visible(self, visible: bool):
        """Menampilkan atau menyembunyikan panel HUD Serious."""
        self.panel.enabled = visible

    def update(self, mission_mgr: MissionManager, interaction_sys: InteractionSystem):
        """Memperbarui teks metrik telemetri secara real-time."""
        if not self.panel.enabled:
            return

        plan = mission_mgr.dual_plan
        robot_a = mission_mgr.robot_alpha
        robot_b = mission_mgr.robot_beta

        # Data metrik A* Search
        if plan:
            cost_a = f"{plan.alpha_plan.total_cost:.1f}"
            nodes_a = f"{plan.alpha_plan.total_nodes_explored}"
            time_a = f"{plan.alpha_plan.total_compute_time_ms:.2f} ms"
            steps_a = f"{robot_a.waypoint_idx}/{robot_a.total_mission_steps}"
        else:
            cost_a, nodes_a, time_a, steps_a = "-", "-", "-", "-"

        # Data metrik GBFS
        if plan:
            cost_b = f"{plan.beta_plan.total_cost:.1f}"
            nodes_b = f"{plan.beta_plan.total_nodes_explored}"
            time_b = f"{plan.beta_plan.total_compute_time_ms:.2f} ms"
            steps_b = f"{robot_b.waypoint_idx}/{robot_b.total_mission_steps}"
        else:
            cost_b, nodes_b, time_b, steps_b = "-", "-", "-", "-"

        # Bottleneck & Kemacetan Lorong
        if plan:
            shared_count = len(plan.shared_bottleneck_nodes)
            cong_pct = plan.congestion_index * 100.0
            if cong_pct < 25.0:
                risk_str = "RENDAH (Arteri Lancar)"
            elif cong_pct < 60.0:
                risk_str = "SEDANG (Persimpangan Bersama)"
            else:
                risk_str = "TINGGI (Bottleneck Koridor Utama)"
        else:
            shared_count = 0
            cong_pct = 0.0
            risk_str = "NORMAL"

        # Status Misi & Target
        pickup_info = (
            f"{mission_mgr.selected_pickup_shelf.shelf_data.shelf_id} ({mission_mgr.selected_pickup_shelf.shelf_data.cargo_item})"
            if mission_mgr.selected_pickup_shelf
            else "Belum Dipilih"
        )
        dropoff_info = (
            f"{mission_mgr.selected_dropoff_shelf.shelf_data.shelf_id}"
            if mission_mgr.selected_dropoff_shelf
            else "Belum Dipilih"
        )

        # Evaluasi akhir
        outcome_str = mission_mgr.overall_efficiency_winner if mission_mgr.race_finished else "Sedang Berlangsung..."

        self.text_display.text = (
            f"=== WMS TELEMETRY DASHBOARD (50x50 ARENA) ===\n"
            f"Mode HUD          : SERIOUS (INDUSTRIAL WMS) [Tekan 'M' Ganti Mode]\n"
            f"Status Operasi    : {interaction_sys.prompt_text}\n"
            f"Konsinyasi Kargo  : {pickup_info} -> Tujuan: {dropoff_info}\n"
            f"----------------------------------------------------------------------\n"
            f"METRIK KINERJA INFORMED SEARCH:\n"
            f"  Parameter Evaluasi       | AGV Alpha (A*)      | AGV Beta (GBFS)\n"
            f"  Total Biaya Rute (Cost)  | {cost_a.ljust(19)} | {cost_b}\n"
            f"  Simpul Dieksplorasi      | {nodes_a.ljust(19)} | {nodes_b}\n"
            f"  Waktu Kalkulasi Jalur    | {time_a.ljust(19)} | {time_b}\n"
            f"  Progres Langkah Navigasi | {steps_a.ljust(19)} | {steps_b}\n"
            f"  Status State Mesin       | {robot_a.state.value[:17].ljust(19)} | {robot_b.state.value[:17]}\n"
            f"----------------------------------------------------------------------\n"
            f"ANALISIS BOTTLENECK JARINGAN:\n"
            f"  Simpul Beririsan         : {shared_count} sel lorong ({cong_pct:.1f}% koridor bersama)\n"
            f"  Tingkat Resiko Macet     : {risk_str}\n"
            f"  Kecepatan Armada         : {mission_mgr.current_speed:.1f}x [Atur dgn +/-]\n"
            f"  Hasil Evaluasi Efisiensi : {outcome_str}"
        )
