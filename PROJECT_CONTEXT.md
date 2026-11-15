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

## 4. Key Module Overview (Optimasi Keseluruhan Sistem)

1. `src/config.py`: Definisi parameter grid 35x25, titik docking Start (1, 1) & (1, 3), titik Goal (32, 21), palet warna (dinding beton & rak), dan path model.
2. `src/cognition/warehouse_graph.py`: Generator layout gudang 35x25 kompleks dengan rintangan dinding (Wall Obstacles) & cul-de-sac traps, serta pra-kalkulasi tabel ketetanggaan (`precompute_adjacency`) untuk lookup rute ultra-cepat.
3. `src/cognition/pathfinding.py`: Implementasi A* Search dengan prioritas tie-breaking $h(n)$ terkecil (memangkas 93% simpul tak perlu & sub-milidetik), Greedy Best-First Search, dan `DualPathPlanner` untuk balapan dual-robot simultan.
4. `src/environment/interactive_shelf.py`: Entitas rak 3D ber-Collider dengan Singleton Selection Indicators dan zero-collider kargo.
5. `src/environment/warehouse_scene.py`: Konstruksi lingkungan 3D teroptimasi ekstrem: Floor Texture Tiling (1 single-plane 35x25), Static Mesh Combining (melebur balok dinding beton abu-abu kontras & rak ke single mesh), Docking & Goal Stations, preset kamera adaptif, dan Asynchronous Loading Generator dengan Loading Screen.
6. `src/environment/asset_loader.py`: Pemuatan model `.obj` eksternal di `assets/models/` dengan graceful procedural fallback dan model reference direct caching.
7. `src/behavior/robot_controller.py`: AGV Controller dengan rotasi halus lerp, lidar scanner, kargo dek, dan Zero-Allocation Trail Entity Pooling (bebas GC stutter).
8. `src/behavior/mission_manager.py`: Sinkronisasi balapan dua robot (A* vs GBFS), stopwatch, penghitung skor efisiensi, dan rating bintang.
9. `src/communication/interaction_system.py`: State-machine point-and-click raycasting berbasis kursor mouse dengan deteksi collider yang diringankan.
10. `src/communication/hud_serious.py`: Dashboard telemetri WMS industri teroptimasi (Rate-limiting 20 Hz & text dirty-checking).
11. `src/communication/hud_gamification.py`: UI Arcade Time-Attack, combo multiplier, dan sistem bintang dengan throttle render font mesh.
12. `src/communication/ui_controller.py`: Pengendali tombol layar & hotkey keyboard (`M`, `G`, `Spasi`, `R`, `V`, `+/-`, `Esc`).
13. `main.py`: Peluncur langsung simulasi 3D tanpa dependensi input terminal.
