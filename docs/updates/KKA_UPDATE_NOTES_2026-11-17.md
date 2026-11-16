# Update Log — Warehouse Digital Twin

**Tanggal:** 17 November 2026  
**Branch kerja:** `feat/ui`  
**Ruang lingkup:** visual warehouse, konsistensi UI, replanning, audit A*/GBFS.

## Ringkasan

Pembaruan ini menyempurnakan tampilan simulator dan memperbaiki konsistensi navigasi AGV tanpa mengganti fokus perbandingan dua algoritma, yaitu **A* Search** dan **Greedy Best-First Search (GBFS)**.

## Perubahan

### 1. Warehouse 3D
- Menambahkan modul `src/environment/warehouse_detailing.py` untuk dekorasi fisik warehouse, termasuk variasi palet/kargo, loading bay, finishing arsitektural, dan lantai beton bertekstur.
- Mengintegrasikan layer detail melalui `src/environment/industrial_facelift.py`.
- Menyesuaikan warna dinding, perimeter, dan pencahayaan pada `src/environment/warehouse_scene.py`.
- Memperbarui target kamera isometrik dan posisi kamera top-down di `src/config.py`.
- Dekorasi visual didesain tanpa collider tambahan agar tidak mengubah graf navigasi.

### 2. UI / HUD
- Menyelaraskan skema warna HUD Serious, Gamification, serta panel kontrol pada `src/communication/ui_controller.py`.
- Menambahkan `src/communication/visual_theme.py` sebagai penyedia tekstur permukaan rounded untuk UI.
- Mempertahankan indikator speed pada control dock dan label lorong yang telah dinonaktifkan sebelumnya.

### 3. Pathfinding & race
- Memperbaiki estimasi heuristik A* agar mempertimbangkan pengali medan termurah pada area speed boost.
- Memperbaiki validasi start/goal dan hasil misi yang tidak lengkap.
- Mengizinkan node dibuka ulang saat ditemukan biaya rute lebih murah.
- Mengubah alur pergantian heuristik saat race berjalan agar robot merencanakan ulang dari posisinya, bukan dipindahkan kembali ke dock.
- Fokus evaluasi aplikasi tetap A* versus GBFS. Algoritma referensi biaya terpendek pada pengujian tidak ditambahkan sebagai peserta race.

### 4. Pengujian
- Menambah `tests/test_search_audit.py` untuk mengecek rute, biaya berbobot, kasus detour speed boost, node yang dibuka ulang, dan misi tidak lengkap.

## Berkas utama

| Kelompok | Berkas |
| --- | --- |
| Algoritma | `src/cognition/pathfinding.py`, `src/behavior/mission_manager.py`, `src/behavior/robot_controller.py` |
| Warehouse | `src/environment/warehouse_detailing.py`, `src/environment/industrial_facelift.py`, `src/environment/warehouse_scene.py`, `src/config.py` |
| UI | `src/communication/ui_controller.py`, `src/communication/hud_serious.py`, `src/communication/hud_gamification.py`, `src/communication/visual_theme.py` |
| Tes | `tests/test_search_audit.py` |

## Checklist sebelum merge

- [ ] `python -m pytest -q tests/test_search_audit.py` lulus pada venv project.
- [ ] `python -m pytest -q` lulus tanpa regressions.
- [ ] Jalankan `python main.py`; pastikan visual warehouse, viewport, dan kontrol speed benar.
- [ ] Mulai race, tekan `H` ketika AGV bergerak; cek tidak teleport, timer dan kargo tidak reset.
- [ ] Coba Zone A dan Zone B; dekorasi warehouse dibangun ulang dengan benar.
- [ ] Coba A* dan GBFS pada boost pad / oil spill; cek biaya di HUD konsisten dengan path.
- [ ] Tambahkan screenshot `before` / `after` pada deskripsi Pull Request.
- [ ] Review `git diff --cached --stat` dan `git diff --cached --check` sebelum commit.

## Status verifikasi

- **Static syntax:** 31 file `.py` pada `src/` dan `tests/` berhasil dikompilasi secara sintaks dalam review ZIP.
- **Automated runtime tests:** belum dapat dijalankan pada lingkungan review karena modul `ursina` tidak terpasang. Jalankan di venv lokal sebelum mengklaim tes lulus.
- **Visual & FPS:** belum diverifikasi pada renderer Ursina Windows.

## Catatan teknis untuk PR

- Perubahan visual tidak boleh menambah collider pada dekorasi.
- Pastikan README dan screenshot mencerminkan tampilan terbaru. README dalam ZIP masih belum mencatat update ini secara khusus.
- Jangan sertakan `.venv/`, `venv/`, `design_backups/`, file cache, maupun folder installer sementara ke commit.
- Branch pada snapshot ZIP adalah `feat/ui`; status upstream harus disegarkan menggunakan `git fetch origin` sebelum push.
