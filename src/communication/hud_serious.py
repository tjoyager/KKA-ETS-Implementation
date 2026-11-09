"""
hud_serious.py
==============
Panel HUD Mode Serius (Warehouse Management System / Industrial Telemetry).
Menampilkan metrik analitik profesional: tabel komparasi A* vs GBFS, total biaya rute,
jumlah simpul dieksplorasi, waktu eksekusi milidetik, serta analisis bottleneck jaringan gudang.
"""

import time
from typing import Optional
from ursina import Entity, Vec3, color, camera, Text

from src.behavior.mission_manager import MissionManager
from src.communication.interaction_system import InteractionSystem


class SeriousHUD:
    """
    HUD Telemetri Industri WMS dengan visual tabel data presisi tinggi teroptimasi
    (Throttle render mesh font untuk mencegah micro-stuttering).
    """

    def __init__(self):
        # Panel dasar semi-transparan kompak dengan gaya cyber-industrial
        self.panel = Entity(
            parent=camera.ui,
            model='quad',
            position=Vec3(-0.54, 0.28, 0),
            scale=Vec3(0.68, 0.38, 1),
            color=color.rgba32(14, 18, 28, 220),
            enabled=True,
        )

        # Garis aksen cyan di bagian atas panel
        Entity(
            parent=self.panel,
            model='quad',
            position=Vec3(0, 0.495, -0.01),
            scale=Vec3(1.0, 0.014, 1),
            color=color.rgb32(0, 229, 255),
        )

        self.text_display = Text(
            parent=self.panel,
            text="",
            position=Vec3(-0.48, 0.46, -0.01),
            scale=0.76,
            color=color.white,
        )

        self._last_update_time: float = 0.0
        self._last_rendered_text: str = ""

    def set_visible(self, visible: bool):
        """Menampilkan atau menyembunyikan panel HUD Serious."""
        self.panel.enabled = visible
        if visible:
            self._last_rendered_text = ""  # Force refresh saat dibuka kembali

    def update(self, mission_mgr: MissionManager, interaction_sys: InteractionSystem):
        """Memperbarui teks metrik telemetri secara efisien dengan dirty-checking dan rate-limiting."""
        if not self.panel.enabled:
            return

        now = time.perf_counter()
        # Batasi regenerasi text mesh Ursina ke 20 Hz (setiap 0.05s) kecuali baru saja selesai balapan
        if (now - self._last_update_time < 0.05) and not mission_mgr.race_finished:
            return
        self._last_update_time = now

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

        # Data Heuristik Aktif
        h_name = mission_mgr.current_heuristic_name.upper()
        h_formula = mission_mgr.current_heuristic_info.get("formula", "")

        new_text = (
            f" [ WMS FLEET TELEMETRY ]                      ● ONLINE\n"
            f" HEURISTIK: [ {h_name} ] (h = {h_formula})      [H] Ganti\n"
            f" Misi: {pickup_info} -> {dropoff_info}\n"
            f" --------------------------------------------------------\n"
            f" METRIK SEARCH       | [CYAN] A* (Alpha)  | [AMBER] GBFS (Beta)\n"
            f" --------------------------------------------------------\n"
            f" Biaya Rute (Cost)   | {cost_a.ljust(18)} | {cost_b}\n"
            f" Simpul Eksplorasi   | {nodes_a.ljust(18)} | {nodes_b}\n"
            f" Waktu Komputasi     | {time_a.ljust(18)} | {time_b}\n"
            f" Progres Langkah     | {steps_a.ljust(18)} | {steps_b}\n"
            f" Status Robot        | {robot_a.state.value[:16].ljust(18)} | {robot_b.state.value[:16]}\n"
            f" --------------------------------------------------------\n"
            f" BOTTLENECK: {shared_count} sel ({cong_pct:.1f}%) | {risk_str}\n"
            f" SPEED: {mission_mgr.current_speed:.1f}x [+/-] | STATUS: {outcome_str[:32]}"
        )

        if new_text != self._last_rendered_text:
            self.text_display.text = new_text
            self._last_rendered_text = new_text
