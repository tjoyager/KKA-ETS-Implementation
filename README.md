# Warehouse Digital Twin: A* vs GBFS Algorithm Pathfinding (v3.0.0 Final)

> **Evaluasi Tengah Semester (ETS) — Konsep Kecerdasan Artificial**  
> *Simulator Digital Twin Gudang Otonom 3D Berbasis Ursina Engine (Panda3D) dengan Navigasi Armada Multi-Agent AGV, Medan Berbobot Dinamis, Sistem Manajemen Baterai & Hitbox, serta Analisis Perbandingan Algoritma Informed Search.*

[![Python Version](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Engine](https://img.shields.io/badge/3D%20Engine-Ursina%20%2F%20Panda3D-orange?logo=panda3d&logoColor=white)](https://www.ursinaengine.org/)
[![Institution](https://img.shields.io/badge/ITS-Teknik%20Informatika-0078C1)](#)
[![Version](https://img.shields.io/badge/Release-v3.0.0%20Final-purple)](#)
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

Simulator ini menyajikan visualisasi grafis 3D dengan pencahayaan dan bayangan dinamis (*directional soft shadows*), deteksi tabrakan berbasis *hitbox*, pengalihan rute otomatis ke *charging station* saat daya menipis, serta antarmuka *telemetry & legend dashboard* modular yang bebas tumpang tindih.

---

## 2. Legenda Visual & Tata Letak UI

Bagian ini menjelaskan seluruh elemen grafis, indikator warna pada panel **Legenda gudang**, serta susunan panel antarmuka pada layar simulator:

```
+----------------------------------------------------------------------------------------+
|                                    LEGENDA GUDANG                                      |
+----------------------------------------------------------------------------------------+
|  KENDARAAN             |  Alpha · A*: Cyan (Jejak hijau) | Beta · GBFS: Amber (Merah)   |
|                        |  Forklift: Rintangan bergerak otonom                          |
|  MEDAN & RINTANGAN     |  Kardus [1]: Menutup jalur      | Oli [2]: Cost 5.0 (Lambat)  |
|                        |  Boost [3]: Cost 0.35 (Cepat)                                 |
|  LOKASI                |  Charger: Isi daya              | Rak: Simpan kargo           |
|                        |  Rak jemput: Ambil kargo        | Rak antar: Taruh kargo      |
|                        |  Goal station: Titik tujuan     | Gerbang: Pindah zone        |
|  PETAK DIEKSPLORASI    |  Merah: A* Only  |  Biru: GBFS Only  |  Ungu: Keduanya       |
+----------------------------------------------------------------------------------------+
```

### Struktur Tata Letak Antarmuka (HUD Layout)
- **Top Command Bar**: Menampilkan identitas simulasi (`WAREHOUSE / Command`), status zona & *timer* aktif, serta indikator antrean misi (`Queue 0`).
- **Panel Kiri Atas (`RACE TELEMETRY`)**: Menyajikan tabel perbandingan metrik *real-time* antara AGV **Alpha** dan **Beta** (*Battery*, *Route cost*, *Nodes*, *Search time*, *Path progress*, *Mission*, *Traffic*, dan *Robot speed*).
- **Panel Kiri Bawah (`Legenda gudang`)**: Panel referensi visual berikon khusus yang terpisah dari panel kontrol sehingga proporsional dan mudah dibaca. Dapat disembunyikan atau dimunculkan kapan saja via tombol **`Tutup [L]` / `Legenda [L]`**.
- **Panel Kanan (`Operations`)**: Terorganisasi dalam 3 bagian terstruktur (`01 / DISPATCH`, `02 / ENVIRONMENT`, `03 / WORKSPACE`) dan dapat dilipat via tombol **`Hide [P]` / `Show [P]`**.
- **Bottom Control Bar & Audio**: Baris kendali cepat di bagian bawah untuk mode tampilan, heuristik, kontrol pemutaran, kamera, kecepatan simulasi, serta pengaturan suara (`[F8]` / `[F9]`).

### Identitas Robot AGV (Multi-Agent Fleet)
- **AGV Alpha [Cyan Elektrik — `#00C3FF`]**:
  - **Algoritma**: **A\* Search** ($f = g + h$).
  - **Karakteristik**: Mempertimbangkan beban biaya riil lintasan ($g$) dan sisa jarak ($h$). Dilengkapi prioritas *heuristic tie-breaking* dengan nilai $h(n)$ terkecil untuk memangkas simpul tak perlu.
  - **Warna Jejak (Trajectory Trail)**: **Jejak hijau** (*Optimal Path*).
- **AGV Beta [Vivid Amber — `#FF8C00`]**:
  - **Algoritma**: **Greedy Best-First Search** ($f = h$).
  - **Karakteristik**: Meluncur menuju target terdekat secara garis lurus, mengabaikan biaya medan, dan rentan terjebak di lorong buntu (*cul-de-sac*).
  - **Warna Jejak (Trajectory Trail)**: **Jejak merah** (*Sub-optimal Path*).

### Heatmap Eksplorasi Memori (Closed-List Heatmap)
Setelah kalkulasi rute atau saat *dynamic replanning* terjadi, simulator menampilkan proyeksi transparan di lantai untuk memperlihatkan simpul graf yang dievaluasi oleh masing-masing algoritma:
- 🟥 **Merah (`rgba(245, 65, 120, 0.40)`)**: Petak yang **hanya dieksplorasi oleh A\***.
- 🟦 **Biru (`rgba(0, 205, 255, 0.40)`)**: Petak yang **hanya dieksplorasi oleh GBFS**.
- 🟪 **Ungu (`rgba(195, 75, 255, 0.55)`)**: Petak irisan (*Shared Nodes*) yang dieksplorasi oleh **keduanya**.

### Weighted Terrain (Medan Berbobot)

| Elemen Medan | Tampilan Visual 3D | Pengali Biaya $g(n)$ | Dampak Kinematika Robot | Respon Algoritma AI |
| :--- | :--- | :---: | :--- | :--- |
| **Genangan Oli (`Oil spill [2]`)** | Piringan Kuning / Amber Berkilau | **$5.0\times$** | Kecepatan turun ke **$0.4\times$**, Baterai terkuras **$2.5\times$** lebih boros | **A\*** menghitung *trade-off* dan memutar menghindari oli; **GBFS** nekat menerobos karena mengabaikan $g(n)$. |
| **Speed Boost (`Speed boost [3]`)** | Konveyor Hijau Neon dengan Panah `>>` | **$0.35\times$** | Kecepatan melonjak ke **$1.75\times$**, Konsumsi baterai turun ke **$0.5\times$** | **A\*** mengarahkan lintasan melewati *booster*; **GBFS** mengabaikannya jika tidak segaris lurus dengan target. |
| **Lorong Normal** | Epoksi Slate Gray dengan Grid | **$1.0\times$** | Kecepatan nominal (**6.0 sel/detik**), Konsumsi baterai normal (0.25%/langkah) | Kedua robot melaju sesuai jalur standar lorong industri. |

---

## 3. Kontrol Interaktif & Cara Bermain

### Kontrol Mouse
| Input Mouse | Target Bidang | Aksi & Fungsionalitas |
| :--- | :--- | :--- |
| **Klik Kiri** | **Rak Berkargo** | **Langkah 1 Misi**: Menetapkan rak sebagai titik jemput (*Rak jemput*). Ditandai cincin hijau mint neon. |
| **Klik Kiri** | **Rak Kosong** | **Langkah 2 Misi**: Menetapkan rak sebagai titik antar (*Rak antar*). Ditandai cincin magenta neon dan memulai simulasi *(jika robot sedang sibuk, pesanan masuk ke `Queue`)*. |
| **Klik Kiri** | **Lantai Lorong Kosong** | Menempatkan rintangan atau modifier medan sesuai tool aktif (**Cargo block**, **Oil spill**, atau **Speed boost**). |
| **Klik Kiri** | **Rintangan / Oli / Boost yang Ada** | Mengangkat dan menghapus rintangan dinamis dari lantai serta memulihkan status sel menjadi *walkable*. |
| **Klik Kanan** | **Bodi Robot AGV** | **Intervensi Darurat**: Memerintahkan robot untuk kembali ke *dock* dan mengisi ulang daya hingga 100%. |
| **Klik Kanan + Drag** | *(Khusus Free Camera)* | Memutar sudut pandang kamera (*Pitch* / *Yaw*). |
| **Scroll Roda Mouse** | Bebas | *Zoom In* dan *Zoom Out* tampilan arena 3D. |

### Pintasan Keyboard (Shortcuts)

| Kategori | Tombol | Label UI | Fungsi & Keterangan |
| :--- | :---: | :---: | :--- |
| **01 / Dispatch** | **`[G]`** | `Random race [G]` | Memilih sepasang rak acak dan langsung memulai balapan AGV Alpha vs Beta. |
| | **`[T]`** | `Transfer zone [T]` | Menginstruksikan armada menuju **Gerbang** untuk berpindah antara **Zone A** dan **Zone B**. |
| **02 / Environment** | **`[1]`** | `Cargo block [1]` | Memilih kuas **Kardus Blokir Penuh** untuk menutup jalur lorong. |
| | **`[2]`** | `Oil spill [2]` | Memilih kuas **Genangan Oli** (*Cost 5.0, memperlambat gerak & menguras baterai*). |
| | **`[3]`** | `Speed boost [3]` | Memilih kuas **Speed Boost** (*Cost 0.35, mempercepat gerak & menghemat baterai*). |
| **03 / Workspace** | **`[B]`** | `Free camera [B]` | Mengaktifkan mode **Free Camera** untuk navigasi sudut pandang bebas 3D. |
| | **`[J]`** | `View analysis [J]` | Menampilkan ringkasan analisis komparatif hasil pencarian dan efisiensi rute. |
| | **`[X]`** / **`[Del]`** | `Clear terrain [X]` | Menghapus seluruh rintangan kardus, oli, *boost pad*, dan visual *heatmap* dari arena. |
| **Tampilan HUD** | **`[L]`** | `Legenda [L]` / `Tutup [L]` | Menampilkan atau menyembunyikan panel **Legenda gudang** di kiri bawah. |
| | **`[P]`** | `Hide [P]` / `Show [P]` | Menampilkan atau menyembunyikan panel **Operations** di sisi kanan. |
| | **`[M]`** | `Serious [M]` | Beralih antara mode **Serious (WMS Telemetry)** dan **Arcade (Gamification)**. |
| **Simulasi & Kamera** | **`[H]`** | `Manhattan [H]` | Mengganti formula heuristik secara *real-time*: **Manhattan ($L_1$)**, **Euclidean ($L_2$)**, **Chebyshev ($L_\infty$)**, atau **Octile**. |
| | **`[C]`** / **`[F]`** / **`[V]`** | `Top-down [C]` | Beralih ke tampilan **Top-Down 2D** serta siklus kamera (**Isometrik**, **POV Alpha**, **POV Beta**). |
| | **`[Spasi]`** | `Pause [Space]` | Menjeda (*pause*) atau melanjutkan jalannya simulasi. |
| | **`[R]`** | `Reset [R]` | Mereset misi aktif dan mengembalikan armada ke stasiun *docking*. |
| | **`[+]`** / **`[-]`** | `SPEED` | Menaikkan atau menurunkan kecepatan pergerakan simulasi. |
| **Audio & Sistem** | **`[F8]`** | `Sound 70% [F8]` | Mengatur tingkat volume efek suara simulasi. |
| | **`[F9]`** | `Test sound [F9]` | Menguji output audio sistem simulasi. |
| | **`[Esc]`** | `Exit` | Menutup jendela aplikasi dengan aman. |

---

## 4. Fitur Utama & Pembaruan Revisi Final (v3.0.0)

1. **Smart Auto-Charging Routing**
   - Saat level baterai AGV menipis di tengah operasional, robot secara otomatis menghitung dan mengalihkan lintasan menuju **Charging Station** terdekat untuk melakukan pengisian daya terlebih dahulu sebelum melanjutkan perjalanan kembali ke titik *docking* dan menuntaskan misi.
2. **Multi-Agent Mission Completion Sync (Anti-Freeze < 20%)**
   - Memperbaiki sinkronisasi status penyelesaian misi antar-robot: misi tidak lagi ditandai selesai secara prematur apabila satu robot telah tiba di *docking* sementara robot lainnya masih berada di lapangan dengan kondisi baterai kritis ($< 20\%$), sehingga mencegah robot kedua mengalami *freeze*.
3. **Collision & Hitbox System**
   - Implementasi fungsi *hitbox* serta penanganan deteksi tabrakan (*collision*) secara presisi saat robot AGV berinteraksi atau bertabrakan dengan unit *forklift* maupun rintangan *box* di area gudang.
4. **Non-Overlapping Modular HUD & Propositional Legend**
   - Pemisahan tata letak antara panel **Operations** (kanan) dan **Legenda gudang** (kiri bawah) menggunakan *root container* berskala 1:1 (*aspect-ratio safe*) dengan aset ikon khusus sehingga bebas tumpang tindih (*overlap*) maupun distorsi proporsi.
5. **3 Autonomous Patrol Forklifts & Dynamic Replanning**
   - Tiga unit *forklift* berpatroli secara otonom di tiga zona gudang dengan pembaruan graf lokal sub-milidetik ($< 0.01\text{ ms}$) dan pemicu gelombang **Sonar Radar Pulse 3D** saat AGV melakukan kalkulasi ulang rute (*replanning*).
6. **Unified Twin Docking, FIFO Queue & Multi-Stage Zone Transfer**
   - Mendukung siklus misi 3 etape (*Dock $\rightarrow$ Pick-up $\rightarrow$ Drop-off $\rightarrow$ Dock*), antrean tugas beruntun (`Queue`), serta perpindahan lintas zona (**Zone A $\longleftrightarrow$ Zone B**) melalui **Transfer Gate**.

---

## 5. Analisis Perbandingan Algoritma: A* vs GBFS

| Parameter Evaluasi | A\* Search Algorithm | Greedy Best-First Search (GBFS) |
| :--- | :--- | :--- |
| **Fungsi Evaluasi** | $f(n) = g(n) + h(n)$ | $f(n) = h(n)$ |
| **Keoptimalan Rute (Optimality)** | **100% Dijamin Optimal** (dengan heuristik *admissible*) | **Tidak Dijamin (Sub-optimal)** |
| **Pertimbangan Medan Berbobot** | **Sangat Peka**: Menghindari oli ($g=5.0$) dan memanfaatkan booster ($g=0.35$). | **Buta Total**: Mengabaikan $g(n)$ dan menerobos rintangan berbiaya tinggi. |
| **Respon Jebakan Cul-de-Sac** | **Adaptif**: Memilih jalur tembus tanpa terjebak di lorong buntu. | **Rentan Terjebak**: Tergiur jarak lurus semu dan mengeksplorasi kantong buntu. |
| **Jumlah Simpul Dieksplorasi** | Efisien dan terkendali berkat *heuristic tie-breaking*. | Fluktuatif (sangat sedikit di ruang terbuka, membengkak pada labirin). |
| **Waktu Komputasi** | **Sub-milidetik (< 0.8 ms)** | **Sub-milidetik (< 0.5 ms)** |
| **Kesesuaian Industri** | **Ideal untuk armada AGV komersial** (efisiensi energi & rute terpendek). | Cocok hanya untuk pencarian cepat pada graf tanpa bobot sederhana. |

---

## 6. Struktur Direktori Proyek

## 6. Struktur Direktori Proyek

```text
KKA-ETS-Implementation/
├── assets/
│   ├── fonts/
│   │   ├── Roboto-Bold.ttf                   # Font tipografi judul & tombol
│   │   └── Roboto-Regular.ttf                # Font telemetri & teks antarmuka
│   ├── models/
│   │   ├── docking-station.obj               # Model 3D stasiun pengisian daya
│   │   ├── emergency-panel-kit.obj           # Model 3D kotak panel listrik dan APAR
│   │   ├── empty-shelf.obj                   # Model 3D rak palet kosong
│   │   ├── forklift.obj                      # Model 3D kendaraan angkut forklift
│   │   ├── occupied-shelf.obj                # Model 3D rak palet berisi kargo
│   │   ├── robot.obj                         # Model 3D sasis AGV industri
│   │   ├── robot-box.obj                     # Model 3D AGV bermuatan kargo
│   │   ├── warehouse-barrier.obj             # Model 3D pagar pembatas antar ruang
│   │   └── warehouse-cabinet.obj             # Model 3D lemari penyimpanan modular gudang
│   └── ui/
│       └── icons/                            # 12 ikon khusus panel Legenda gudang
│           ├── alpha.png, beta.png, forklift.png
│           ├── kardus.png, oli.png, boost.png
│           └── charger.png, rak.png, rak_jemput.png, rak_antar.png, goal.png, gerbang.png
│
├── src/
│   ├── config.py                             # Parameter grid 35x25, palet warna, dock & baterai
│   ├── simulation.py                         # Loop utama Ursina Engine & orchestrator aplikasi
│   │
│   ├── cognition/                            # [LAPISAN KOGNISI] Graf & Algoritma Pencarian
│   │   ├── heuristics.py                     # Manhattan, Euclidean, Chebyshev, Octile
│   │   ├── warehouse_graph.py                # Matriks graf 35x25, layout generator & access nodes
│   │   └── pathfinding.py                    # Engine A*, GBFS, DualPathPlanner & nearest charger/dock
│   │
│   ├── behavior/                             # [LAPISAN BEHAVIOR] Kinematika, Hitbox & Misi
│   │   ├── robot_controller.py               # Controller AGV, hitbox/collision, auto-charging & trail
│   │   ├── forklift_controller.py            # AI Patrol Forklift mandiri (Dynamic moving obstacles)
│   │   └── mission_manager.py                # Dispatcher balapan, sinkronisasi misi & zone transfer
│   │
│   ├── environment/                          # [LAPISAN ENVIRONMENT] Lingkungan 3D & Scene Graph
│   │   ├── asset_loader.py                   # Loader model 3D eksternal dengan graceful fallback
│   │   ├── interactive_shelf.py              # Entitas rak 3D ber-Collider dengan indikator seleksi
│   │   └── warehouse_scene.py                # Lantai tiled, docking/charging stations & heatmap
│   │
│   └── communication/                        # [LAPISAN KOMUNIKASI] UI, Legenda & Telemetri
│       ├── interaction_system.py             # Raycasting kursor mouse & penempatan medan
│       ├── hud_serious.py                    # Dashboard analitik industri WMS
│       ├── hud_gamification.py               # HUD Arcade: Time-Attack, skor, combo & rating
│       ├── warehouse_legend.py               # Renderer panel Legenda gudang proporsional
│       └── ui_controller.py                  # Master UI Controller & keyboard/mouse dispatcher
│
├── tests/
│   ├── test_full_suite.py                    # Uji integrasi fungsionalitas utama simulasi
│   ├── test_hud_and_legend_proportions.py    # Uji proporsi skala container HUD & legenda
│   ├── test_pov_camera.py                    # Uji stabilitas orientasi kamera POV First-Person
│   └── test_ui_refactor.py                   # Uji tata letak & anti-overlap panel UI
│
├── requirements.txt                          # Berkas dependensi Python
├── README.md                                 # Dokumentasi utama proyek
└── main.py                                   # Titik masuk eksekusi langsung aplikasi
```

---

## 7. Instalasi & Menjalankan Program

### Prasyarat Sistem
- **Sistem Operasi**: Linux (Ubuntu 20.04/24.04 LTS direkomendasikan), Windows 10/11, atau macOS.
- **Python**: Versi **3.9**, **3.10**, **3.11**, atau **3.12**.
- **Perangkat Keras**: GPU dengan dukungan OpenGL 3.3+ (Integrated Intel/AMD atau Dedicated NVIDIA/AMD).

### Langkah Instalasi

1. **Clone repositori proyek ini**:
   ```bash
   git clone [https://github.com/tjoyager/KKA-ETS-Implementation.git](https://github.com/tjoyager/KKA-ETS-Implementation.git)
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
   ```

3. **Pasang paket pustaka dependensi**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Jalankan simulator 3D**:
   ```bash
   python main.py
   ```
   atau
   ```bash
   python3 main.py
   ```

5. *(Opsional)* **Menjalankan Pengujian Otomatis**:
   ```bash
   PYTHONPATH=. pytest -p no:launch_testing tests/
   ```

---

## 8. Informasi Akademik & Kontributor

- **Institusi**: Institut Teknologi Sepuluh Nopember (ITS) — S-1 Teknik Informatika
- **Mata Kuliah**: Konsep Kecerdasan Artificial (KKA) — Semester Gasal 2026/2027
- **Agenda**: Evaluasi Tengah Semester (ETS) — Implementasi Praktis
- **Versi Rilis**: **v3.0.0 (Final Release)**

### Tim Pengembang

| Nama Mahasiswa | NRP | Kontribusi |
| :--- | :---: | :--- |
| **Hadryan Rizky Dimas Saputra** | `5025251027` | Mengembangkan alur utama (*core flow*) simulasi serta mengoordinasikan pembagian kerja kelompok. |
| **Aga Nafta Filadelfiano** | `5025251055` | Menyiapkan seluruh aset 3D dan *environment* simulasi, serta logika pengalihan rute otomatis ke *charging station* terdekat saat baterai menipis. |
| **Nabil Khairie** | `5025251066` | Mengembangkan algoritma pencarian serta logika interaksi AGV, termasuk fungsi *hitbox* dan deteksi tabrakan (*collision*) dengan *forklift* dan *box*. |
| **Azka Fairus Syamsa** | `5025251067` | Merancang sistem baterai AGV (*battery level*, *charging station*, *charging logic*) serta memperbaiki sinkronisasi status misi agar robot kedua tidak *freeze* pada baterai $< 20\%$. |
| **Asher Yedijah Hoesono** | `5025251106` | Merancang dan mengembangkan antarmuka pengguna (*User Interface* / HUD) serta menyempurnakan tata letak dan proporsi panel **Legenda gudang**. |
