"""V14: calm aisle navigation markers and industrial detailing for Ursina.

V14 is a *visual-only* add-on. It never changes grid cells, route costs,
colliders, AGV physics, forklift controls, or mission logic. Built once after the
warehouse finishes loading, and rebuilt when MissionManager switches zones.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from ursina import Entity, Vec3, Texture, color, destroy

from src.config import (
    GRID_WIDTH, GRID_HEIGHT, PERIMETER_WALL_HEIGHT, SPAWN_ALPHA,
    SPAWN_BETA, grid_to_world,
)

# Restrained industrial palette: graphite, warm concrete, brushed metal,
# warehouse safety ochre. Algorithm colors remain exclusive to Alpha/Beta.
CONCRETE = (65, 63, 59)
MARKING = (172, 147, 99)
GUIDE = (143, 132, 112)
STEEL = (96, 100, 103)
STEEL_LIGHT = (150, 151, 145)
GRAPHITE = (34, 34, 36)
SAFETY_DARK = (38, 37, 35)


def _rect(parent, position, scale, rgb):
    """Non-interactive visual geometry, deliberately without a collider."""
    return Entity(
        parent=parent,
        model="cube",
        position=position,
        scale=scale,
        color=color.rgb32(*rgb),
        collider=None,
    )


def _font(size: int):
    """Use the repo's own font; fall back cleanly on machines without it."""
    root = Path(__file__).resolve().parents[2]
    choices = (
        root / "assets/fonts/Roboto-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "arialbd.ttf",
    )
    for choice in choices:
        try:
            return ImageFont.truetype(str(choice), size=size)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default(size=size)


def _sign_texture(title: str):
    """Simple single-line aisle placard. No confusing tiny subtitle."""
    im = Image.new("RGBA", (512, 140), (31, 32, 32, 255))
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 13, 139), fill=(171, 145, 96, 255))
    draw.rectangle((14, 1, 510, 138), outline=(97, 94, 86, 255), width=2)
    draw.text((32, 24), title, font=_font(59), fill=(240, 235, 223, 255))
    return Texture(im)


def _aisle_candidates(graph):
    """Return aisle-mouth suggestions based on actual walkable shelf corridors.

    The generated labels are wayfinding identifiers, not shelf IDs. They are
    stable for the current zone layout and aren't attached to random shelves.
    """
    shelf_cells = set(getattr(graph, "shelves", {}).keys())
    candidates = []
    if not shelf_cells:
        return candidates

    for vertical in (True, False):
        outer_n = graph.width if vertical else graph.height
        inner_n = graph.height if vertical else graph.width
        for cross in range(2, outer_n - 2):
            run = []
            def flush():
                if len(run) < 5:
                    return
                supported = []
                for pos in run:
                    px, py = (cross, pos) if vertical else (pos, cross)
                    side = ((px-1, py), (px+1, py)) if vertical else ((px, py-1), (px, py+1))
                    if any(c in shelf_cells for c in side):
                        supported.append(pos)
                if len(supported) < 2:
                    return
                # Place near the start of the shelf-lined run, with a small
                # approach gap so the sign reads as an aisle entry marker.
                entry = max(run[0], supported[0]-1)
                if entry not in run:
                    entry = supported[0]
                x, y = ((cross, entry) if vertical else (entry, cross))
                score = len(supported)*3 + len(run)
                candidates.append((score, x, y, vertical))
            for index in range(1, inner_n - 1):
                x, y = (cross, index) if vertical else (index, cross)
                if graph.is_walkable(x, y):
                    run.append(index)
                else:
                    flush()
                    run = []
            flush()
    # Long, shelf-lined corridors first, with deterministic tie-breaking.
    candidates.sort(key=lambda item: (-item[0], item[2], item[1], not item[3]))
    return candidates


class IndustrialFacelift:
    """Keeps decorative meshes in a separate layer, synced with the scene graph."""

    def __init__(self, warehouse_scene):
        self.scene = warehouse_scene
        self.root = None
        self._source_key = None

    def refresh(self):
        scene = self.scene
        # Wait until the full floor, walls and racks are available. The scene
        # uses an asynchronous generator during initial loading.
        if getattr(scene, "_async_loader", None) is not None:
            return
        graph = getattr(scene, "graph", None)
        if graph is None or getattr(scene, "floor", None) is None:
            return
        if getattr(scene, "static_walls_parent", None) is None:
            return

        signature = (id(graph), id(scene.floor), id(scene.static_walls_parent))
        if signature == self._source_key and self.root is not None:
            return

        old = self.root
        self.root = Entity(parent=scene, name="V13_Industrial_Detail_Layer")
        self._source_key = signature
        if old is not None:
            destroy(old)

        self._build_decor(graph)

    def _build_decor(self, graph):
        self._build_lane_markings(graph)
        self._build_loading_bay(graph)
        self._build_perimeter_trim()
        # Aisle signage deliberately disabled: keep the clean warehouse view.
        self._build_partition_supports(graph)
        self._build_wall_corner_details()
        # V15 warehouse detailing is visual only, attached to this disposable root.
        from src.environment.warehouse_detailing import WarehouseDetailing
        WarehouseDetailing(self.root, graph, self.scene).build()

    @staticmethod
    def _walkable(graph, x, y):
        return (0 < x < graph.width - 1 and 0 < y < graph.height - 1
                and graph.is_walkable(x, y))

    def _build_lane_markings(self, graph):
        """Structured, dashed forklift aisles. All stripes are *below* path FX."""
        major = Entity(parent=self.root, name="forklift_lane_dashes")
        minor = Entity(parent=self.root, name="aisle_edge_guides")
        count = 0

        # Rather than painting an arbitrary cross over shelves, choose the
        # clearest natural corridors in the current graph's actual layout.
        col_candidates = range(3, graph.width - 3, 2)
        row_candidates = range(3, graph.height - 3, 2)
        cols = sorted(col_candidates, key=lambda x: sum(
            self._walkable(graph, x, y) for y in range(2, graph.height - 2)), reverse=True)
        rows = sorted(row_candidates, key=lambda y: sum(
            self._walkable(graph, x, y) for x in range(2, graph.width - 2)), reverse=True)

        chosen_cols = []
        for x in cols:
            if all(abs(x - old) >= 6 for old in chosen_cols):
                chosen_cols.append(x)
            if len(chosen_cols) == 3:
                break
        chosen_rows = []
        for y in rows:
            if all(abs(y - old) >= 6 for old in chosen_rows):
                chosen_rows.append(y)
            if len(chosen_rows) == 2:
                break

        # Dashes are thin, neutral yellow. Each stripe has no collider and is
        # batched into one mesh per color to keep draw calls predictable.
        for x in chosen_cols:
            for y in range(2, graph.height - 2, 2):
                if all(self._walkable(graph, x, yy) for yy in (y - 1, y, y + 1)):
                    p = grid_to_world(x, y, 0.024)
                    _rect(major, Vec3(p.x, 0.024, p.z), Vec3(0.075, 0.009, 0.56), MARKING)
                    count += 1
        for y in chosen_rows:
            for x in range(2, graph.width - 2, 2):
                if all(self._walkable(graph, xx, y) for xx in (x - 1, x, x + 1)):
                    p = grid_to_world(x, y, 0.024)
                    _rect(major, Vec3(p.x, 0.024, p.z), Vec3(0.56, 0.009, 0.075), MARKING)
                    count += 1

        # Short off-white guide segments beside the first two broad corridors.
        for x in chosen_cols[:2]:
            for y in range(3, graph.height - 3, 4):
                if all(self._walkable(graph, x, yy) for yy in (y - 1, y, y + 1)):
                    p = grid_to_world(x, y, 0.018)
                    _rect(minor, Vec3(p.x + 0.42, 0.018, p.z), Vec3(0.034, 0.008, 0.70), GUIDE)

        if count:
            major.combine(auto_destroy=True)
        if minor.children:
            minor.combine(auto_destroy=True)

    def _build_loading_bay(self, graph):
        """Two marked loading bays plus compact pedestrian caution strip."""
        bays = Entity(parent=self.root, name="loading_bays")
        markers = Entity(parent=self.root, name="dock_safety_chevrons")
        for coord in (SPAWN_ALPHA, SPAWN_BETA):
            x, y = coord
            if not graph.is_in_bounds(x, y):
                continue
            p = grid_to_world(x, y, 0.0)
            for dx in (-0.52, 0.52):
                _rect(bays, Vec3(p.x + dx, 0.022, p.z), Vec3(0.045, 0.012, 1.12), STEEL_LIGHT)
            for dz in (-0.55, 0.55):
                _rect(bays, Vec3(p.x, 0.022, p.z + dz), Vec3(1.08, 0.012, 0.045), STEEL_LIGHT)
            # Hazard stripes in front of each charger; painted, not obstructive.
            for offset in (-0.30, 0.0, 0.30):
                _rect(markers, Vec3(p.x + offset, 0.023, p.z + 0.66),
                      Vec3(0.18, 0.009, 0.22), MARKING)

        bays.combine(auto_destroy=True)
        markers.combine(auto_destroy=True)

        # A pedestrian crossing near the dock approach, only on open cells.
        center_x = round((SPAWN_ALPHA[0] + SPAWN_BETA[0]) / 2)
        approach_y = max(1, min(graph.height - 2, max(SPAWN_ALPHA[1], SPAWN_BETA[1]) + 2))
        walkway = Entity(parent=self.root, name="bay_crosswalk")
        for x in range(center_x - 2, center_x + 3):
            if not self._walkable(graph, x, approach_y):
                continue
            p = grid_to_world(x, approach_y, 0.029)
            _rect(walkway, Vec3(p.x, 0.029, p.z), Vec3(0.54, 0.009, 0.44), STEEL_LIGHT)
        if walkway.children:
            walkway.combine(auto_destroy=True)

    def _build_perimeter_trim(self):
        """Metallic perimeter coping and repeating safety blocks add depth."""
        width, height = GRID_WIDTH + 2, GRID_HEIGHT + 2
        wall_y = PERIMETER_WALL_HEIGHT + 0.085
        cap = Entity(parent=self.root, name="perimeter_metal_cap")
        for z in (-height / 2, height / 2):
            _rect(cap, Vec3(0, wall_y, z), Vec3(width, 0.09, 0.60), STEEL)
        for x in (-width / 2, width / 2):
            _rect(cap, Vec3(x, wall_y, 0), Vec3(0.60, 0.09, height), STEEL)
        cap.combine(auto_destroy=True)

        # The wall stripe is continuous in steel, interrupted by warm hazard
        # plates near industrial entrances, like a real loading facility.
        blocks = Entity(parent=self.root, name="perimeter_hazard_markers")
        for x in range(-int(width / 2) + 2, int(width / 2), 5):
            for z in (-height / 2, height / 2):
                _rect(blocks, Vec3(x, wall_y + 0.051, z), Vec3(0.80, 0.01, 0.58), MARKING)
        blocks.combine(auto_destroy=True)

    def _build_rack_signs(self, graph):
        """At most four clear aisle *entrance* signs, never one per shelf.

        Positions are selected from real walkable corridors adjacent to shelves,
        and each sign gets a slim physical post at the lane edge. Labels are
        sequential wayfinding names per zone, not fake per-shelf IDs.
        """
        candidates = _aisle_candidates(graph)
        if not candidates:
            return

        selected = []
        for _, x, y, vertical in candidates:
            # Interior mouths are easier to recognize than edge-aligned signs.
            if not (3 <= x < graph.width - 3 and 3 <= y < graph.height - 3):
                continue
            if any((x-px)**2+(y-py)**2 < 7**2 for px, py, _ in selected):
                continue
            if any((x-dx)**2+(y-dy)**2 < 3**2 for dx, dy in (SPAWN_ALPHA, SPAWN_BETA)):
                continue
            selected.append((x,y,vertical))
            if len(selected) >= 4:
                break

        # The zone is part of the label; changing zones rebuilds this layer.
        name = str(getattr(getattr(self.scene, "mission_mgr", None), "current_zone", "Zone A"))
        prefix = name.split()[-1][0].upper() if name.strip() else "A"
        signs = Entity(parent=self.root, name="warehouse_aisle_wayfinding")
        posts = Entity(parent=self.root, name="aisle_sign_posts")
        for n, (x, y, vertical) in enumerate(sorted(selected, key=lambda a: (a[1], a[0])), 1):
            p = grid_to_world(x, y, 0)
            if vertical:
                delta_x, delta_z = 0.43, 0.0
            else:
                delta_x, delta_z = 0.0, 0.43
            sign_pos = Vec3(p.x + delta_x, 1.42, p.z + delta_z)
            _rect(posts, Vec3(sign_pos.x, 0.72, sign_pos.z),
                  Vec3(0.045, 1.43, 0.045), STEEL)
            Entity(parent=signs, model="quad", position=sign_pos,
                   scale=Vec3(1.72, 0.44, 1), billboard=True,
                   texture=_sign_texture(f"AISLE {prefix}-{n:02d}"),
                   double_sided=True, collider=None, color=color.white)
        if posts.children:
            posts.combine(auto_destroy=True)


    def _build_partition_supports(self, graph):
        """Break up large featureless black partitions into framed wall modules."""
        from src.cognition.warehouse_graph import CellType

        cells = [
            (x, y)
            for y in range(1, graph.height - 1)
            for x in range(1, graph.width - 1)
            if graph.grid[y, x] == CellType.WALL
        ]
        if not cells:
            return
        # A maximum of 18 support fixtures prevents hundreds of extra objects.
        step = max(1, len(cells) // 18)
        frames = Entity(parent=self.root, name="partition_steel_braces")
        warnings = Entity(parent=self.root, name="partition_safety_bands")
        for x, y in cells[::step][:18]:
            p = grid_to_world(x, y, 0)
            # Attach to the *front* surface of existing walls. Never add
            # geometry or collision into the pathfinding grid itself.
            _rect(frames, Vec3(p.x, 0.90, p.z - 0.50),
                  Vec3(0.075, 1.75, 0.065), STEEL)
            _rect(warnings, Vec3(p.x, 0.30, p.z - 0.54),
                  Vec3(0.080, 0.20, 0.070), MARKING)
        frames.combine(auto_destroy=True)
        warnings.combine(auto_destroy=True)

    def _build_wall_corner_details(self):
        """Simple warning bollards at *outside* arena corners, no path collision."""
        corners = Entity(parent=self.root, name="corner_stanchions")
        px = (GRID_WIDTH + 2) / 2 - 0.85
        pz = (GRID_HEIGHT + 2) / 2 - 0.85
        for x in (-px, px):
            for z in (-pz, pz):
                _rect(corners, Vec3(x, 0.45, z), Vec3(0.14, 0.90, 0.14), GRAPHITE)
                _rect(corners, Vec3(x, 0.76, z), Vec3(0.16, 0.12, 0.16), MARKING)
                _rect(corners, Vec3(x, 0.24, z), Vec3(0.16, 0.12, 0.16), MARKING)
        corners.combine(auto_destroy=True)
