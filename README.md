# 🤖 Simulasi Robot Gudang 3D (Autonomous Warehouse AGV)
> **Tugas / Proyek Kuliah Konsep Kecerdasan Artificial (KKA)**  
> Simulasi robot pengangkut barang otomatis (*Automated Guided Vehicle* / AGV) bernavigasi di dalam gudang menggunakan algoritma **Informed Search (A\* Search vs Greedy Best-First Search)** dengan visualisasi 3D interaktif berbasis **Ursina Engine**.

---

## 📌 Ringkasan Proyek

Proyek ini mendemonstrasikan perbandingan dua algoritma pencarian jalur berinformasi (*Informed Search*) untuk robot gudang:
1. **A\* Search**: Algoritma yang mengevaluasi biaya aktual dari titik awal $g(n)$ ditambah perkiraan sisa jarak ke tujuan $h(n)$ ($f(n) = g(n) + h(n)$). Menjamin ditemukannya jalur **terpendek dan optimal**.
2. **Greedy Best-First Search (GBFS)**: Algoritma yang hanya mengandalkan nilai perkiraan heuristik $h(n)$ ($f(n) = h(n)$). Bekerja sangat cepat mengeksplorasi sedikit simpul, namun rentan terjebak rute memutar (**suboptimal**).

Visualisasi 3D dirancang menggunakan **Ursina Engine** (Panda3D) yang sangat ringan (*lightweight*), tidak membutuhkan ROS/Gazebo, dan dapat langsung dijalankan dengan mulus di **Windows**, **Ubuntu / Linux**, maupun **macOS**.

---

## 📂 Struktur Direktori

```text
KKA-ETS-Implementation/
│
├── src/
│   ├── __init__.py           # Inisialisasi paket Python
│   ├── map_grid.py           # Logika grid 2D: rak rintangan, lorong, start, & goal
│   ├── algorithms.py         # Implementasi A* Search, GBFS, heuristik Manhattan/Euclidean
│   └── simulation_3d.py      # Visualisasi 3D Ursina: AGV 3D, rak gudang, kamera, & tombol UI
│
├── requirements.txt          # Daftar pustaka (numpy, ursina)
├── .gitignore                # Berkas yang diabaikan Git (venv, __pycache__)
├── README.md                 # Dokumentasi panduan penggunaan & analisis KKA
└── main.py                   # Berkas utama peluncur program
```

---

## 🛠️ Langkah Instalasi Cepat (Pemula-Friendly)

Pastikan komputer Anda sudah terpasang **Python 3.9 - 3.12**.

### 🔹 Untuk Pengguna Windows
1. **Buka terminal**: Tekan `Win + R`, ketik `powershell` atau `cmd`, lalu tekan Enter.
2. Masuk ke folder proyek:
   ```powershell
   cd "path\ke\KKA-ETS-Implementation"
   ```
3. Buat dan aktifkan *Virtual Environment* (disarankan agar rapi):
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
4. Pasang pustaka yang dibutuhkan:
   ```powershell
   pip install -r requirements.txt
   ```

---

### 🔹 Untuk Pengguna Ubuntu / Linux
1. **Buka Terminal** (`Ctrl + Alt + T`).
2. Masuk ke folder proyek:
   ```bash
   cd "path/ke/KKA-ETS-Implementation"
   ```
3. Buat dan aktifkan *Virtual Environment*:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Pasang pustaka pendukung:
   ```bash
   pip install -r requirements.txt
   ```
   *(Opsional - Khusus Ubuntu jika OpenGL belum ada)*:
   Pada Ubuntu 22.04 / 24.04 LTS (Noble), gunakan paket modern `libgl1`:
   ```bash
   sudo apt update && sudo apt install -y libgl1 libglx-mesa0
   ```

---

## 🚀 Cara Menjalankan Program (Paling Mudah)

Anda **tidak perlu** mengetik perintah atau argumen yang panjang. Cukup jalankan perintah berikut:

```bash
python main.py
```
*(atau `python3 main.py`)*

Program akan menampilkan **Menu Interaktif Sederhana**:
```text
===================================================================
      SIMULASI ROBOT GUDANG 3D - KECERDASAN BUATAN (KKA)
         Navigasi Informed Search: A* Search vs GBFS
===================================================================

Silakan pilih mode yang ingin dijalankan:
  [1] Buka Visualisasi 3D Interaktif (Bisa ganti A* & GBFS di dalam jendela 3D) [Rekomendasi]
  [2] Tampilkan Tabel Perbandingan & Analisis Teori KKA di Terminal
  [3] Mode Terminal Saja (Tampilkan Peta ASCII & Metrik tanpa GUI)
  [4] Keluar

Masukkan pilihan Anda [1-4] (Tekan ENTER untuk Opsi 1): 
```

> 💡 **Cukup tekan `[ENTER]`**, dan jendela visualisasi 3D akan langsung terbuka secara otomatis!

---

## 🎮 Panduan Kontrol Simulasi 3D

Saat jendela visualisasi 3D terbuka, seluruh kontrol dapat diakses dengan **dua cara**:
1. **Mengklik Tombol UI langsung di layar monitor** (terletak di bagian bawah layar).
2. **Menggunakan Tombol Keyboard**:

| Tombol Keyboard | Tombol UI di Layar | Fungsi & Keterangan |
| :---: | :---: | :--- |
| **`[Tab]`** | **`[Ganti Algoritma]`** | **Fitur Unggulan**: Beralih rute secara langsung antara **A\* Search** dan **GBFS** tanpa me-restart simulasi! Robot akan otomatis kembali ke titik awal dan menelusuri rute baru. |
| **`[Spasi]`** | **`[Jeda / Lanjut]`** | Menjeda (*pause*) atau melanjutkan pergerakan robot AGV. |
| **`[R]`** | **`[Reset]`** | Mengulang pergerakan robot kembali ke titik awal (*Start Dock*). |
| **`[V]`** | **`[Kamera: ...]`** | Mengganti sudut pandang kamera: **Isometrik** $\rightarrow$ **Tampak Atas (Top-Down 2D)** $\rightarrow$ **Bebas (Free Orbit)**. |
| **`[+]` / `[-]`** | **`[Cepat] / [Lambat]`** | Menambah atau memperlambat laju kecepatan robot. |
| **Klik Kanan + Drag** | *(Khusus Mode Bebas)* | Memutar / mengorbit kamera di sekitar gudang untuk melihat detail 3D dari segala sisi. |
| **Scroll Mouse** | - | *Zoom-in* / *Zoom-out* kamera. |
| **`[Esc]`** | **`[Keluar]`** | Menutup jendela 3D dan kembali ke terminal. |

---

## 📊 Hasil Analisis Perbandingan: A* Search vs GBFS

Berikut adalah data metrik riil hasil pencarian rute pada denah gudang labirin kompleks berukuran **30x20 sel**:

```text
TABEL PERBANDINGAN METRIK KINERJA:
+----------------------------+------------+----------------+---------------+-----------------------+--------------+
| Algoritma                  | Status     | Panjang Rute   | Total Biaya   | Simpul Dieksplorasi   | Waktu (ms)   |
+----------------------------+------------+----------------+---------------+-----------------------+--------------+
| A* Search                  | SUKSES     | 43 sel         | 42.00         | 188 simpul            | ~3.2 ms      |
| Greedy Best-First Search   | SUKSES     | 49 sel         | 48.00         | 53 simpul             | ~0.8 ms      |
+----------------------------+------------+----------------+---------------+-----------------------+--------------+
```

### 🧠 Analisis Teoritis untuk Laporan Tugas KKA:

1. **Optimalitas Rute ($f(n) = g(n) + h(n)$ vs $f(n) = h(n)$)**:
   - **A\* Search** berhasil menemukan rute yang **paling pendek dan optimal** dengan total biaya **42.00**. A* mempertimbangkan biaya langkah yang sudah ditempuh $g(n)$, sehingga robot memilih lorong tembus di tengah gudang yang bebas hambatan.
   - **Greedy Best-First Search (GBFS)** menghasilkan rute **suboptimal** dengan total biaya **48.00** (lebih panjang 6 langkah / +14.3%). Karena hanya berpatokan pada nilai $h(n)$ (jarak terdekat ke Goal), GBFS terburu-buru bergerak lurus ke arah atas sehingga terhalang sekat dinding partisi rak di dekat Goal dan terpaksa memutar jauh ke lorong paling atas.

2. **Efisiensi Eksplorasi Simpul**:
   - **GBFS** hanya mengeksplorasi **53 simpul** sebelum mencapai tujuan. Pencariannya sangat cepat dan terarah (*greedy*).
   - **A\*** mengeksplorasi **188 simpul** karena harus menguji lorong-lorong alternatif demi membuktikan secara matematis bahwa tidak ada jalur lain yang lebih pendek.

3. **Visualisasi Jejak Jalur (*Trajectory Trail*) di 3D**:
   - **A\* Search**: Menghasilkan jejak bercahaya warna **Hijau Neon** yang melintas langsung membelah lorong tengah secara efisien.
   - **GBFS**: Menghasilkan jejak bercahaya warna **Oranye Api** yang menunjukkan robot tergiur lorong atas sebelum terpaksa berbelok memutar.

---

## ⚙️ Opsi Tambahan untuk Pengguna Lanjutan (Opsional)

Jika ingin menjalankan skrip secara otomatis tanpa menu interaktif:

```bash
# Langsung jalankan rute A* Search
python main.py --algo astar

# Langsung jalankan rute GBFS
python main.py --algo gbfs

# Jalankan mode terminal saja tanpa jendela 3D (sangat cocok untuk server/testing)
python main.py --no-gui

# Menggunakan heuristik Euclidean Distance dengan pergerakan diagonal 8-arah
python main.py --heuristic euclidean --diagonal
```
