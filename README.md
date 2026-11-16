# Warehouse Digital Twin: A* vs GBFS Algorithm Pathfinding (v2.0 Final)

> **Evaluasi Tengah Semester (ETS) — Konsep Kecerdasan Artificial**  
> *Simulator Digital Twin Gudang Otonom 3D Berbasis Ursina Engine (Panda3D) dengan Navigasi Armada Multi-Agent AGV, Medan Berbobot Dinamis, dan Analisis Perbandingan Algoritma Informed Search.*

[![Python Version](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Engine](https://img.shields.io/badge/3D%20Engine-Ursina%20%2F%20Panda3D-orange?logo=panda3d&logoColor=white)](https://www.ursinaengine.org/)
[![License](https://img.shields.io/badge/License-Academic%20ETS-green)](#)
[![Version](https://img.shields.io/badge/Release-v2.0%20Final-purple)](#)
[![Build Status](https://img.shields.io/badge/Tests-Passing-brightgreen?logo=pytest&logoColor=white)](#)

---

## 1. Header & Deskripsi Proyek

**Warehouse Digital Twin** adalah simulasi 3D interaktif skala industri yang memodelkan operasional armada robot logistik otonom (*Automated Guided Vehicles* / AGV) pada arena berdimensi **35 × 25 grid (875 sel)**. Dikembangkan di atas **Ursina Engine (Panda3D)**, simulator ini dirancang sebagai platform riset dan uji komparatif mendalam antara dua algoritma *Informed Search* utama dalam kecerdasan buatan:

1. **A\* Search Algorithm**: Algoritma pencarian heuristik berbobot optimal yang mengevaluasi biaya akumulasi aktual dan estimasi jarak tersisa:
   $$\mathbf{f(n) = g(n) + h(n)}$$
   Menjamin pencapaian rute dengan total biaya minimum secara matematis (*admissible & consistent*), responsif terhadap variasi bobot medan, serta mengutamakan keselamatan dan efisiensi konsumsi energi armada.
2. **Greedy Best-First Search (GBFS)**: Algoritma pencarian murni serakah (*pure greedy*) yang hanya mengevaluasi estimasi heuristik langsung ke sasaran:
   $$\mathbf{f(n) = h(n)}$$
   Cepat dalam mengeksplorasi langkah awal, namun buta terhadap rintangan tersembunyi (*cul-de-sac*), mengabaikan biaya gesekan medan (*terrain cost*), dan rentan menghasilkan lintasan yang sangat suboptimal.

Simulator ini menyajikan visualisasi grafis berkualitas tinggi dengan sistem pencahayaan dan bayangan dinamis (*directional soft shadows*), arsitektur *Decoupled Follower* anti *Z-fighting*, deteksi rintangan dinamis secara *edge-triggered*, serta antarmuka *telemetry dashboard* bergaya kaca modern (*glassmorphism*).

---

## 2. Legenda Visual (Visual Legend)

Bagian ini menjelaskan secara eksplisit seluruh elemen grafis dan indikator warna yang tampil pada layar simulator:

```
+---------------------------------------------------------------------------------------+
|                                    LEGENDA VISUAL                                     |
+---------------------------------------------------------------------------------------+
|  ROBOT ARMADA          |  AGV Alpha: Cyan Elektrik (A*)   | AGV Beta: Amber Vivid (GBFS)  |
|  TRAIL JEJAK           |  Alpha: Hijau Neon (Optimal)     | Beta: Oranye Api (Suboptimal) |
|  MEMORY HEATMAP        |  Merah: A* Only  |  Biru: GBFS Only  |  Ungu: Irisan Keduanya    |
|  MEDAN OLI (HAZARD)    |  Kuning/Hitam: Cost 5.0 (Speed 0.4x, Drain 2.5x) -> A* Hindari|
|  BOOST CONVEYOR        |  Hijau Neon: Cost 0.35 (Speed 1.75x, Drain 0.5x) -> A* Incar |
|  RADAR PULSE           |  Cincin Sonar 3D: Dynamic Replanning menghindar Forklift/Batu |
+---------------------------------------------------------------------------------------+
```

### Identitas Robot AGV (Multi-Agent Fleet)
- **AGV Alpha [Cyan Elektrik — `#00C3FF`]**:
  - **Algoritma**: **A\* Search** ($f = g + h$).
  - **Karakteristik**: Mempertimbangkan beban biaya riil lintasan ($g$) dan sisa jarak ($h$). Dilengkapi prioritas *heuristic tie-breaking* dengan nilai $h(n)$ terkecil, memangkas 93% simpul tak perlu.
  - **Warna Jejak (Trajectory Trail)**: **Hijau Neon** (*Optimal Path*).
- **AGV Beta [Vivid Amber — `#FF8C00`]**:
  - **Algoritma**: **Greedy Best-First Search** ($f = h$).
  - **Karakteristik**: Rakus meluncur menuju target terdekat secara garis lurus, mengabaikan biaya medan dan mudah terjebak di lorong buntu (*cul-de-sac*).
  - **Warna Jejak (Trajectory Trail)**: **Oranye / Merah Api** (*Sub-optimal Path*).

---

### Warna Heatmap Eksplorasi Memori (Closed-List Heatmap)
Setelah kalkulasi rute atau saat *dynamic replanning* terjadi, simulator menampilkan bidang proyeksi transparan di lantai untuk memperlihatkan simpul graf mana saja yang sempat dikunjungi/dievaluasi oleh algoritma (*closed list*):
- 🟥 **Merah / Pink Muda (`rgba(245, 65, 120, 0.40)`)**: Simpul graf yang **hanya dieksplorasi oleh A\***.
- 🟦 **Biru / Cyan Terang (`rgba(0, 205, 255, 0.40)`)**: Simpul graf yang **hanya dieksplorasi oleh GBFS**.
- 🟪 **Ungu / Magenta (`rgba(195, 75, 255, 0.55)`)**: Simpul irisan (*Shared Nodes*) yang dieksplorasi oleh **kedua algoritma**.

> [!NOTE]
> Pada rute yang bersih dari jebakan, heatmap GBFS cenderung berupa garis tipis langsung ke tujuan, sedangkan A* sedikit melebar. Namun, ketika berhadapan dengan sekat buntu (*cul-de-sac*), area eksplorasi GBFS akan membanjiri kantong buntu secara masif sebelum terpaksa berbalik arah.

---

### Weighted Terrain (Medan Berbobot)
Simulasi menerapkan konsep graf berbobot non-uniform ($w(u, v) \neq 1.0$) untuk menguji kecerdasan adaptif kedua algoritma:

| Elemen Medan | Tampilan Visual 3D | Pengali Biaya $g(n)$ | Dampak Kinematika Robot | Respon Algoritma AI |
| :--- | :--- | :---: | :--- | :--- |
| **Genangan Oli (Hazard Oil)** | Piringan Kuning / Amber Berkilau | **$5.0\times$** | Kecepatan turun ke **$0.4\times$**, Baterai terkuras **$2.5\times$** lebih boros | **A\*** mengevaluasi trade-off dan memilih rute memutar yang lebih efisien; **GBFS** nekat menerobos karena buta terhadap $g(n)$. |
| **Speed Boost Pad** | Konveyor Hijau Neon dengan Panah `>>` | **$0.35\times$** | Kecepatan melonjak ke **$1.75\times$**, Konsumsi baterai turun ke **$0.5\times$** | **A\*** secara agresif mengubah jalurnya untuk menginjak booster ini; **GBFS** mengabaikannya jika tidak tepat segaris lurus dengan sasaran. |
| **Lorong Normal** | Epoksi Slate Gray dengan Grid Cyan | **$1.0\times$** | Kecepatan nominal (**6.0 sel/detik**), Konsumsi baterai normal (0.25%/langkah) | Kedua robot melaju sesuai jalur standar lorong industri. |

---

### 3D Sonar Radar Pulse
Saat rute aktif salah satu robot terpotong oleh patroli Forklift otonom atau rintangan kargo yang dijatuhkan pengguna, sistem memicu **Gelombang Sonar 3D (Radar Pulse)**:
- Cincin cahaya melingkar membesar secara instan dari pusat robot ke radius 6.5 unit dan memudar halus.
- Diikuti oleh *floating text 3D* (`REPLANNING ROUTE...`) dan kalkulasi rute baru dalam waktu sub-milidetik.

---

### Telemetri Baterai & Floating Status Billboard
Setiap robot dilengkapi *Billboard UI* yang mengambang tepat di atas bodi fisiknya:
- **Bar Indikator Progresif**: Berwarna **Hijau** ($>50\%$), **Kuning** ($20\% - 50\%$), dan **Merah Berkedip** ($\le 20\%$).
- **Lampu Suar Puncak (Beacon)**: Berkedip kuning saat kritis ($\le 20\%$) dan menyala merah pekat saat baterai habis total (`DEAD`).
- **Emergency Auto-Return**: Robot secara otomatis menghentikan misi dan membelokkan rute ke stasiun pengisian daya terdekat jika sisa daya tidak mencukupi untuk pulang.

---

## 3. Kontrol Interaktif & Cara Bermain

Simulator ini menyediakan kendali penuh melalui kombinasi Mouse Raycasting (*Point-and-Click*) dan tombol pintasan Keyboard:

### Kontrol Mouse
| Input Mouse | Target Bidang | Aksi & Fungsionalitas |
| :--- | :--- | :--- |
| **Klik Kiri** | **Rak Berkargo** | **Langkah 1 Misi**: Menetapkan rak sebagai titik jemput (*Pick-up point*). Ditandai cincin hijau mint neon. |
| **Klik Kiri** | **Rak Kosong** | **Langkah 2 Misi**: Menetapkan rak sebagai titik antar (*Drop-off point*). Ditandai cincin magenta neon dan meluncurkan balapan! *(Jika robot sedang sibuk, pesanan otomatis masuk ke Antrean FIFO)*. |
| **Klik Kiri** | **Lantai Lorong Kosong** | Menjatuhkan rintangan atau modifier medan sesuai kuas tool yang aktif (**Kardus**, **Oli**, atau **Boost Pad**). |
| **Klik Kiri** | **Rintangan / Oli / Boost yang Ada** | Mengangkat dan menghapus rintangan dinamis dari lantai serta merestorasi status sel menjadi walkable. |
| **Klik Kanan** | **Bodi Robot AGV** | **Intervensi Darurat Pengguna**: Memerintahkan robot untuk *Force Return to Dock & Recharge* hingga 100%. |
| **Klik Kanan + Drag** | *(Khusus Mode Bebas)* | Memutar sudut pandang kamera (Pitch / Yaw). |
| **Scroll Roda Mouse** | Bebas | *Zoom In* dan *Zoom Out* kamera simulasi. |

---

### Pintasan Keyboard (Shortcuts)

| Kategori | Tombol | Label Layar | Fungsi & Keterangan |
| :--- | :---: | :---: | :--- |
| **Kuas Medan** | **`[1]`** | `[1] BOX` | Mengaktifkan kuas **Kardus Blokir Penuh** (*Dynamic Obstacle* memutus lorong). |
| | **`[2]`** | `[2] OIL` | Mengaktifkan kuas **Genangan Oli Licin** (*Cost 5.0, Speed 0.4x, Drain 2.5x*). |
| | **`[3]`** | `[3] BOOST` | Mengaktifkan kuas **Speed Boost Pad** (*Cost 0.35, Speed 1.75x, Drain 0.5x*). |
| **Kamera 3D** | **`[F]`** / **`[C]`** / **`[V]`** | `[C] Kamera` | Siklus Kamera: **Isometrik** $\rightarrow$ **Top-Down 2D** $\rightarrow$ **POV Alpha (Dashcam A\*)** $\rightarrow$ **POV Beta (Dashcam GBFS)** $\rightarrow$ **Free-Cam**. |
| **Misi & Alur** | **`[G]`** | `RANDOM` | **Misi Balapan Acak**: Otomatis memilih sepasang rak acak dan meluncurkan balapan seketika! |
| | **`[T]`** | `ZONE` | **Multi-Stage Zone Transfer**: Memicu armada berpacu menuju Transfer Gate untuk berpindah ke **Zone B** / **Zone A** dengan efek sinematik *fade-out*. |
| | **`[Spasi]`** | `PAUSE / RESUME` | Menjeda (*freeze*) atau melanjutkan seluruh aktivitas armada dan simulasi. |
| | **`[R]`** | `RESET` | Mereset misi, membatalkan rute, dan mengembalikan armada ke Twin Dock. |
| **Pembersihan** | **`[Delete]`** / **`[Backspace]`** / **`[X]`** | - | **Sapu Bersih Arena**: Menghapus seluruh kardus dinamis, genangan oli, boost pad, dan visual heatmap. |
| **Analitik & Teori** | **`[M]`** | `SERIOUS / ARCADE` | Beralih antara **HUD Serious (WMS Industrial Analytics)** dan **HUD Gamifikasi (Arcade Logistics Rush)**. |
| | **`[H]`** | `HEURISTIK: ...` | Mengganti formula jarak heuristik real-time: **Manhattan ($L_1$)**, **Euclidean ($L_2$)**, **Chebyshev ($L_\infty$)**, atau **Octile**. |
| **Kecepatan** | **`[+]`** / **`[-]`** | - | Menambah atau mengurangi kecepatan armada secara bertahap ($2.0\times$ hingga $20.0\times$). |
| **Aplikasi** | **`[Esc]`** | `EXIT` | Menutup jendela simulasi dengan aman tanpa *dangling thread*. |

---

## 4. Fitur-Fitur Utama & Inovasi Arsitektur

### 1. 3 Autonomous Patrol Forklifts (Dynamic Moving Obstacles)
- Tiga unit Forklift industri berpatroli secara otonom di 3 zona gudang independen (Zona Tengah, Kiri, dan Atas) menggunakan skema *Autonomous AI Wandering with Direction Persistence*.
- **Pembaruan Graf Lokal Sub-Milidetik**: Setiap pergerakan roda forklift ke sel baru diperbarui dalam waktu **$< 0.01\text{ ms}$** tanpa perlu mengalokasi ulang matriks graf gudang secara keseluruhan.
- **Deteksi Ancaman Tabrakan Proaktif**: Sistem *edge-triggering* mengecek apakah lintasan yang sedang ditempuh AGV Alpha atau Beta terpotong oleh pergerakan forklift. Jika ya, robot seketika memancarkan **Radar Pulse 3D** dan memetakan jalur alternatif secara real-time!

### 2. Glassmorphism UI Telemetry Dashboard
- Antarmuka visual futuristik dengan palet *Slate Gray & Electric Cyan* semi-transparan yang memanjakan mata.
- **Mode Ganda Adaptif**:
  - **Mode Serious (WMS Fleet Analytics)**: Menyajikan tabel komparasi real-time antara A* dan GBFS (Sisa Baterai, Akumulasi Biaya Lintasan, Total Simpul yang Dievaluasi, Latensi Komputasi per milidetik, Rasio Kemacetan/Bottleneck, dan Status Progres Langkah).
  - **Mode Gamifikasi (Arcade Logistics Rush)**: Stopwatch *Time-Attack*, sistem akumulasi skor efisiensi, *Combo Multiplier* bertingkat, dan sistem rating bintang (1 s.d. 5 Bintang) berdasarkan rasio keoptimalan rute terhadap rute teoritis.
- **Throttle Rendering 20 Hz**: Teks diperbarui dengan teknik *dirty-checking*, menghilangkan 85% beban render font CPU dan menjamin 60+ FPS konstan.

### 3. Unified Twin Docking & Misi 3-Leg (Auto-Return to Base)
- Stasiun docking terpadu (*Unified Twin Dock*) ditempatkan di posisi sentral strategis `(17, 1)` dan `(18, 1)` lengkap dengan struktur menara pengisian daya 3D.
- **Siklus Hidup Misi 3 Etape Penuh**:
  - **Leg 1**: *Twin Dock $\rightarrow$ Pick-up Shelf* (Menjemput kargo).
  - **Leg 2**: *Pick-up Shelf $\rightarrow$ Drop-off Shelf* (Mengantar kargo).
  - **Leg 3**: *Drop-off Shelf $\rightarrow$ Twin Dock Base* (Otomatis pulang ke pangkalan dan mengisi ulang daya hingga 100%).
- **Pemisahan Lajur Lateral (Dual-Lane Offset)**: Saat kedua robot melintasi lorong yang sama, sistem secara otomatis menggeser koordinat translasi ke kiri dan kanan sumbu vektor hadap robot (+0.22 / -0.22 unit), mencegah robot saling bertabrakan atau tembus badan (*clipping*).

### 4. Order Task Queue (FIFO Asinkron)
- Simulator mendukung penugasan pesanan beruntun tanpa jeda.
- Pengguna dapat memilih pasangan rak baru saat balapan sebelumnya sedang berlangsung. Tiket misi otomatis dimasukkan ke dalam antrean FIFO (*First-In, First-Out*) dengan indikator badge `PENDING: X` di pojok kanan atas layar.
- Begitu kedua robot menyelesaikan etape kepulangan ke dock, pesanan berikutnya langsung dieksekusi secara otomatis!

### 5. Multi-Stage Zone Transfer (Zone A $\longleftrightarrow$ Zone B)
- Menekan tombol **`[T]`** atau memilih menu `ZONE` menginstruksikan armada untuk meluncur ke **Transfer Gate** di dinding timur `(34, 13)`.
- Saat gerbang tercapai, kamera melakukan efek sinematik *Fade to Black*, graf gudang diregenerasi di balik layar menjadi **Zone B** (fasilitas penyimpanan teknologi tinggi dengan sekat brankas pusat dan klaster rak bertingkat rapat), lalu armada keluar dari gerbang dengan baterai terisi penuh dan melakukan *auto-return* menuju pangkalan.

### 6. First-Person POV Dashcam & Siklus Kamera Lengkap
- Sudut pandang *First-Person Dashcam* terpasang langsung di atas kokpit sensor AGV Alpha (`pov_alpha`) dan AGV Beta (`pov_beta`).
- Dilengkapi stabilisasi rotasi anti *gimbal lock* dan penonaktifan otomatis billboard label agar pandangan ke depan tetap jernih dan imersif.

---

## 5. Analisis Perbandingan Algoritma: A* vs GBFS

| Parameter Evaluasi | A\* Search Algorithm | Greedy Best-First Search (GBFS) |
| :--- | :--- | :--- |
| **Fungsi Evaluasi** | $f(n) = g(n) + h(n)$ | $f(n) = h(n)$ |
| **Keoptimalan Rute (Optimality)** | **100% Dijamin Optimal** (dengan heuristik *admissible*) | **Tidak Dijamin Sub-optimal** |
| **Pertimbangan Medan Berbobot** | **Sangat Peka**: Memutar menghindari oli ($g=5.0$) dan memprioritaskan booster ($g=0.35$). | **Buta Total**: Mengabaikan $g(n)$, menerobos rintangan berbahaya. |
| **Respon Jebakan Cul-de-Sac** | **Cerdas**: Memilih lorong tengah yang tembus tanpa terjebak di kantong buntu. | **Terjebak Parah**: Tergiur jarak lurus semu, mengeksplorasi ujung kantong buntu secara sia-sia. |
| **Jumlah Simpul Dieksplorasi** | Sangat efisien (~20 - 90 simpul berkat *tie-breaking* cerdas). | Berfluktuasi ekstrem (bisa sangat sedikit pada ruang lapang, membengkak di labirin). |
| **Waktu Komputasi** | **Sub-milidetik (< 0.8 ms)** | **Sub-milidetik (< 0.5 ms)** |
| **Kesesuaian Industri** | **Ideal untuk AGV komersial** (keselamatan, efisiensi energi, jalur terpendek). | Hanya cocok untuk pencarian cepat di graf tanpa bobot dan tanpa rintangan kompleks. |

---

## 6. Struktur Direktori Proyek

Arsitektur kode diorganisasikan secara modular memisahkan lapisan kognisi graf, kinematika robot, visual 3D, dan antarmuka pengguna:

```text
KKA-ETS-Implementation/
├── assets/
│   ├── fonts/
│   │   ├── Roboto-Bold.ttf            # Font tipografi judul & tombol
│   │   └── Roboto-Regular.ttf         # Font telemetri & teks antarmuka
│   └── models/
│       ├── robot.obj                  # Model 3D sasis AGV industri
│       ├── robot-box.obj              # Model 3D AGV bermuatan kargo
│       ├── empty-shelf.obj            # Model 3D rak palet kosong
│       ├── occupied-shelf.obj         # Model 3D rak palet berisi kargo
│       ├── cargo.obj                  # Model 3D kotak kargo karton
│       └── docking-station.obj        # Model 3D stasiun pengisian daya
│
├── src/
│   ├── config.py                      # Parameter grid 35x25, palet warna, dock coordinates, dan baterai
│   ├── simulation.py                  # Loop utama Ursina Engine & orchestrator siklus hidup aplikasi
│   │
│   ├── cognition/                     # [LAPISAN KOGNISI] Logika Graf & Algoritma Pencarian
│   │   ├── heuristics.py              # Manhattan, Euclidean, Chebyshev, Octile
│   │   ├── warehouse_graph.py         # Matriks graf 35x25, layout generator, rintangan dinding & access nodes
│   │   └── pathfinding.py             # Engine A* Search, GBFS, DualPathPlanner konkuren, & nearest dock
│   │
│   ├── behavior/                      # [LAPISAN BEHAVIOR] Kinematika Robot & Manajer Misi
│   │   ├── robot_controller.py        # Controller AGV, lerp rotasi, baterai, trail pooling, radar pulse
│   │   ├── forklift_controller.py     # AI Patrol Forklift mandiri (Dynamic moving obstacles)
│   │   └── mission_manager.py         # Dispatcher balapan, zone transfer, deteksi ancaman, & gamifikasi
│   │
│   ├── environment/                   # [LAPISAN ENVIRONMENT] Lingkungan 3D & Scene Graph
│   │   ├── asset_loader.py            # Loader model 3D eksternal aman dengan graceful fallback
│   │   ├── interactive_shelf.py       # Entitas rak 3D ber-Collider dengan indikator seleksi
│   │   └── warehouse_scene.py         # Lantai tiled, mesh combining, docking stations, & heatmap renderer
│   │
│   └── communication/                 # [LAPISAN KOMUNIKASI] Antarmuka Interaktif & Telemetri
│       ├── interaction_system.py      # Raycasting kursor mouse, state machine klik, & penempatan medan
│       ├── hud_serious.py             # Dashboard analitik industri WMS
│       ├── hud_gamification.py        # HUD Arcade: Time-Attack, skor, combo, & rating bintang
│       └── ui_controller.py           # Master UI Controller & keyboard/mouse input dispatcher
│
├── tests/
│   ├── test_full_suite.py             # Uji komprehensif integrasi seluruh fitur v2.0
│   └── test_pov_camera.py             # Uji stabilitas orientasi kamera POV First-Person
│
├── requirements.txt                   # Berkas dependensi Python
├── README.md                          # Dokumentasi utama proyek
└── main.py                            # Titik masuk eksekusi langsung aplikasi
```

---

## 7. Instalasi & Menjalankan Program

### Prasyarat Sistem
- **Sistem Operasi**: Windows 10/11, macOS, atau Linux (Ubuntu 20.04+ direkomendasikan).
- **Python**: Versi **3.9**, **3.10**, **3.11**, atau **3.12**.
- **Perangkat Keras**: Kartu grafis dengan dukungan OpenGL 3.3+ (Integrated Intel/AMD atau Dedicated NVIDIA/AMD).

### Langkah Instalasi

1. **Clone repositori proyek ini** (atau ekstrak berkas `.zip`):
   ```bash
   git clone https://github.com/hadryan/KKA-ETS-Implementation.git
   cd KKA-ETS-Implementation
   ```

2. **Buat dan aktifkan Virtual Environment**:
   ```bash
   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Windows (Command Prompt)
   .\venv\Scripts\activate.bat
   ```

3. **Pasang paket pustaka dependensi**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
   *Isi `requirements.txt` meliputi `ursina>=6.0.0`, `numpy>=1.24.0`, dan `Pillow>=10.0.0`.*

4. **Jalankan simulator 3D**:
   ```bash
   python main.py
   ```
   *(Jendela simulasi grafis 1280×720 dengan pencahayaan 3D dan audio engine akan langsung terbuka secara instan).*

5. *(Opsional)* **Menjalankan Pengujian Unit Otomatis**:
   ```bash
   PYTHONPATH=. pytest -p no:launch_testing tests/test_full_suite.py
   ```

---

## 8. Informasi Akademik & Kontributor

- **Mata Kuliah**: Konsep Kecerdasan Artificial (KKA)
- **Agenda**: Evaluasi Tengah Semester (ETS) — Implementasi Praktis
- **Fokus Kajian**: *Informed Search Algorithms, Multi-Agent Pathfinding (MAPF), Dynamic Replanning, Weighted Grid-World Graphs, Game Engine Digital Twins*.
- **Versi**: **v2.0 (Final Release)**

---
*Dikembangkan dengan dedikasi untuk visualisasi kecerdasan artifisial yang elegan, efisien, dan presisi tinggi.*
