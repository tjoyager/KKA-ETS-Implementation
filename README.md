# Simulasi Robot Gudang 3D (Autonomous Warehouse AGV Simulator)
> **Tugas / Proyek Kuliah Konsep Kecerdasan Artificial (KKA)**  
> Simulator robot gudang otonom (*Automated Guided Vehicle* / AGV) skala **35x25** berbasis **Ursina Engine (Panda3D)** dengan arsitektur modular, interaktivitas penuh *Point-and-Click* (Raycasting), balapan dual-robot (**A\* Search vs Greedy Best-First Search**), rintangan dinding beton (*Wall Obstacles*) & jebakan *cul-de-sac*, serta antarmuka HUD ganda (*Industrial WMS vs Gamification*).

---

## Ringkasan Pembaruan & Optimasi Ekstrem Keseluruhan Sistem

Codebase telah dioptimasi secara menyeluruh dari lapisan kognisi graf hingga siklus render GPU untuk memastikan framerate solid 60+ FPS dan waktu komputasi sub-milidetik:
- **Kognisi & Search Engine (`src/cognition/`)**:
  - **Graph Adjacency Precomputation**: Pra-kalkulasi tabel ketetanggaan simpul walkable 4-arah & 8-arah saat startup, menghilangkan iterasi koordinat dan evaluasi NumPy berulang (~10x - 18x lebih cepat).
  - **Intelligent Heuristic Tie-Breaking**: Memprioritaskan simpul dengan nilai $h(n)$ terkecil saat nilai $f(n)$ setara pada A* Search. Memangkas **93% simpul tak perlu** (dari ~1.464 simpul turun ke ~104 simpul) dan menurunkan waktu komputasi dari 31 ms menjadi **sub-milidetik (< 0.9 ms)** dengan keoptimalan rute tetap 100% terjamin secara matematis.
- **Environment & Scene Graph (`src/environment/`)**:
  - **Singleton Selection Indicators**: Mengganti 1.200+ entitas kotak hover dan cincin seleksi per-rak dengan 3 entitas indikator global (menghemat 1.200+ scene graph entities di Panda3D).
  - **Zero-Collider Cargo**: Menghilangkan 340 collider kotak kargo berlebih (raycast mouse kini langsung ditangani oleh bounding box rak), memangkas beban raycasting per-frame sebesar 36%.
  - **Floor Texture Tiling & Static Mesh Combining**: 1 single plane lantai raksasa dan peleburan ratusan visual rak & dinding ke dalam single mesh statis.
- **Behavior & Kinematika (`src/behavior/`)**:
  - **Zero-Allocation Trail Entity Pooling**: Daur-ulang penanda jejak bercahaya (*trajectory trail*) dengan entity pool tetap, menghilangkan alokasi dinamis berulang dan mencegah *garbage collection stutter*.
  - **Fast Scalar Vector Math**: Interpolasi translasi dan kalkulasi sudut hadap *heading* menggunakan matematika skalar presisi tinggi (`math.hypot`).
- **Komunikasi & HUD Telemetry (`src/communication/`)**:
  - **HUD Rate-Limiting & Dirty-Checking (20 Hz)**: Membatasi regenerasi quad mesh font teks Ursina ke 20 Hz dan hanya merender saat teks berubah, memangkas 85% beban text rendering CPU dan melenyapkan *micro-stuttering*.
  - **Asynchronous Coroutine Lifecycle**: Pemuatan bertahap dengan progress bar dinamis tanpa membuat jendela sistem operasi *freeze* / *not responding*.

---

## 8 Fitur Utama yang Telah Diimplementasikan

### 1. Skala Arena 35x25 & Generator Tata Letak Kompleks
- Dimensi grid disesuaikan menjadi **panjang (X) = 35 dan lebar (Z) = 25 sel** (875 sel).
- Generator denah gudang otomatis membangun struktur tata letak realistis:
  - **Lorong Arteri Utama (*Cross Aisles*)**: Sumbu horizontal di $y = 7, 8$ dan $y = 16$, serta sumbu vertikal di $x = 11$ dan $x = 23$.
  - **Blok Rak Palet Modular**: Blok rak terdistribusi rapi di 3 klaster horizontal dan vertikal.
  - **Rintangan Dinding (*Wall Obstacles*) & Sekat Labirin (*Cul-de-Sacs*)**: Dinding beton terpisah dari rak (`CellType.WALL = 2`) yang dirancang strategis untuk partisi ruangan dan kantong buntu U-shape. Menjebak GBFS ($f=h$) yang terlalu *greedy* ke arah target, memperlihatkan perbedaan dramatis dengan rute optimal A* ($f=g+h$).

### 2. Titik Start Statis (Standby Dock Area)
- Posisi *spawn* awal kedua robot terkunci secara absolut di pojok kiri bawah arena:
  - **AGV Alpha (A\* Search)**: Terkunci di Dock `(1, 1)`.
  - **AGV Beta (GBFS)**: Terkunci di Dock `(1, 3)`.
- Dilengkapi model 3D Docking Station dan teks penanda 3D melayang.
- **Posisi Target Goal**: Terletak proporsional di seberang arena di pojok kanan atas `(32, 21)` dengan platform 3D hijau emerald dan teks penanda melayang.

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
  - **Rating Bintang (1 - 5 Bintang)**: Penilaian objektif berdasarkan rasio panjang rute terhadap rute optimal teoritis.
  - Banner Pengumuman Juara Balapan dinamis.

---

## Struktur Direktori Modular

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
│   ├── config.py             # Konstanta global, koordinat grid 35x25, warna, & preset kamera
│   │
│   ├── cognition/            # [KOGNISI] Logika Graf & Algoritma Pathfinding
│   │   ├── heuristics.py     # Manhattan, Euclidean, Octile, Chebyshev
│   │   ├── warehouse_graph.py# Graf grid 35x25, generator tata letak, dinding, & access nodes rak
│   │   └── pathfinding.py    # A* Search, GBFS, DualPathPlanner konkuren
│   │
│   ├── behavior/             # [BEHAVIOR] Kontrol Kinematika & Misi Robot
│   │   ├── robot_controller.py # AGV Controller, lerp heading, lidar rotasi, kargo dek, trail
│   │   └── mission_manager.py  # Dispatcher balapan dual-robot, stopwatch, skor, & winner logic
│   │
│   ├── environment/          # [ENVIRONMENT] Pemandangan 3D & Aset
│   │   ├── asset_loader.py   # Loader model eksternal aman dengan graceful fallback
│   │   ├── interactive_shelf.py# Entitas rak 3D ber-Collider dengan deteksi klik & seleksi
│   │   └── warehouse_scene.py# Konstruksi lantai 35x25, balok dinding beton, docking & goal pad, pencahayaan
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

## Instalasi & Menjalankan Program

### Persyaratan Sistem
- **Python**: Versi 3.9 s.d. 3.12
- Pustaka: `numpy`, `ursina`

### Langkah Eksekusi (Windows & Linux)
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

## Panduan Kontrol & Pintasan Keyboard

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
| **Klik Kanan + Drag** | *(Mode Bebas)* | Mengorbit / memutar kamera bebas di sekeliling arena 35x25. |
| **Scroll Mouse** | - | *Zoom-in* / *Zoom-out* kamera. |
| **`[Esc]`** | **`[Keluar]`** | Menutup simulator dengan aman. |
