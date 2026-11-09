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
        # Root container unscaled (scale=Vec3(1,1,1)) - menjaga rasio aspek font 1:1 sempurna
        self.container = Entity(parent=camera.ui, enabled=True)

        self.panel_w = 0.58
        self.panel_h = 0.40

        # Panel dasar semi-transparan kompak dengan gaya cyber-industrial
        self.bg_panel = Entity(
            parent=self.container,
            model='quad',
            position=Vec3(-0.48, 0.25, 0),
            scale=Vec3(self.panel_w, self.panel_h, 1),
            color=color.rgba32(14, 18, 28, 225),
        )

        # Garis aksen cyan di bagian atas panel
        self.accent_line = Entity(
            parent=self.container,
            model='quad',
            position=Vec3(-0.48, 0.25 + self.panel_h / 2 - 0.003, -0.005),
            scale=Vec3(self.panel_w, 0.006, 1),
            color=color.rgb32(0, 229, 255),
        )

        # Teks telemetri WMS unscaled (tidak gepeng/squished)
        self.text_display = Text(
            parent=self.container,
            text="",
            position=Vec3(-0.76, 0.43, -0.01),
            scale=0.68,
            color=color.white,
        )

        self._last_update_time: float = 0.0
        self._last_rendered_text: str = ""
        self._last_aspect_ratio: float = 0.0

        from ursina import window
        self.update_layout()

    def update_layout(self):
        """Menyesuaikan posisi panel secara dinamis agar selalu menempel rapi di kiri atas layar."""
        from ursina import window
        aspect = window.aspect_ratio
        if abs(aspect - self._last_aspect_ratio) < 0.01:
            return
        self._last_aspect_ratio = aspect

        margin_x = 0.02
        screen_left = -aspect / 2.0
        center_x = screen_left + margin_x + (self.panel_w / 2.0)
        center_y = 0.25

        self.bg_panel.position = Vec3(center_x, center_y, 0)
        self.bg_panel.scale = Vec3(self.panel_w, self.panel_h, 1)

        self.accent_line.position = Vec3(center_x, center_y + self.panel_h / 2.0 - 0.003, -0.005)
        self.accent_line.scale = Vec3(self.panel_w, 0.006, 1)

        self.text_display.position = Vec3(center_x - self.panel_w / 2.0 + 0.016, center_y + self.panel_h / 2.0 - 0.020, -0.01)

    def set_visible(self, visible: bool):
        """Menampilkan atau menyembunyikan panel HUD Serious."""
        self.container.enabled = visible
        if visible:
            self._last_rendered_text = ""  # Force refresh saat dibuka kembali

    def update(self, mission_mgr: MissionManager, interaction_sys: InteractionSystem):
        """Memperbarui teks metrik telemetri secara efisien dengan dirty-checking dan rate-limiting."""
        if not self.container.enabled:
            return

        self.update_layout()

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
