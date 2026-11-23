"""Regression tests for confirmed bugs across AGV navigation, HUDs, graph, and UI."""

from unittest.mock import MagicMock

import pytest
from ursina import Vec3, time as utime

from src.behavior.forklift_controller import ForkliftController
from src.behavior.mission_manager import MissionManager
from src.behavior.robot_controller import AGVRobot, RobotState
from src.cognition.heuristics import chebyshev_distance, euclidean_distance
from src.cognition.warehouse_graph import CellType, ShelfData, WarehouseGraph100
from src.communication.hud_gamification import GamificationHUD
from src.communication.hud_serious import SeriousHUD
from src.communication.interaction_system import InteractionState, InteractionSystem, PlacementTool
from src.communication.warehouse_audio import WarehouseAudio
from src.config import CHARGING_STATIONS, DEFAULT_GOAL, SPAWN_ALPHA, SPAWN_BETA, grid_to_world
from src.environment.interactive_shelf import InteractiveShelf
from src.environment.warehouse_scene import WarehouseScene

pytestmark = pytest.mark.usefixtures("ursina_app")


def _make_setup(graph=None):
    graph = graph or WarehouseGraph100.generate_complex_warehouse()
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    scene_mock = MagicMock()
    scene_mock.interactive_shelves = {}
    scene_mock.dynamic_obstacle_entities = {}
    scene_mock.oil_spill_entities = {}
    scene_mock.boost_pad_entities = {}
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)
    return graph, scene_mock, mgr, r_alpha, r_beta


def _step_robot_to_next_waypoint(robot, monkeypatch, dt=0.25, max_frames=30):
    monkeypatch.setattr(utime, "dt", dt)
    prev_steps = robot.total_steps_executed
    for _ in range(max_frames):
        robot.update()
        if robot.total_steps_executed > prev_steps or robot.state in (
            RobotState.LOADING_CARGO,
            RobotState.UNLOADING_CARGO,
            RobotState.CHARGING,
            RobotState.FINISHED,
            RobotState.DEAD,
        ):
            break


def test_step_counter_continuity_and_edge_count_across_stops_and_replans(monkeypatch):
    graph = WarehouseGraph100(12, 8)
    graph.dock_alpha = (1, 1)
    graph.dock_beta = (1, 1)
    r_alpha = AGVRobot("AGV Alpha", "A*", (1, 1), (0, 200, 255), (0, 150, 255), speed=10.0, is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", (1, 1), (255, 180, 0), (255, 140, 0), speed=10.0, is_alpha=False)
    scene_mock = MagicMock()
    scene_mock.interactive_shelves = {}
    mgr = MissionManager(graph, scene_mock, r_alpha, r_beta)

    serious = SeriousHUD()
    arcade = GamificationHUD()
    arcade.set_visible(True)
    interaction_sys = InteractionSystem(mgr, scene_mock)

    leg1 = [(1, 1), (2, 1), (3, 1)]       # 2 steps
    leg2 = [(3, 1), (4, 1), (5, 1), (6, 1)]  # 3 steps
    leg3 = [(6, 1), (5, 1), (4, 1), (3, 1), (2, 1), (1, 1)]  # 5 steps

    s_pick = MagicMock()
    s_pick.shelf_data = ShelfData(coord=(3, 2), shelf_id="R-0302", has_cargo=True, access_nodes=[(3, 1)])
    s_drop = MagicMock()
    s_drop.shelf_data = ShelfData(coord=(6, 2), shelf_id="R-0602", has_cargo=False, access_nodes=[(6, 1)])
    mgr.selected_pickup_shelf = s_pick
    mgr.selected_dropoff_shelf = s_drop
    mgr.is_race_active = True

    from src.cognition.pathfinding import DualPathPlanner
    mgr.dual_plan = DualPathPlanner.plan_dual_race(graph, (1, 1), (1, 1), (3, 1), (6, 1))
    r_alpha.set_mission_legs(leg1, leg2, leg3)
    r_beta.set_mission_legs(leg1, leg2, leg3)

    # Expected edge count = 2 + 3 + 5 = 10 (not node sum 3 + 4 + 6 = 13)
    assert r_alpha.total_mission_steps == 10
    assert r_alpha.total_steps_executed == 0

    def read_hud_progress():
        serious._last_update = 0.0
        arcade._last_update = 0.0
        serious.update(mgr, interaction_sys)
        arcade.update(mgr, interaction_sys)
        return serious.rows[4]["a"].text, arcade.cards[0][4].text

    observed_steps = []
    monkeypatch.setattr(utime, "dt", 0.25)

    # Walk Leg 1
    while r_alpha.state == RobotState.MOVING_TO_PICKUP:
        r_alpha.update()
        observed_steps.append(r_alpha.total_steps_executed)
    assert r_alpha.state == RobotState.LOADING_CARGO
    assert r_alpha.total_steps_executed == 2
    s_txt, a_txt = read_hud_progress()
    assert s_txt == "2/10"
    assert a_txt == "Steps 2/10"

    # Wait out loading stop -> Leg 2
    while r_alpha.state == RobotState.LOADING_CARGO:
        r_alpha.update()
    assert r_alpha.state == RobotState.MOVING_TO_DROPOFF
    s_txt, a_txt = read_hud_progress()
    assert s_txt == "2/10"
    assert a_txt == "Steps 2/10"

    # Take 1 step on Leg 2, then replan around an obstacle
    _step_robot_to_next_waypoint(r_alpha, monkeypatch)
    assert r_alpha.total_steps_executed == 3
    graph.add_dynamic_obstacle(5, 1)
    assert r_alpha.recalculate_route(graph, mgr.current_heuristic_fn, (3, 2), (6, 2))
    assert r_alpha.total_steps_executed == 3  # Replan never resets executed steps
    s_txt, a_txt = read_hud_progress()
    assert s_txt.startswith("3/")
    assert a_txt.startswith("Steps 3/")

    # Walk to drop-off stop -> unload -> Leg 3
    while r_alpha.state == RobotState.MOVING_TO_DROPOFF:
        r_alpha.update()
        observed_steps.append(r_alpha.total_steps_executed)
    assert r_alpha.state == RobotState.UNLOADING_CARGO
    steps_at_dropoff = r_alpha.total_steps_executed
    assert steps_at_dropoff > 3

    while r_alpha.state == RobotState.UNLOADING_CARGO:
        r_alpha.update()
    assert r_alpha.state == RobotState.RETURNING_TO_DOCK
    s_txt, a_txt = read_hud_progress()
    assert s_txt.startswith(f"{steps_at_dropoff}/")
    assert a_txt.startswith(f"Steps {steps_at_dropoff}/")

    # Walk Leg 3 home
    while r_alpha.state == RobotState.RETURNING_TO_DOCK:
        r_alpha.update()
        observed_steps.append(r_alpha.total_steps_executed)

    assert r_alpha.state == RobotState.FINISHED
    assert r_alpha.total_steps_executed == r_alpha.total_mission_steps
    assert observed_steps == sorted(observed_steps)
    serious._last_update = 0.0
    arcade._last_update = 0.0
    arcade.update(mgr, interaction_sys)
    assert arcade.cards[0][4].text == f"Steps {r_alpha.total_mission_steps}/{r_alpha.total_mission_steps}"

    serious.container.enabled = False
    arcade.container.enabled = False


def test_leg3_low_battery_near_home_does_not_freeze_or_die_on_arrival(monkeypatch):
    graph, _, mgr, r_alpha, _ = _make_setup()
    # Near home dock (17, 1) on walkable cells, low battery (2%), 2 steps left: (18, 2) -> (17, 2) -> (17, 1)
    r_alpha.speed = 10.0
    r_alpha.position = grid_to_world(18, 2, 0.0)
    r_alpha.leg3_grid_path = [(18, 2), (17, 2), (17, 1)]
    r_alpha.leg3_waypoints = [grid_to_world(x, y, 0.0) for x, y in r_alpha.leg3_grid_path]
    r_alpha.active_grid_path = list(r_alpha.leg3_grid_path)
    r_alpha.active_waypoints = list(r_alpha.leg3_waypoints)
    r_alpha.waypoint_idx = 0
    r_alpha.state = RobotState.RETURNING_TO_DOCK
    r_alpha.battery = 2.0  # Final step drains battery to 0% right on spawn_coord

    monkeypatch.setattr(utime, "dt", 0.25)
    for _ in range(40):
        r_alpha.update()
        if r_alpha.state in (RobotState.FINISHED, RobotState.DEAD):
            break

    assert r_alpha.state == RobotState.FINISHED
    assert r_alpha.battery == 100.0
    assert r_alpha.get_current_grid_coord() == SPAWN_ALPHA

    # Case B: Interior dock (19, 9) is closer than spawn (17, 1) (cost 3 vs 9), yet battery (18%) suffices for home (needed 15).
    # Robot must restore RETURNING_TO_DOCK, cache per-cell check, and move home instead of freezing.
    from src.cognition.pathfinding import a_star_search
    r_alpha.reset_to_dock()
    r_alpha.speed = 10.0
    r_alpha.position = grid_to_world(19, 6, 0.0)
    home_res = a_star_search(graph, (19, 6), SPAWN_ALPHA)
    assert home_res.success
    r_alpha.leg3_grid_path = list(home_res.path)
    r_alpha.leg3_waypoints = [grid_to_world(x, y, 0.0) for x, y in r_alpha.leg3_grid_path]
    r_alpha.active_grid_path = list(r_alpha.leg3_grid_path)
    r_alpha.active_waypoints = list(r_alpha.leg3_waypoints)
    r_alpha.waypoint_idx = 0
    r_alpha.state = RobotState.RETURNING_TO_DOCK
    r_alpha.battery = 18.0

    for _ in range(80):
        r_alpha.update()
        if r_alpha.state in (RobotState.FINISHED, RobotState.DEAD):
            break

    assert r_alpha.state == RobotState.FINISHED
    assert r_alpha.get_current_grid_coord() == SPAWN_ALPHA


def test_charger_detour_step_counter_continuity(monkeypatch):
    from src.cognition.pathfinding import a_star_search
    graph, _, mgr, r_alpha, _ = _make_setup()
    r_alpha.speed = 10.0
    start_c = (22, 13)
    r_alpha.position = grid_to_world(*start_c, 0.0)
    leg1 = [start_c, (22, 12)]
    leg2 = [(22, 12), (22, 11)]
    leg3 = a_star_search(graph, (22, 11), SPAWN_ALPHA).path
    r_alpha.set_mission_legs(leg1, leg2, leg3)
    r_alpha.pickup_access = (22, 12)
    r_alpha.dropoff_access = (22, 11)
    r_alpha.battery = 15.0  # Critical -> detours to nearest interior dock (22, 15)

    monkeypatch.setattr(utime, "dt", 0.25)
    assert r_alpha._check_battery_emergency() is True
    assert r_alpha.state == RobotState.TO_CHARGER
    assert r_alpha.emergency_dock == (22, 15)

    # Walk to charger (22, 15): 2 moves from (22, 13) -> total_steps_executed == 2
    for _ in range(30):
        r_alpha.update()
        if r_alpha.state == RobotState.CHARGING:
            break
    assert r_alpha.state == RobotState.CHARGING
    assert r_alpha.total_steps_executed == 2

    # Finish charging -> resumes MOVING_TO_PICKUP, total_steps_executed stays 2 (never resets!)
    r_alpha.recharge_full()
    r_alpha._finish_charging()
    assert r_alpha.state == RobotState.MOVING_TO_PICKUP
    assert r_alpha.total_steps_executed == 2
    assert r_alpha.total_mission_steps >= r_alpha.total_steps_executed + (len(r_alpha.active_waypoints) - 1)


def test_finish_charging_with_missing_resume_state_recovers_to_returning():
    graph, _, mgr, r_alpha, _ = _make_setup()
    r_alpha.position = grid_to_world(22, 15, 0.0)
    r_alpha.state = RobotState.RETURNING_TO_DOCK
    r_alpha.emergency_dock = (22, 15)
    r_alpha._resume_state = None
    r_alpha.battery = 15.0

    r_alpha._handle_leg_completion()
    assert r_alpha.state == RobotState.CHARGING
    assert r_alpha._resume_state == RobotState.RETURNING_TO_DOCK

    r_alpha.recharge_full()
    r_alpha._finish_charging()
    assert r_alpha.state == RobotState.RETURNING_TO_DOCK
    assert r_alpha.emergency_dock is None
    assert r_alpha.active_grid_path[-1] == SPAWN_ALPHA


def test_apply_new_active_path_syncs_waypoints_and_avoids_duplicate_cell():
    graph, _, _, r_alpha, _ = _make_setup()
    r_alpha.position = grid_to_world(17, 5, 0.0)
    r_alpha.state = RobotState.MOVING_TO_PICKUP
    r_alpha.leg2_grid_path = [(17, 7), (17, 8)]
    r_alpha.leg3_grid_path = [(17, 8), (17, 1)]
    r_alpha.total_steps_executed = 4

    new_path = [(17, 5), (17, 6), (17, 7)]
    r_alpha._apply_new_active_path(new_path)

    assert r_alpha.active_grid_path == new_path
    assert len(r_alpha.active_waypoints) == len(r_alpha.active_grid_path)
    assert r_alpha.active_waypoints[0] == r_alpha.position
    assert r_alpha.total_mission_steps == 4 + 2 + 1 + 1

    # Unwalkable current cell fallback prepends curr_coord cleanly
    graph.set_cell(17, 5, CellType.WALL)
    r_alpha._apply_new_active_path([(17, 6), (17, 7)])
    assert r_alpha.active_grid_path == [(17, 5), (17, 6), (17, 7)]
    assert len(r_alpha.active_waypoints) == len(r_alpha.active_grid_path)


def test_forklift_over_oil_and_boost_and_special_cell_restoration():
    graph = WarehouseGraph100(10, 10)
    oil = (4, 4)
    boost = (5, 4)
    graph.add_hazard_oil(*oil)
    graph.add_boost_pad(*boost)
    graph.precompute_adjacency()

    # Forklift steps onto oil -> blocked in grid and neighbor caches
    graph.update_forklift_cell(None, oil)
    assert graph.grid[oil[1], oil[0]] == CellType.FORKLIFT
    assert not graph.is_walkable(*oil)
    assert oil not in graph.get_neighbors(3, 4)

    # Forklift steps onto boost -> oil restored, boost blocked
    graph.update_forklift_cell(oil, boost)
    assert graph.grid[oil[1], oil[0]] == CellType.HAZARD_OIL
    assert graph.is_walkable(*oil)
    assert oil in graph.get_neighbors(3, 4)
    assert graph.grid[boost[1], boost[0]] == CellType.FORKLIFT
    assert not graph.is_walkable(*boost)

    # Forklift leaves boost -> boost restored
    graph.update_forklift_cell(boost, (6, 4))
    assert graph.grid[boost[1], boost[0]] == CellType.BOOST_PAD
    assert graph.is_walkable(*boost)

    # Removing terrain modifier restores GOAL / DOCK / TRANSFER_GATE instead of EMPTY
    goal = (8, 8)
    graph.goal = goal
    graph.set_cell(goal[0], goal[1], CellType.GOAL)
    assert graph.add_boost_pad(goal[0], goal[1])
    assert graph.remove_terrain_modifier(goal[0], goal[1])
    assert graph.grid[goal[1], goal[0]] == CellType.GOAL

    gate = (9, 5)
    graph.transfer_gate_coords = {gate}
    graph.set_cell(gate[0], gate[1], CellType.TRANSFER_GATE)
    assert graph.add_hazard_oil(gate[0], gate[1])
    assert graph.remove_terrain_modifier(gate[0], gate[1])
    assert graph.grid[gate[1], gate[0]] == CellType.TRANSFER_GATE


def test_zone_b_forklift_spawn_and_transition_cleanup(monkeypatch):
    zone_b = WarehouseGraph100.generate_zone_b_warehouse()
    assert zone_b.grid[20, 23] == CellType.SHELF_OBSTACLE

    # ForkliftController given (23, 20) in Zone B resolves to a walkable cell
    fl3 = ForkliftController(graph=zone_b, start_coord=(23, 20), control_scheme="ijkl", name="FL3")
    assert zone_b.is_walkable(*fl3.current_coord) or zone_b.grid[fl3.current_coord[1], fl3.current_coord[0]] == CellType.FORKLIFT
    assert fl3.current_coord != (23, 20)
    fl3.on_destroy()

    # Full Zone A -> Zone B transition clears stale queue/results and spawns forklifts safely
    graph_a = WarehouseGraph100.generate_complex_warehouse()
    scene = WarehouseScene(graph=graph_a)
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    fl1 = ForkliftController(graph=graph_a, start_coord=(17, 11), control_scheme="wasd", name="FL1")
    fl2 = ForkliftController(graph=graph_a, start_coord=(5, 7), control_scheme="arrows", name="FL2")
    fl3_a = ForkliftController(graph=graph_a, start_coord=(23, 20), control_scheme="ijkl", name="FL3")
    scene.forklifts = [fl1, fl2, fl3_a]
    scene.forklift = fl1

    mgr = MissionManager(graph_a, scene, r_alpha, r_beta)
    mgr.set_forklifts(scene.forklifts)
    mgr.enqueue_order(MagicMock(), MagicMock())
    mgr.first_to_arrive = "AGV Alpha (A* Search)"
    mgr.arrival_delta_time = 12.3

    monkeypatch.setattr("ursina.camera.overlay.animate_color", lambda *a, **kw: None)
    mgr._finish_zone_transition()

    assert mgr.current_zone == "Zone B"
    assert len(mgr.task_queue) == 0
    assert mgr.first_to_arrive is None
    assert mgr.arrival_delta_time == 0.0
    assert mgr.dual_plan is not None
    assert fl3_a.current_coord != (23, 20)
    assert mgr.graph.shelves[(23, 20)].coord == (23, 20)
    assert mgr.graph.grid[fl3_a.current_coord[1], fl3_a.current_coord[0]] == CellType.FORKLIFT

    for fl in scene.forklifts:
        fl.on_destroy()


def test_start_return_leg_uses_active_heuristic(monkeypatch):
    graph, _, mgr, r_alpha, _ = _make_setup()
    called_with = []

    def tracking_heuristic(a, b):
        called_with.append((a, b))
        return chebyshev_distance(a, b)

    r_alpha.heuristic_fn = tracking_heuristic
    r_alpha.position = grid_to_world(21, 15, 0.0)
    r_alpha.leg3_waypoints = []
    r_alpha.battery = 80.0
    r_alpha._start_return_leg()

    assert len(called_with) > 0
    assert r_alpha.state == RobotState.RETURNING_TO_DOCK


def test_reset_and_zone_transfer_update_dual_plan():
    graph, _, mgr, r_alpha, r_beta = _make_setup()
    shelves = list(graph.shelves.values())
    s_pick = MagicMock(); s_pick.shelf_data = [s for s in shelves if s.has_cargo][0]
    s_drop = MagicMock(); s_drop.shelf_data = [s for s in shelves if not s.has_cargo][0]
    assert mgr.dispatch_race(s_pick, s_drop)
    old_plan = mgr.dual_plan
    assert old_plan is not None

    mgr.reset_race()
    assert mgr.dual_plan is None

    assert mgr.dispatch_zone_transfer()
    assert mgr.dual_plan is not None
    assert mgr.dual_plan is not old_plan
    assert mgr.dual_plan.alpha_plan.leg1.path[-1] == (33, 13)


def test_interaction_system_guards_and_midrace_queue_state(monkeypatch):
    graph = WarehouseGraph100.generate_complex_warehouse()
    scene = WarehouseScene(graph=graph)
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    mgr = MissionManager(graph, scene, r_alpha, r_beta)
    isys = InteractionSystem(mgr, scene)

    cargo_shelves = [s for s in graph.shelves.values() if s.has_cargo]
    empty_shelves = [s for s in graph.shelves.values() if not s.has_cargo]
    sh_c1 = InteractiveShelf(cargo_shelves[0])
    sh_c2 = InteractiveShelf(cargo_shelves[1])
    sh_e1 = InteractiveShelf(empty_shelves[0])
    sh_e2 = InteractiveShelf(empty_shelves[1])

    # 1. Dispatch initial race
    isys.hovered_shelf = sh_c1
    isys.handle_click()
    assert isys.state == InteractionState.SELECT_DROPOFF

    # Reject occupied shelf as drop-off
    isys.hovered_shelf = sh_c2
    isys.handle_click()
    assert isys.state == InteractionState.SELECT_DROPOFF
    assert "sudah terisi kargo" in isys.prompt_text.lower()

    # Valid empty shelf starts race
    isys.hovered_shelf = sh_e1
    isys.handle_click()
    assert isys.state == InteractionState.RACING
    assert mgr.is_race_active

    # 2. Mid-race queue selection must restore RACING so race completion triggers COMPLETED
    isys.hovered_shelf = sh_c2
    isys.handle_click()
    assert isys.state == InteractionState.SELECT_DROPOFF

    # Reject already-booked drop-off sh_e1
    isys.hovered_shelf = sh_e1
    isys.handle_click()
    assert isys.state == InteractionState.SELECT_DROPOFF
    assert "booking" in isys.prompt_text.lower()

    # Queue sh_c2 -> sh_e2
    isys.hovered_shelf = sh_e2
    isys.handle_click()
    assert len(mgr.task_queue) == 1
    assert isys.state == InteractionState.RACING

    # Simulate finishing active race and consuming queue
    mgr.task_queue.clear()
    mgr.race_finished = True
    mgr.is_race_active = False
    isys.hovered_shelf = None
    isys.update()
    assert isys.state == InteractionState.COMPLETED

    # 3. Protected special cells reject tool placement
    isys.set_tool(PlacementTool.CARGO_BOX)
    from ursina import mouse
    for protected in (CHARGING_STATIONS[0], DEFAULT_GOAL, (34, 13)):
        world_pt = grid_to_world(*protected, 0.0)
        monkeypatch.setattr(type(mouse), "world_point", property(lambda self, p=world_pt: p))
        isys.handle_click()
        assert protected not in graph.dynamic_obstacles
        assert "fasilitas" in isys.prompt_text.lower()


def test_pause_freezes_forklifts_and_arrival_uses_elapsed_time(monkeypatch):
    graph, _, mgr, r_alpha, _ = _make_setup()
    fl = ForkliftController(graph=graph, start_coord=(17, 11))
    mgr.set_forklift(fl)

    mgr.toggle_pause()
    assert mgr.is_paused
    assert fl.is_paused

    monkeypatch.setattr(utime, "dt", 0.5)
    fl.wait_timer = 0.0
    pos_before = fl.current_coord
    fl.update()
    assert fl.current_coord == pos_before
    assert not fl.is_moving

    mgr.toggle_pause()
    assert not fl.is_paused

    # _on_robot_finish uses race_elapsed_time safely even if race_start_time is None
    mgr.race_start_time = None
    mgr.race_elapsed_time = 14.5
    mgr.first_to_arrive = None
    mgr._on_robot_finish(r_alpha)
    assert mgr.arrival_delta_time == pytest.approx(14.5)

    fl.on_destroy()


def test_warehouse_audio_treats_to_charger_as_moving(monkeypatch):
    _, _, mgr, r_alpha, _ = _make_setup()
    audio = WarehouseAudio(mgr)
    audio.available = True
    motor_mock = MagicMock()
    motor_mock.status.return_value = 1
    audio.sounds = {"motor": motor_mock, "pickup": MagicMock(), "dropoff": MagicMock()}

    monkeypatch.setattr(utime, "dt", 0.05)
    r_alpha.state = RobotState.TO_CHARGER
    r_alpha.position = Vec3(0, 0, 0)
    audio.update()
    r_alpha.position = Vec3(0, 0, 0.5)
    audio.update()

    assert audio.level > 0.0
    audio.on_destroy()


def test_ui_hud_hide_persists_and_clear_terrain_replans():
    from src.communication.ui_controller import UIController

    graph = WarehouseGraph100.generate_complex_warehouse()
    scene = WarehouseScene(graph=graph)
    r_alpha = AGVRobot("AGV Alpha", "A*", SPAWN_ALPHA, (0, 200, 255), (0, 150, 255), is_alpha=True)
    r_beta = AGVRobot("AGV Beta", "GBFS", SPAWN_BETA, (255, 180, 0), (255, 140, 0), is_alpha=False)
    mgr = MissionManager(graph, scene, r_alpha, r_beta)
    isys = InteractionSystem(mgr, scene)
    ui = UIController(mgr, isys, scene)

    ui.handle_input("u")
    assert not ui.hud_visible
    assert not ui.hud_serious.container.enabled
    assert not ui.hud_gamification.container.enabled
    ui.update()
    assert not ui.hud_serious.container.enabled
    assert not ui.hud_gamification.container.enabled

    # Clearing terrain during an active race triggers replanning
    shelves = list(graph.shelves.values())
    s_pick = MagicMock(); s_pick.shelf_data = [s for s in shelves if s.has_cargo][0]
    s_drop = MagicMock(); s_drop.shelf_data = [s for s in shelves if not s.has_cargo][0]
    mgr.dispatch_race(s_pick, s_drop)
    old_replan = r_alpha.replan_count
    ui.clear_terrain()
    assert r_alpha.replan_count > old_replan

    ui.warehouse_audio.on_destroy()
