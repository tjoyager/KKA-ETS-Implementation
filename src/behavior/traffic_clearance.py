"""Horizontal clearance for moving AGVs, cartons and forklift reservations."""
import math
from typing import NamedTuple, Optional

from src.config import grid_to_world


class Bounds(NamedTuple):
    left: float
    right: float
    back: float
    front: float
    is_carton: bool = False

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

    def point_distance_sq(self, px: float, pz: float) -> float:
        dx = max(self.left - px, 0.0, px - self.right)
        dz = max(self.back - pz, 0.0, pz - self.front)
        return dx * dx + dz * dz

    def segment_distance_sq(self, start, end) -> float:
        if self.hits_segment(start, end, 0.0):
            return 0.0
        vx = end.x - start.x
        vz = end.z - start.z
        len2 = vx * vx + vz * vz
        candidates = [0.0, 1.0]
        if abs(vx) > 1e-9:
            for edge_x in (self.left, self.right):
                t = (edge_x - start.x) / vx
                if 0.0 < t < 1.0:
                    candidates.append(t)
        if abs(vz) > 1e-9:
            for edge_z in (self.back, self.front):
                t = (edge_z - start.z) / vz
                if 0.0 < t < 1.0:
                    candidates.append(t)
        if len2 > 1e-12:
            for cx in (self.left, self.right):
                for cz in (self.back, self.front):
                    t = ((cx - start.x) * vx + (cz - start.z) * vz) / len2
                    if 0.0 < t < 1.0:
                        candidates.append(t)
        return min(self.point_distance_sq(start.x + vx * t, start.z + vz * t) for t in candidates)

    def blocks_segment(self, start, end, radius: float, carton_radius: Optional[float] = None) -> bool:
        """Check whether a barrier blocks the segment, keeping 1-cell carton exits passable."""
        if not self.is_carton:
            return self.hits_segment(start, end, radius)
        r = radius if carton_radius is None else carton_radius
        if not self.hits_segment(start, end, r):
            return False
        min_d2 = self.segment_distance_sq(start, end)
        r2 = r * r
        if min_d2 >= r2:
            return False
        start_d2 = self.point_distance_sq(start.x, start.z)
        end_d2 = self.point_distance_sq(end.x, end.z)
        if start_d2 > 1e-6 and end_d2 >= r2 and min_d2 >= start_d2 - 1e-6:
            return False
        return True


def carton_bounds(coord):
    p = grid_to_world(*coord)
    # The .82-wide carton includes raised labels and tape.
    return Bounds(p.x - .43, p.x + .43, p.z - .43, p.z + .43, True)


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
    for r in (manager.robot_alpha, manager.robot_beta):
        if bounds.is_carton:
            r_carton = getattr(r, 'carton_radius', r.traffic_radius)
            if bounds.point_distance_sq(r.position.x, r.position.z) < r_carton * r_carton:
                return True
        elif bounds.hits_segment(r.position, r.position, r.traffic_radius):
            return True
    return False


class ClearanceGraph:
    """Filter edges for one replan snapshot. Keep the warehouse's movement costs."""
    def __init__(self, graph, barriers, radius, start, position, carton_radius=None):
        self.graph = graph
        self.barriers = barriers
        self.radius = radius
        self.carton_radius = radius if carton_radius is None else carton_radius
        self.start = start
        self.position = position
        self.is_walkable = graph.is_walkable
        self.get_movement_cost = graph.get_movement_cost
        self.terrain_weights = graph.terrain_weights

    def get_neighbors(self, x, y, allow_diagonal=False):
        origin = self.position if (x, y) == self.start else grid_to_world(x, y)
        for node in self.graph.get_neighbors(x, y, allow_diagonal):
            end = grid_to_world(*node)
            if not any(b.blocks_segment(origin, end, self.radius, self.carton_radius) for b in self.barriers):
                yield node
