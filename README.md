# 🤖 Simulasi Robot Gudang 3D (Autonomous Warehouse AGV Simulator)
> **Tugas / Proyek Kuliah Konsep Kecerdasan Artificial (KKA)**  
> Simulator robot gudang otonom (*Automated Guided Vehicle* / AGV) skala **50x50** berbasis **Ursina Engine (Panda3D)** dengan arsitektur modular, interaktivitas penuh *Point-and-Click* (Raycasting), balapan dual-robot (**A\* Search vs Greedy Best-First Search**), dan antarmuka HUD ganda (*Industrial WMS vs Gamification*).

---

## 📌 Ringkasan Pembaruan Arsitektur Besar (Massive Refactoring)

Codebase telah dirombak secara menyeluruh dari skrip monolitik menjadi arsitektur modular modern berbasis pemisahan tanggung jawab:
- 🧠 **Kognisi (`src/cognition/`)**: Logika representasi graf gudang 50x50, fungsi heuristik matematika (*Manhattan, Euclidean, Octile*), serta algoritma *Informed Search* dan perencana rute konkuren dual-robot (*Dual Path Planner*).
- ⚙️ **Behavior (`src/behavior/`)**: Kinematika pergerakan robot otonom (*smooth waypoint translation*, interpolasi sudut hadap *lerp_angle*, animasi pemuatan kargo, dan penanda jejak bercahaya *trajectory trail*), serta *Mission Manager*.
- 🌐 **Environment (`src/environment/`)**: Pemuatan aset 3D eksternal (`.obj` / `.gltf`) dengan *graceful procedural fallback*, perakitan pemandangan 3D gudang skala 50x50 dengan **Floor Texture Tiling**, **Static Mesh Combining** (melebur ratusan rak dan dinding menjadi single mesh), serta pemisahan entitas rak interaktif (*Interactive Shelf* ber-Collider ringan tanpa beban draw call).
- 💬 **Komunikasi (`src/communication/`)**: Sistem raycasting mouse (*Point-and-Click* state-machine), HUD Mode Serius (*Industrial WMS Telemetry & Bottleneck Radar*), HUD Mode Gamifikasi (*Time-Attack & Star Rating*), serta UI Controller.
- ⚡ **Asynchronous Loading Lifecycle**: Inisialisasi lingkungan menggunakan generator coroutine dengan layar *loading screen* dinamis ("MEMUAT ARENA 50x50... MOHON TUNGGU") yang mencegah jendela freeze / not responding saat startup.

---

## 🚀 8 Fitur Utama yang Telah Diimplementasikan

### 1. Skala Arena 50x50 & Generator Tata Letak Kompleks
- Dimensi grid disesuaikan menjadi **50x50 sel** (2.500 sel).
- Generator denah gudang otomatis membangun struktur tata letak realistis:
  - **Lorong Arteri Utama (*Cross Aisles*)**: Lebar 3 sel di $y = 10..12, 24..26, 38..40$ dan $x = 10..12, 24..26, 38..40$ untuk pergerakan bebas hambatan.
  - **Blok Rak Palet Ganda (*Double-Deep Racks*)**: Ratusan rak berbaris memanjang dipisahkan lorong sempit (*narrow aisles*) selebar 2 sel.
  - **Sekat Partisi Labirin (*Cul-de-Sacs*)**: Jebakan buntu proporsional yang secara teoritis memancing kelemahan GBFS ($f=h$) agar terbentur dinding, membuktikan keunggulan matematis A* ($f=g+h$).

### 2. Titik Start Statis (Standby Dock Area)
- Posisi *spawn* awal kedua robot terkunci secara absolut di pojok kiri bawah arena:
  - **AGV Alpha (A\* Search)**: Terkunci di Dock `(1, 1)`.
  - **AGV Beta (GBFS)**: Terkunci di Dock `(1, 3)`.
- Dilengkapi platform pengisian daya 3D (*Charging Pad Platform*) dengan label penanda melayang.

### 3. Interaktivitas Raycasting (Point-and-Click)
- **Bebas Dependensi Terminal**: Program tidak lagi meminta input teks melalui CLI; simulasi langsung membuka jendela 3D interaktif secara instan.
- **Komponen Collider**: Setiap rak dan kotak kargo memiliki komponen `collider='box'`.
- **State-Machine Dua Langkah**:
  - **Klik 1 (Pick-up)**: Klik rak atau kotak kargo yang ada barangnya untuk menjadikannya titik jemput (ditandai cincin cahaya *Cyan Neon*).
  - **Klik 2 (Drop-off)**: Klik rak kosong mana saja sebagai tujuan pengantaran (ditandai cincin cahaya *Magenta Neon*).
  - Sistem langsung meluncurkan balapan kedua robot secara otomatis!

### 4. Entitas Rak Dinamis (Graph Access Nodes)
- Rak bukan sekadar balok rintangan statis, melainkan *node* graf tujuan yang interaktif.
- Algoritma *pathfinding* secara cerdas mencari rute menuju **Access Node** (sel lorong tetangga terdekat yang dapat dilalui robot) dari rak terpilih.

### 5. Dukungan Aset Model 3D Eksternal (.obj / .gltf)
- Kerangka folder `assets/models/` menyediakan model 3D Wavefront `.obj` siap pakai:
  - `agv.obj`: Robot AGV industri lengkap dengan sasis, bumper, dek kargo, dan tower sensor.
  - `shelf.obj`: Rak palet penyimpanan bertingkat (*multi-tier rack*).
  - `cargo.obj`: Kotak kontainer kargo logistik.
  - `dock.obj`: Bantalan stasiun pengisian daya otomatis.
- **Mekanisme Graceful Fallback**: Jika berkas eksternal belum tersedia atau gagal dimuat, `AssetLoader` secara otomatis melakukan *fallback* ke model prosedural modular tanpa pernah mengalami *crash*.
- Disertai dokumentasi lengkap dan tautan pengunduhan model 3D di [assets/models/README.md](assets/models/README.md).

### 6. Simulasi Balapan Dual-Robot (A* Search vs GBFS)
- Instansiasi dua *controller* AGV independen yang berlaga serentak:
  - **AGV Alpha (Electric Cyan)**: Dikendalikan oleh algoritma **A\* Search** (Jalur Optimal dengan *Neon Green Trail*).
  - **AGV Beta (Vivid Amber)**: Dikendalikan oleh algoritma **Greedy Best-First Search** (Jalur Heuristik Cepat dengan *Fiery Orange Trail*).
- Kalkulasi rute konkuren dua etape (*Leg 1: Spawn $\rightarrow$ Pick-up, Leg 2: Pick-up $\rightarrow$ Drop-off*).
- Pengguna dapat menyaksikan langsung bagaimana GBFS tergiur lorong buntu karena hanya mengandalkan $h(n)$, sementara A* menavigasi lorong tengah secara efisien dan memenangkan keoptimalan rute.

### 7. HUD Mode Ganda (Serious vs Gamification)
Beralih instan antara dua mode tampilan hanya dengan menekan tombol **`[M]`** pada keyboard atau mengklik tombol layar:
- **Mode Serious (Warehouse Management System Analytics)**:
  - Tabel telemetri industri komparatif: Biaya rute (*Cost*), Simpul dieksplorasi (*Nodes Explored*), Waktu eksekusi milidetik (*Execution Time ms*), dan progres langkah.
  - Radar Bottleneck Jaringan: Deteksi sel lorong bersama (*shared corridor cells*) dan indeks kemacetan (*congestion risk*).
  - Status armada AGV real-time.
- **Mode Gamifikasi (Arcade Logistics Rush)**:
  - **Time-Attack Stopwatch**: Pelacak waktu misi berdetik milidetik.
  - **Sistem Skor & Combo Multiplier**: Akumulasi poin berdasarkan kecepatan dan keoptimalan pengiriman (Combo x1, x2, x3...).
  - **Rating Bintang (1 - 5 Bintang ⭐⭐⭐⭐⭐)**: Penilaian objektif berdasarkan rasio panjang rute terhadap rute optimal teoritis.
  - Banner Pengumuman Juara Balapan dinamis.

---

## 📂 Struktur Direktori Modular

```text
KKA-ETS-Implementation/
├── assets/
│   └── models/               # Berkas model 3D eksternal & dokumentasi unduhan
│       ├── agv.obj
│       ├── shelf.obj
│       ├── cargo.obj
│       ├── dock.obj
│       └── README.md
│
├── src/
│   ├── config.py             # Konstanta global, koordinat grid 100x100, warna, & preset kamera
│   │
│   ├── cognition/            # [KOGNISI] Logika Graf & Algoritma Pathfinding
│   │   ├── heuristics.py     # Manhattan, Euclidean, Octile, Chebyshev
│   │   ├── warehouse_graph.py# Graf grid 100x100, generator tata letak, & access nodes rak
│   │   └── pathfinding.py    # A* Search, GBFS, DualPathPlanner konkuren
│   │
│   ├── behavior/             # [BEHAVIOR] Kontrol Kinematika & Misi Robot
│   │   ├── robot_controller.py # AGV Controller, lerp heading, lidar rotasi, kargo dek, trail
│   │   └── mission_manager.py  # Dispatcher balapan dual-robot, stopwatch, skor, & winner logic
│   │
│   ├── environment/          # [ENVIRONMENT] Pemandangan 3D & Aset
│   │   ├── asset_loader.py   # Loader model eksternal aman dengan graceful fallback
│   │   ├── interactive_shelf.py# Entitas rak 3D ber-Collider dengan deteksi klik & seleksi
│   │   └── warehouse_scene.py# Konstruksi lantai 100x100, dinding, docking pad, pencahayaan
│   │
│   ├── communication/        # [KOMUNIKASI] Antarmuka Interaktif
│   │   ├── interaction_system.py # Raycast mouse hover & state-machine klik
│   │   ├── hud_serious.py    # Dashboard analitik industri WMS
│   │   ├── hud_gamification.py # Arcade UI: Time-Attack, skor, combo, & bintang
│   │   └── ui_controller.py  # Master UI: tombol layar & handler hotkey keyboard
│   │
│   └── simulation.py         # Koordinator aplikasi utama Ursina Engine
│
├── requirements.txt          # Dependensi (numpy>=1.24.0, ursina>=6.0.0)
├── README.md                 # Dokumentasi panduan lengkap
└── main.py                   # Berkas peluncur langsung (tanpa dependensi terminal)
```

---

## 🛠️ Instalasi & Menjalankan Program

### 🔹 Persyaratan Sistem
- **Python**: Versi 3.9 s.d. 3.12
- Pustaka: `numpy`, `ursina`

### 🔹 Langkah Eksekusi (Windows & Linux)
1. Aktifkan virtual environment Anda:
   ```bash
   # Linux / Ubuntu
   source venv/bin/activate

   # Windows
   .\venv\Scripts\activate
   ```
2. Pastikan paket dependensi terpasang:
   ```bash
   pip install -r requirements.txt
   ```
3. Jalankan simulator:
   ```bash
   python main.py
   ```
   *(Jendela 3D interaktif 1280x720 akan langsung terbuka tanpa pertanyaan di terminal!)*

---

## 🎮 Panduan Kontrol & Pintasan Keyboard

| Kontrol Input | Tombol Layar | Fungsi & Keterangan |
| :--- | :--- | :--- |
| **Klik Kiri Mouse** | - | **Raycasting Point-and-Click**: Klik 1 pada rak kargo (Pick-up), Klik 2 pada rak kosong (Drop-off). |
| **`[M]`** | **`[Mode HUD]`** | **Toggle HUD Mode Ganda**: Beralih antara **Serious (WMS Analytics)** dan **Gamifikasi (Arcade)**. |
| **`[G]`** | **`[Misi Acak]`** | **Instan Random Race**: Otomatis memilih sepasang rak acak dan langsung meluncurkan balapan! |
| **`[Spasi]`** | **`[Jeda / Lanjut]`** | Menjeda (*pause*) atau melanjutkan pergerakan armada AGV. |
| **`[R]`** | **`[Reset]`** | Mengembalikan kedua robot kembali ke stasiun dock pojok kiri bawah. |
| **`[V]`** | **`[Kamera: ...]`** | Mengganti sudut kamera: **Isometrik** $\rightarrow$ **Top-Down 2D** $\rightarrow$ **Follow Alpha** $\rightarrow$ **Follow Beta** $\rightarrow$ **Bebas (Free Orbit)**. |
| **`[1]` / `[2]`** | - | Langsung mengunci kamera mengekor di belakang AGV Alpha / AGV Beta. |
| **`[+]` / `[-]`** | **`[Cepat] / [Lambat]`** | Menambah atau memperlambat laju kecepatan simulasi. |
| **Klik Kanan + Drag** | *(Mode Bebas)* | Mengorbit / memutar kamera bebas di sekeliling arena 50x50. |
| **Scroll Mouse** | - | *Zoom-in* / *Zoom-out* kamera. |
| **`[Esc]`** | **`[Keluar]`** | Menutup simulator dengan aman. |
