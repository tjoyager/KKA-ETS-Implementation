"""Horizontal clearance for moving AGVs, cartons and forklift reservations."""
import math
from typing import NamedTuple

from src.config import grid_to_world


class Bounds(NamedTuple):
    left: float
    right: float
    back: float
    front: float

    def overlaps(self, other):
        return (self.left <= other.right and self.right >= other.left
                and self.back <= other.front and self.front >= other.back)

    def hits_segment(self, start, end, radius):
        """Clip the whole translation against a rectangle expanded by the footprint."""
        low, high = 0.0, 1.0
        for a, b, lo, hi in ((start.x, end.x, self.left, self.right),
                             (start.z, end.z, self.back, self.front)):
            lo -= radius
            hi += radius
            delta = b - a
            if abs(delta) < 1e-9:
                if a < lo or a > hi:
                    return False
            else:
                t1, t2 = (lo - a) / delta, (hi - a) / delta
                low = max(low, min(t1, t2))
                high = min(high, max(t1, t2))
                if low > high:
                    return False
        return True


def carton_bounds(coord):
    p = grid_to_world(*coord)
    # The .82-wide carton includes raised labels and tape.
    return Bounds(p.x - .43, p.x + .43, p.z - .43, p.z + .43)


def forklift_bounds(forklift, target=None, heading=None):
    """Bound chassis, wheels and forks throughout translation and steering."""
    start = forklift.position
    if target is None:
        target = forklift.target_pos if forklift.is_moving else start
        heading = forklift.target_rot if forklift.is_moving else forklift.rotation_y
    turn = (heading - forklift.rotation_y + 180) % 360 - 180
    if abs(turn) > .01:
        # The tips reach z=1.21. Reserve their turning circle until aligned.
        left, right, back, front = -1.25, 1.25, -1.25, 1.25
    else:
        angle = math.radians(heading)
        c, s = math.cos(angle), math.sin(angle)
        corners = [(x*c + z*s, -x*s + z*c)
                   for x in (-.57, .57) for z in (-.60, .64)]
        corners += [(x*c + z*s, -x*s + z*c)
                    for x in (-.26, .26) for z in (.60, 1.22)]
        xs, zs = zip(*corners)
        left, right, back, front = min(xs), max(xs), min(zs), max(zs)
    return Bounds(min(start.x, target.x) + left, max(start.x, target.x) + right,
                  min(start.z, target.z) + back, max(start.z, target.z) + front)


def obstacles(graph):
    manager = getattr(graph, 'traffic_manager', None)
    return ([carton_bounds(coord) for coord in graph.dynamic_obstacles]
            + [forklift_bounds(f) for f in getattr(manager, 'forklifts', ()) if f])


def touches_robot(bounds, manager):
    if manager is None:
        return False
    return any(bounds.hits_segment(r.position, r.position, r.traffic_radius)
               for r in (manager.robot_alpha, manager.robot_beta))


class ClearanceGraph:
    """Filter edges for one replan snapshot. Keep the warehouse's movement costs."""
    def __init__(self, graph, barriers, radius, start, position):
        self.graph = graph
        self.barriers = barriers
        self.radius = radius
        self.start = start
        self.position = position
        self.is_walkable = graph.is_walkable
        self.get_movement_cost = graph.get_movement_cost
        self.terrain_weights = graph.terrain_weights

    def get_neighbors(self, x, y, allow_diagonal=False):
        origin = self.position if (x, y) == self.start else grid_to_world(x, y)
        for node in self.graph.get_neighbors(x, y, allow_diagonal):
            end = grid_to_world(*node)
            if not any(b.hits_segment(origin, end, self.radius) for b in self.barriers):
                yield node
