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
   *(Opsional)* Jika sistem Ubuntu Anda belum memiliki driver OpenGL standar:
   ```bash
   sudo apt update && sudo apt install -y libgl1-mesa-glx
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

Berikut adalah data metrik riil hasil pencarian rute pada denah gudang default (20x15 sel):

```text
TABEL PERBANDINGAN METRIK KINERJA:
+----------------------------+------------+----------------+---------------+-----------------------+--------------+
| Algoritma                  | Status     | Panjang Rute   | Total Biaya   | Simpul Dieksplorasi   | Waktu (ms)   |
+----------------------------+------------+----------------+---------------+-----------------------+--------------+
| A* Search                  | SUKSES     | 28 sel         | 27.00         | 113 simpul            | ~1.0 ms      |
| Greedy Best-First Search   | SUKSES     | 32 sel         | 31.00         | 40 simpul             | ~0.3 ms      |
+----------------------------+------------+----------------+---------------+-----------------------+--------------+
```

### 🧠 Analisis Teoritis untuk Laporan Tugas KKA:

1. **Optimalitas Rute ($f(n) = g(n) + h(n)$ vs $f(n) = h(n)$)**:
   - **A\* Search** berhasil menemukan rute yang **paling pendek dan optimal** dengan total biaya **27.00**. A* mempertimbangkan biaya langkah yang sudah ditempuh $g(n)$, sehingga tidak tergiur lorong buntu.
   - **Greedy Best-First Search (GBFS)** menghasilkan rute **suboptimal** dengan total biaya **31.00** (lebih panjang 4 langkah). Karena hanya melihat $h(n)$ (jarak terdekat ke Goal), GBFS terburu-buru bergerak lurus ke arah target di sisi atas sehingga terhadang barisan rak dan terpaksa memutar lebih jauh.

2. **Efisiensi Eksplorasi Simpul**:
   - **GBFS** hanya mengeksplorasi **40 simpul** sebelum mencapai tujuan. Pencarian sangat cepat dan terarah (*greedy*).
   - **A\*** mengeksplorasi **113 simpul** karena harus memeriksa simpul alternatif di lorong lain untuk membuktikan secara matematis bahwa tidak ada jalur lain yang lebih pendek.

3. **Kesimpulan Praktis di Industri Gudang**:
   - Untuk robot gudang otonom (AGV) yang beroperasi ribuan kali sehari mengantar paket, **A\* Search lebih direkomendasikan** karena penghematan jarak tempuh (baterai & waktu perjalanan fisik) jauh lebih berharga daripada selisih waktu komputasi mikrodetik.

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
