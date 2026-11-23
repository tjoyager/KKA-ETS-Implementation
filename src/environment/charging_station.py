"""
charging_station.py
===================
Modul konstruksi Unified Twin Docking Station (SPAWN_ALPHA & SPAWN_BETA)
dan manajemen entitas stasiun pengisian daya gudang.
"""

from typing import Any, List, Optional
from ursina import Entity, Text, Vec3, color

from src.config import (
    COLOR_ALPHA_PRIMARY,
    COLOR_BETA_PRIMARY,
    SPAWN_ALPHA,
    SPAWN_BETA,
    grid_to_world,
)
from src.environment.asset_loader import AssetLoader
from src.environment.interior_charging_station import InteriorChargingStation


def build_charging_station(scene: Optional[Any] = None) -> List[Any]:
    """
    Membangun visual Unified Twin Docking Station di area bawah/tengah arena (x=17, 18, y=1).

    Args:
        scene: Parent entity opsional (misalnya instance WarehouseScene).

    Returns:
        List entitas visual yang dibuat.
    """
    dock_tower_model = AssetLoader.get_dock_model()

    pos_a = grid_to_world(SPAWN_ALPHA[0], SPAWN_ALPHA[1], 0.0)
    pos_b = grid_to_world(SPAWN_BETA[0], SPAWN_BETA[1], 0.0)
    mid_pos = (pos_a + pos_b) / 2.0

    entities: List[Any] = []
    parent_kwargs = {"parent": scene} if isinstance(scene, Entity) else {}

    # 1. Platform Terpadu Raksasa (Unified Docking Platform)
    entities.append(
        Entity(
            model='cube',
            position=mid_pos - Vec3(0, 0.025, 0),
            scale=Vec3(3.2, 0.06, 1.8),
            color=color.rgba32(18, 24, 34, 230),
            **parent_kwargs,
        )
    )

    # 2. Pad Lantai Parkir Alpha (A* Search) - Cyan Neon
    entities.append(
        Entity(
            model='cube',
            position=pos_a - Vec3(0, 0.015, 0),
            scale=Vec3(1.35, 0.065, 1.5),
            color=color.rgba32(110, 149, 144, 165),
            **parent_kwargs,
        )
    )
    # Menara charger stasiun Alpha di belakang robot
    entities.append(
        Entity(
            model=dock_tower_model,
            position=pos_a + Vec3(0, 0, -0.75),
            rotation=Vec3(0, 0, 0),
            scale=Vec3(0.55, 0.65, 0.55),
            **parent_kwargs,
        )
    )

    # 3. Pad Lantai Parkir Beta (GBFS) - Orange Neon
    entities.append(
        Entity(
            model='cube',
            position=pos_b - Vec3(0, 0.015, 0),
            scale=Vec3(1.35, 0.065, 1.5),
            color=color.rgba32(176, 132, 84, 165),
            **parent_kwargs,
        )
    )
    # Menara charger stasiun Beta di belakang robot
    entities.append(
        Entity(
            model=dock_tower_model,
            position=pos_b + Vec3(0, 0, -0.75),
            rotation=Vec3(0, 0, 0),
            scale=Vec3(0.55, 0.65, 0.55),
            **parent_kwargs,
        )
    )

    # 4. Header Billboard Terpadu
    entities.append(
        Text(
            text="UNIFIED TWIN DOCK\n[ A* SEARCH  |  GBFS ]",
            position=mid_pos + Vec3(0, 2.1, -0.75),
            scale=1.45,
            color=color.rgb32(110, 149, 144),
            billboard=True,
            origin=(0, 0),
            font='assets/fonts/Roboto-Bold.ttf',
            **parent_kwargs,
        )
    )
    offset_text = 0.35 if SPAWN_ALPHA == SPAWN_BETA else 0.0
    entities.append(
        Text(
            text="ALPHA (A*)",
            position=pos_a + Vec3(-offset_text, 1.55, -0.75),
            scale=1.1,
            color=color.rgb32(*COLOR_ALPHA_PRIMARY),
            billboard=True,
            origin=(0, 0),
            font='assets/fonts/Roboto-Bold.ttf',
            **parent_kwargs,
        )
    )
    entities.append(
        Text(
            text="BETA (GBFS)",
            position=pos_b + Vec3(offset_text, 1.55, -0.75),
            scale=1.1,
            color=color.rgb32(*COLOR_BETA_PRIMARY),
            billboard=True,
            origin=(0, 0),
            font='assets/fonts/Roboto-Bold.ttf',
            **parent_kwargs,
        )
    )

    return entities


__all__ = [
    "build_charging_station",
    "InteriorChargingStation",
]
