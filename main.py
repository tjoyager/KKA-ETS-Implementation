"""
main.py
=======
File eksekusi utama untuk Simulator Robot Gudang 3D Otonom (Autonomous Warehouse AGV).
Menerapkan arsitektur modular terkini: Kognisi, Behavior, Environment, dan Komunikasi.

Fitur Unggulan:
- Skala Arena 50x50 dengan generator tata letak gudang kompleks dan realistis.
- Bebas dependensi terminal (langsung membuka visualisasi 3D interaktif).
- Interaktivitas penuh Point-and-Click (Raycasting): Klik kargo (Pick-up) & rak kosong (Drop-off).
- Entitas rak dinamis sebagai target node dengan titik akses (access nodes) terdekat.
- Dukungan pemuatan aset 3D eksternal (.obj/.gltf) di assets/models/ dengan graceful fallback.
- Simulasi balapan dual-robot konkuren (AGV Alpha: A* Search vs AGV Beta: GBFS).
- Mode HUD ganda: Serious (WMS Industrial Analytics) vs Gamifikasi (Arcade Time-Attack & Star Rating).
"""

import sys
from src.simulation import run_warehouse_simulation


def main():
    """Titik masuk utama simulator gudang 3D."""
    run_warehouse_simulation()


if __name__ == "__main__":
    main()
