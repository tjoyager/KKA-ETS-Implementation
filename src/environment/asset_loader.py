"""
asset_loader.py
===============
Modul pemuatan aset 3D eksternal (.obj / .gltf) dengan mekanisme graceful fallback.
Memastikan simulator tidak pernah mengalami crash meskipun aset eksternal belum diunduh,
sekaligus siap merender model kompleks (.obj / .gltf) secara native jika tersedia.
"""

import os
from typing import Optional

from src.config import (
    MODEL_PATH_AGV,
    MODEL_PATH_AGV_LOADED,
    MODEL_PATH_SHELF,
    MODEL_PATH_SHELF_EMPTY,
    MODEL_PATH_SHELF_OCCUPIED,
    MODEL_PATH_CARGO,
    MODEL_PATH_DOCK,
)


class AssetLoader:
    """
    Pengelola pemuatan model 3D dengan fallback cerdas.
    Mengembalikan path string berkas model agar Ursina Engine menginstansiasi
    salinan mesh independen untuk setiap entitas (mencegah bug node-stealing / reparent conflict).
    """
    _checked_cache_dir = False

    @classmethod
    def _ensure_cache_dirs(cls):
        """Membuat direktori cache model_compressed agar Ursina dapat menyimpan .bam tanpa error."""
        if not cls._checked_cache_dir:
            os.makedirs("models_compressed/assets/models", exist_ok=True)
            cls._checked_cache_dir = True

    @classmethod
    def load_model_safe(cls, model_path: str, fallback_model_name: str = "cube") -> str:
        """
        Memeriksa ketersediaan berkas model 3D eksternal.
        Mengembalikan path string berkas jika berkas ada dan valid,
        atau fallback_model_name primitif jika berkas tidak ditemukan.
        """
        cls._ensure_cache_dirs()
        if os.path.exists(model_path):
            return model_path
        return fallback_model_name

    @classmethod
    def get_agv_model(cls) -> str:
        """Mengambil model robot AGV industri eksternal atau fallback."""
        return cls.load_model_safe(MODEL_PATH_AGV, fallback_model_name="cube")

    @classmethod
    def get_shelf_model(cls) -> str:
        """Mengambil model rak palet bertingkat eksternal atau fallback."""
        return cls.load_model_safe(MODEL_PATH_SHELF, fallback_model_name="cube")

    @classmethod
    def get_cargo_model(cls) -> str:
        """Mengambil model kotak kargo kontainer eksternal atau fallback."""
        return cls.load_model_safe(MODEL_PATH_CARGO, fallback_model_name="cube")

    @classmethod
    def get_dock_model(cls) -> str:
        """Mengambil model stasiun pengisian daya eksternal atau fallback."""
        return cls.load_model_safe(MODEL_PATH_DOCK, fallback_model_name="cube")

    @classmethod
    def get_shelf_empty_model(cls) -> str:
        """Mengambil model rak kosong eksternal atau fallback."""
        return cls.load_model_safe(MODEL_PATH_SHELF_EMPTY, fallback_model_name="cube")

    @classmethod
    def get_shelf_occupied_model(cls) -> str:
        """Mengambil model rak terisi kargo eksternal atau fallback."""
        return cls.load_model_safe(MODEL_PATH_SHELF_OCCUPIED, fallback_model_name="cube")

    @classmethod
    def get_agv_loaded_model(cls) -> str:
        """Mengambil model robot AGV bermuatan kargo eksternal atau fallback."""
        return cls.load_model_safe(MODEL_PATH_AGV_LOADED, fallback_model_name="cube")
