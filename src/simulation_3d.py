"""
simulation_3d.py
================
Modul backward-compatibility yang menghubungkan eksekusi 3D ke arsitektur modular baru.
"""

from src.simulation import run_warehouse_simulation

run_3d_simulation = run_warehouse_simulation

__all__ = ["run_3d_simulation", "run_warehouse_simulation"]
