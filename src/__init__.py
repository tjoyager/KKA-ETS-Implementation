"""
Paket Simulator Robot Gudang 3D (Autonomous Warehouse AGV).
Arsitektur Modular: Kognisi, Behavior, Environment, dan Komunikasi.
"""

from src.cognition import (
    manhattan_distance,
    euclidean_distance,
    octile_distance,
    chebyshev_distance,
    WarehouseGraph100,
    CellType,
    ShelfData,
    SearchResult,
    MissionLegs,
    DualRacePlan,
    a_star_search,
    greedy_best_first_search,
    DualPathPlanner,
)

from src.environment import (
    AssetLoader,
    InteractiveShelf,
    WarehouseScene,
)

from src.behavior import (
    AGVRobot,
    RobotState,
    MissionManager,
)

from src.communication import (
    InteractionSystem,
    InteractionState,
    SeriousHUD,
    GamificationHUD,
    UIController,
)

from src.simulation import run_warehouse_simulation

# Backward compatibility alias
WarehouseGrid = WarehouseGraph100
run_3d_simulation = run_warehouse_simulation

__all__ = [
    # Cognition
    "manhattan_distance",
    "euclidean_distance",
    "octile_distance",
    "chebyshev_distance",
    "WarehouseGraph100",
    "WarehouseGrid",
    "CellType",
    "ShelfData",
    "SearchResult",
    "MissionLegs",
    "DualRacePlan",
    "a_star_search",
    "greedy_best_first_search",
    "DualPathPlanner",
    # Environment
    "AssetLoader",
    "InteractiveShelf",
    "WarehouseScene",
    # Behavior
    "AGVRobot",
    "RobotState",
    "MissionManager",
    # Communication
    "InteractionSystem",
    "InteractionState",
    "SeriousHUD",
    "GamificationHUD",
    "UIController",
    # Main runner
    "run_warehouse_simulation",
    "run_3d_simulation",
]
