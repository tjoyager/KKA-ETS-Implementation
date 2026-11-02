# 📦 Direktori Aset Model 3D Gudang (Warehouse 3D Assets)

Direktori ini digunakan untuk menyimpan berkas aset 3D eksternal yang dimuat secara dinamis oleh simulator gudang 3D berbasis **Ursina Engine**.

---

## 📁 Struktur Berkas Bawaan

Secara *default*, proyek ini telah menyediakan model Wavefront (`.obj`) *clean low-poly* siap pakai:
- `agv.obj` : Model robot AGV industri lengkap dengan sasis, bumper pelindung, dek kargo, dan sensor LIDAR.
- `shelf.obj` : Model rak penyimpanan palet gudang bertingkat (*multi-tier industrial shelf*).
- `cargo.obj` : Model kotak kargo kontainer logistik dengan sabuk penguat.
- `dock.obj` : Model bantalan stasiun pengisian daya otomatis (*charging dock pad*).

Sistem `src/environment/asset_loader.py` akan secara otomatis memuat berkas-berkas di atas menggunakan `load_model()`. Jika berkas sengaja dihapus atau belum tersedia, sistem memiliki mekanisme *graceful procedural fallback* agar simulasi tetap dapat berjalan mulus tanpa *crash*.

---

## 🌐 Sumber Pengunduhan Model 3D Open-Source Kompatibel

Anda dapat mengganti atau meningkatkan kualitas visual model 3D dengan mengunduh aset gratis (*Royalty-Free / CC0 / CC-BY*) dari repositori berikut:

1. **[Kenney.nl (Asset Kits)](https://kenney.nl/assets)**
   - *Rekomendasi*: **Space Kit**, **Car Kit**, atau **Furniture Kit**.
   - Lisensi: **CC0 1.0 Universal** (Bebas untuk keperluan akademis & komersial).
   - Format: `.obj`, `.fbx`, `.gltf`.

2. **[Poly Pizza](https://poly.pizza/)**
   - Koleksi model 3D *low-poly* Google Poly yang diarsipkan.
   - Kata kunci pencarian: `agv`, `forklift`, `warehouse rack`, `crate`, `pallet`.
   - Format: `.obj` (sangat direkomendasikan langsung untuk Ursina).

3. **[Sketchfab](https://sketchfab.com/)**
   - Filter pencarian: *Downloadable*, *License: CC / Free*.
   - Kata kunci: `warehouse shelf`, `automated guided vehicle`, `industrial robot`.
   - Format: `.gltf` / `.glb` atau `.obj`.

4. **[Free3D](https://free3d.com/) & [OpenGameArt](https://opengameart.org/)**
   - Beragam model gratis siap pakai dalam format `.obj`.

---

## ⚙️ Panduan Format & Integrasi ke Ursina Engine

Ursina Engine (berbasis Panda3D) secara *native* mendukung:
- **`.obj` (Wavefront OBJ)**: Format paling stabil dan mudah dimodifikasi. Pastikan *face* berupa *quads* atau *triangles*.
- **`.bam` (Panda3D Binary)**: Format kompresi internal yang otomatis di-cache Ursina di folder `models_compressed/`.
- **`.gltf` / `.glb`**: Didukung jika pustaka `panda3d-gltf` terpasang (`pip install panda3d-gltf`).

### 🔧 Cara Memasang Model Baru:
1. Unduh model 3D pilihan Anda (misalnya model robot AGV baru).
2. Ubah nama berkas menjadi `agv.obj` (atau sesuaikan konstanta di [src/config.py](../../src/config.py)).
3. Letakkan di dalam folder `assets/models/`.
4. Jalankan `python main.py` — model baru akan otomatis dirender di arena 100x100!
