BRIEFING TUGAS PROJECT SIMULASI KKA (KECERDASAN KOMPUTASIONAL & ARTIFISIAL)

Halo tim! Arsitektur proyek kita di repositori sudah dirombak besar-besaran menjadi bentuk modular (3D menggunakan Ursina Engine) agar lebih rapi.

Semua anggota wajib memahami letak dan cara kerja Algoritma Informed Search (A Search & Greedy Best-First Search)* yang kita gunakan. Algoritma intinya sekarang berada di dalam file:
src/cognition/pathfinding.py dan src/cognition/heuristics.py.
Pahami bagaimana algoritma ini menghitung cost (g) dan heuristic (h) untuk mencari jalan di dalam arena grid 100x100.

Deskripsi Tugas:
Karena kamu punya latar belakang programming robotik, tugasmu adalah memoles behavior atau pergerakan fisik AGV agar simulasi terasa seperti robot sungguhan, bukan sekadar objek meluncur.

Cara Mengerjakan:

1. Fokus kerjamu ada di direktori src/behavior/robot_controller.py dan src/behavior/mission_manager.py.

2. Improvisasi logika kinematikanya: tambahkan efek perlambatan (deselerasi) saat robot berbelok tajam di persimpangan, perbaiki lerp angle rotasi agar lebih mulus, atau animasikan sensor LIDAR yang berputar di atas AGV.

3. Pastikan sinkronisasi balapan (race) antara robot Alpha (A*) dan Beta (GBFS) berjalan lancar tanpa bug visual.

Aturan Git, Clone, & Pull Request
Karena kalian akan ngoding bareng, ikuti aturan ini agar branch utama (main) tidak rusak (conflict):

1. Cara Clone & Persiapan Repo:

Buka terminal/Git Bash, jalankan: git clone [https://github.com/tjoyager/KKA-ETS-Implementation.git](https://github.com/tjoyager/KKA-ETS-Implementation.git)

Masuk ke folder proyek: cd KKA-ETS-Implementation

Install requirement: pip install -r requirements.txt

2. Cara Membuat Branch Kerja:
Jangan pernah coding dan push langsung di branch main. Buat branch khusus untuk tugasmu:

git checkout -b feature/robot-kinematics

3. Aturan Pull Request (PR):

Jika kodinganmu sudah selesai dan berjalan normal tanpa error, lakukan git add ., git commit -m "Deskripsi jelas (contoh: Menambahkan model AGV industri)", lalu git push origin nama-branch-kalian.

Buka GitHub, buat Pull Request ke branch main.

Wajib: Tuliskan deskripsi di PR tentang file apa saja yang kamu ubah. Jangan di-merge sendiri!