"""
asset_loader.py
===============
Modul pemuatan aset 3D eksternal (.obj / .gltf) dengan mekanisme graceful fallback.
Memastikan simulator tidak pernah mengalami crash meskipun aset eksternal belum diunduh,
sekaligus siap merender model kompleks (.obj / .gltf) secara native jika tersedia.
"""

import os
from typing import Optional
from ursina import Entity, Vec3, color, load_model

from src.config import (
    MODEL_PATH_AGV,
    MODEL_PATH_SHELF,
    MODEL_PATH_CARGO,
    MODEL_PATH_DOCK,
)


class AssetLoader:
    """
    Pengelola pemuatan model 3D dengan fallback cerdas dan caching langsung.
    """
    _cache = {}
    _checked_cache_dir = False
    _agv_model = None
    _shelf_model = None
    _cargo_model = None
    _dock_model = None

    @classmethod
    def _ensure_cache_dirs(cls):
        """Membuat direktori cache model_compressed agar Ursina dapat menyimpan .bam tanpa error."""
        if not cls._checked_cache_dir:
            os.makedirs("models_compressed/assets/models", exist_ok=True)
            cls._checked_cache_dir = True

    @classmethod
    def load_model_safe(cls, model_path: str, fallback_model_name: str = "cube"):
        """
        Mencoba memuat model 3D eksternal via Ursina load_model().
        Jika berkas ada dan valid, mengembalikan model tersebut.
        Jika tidak ditemukan, mengembalikan model fallback primitif.
        """
        if model_path in cls._cache:
            return cls._cache[model_path]

        cls._ensure_cache_dirs()

        model = None
        if os.path.exists(model_path):
            try:
                model = load_model(model_path)
            except Exception as e:
                print(f"[AssetLoader] Peringatan: Gagal memuat {model_path} ({e}), menggunakan fallback.")
                model = None

        if model is None:
            model = fallback_model_name

        cls._cache[model_path] = model
        return model

    @classmethod
    def get_agv_model(cls):
        """Mengambil model robot AGV industri eksternal atau fallback."""
        if cls._agv_model is None:
            cls._agv_model = cls.load_model_safe(MODEL_PATH_AGV, fallback_model_name="cube")
        return cls._agv_model

    @classmethod
    def get_shelf_model(cls):
        """Mengambil model rak palet bertingkat eksternal atau fallback."""
        if cls._shelf_model is None:
            cls._shelf_model = cls.load_model_safe(MODEL_PATH_SHELF, fallback_model_name="cube")
        return cls._shelf_model

    @classmethod
    def get_cargo_model(cls):
        """Mengambil model kotak kargo kontainer eksternal atau fallback."""
        if cls._cargo_model is None:
            cls._cargo_model = cls.load_model_safe(MODEL_PATH_CARGO, fallback_model_name="cube")
        return cls._cargo_model

    @classmethod
    def get_dock_model(cls):
        """Mengambil model stasiun pengisian daya eksternal atau fallback."""
        if cls._dock_model is None:
            cls._dock_model = cls.load_model_safe(MODEL_PATH_DOCK, fallback_model_name="cube")
        return cls._dock_model
