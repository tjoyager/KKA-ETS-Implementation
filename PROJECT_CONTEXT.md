# Project Context: Simulator Robot Gudang 3D (Autonomous Warehouse AGV)

Konteks lengkap source code, konfigurasi, dokumentasi, dan struktur direktori proyek setelah **Perombakan Arsitektur Besar-Besaran (Massive Refactoring)** ke arsitektur modular (Kognisi, Behavior, Environment, Komunikasi).

---

## 1. Documentation

### File: `/media/hadryan/Data/Kuliah/Semester 3/3. Konsep Kecerdasan Artificial/KKA-ETS-Implementation/README.md`

Lihat dokumentasi lengkap pada `README.md`.

---

## 2. Directory Tree

```text
KKA-ETS-Implementation/
├── .gitignore
├── PROJECT_CONTEXT.md
├── README.md
├── requirements.txt
├── main.py
│
├── assets/
│   └── models/
│       ├── agv.obj
│       ├── shelf.obj
│       ├── cargo.obj
│       ├── dock.obj
│       └── README.md
│
└── src/
    ├── __init__.py
    ├── config.py
    ├── simulation.py
    ├── algorithms.py         # Backward compatibility
    ├── map_grid.py           # Backward compatibility
    ├── simulation_3d.py      # Backward compatibility
    │
    ├── cognition/            # [KOGNISI] Logika Graph & Algoritma Pathfinding
    │   ├── __init__.py
    │   ├── heuristics.py
    │   ├── warehouse_graph.py
    │   └── pathfinding.py
    │
    ├── behavior/             # [BEHAVIOR] Kontrol Pergerakan Robot & Misi
    │   ├── __init__.py
    │   ├── robot_controller.py
    │   └── mission_manager.py
    │
    ├── environment/          # [ENVIRONMENT] Pemandangan 3D & Aset
    │   ├── __init__.py
    │   ├── asset_loader.py
    │   ├── interactive_shelf.py
    │   └── warehouse_scene.py
    │
    └── communication/        # [KOMUNIKASI] HUD Ganda & Raycasting
        ├── __init__.py
        ├── interaction_system.py
        ├── hud_serious.py
        ├── hud_gamification.py
        └── ui_controller.py
```

---

## 3. Configuration Files

### `requirements.txt`
```text
numpy>=1.24.0
ursina>=6.0.0
```

---

## 4. Key Module Overview

1. `src/config.py`: Definisi parameter grid 50x50, titik spawn statis (1, 1) & (1, 3), palet warna, dan path model.
2. `src/cognition/warehouse_graph.py`: Generator layout gudang 50x50 kompleks dengan ratusan rak interaktif, lorong arteri (y & x = 10..12, 24..26, 38..40), sekat cul-de-sac proporsional, dan access nodes.
3. `src/cognition/pathfinding.py`: Implementasi A* Search, Greedy Best-First Search, dan `DualPathPlanner` untuk balapan dual-robot simultan.
4. `src/environment/interactive_shelf.py`: Entitas rak 3D ber-Collider yang dipisahkan dari model visual rangka (zero draw-call collider) dengan indikator penanda seleksi pick-up (Cyan) dan drop-off (Magenta).
5. `src/environment/warehouse_scene.py`: Konstruksi lingkungan 3D teroptimasi ekstrem: Floor Texture Tiling (1 single-plane 50x50), Static Mesh Combining (melebur ratusan rak & dinding ke single mesh), dan Asynchronous Loading Generator dengan Loading Screen.
6. `src/environment/asset_loader.py`: Pemuatan model `.obj` eksternal di `assets/models/` dengan graceful procedural fallback.
6. `src/behavior/robot_controller.py`: AGV Controller dengan rotasi halus lerp, lidar scanner, kargo dek, dan trajectory trail.
7. `src/behavior/mission_manager.py`: Sinkronisasi balapan dua robot (A* vs GBFS), stopwatch, penghitung skor efisiensi, dan rating bintang.
8. `src/communication/interaction_system.py`: State-machine point-and-click raycasting berbasis kursor mouse.
9. `src/communication/hud_serious.py`: Dashboard telemetri WMS industri & radar bottleneck jaringan.
10. `src/communication/hud_gamification.py`: UI Arcade Time-Attack, combo multiplier, dan sistem bintang 1-5.
11. `src/communication/ui_controller.py`: Pengendali tombol layar & hotkey keyboard (`M`, `G`, `Spasi`, `R`, `V`, `+/-`, `Esc`).
12. `main.py`: Peluncur langsung simulasi 3D tanpa dependensi input terminal.
