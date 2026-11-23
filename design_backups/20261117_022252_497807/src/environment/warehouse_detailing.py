"""Warehouse V15 visual dressing; no grid, collider, actor or pathfinding changes.

Attached below the V14.1 industrial facade. Built once when the scene's graph
becomes ready and recreated automatically on zone rebuild. All props deliberately
stay on an existing shelf cell, the exterior perimeter, or a floor-marking plane.
"""
from __future__ import annotations

import random
from PIL import Image, ImageDraw
from ursina import Entity, Vec3, Texture, color
from src.config import GRID_HEIGHT, GRID_WIDTH, PERIMETER_WALL_HEIGHT, SPAWN_ALPHA, SPAWN_BETA, grid_to_world

# A warm, industrial warehouse instead of saturated game-neon.
CONCRETE = (93, 89, 82)
SEAM = (69, 68, 64)
CHALK = (189, 182, 165)
OCHRE = (181, 148, 78)
METAL = (99, 109, 109)
ALUMINIUM = (153, 157, 149)
DARK = (39, 45, 47)
PALLET = (139, 105, 65)
BOXES = ((165, 128, 89), (189, 148, 101), (128, 139, 135), (114, 124, 135), (170, 161, 142))


def _piece(parent, position, scale, rgb):
    return Entity(parent=parent, model='cube', position=position, scale=scale,
                  color=color.rgb32(*rgb), collider=None)


def _batch(parent):
    """Combine a material's geometry to avoid one draw-call per small detail."""
    if getattr(parent, 'children', ()):
        parent.combine(auto_destroy=True)


def concrete_tile(size=128):
    """Deterministic textured concrete tile with hairline control joints.

    The existing floor uses one tile per walkable grid cell. Unlike the bright
    neon grid, the seam here is deliberately just a subtle physical joint.
    """
    rng = random.Random(1805)
    im = Image.new('RGBA', (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            fleck = rng.randrange(-5, 6)
            # Low-frequency trowel variation stops the surface looking flat.
            wave = ((x // 17 + y // 21) % 3) - 1
            px[x, y] = tuple(max(0, min(255, c + fleck + wave * 2)) for c in CONCRETE) + (255,)
    draw = ImageDraw.Draw(im)
    draw.line([(0, 0), (size-1, 0)], fill=SEAM + (255,), width=1)
    draw.line([(0, 0), (0, size-1)], fill=SEAM + (255,), width=1)
    draw.line([(2, 2), (size-2, 2)], fill=(99, 95, 87, 255), width=1)
    # Rare small discolorations rather than a repetitive speckle pattern.
    for _ in range(11):
        x, y = rng.randrange(5, size-5), rng.randrange(5, size-5)
        draw.ellipse((x, y, x+1, y+1), fill=(104, 98, 89, 255))
    return Texture(im)


class WarehouseDetailing:
    def __init__(self, parent, graph, warehouse_scene):
        self.parent = parent
        self.graph = graph
        self.scene = warehouse_scene

    def build(self):
        self._concrete_floor()
        self._pallet_rack_variation()
        self._loading_wall()
        self._service_bay_paint()
        self._partition_cladding()
        self._industrial_fixtures()

    def _concrete_floor(self):
        floor = getattr(self.scene, 'floor', None)
        if floor is not None:
            floor.texture = concrete_tile()
            # No changes to floor geometry, texture scale, shader or collider.

    def _pallet_rack_variation(self):
        """Racks already have OBJ cargo. Add restrained secondary stacked loads.

        Palette and package shape vary per coordinate, and every package stays
        inside that rack's existing occupied physical cell. No cargo props on
        aisle cells. No fake aisle labels or shelf ID overlays.
        """
        shelves = list(getattr(self.graph, 'shelves', {}).values())
        shelves.sort(key=lambda s: (s.y, s.x))
        # Small subset: rack details must not obscure robots, pick/drop FX, or floor.
        featured = [s for s in shelves if ((s.x * 23 + s.y * 17) % 7) < 2]
        featured = featured[:64]
        if not featured:
            return
        groups = {name: Entity(parent=self.parent, name='rack_'+name) for name in
                  ('wood', 'wood2', 'strap', 'metal', 'box0', 'box1', 'box2', 'box3', 'box4')}
        for shelf in featured:
            pos = grid_to_world(shelf.x, shelf.y, 0)
            # Existing occupied shelf OBJ reaches y=1.18, empty shelf y=0.81.
            # Pallets sit neatly on those respective model caps.
            h = 1.225 if shelf.has_cargo else .845
            kind = (shelf.x * 5 + shelf.y * 11) % 5
            _piece(groups['wood'], Vec3(pos.x, h, pos.z), Vec3(.66, .065, .64), PALLET)
            for dz in (-.23, .0, .23):
                _piece(groups['wood2'], Vec3(pos.x, h + .052, pos.z + dz),
                       Vec3(.66, .035, .105), (177, 137, 90))
            if shelf.has_cargo:
                box = BOXES[kind]
                # Two smaller modules have a more realistic silhouette than one cube.
                _piece(groups['box'+str(kind)], Vec3(pos.x - .157, h + .205, pos.z),
                       Vec3(.30, .25, .45), box)
                _piece(groups['box'+str((kind+1)%5)], Vec3(pos.x + .157, h + .205, pos.z),
                       Vec3(.30, .25, .45), BOXES[(kind+1)%5])
                _piece(groups['strap'], Vec3(pos.x, h + .337, pos.z),
                       Vec3(.62, .014, .055), (209, 198, 158))
            else:
                # Empty shelf still has a pallet, but no dummy cargo.
                _piece(groups['metal'], Vec3(pos.x, h + .07, pos.z),
                       Vec3(.60, .022, .58), (112, 115, 111))
        for group in groups.values():
            _batch(group)

    def _loading_wall(self):
        """Three closed roll-up bay doors, mounted flush on the existing back wall.

        The wall collision remains unchanged. Doors are decorative and are not
        presented as traversable exits. All details stay on the perimeter.
        """
        wall_z = (GRID_HEIGHT + 2) / 2.0
        front_z = wall_z - .275
        all_groups = {name: Entity(parent=self.parent, name='loading_'+name) for name in
                      ('door', 'slat', 'frame', 'edge', 'indicator')}
        # Centered in large back-wall spans, leaving the right transfer gate alone.
        for cx in (-11.0, -2.5, 6.0):
            # Existing perimeter wall (height 2.4) remains the collision surface.
            _piece(all_groups['door'], Vec3(cx, 1.06, front_z), Vec3(4.45, 1.95, .042), (68, 76, 76))
            for ystep in range(1, 14):
                y = .18 + ystep * .135
                _piece(all_groups['slat'], Vec3(cx, y, front_z - .038),
                       Vec3(4.34, .026, .031), (114, 121, 119))
            for dx in (-2.29, 2.29):
                _piece(all_groups['frame'], Vec3(cx + dx, 1.13, front_z - .070),
                       Vec3(.15, 2.23, .15), METAL)
                _piece(all_groups['edge'], Vec3(cx + dx, .25, front_z - .16),
                       Vec3(.18, .48, .18), OCHRE)
            _piece(all_groups['frame'], Vec3(cx, 2.20, front_z - .066),
                   Vec3(4.73, .17, .15), (133, 140, 136))
            _piece(all_groups['indicator'], Vec3(cx, 2.33, front_z - .15),
                   Vec3(.42, .12, .20), OCHRE)
            # Protective threshold on the interior side of the wall.
            _piece(all_groups['edge'], Vec3(cx, .038, front_z - .36),
                   Vec3(4.72, .076, .22), DARK)
        for group in all_groups.values():
            _batch(group)

    def _service_bay_paint(self):
        """Muted concrete pad + safety markings around the two existing AGV docks.

        All shapes are flush with the floor; no new walls or path blockers.
        Loading platforms and chargers retain original models and colors.
        """
        a, b = grid_to_world(*SPAWN_ALPHA, 0), grid_to_world(*SPAWN_BETA, 0)
        center = (a + b) / 2
        base = Entity(parent=self.parent, name='service_bay_pavement')
        guide = Entity(parent=self.parent, name='service_bay_guides')
        # y=0.004 keeps the pad below existing dock geometry.
        _piece(base, Vec3(center.x, .004, center.z + .18),
               Vec3(5.3, .006, 3.1), (78, 81, 78))
        for side in (-2.65, 2.65):
            _piece(guide, Vec3(center.x+side, .013, center.z+.18),
                   Vec3(.045, .008, 3.10), CHALK)
        for z in (-1.35, 1.65):
            _piece(guide, Vec3(center.x, .013, center.z+z),
                   Vec3(5.30, .008, .05), OCHRE)
        # Only paint short dashes on cells known to be walkable.
        for x in range(13, 23):
            y = 4
            if not self.graph.is_in_bounds(x, y) or not self.graph.is_walkable(x, y):
                continue
            p = grid_to_world(x, y, 0)
            _piece(guide, Vec3(p.x, .013, p.z), Vec3(.42, .007, .08), OCHRE)
        _batch(base)
        _batch(guide)

    def _partition_cladding(self):
        """Replace the huge featureless black visual faces with steel wall panels.

        Facing is on the front half of existing wall grid cells. All geometry
        has collider=None and does not affect the graph's blocking cells.
        """
        try:
            from src.cognition.warehouse_graph import CellType
        except ImportError:
            return
        cladding = Entity(parent=self.parent, name='industrial_partition_facing')
        cornice = Entity(parent=self.parent, name='partition_top_caps')
        cells = [(x, y) for y in range(1, self.graph.height-1)
                 for x in range(1, self.graph.width-1)
                 if self.graph.grid[y, x] == CellType.WALL]
        for x, y in cells[:240]:
            p = grid_to_world(x, y, 0)
            # Face plates sit on the wall's front (negative Z) surface.
            _piece(cladding, Vec3(p.x, .94, p.z-.492),
                   Vec3(.965, 1.78, .02), (57, 64, 66))
            _piece(cornice, Vec3(p.x, 2.03, p.z),
                   Vec3(.985, .07, .985), (103, 111, 111))
        _batch(cladding)
        _batch(cornice)

    def _industrial_fixtures(self):
        """Wall-mounted faux strip lights. Geometry only, no expensive new lights."""
        strips = Entity(parent=self.parent, name='warehouse_service_lights')
        mounts = Entity(parent=self.parent, name='warehouse_light_mounts')
        z = -((GRID_HEIGHT + 2)/2) + .18
        for x in (-13, -6, 1, 8, 14):
            _piece(mounts, Vec3(x, 2.27, z), Vec3(2.6, .12, .22), DARK)
            _piece(strips, Vec3(x, 2.25, z-.14), Vec3(2.30, .06, .07),
                   (215, 206, 177))
        _batch(strips)
        _batch(mounts)
