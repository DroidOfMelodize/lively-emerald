#!/usr/bin/env python3
"""
Lively Emerald - decorative ambient Pokemon.

Ambient Pokemon are ordinary object events with a Pokemon overworld sprite, no script
(so the player cannot interact with them) and one of the movement types
MOVEMENT_TYPE_AMBIENT_WANDER / MOVEMENT_TYPE_AMBIENT_PERCH. In-game they only ever
step onto tiles of the same kind as their spawn tile (blocked, water or open ground),
see GetAmbientTileClass() in src/event_object_movement.c.

The placements live in tools/lively/ambient_pokemon.json. This script

    python3 tools/lively/ambient_pokemon.py apply     # write them into data/maps/*/map.json
    python3 tools/lively/ambient_pokemon.py check     # validate without writing
    python3 tools/lively/ambient_pokemon.py show MAP  # print a map's tile grid

`apply` replaces every previously generated ambient object on the listed maps, so it can
be re-run safely after editing the JSON. Generated objects are recognised by their
local_id prefix LOCALID_AMBIENT_.

Validation rules for every placement:
  * the spawn tile and every tile the Pokemon can reach inside its movement range
    belong to the same tile class as the spawn tile (blocked, water or open)
  * "open" spawns must not be reachable by the player (flood fill from warps and map
    connections), otherwise the player could bump into a Pokemon it cannot talk to
  * no two ambient Pokemon start on the same tile, and none starts on another object
"""
import collections
import json
import os
import re
import struct
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CONFIG = os.path.join(ROOT, 'tools', 'lively', 'ambient_pokemon.json')
LOCALID_PREFIX = 'LOCALID_AMBIENT_'
NUM_METATILES_IN_PRIMARY = 512
MOVEMENT_TYPES = {'wander': 'MOVEMENT_TYPE_AMBIENT_WANDER', 'perch': 'MOVEMENT_TYPE_AMBIENT_PERCH'}

OPEN, BLOCKED, WATER = 'open', 'blocked', 'water'


def _metatile_behaviors():
    text = open(os.path.join(ROOT, 'include', 'constants', 'metatile_behaviors.h')).read()
    value, names = 0, {}
    for name, explicit in re.findall(r'^\s*(MB_[A-Z0-9_]+)\s*(?:=\s*(\w+))?,', text, re.M):
        if explicit:
            value = int(explicit, 0)
        names[value] = name
        value += 1
    return names


BEHAVIORS = _metatile_behaviors()
# Mirrors MetatileBehavior_IsSurfableFishableWater() in src/metatile_behavior.c
SURFABLE = {'MB_POND_WATER', 'MB_OCEAN_WATER', 'MB_INTERIOR_DEEP_WATER', 'MB_DEEP_WATER',
            'MB_SOOTOPOLIS_DEEP_WATER', 'MB_EASTWARD_CURRENT', 'MB_WESTWARD_CURRENT',
            'MB_NORTHWARD_CURRENT', 'MB_SOUTHWARD_CURRENT'}
JUMPS = {'MB_JUMP_SOUTH': (0, 1), 'MB_JUMP_NORTH': (0, -1), 'MB_JUMP_EAST': (1, 0), 'MB_JUMP_WEST': (-1, 0)}


def _tileset_dir(symbol):
    name = re.sub(r'^gTileset_', '', symbol)
    name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    for kind in ('primary', 'secondary'):
        path = os.path.join(ROOT, 'data', 'tilesets', kind, name)
        if os.path.isdir(path):
            return path
    raise FileNotFoundError(f'tileset {symbol}')


def _u16s(path):
    data = open(path, 'rb').read()
    return struct.unpack('<%dH' % (len(data) // 2), data)


class Grid:
    def __init__(self, layout_id):
        layouts = json.load(open(os.path.join(ROOT, 'data', 'layouts', 'layouts.json')))['layouts']
        lay = next(l for l in layouts if l.get('id') == layout_id)
        self.w, self.h = lay['width'], lay['height']
        blocks = _u16s(os.path.join(ROOT, lay['blockdata_filepath']))
        primary = _u16s(os.path.join(_tileset_dir(lay['primary_tileset']), 'metatile_attributes.bin'))
        secondary = _u16s(os.path.join(_tileset_dir(lay['secondary_tileset']), 'metatile_attributes.bin'))
        self.cells = {}
        for y in range(self.h):
            for x in range(self.w):
                b = blocks[y * self.w + x]
                mt = b & 0x3FF
                attr = primary[mt] if mt < NUM_METATILES_IN_PRIMARY else secondary[mt - NUM_METATILES_IN_PRIMARY]
                self.cells[(x, y)] = (mt, (b >> 10) & 3, b >> 12, BEHAVIORS.get(attr & 0xFF, ''))

    def inside(self, p):
        return p in self.cells

    def tile_class(self, p):
        mt, col, elev, beh = self.cells[p]
        if beh in SURFABLE:
            return WATER
        if col:
            return BLOCKED
        return OPEN

    def player_reachable(self, map_json):
        """Tiles the player can walk on (ledges respected, surf/bike tricks ignored)."""
        def walkable(p):
            return self.inside(p) and self.tile_class(p) == OPEN

        def elevation_ok(a, b):
            ea, eb = self.cells[a][2], self.cells[b][2]
            return ea in (0, 15) or eb in (0, 15) or ea == eb

        seeds = {(w['x'], w['y']) for w in map_json['warp_events']}
        edges = {'up': [(x, 0) for x in range(self.w)], 'down': [(x, self.h - 1) for x in range(self.w)],
                 'left': [(0, y) for y in range(self.h)], 'right': [(self.w - 1, y) for y in range(self.h)]}
        for conn in map_json.get('connections') or []:
            seeds.update(p for p in edges.get(conn['direction'], []) if walkable(p))
        seen = {p for p in seeds if self.inside(p)}
        queue = collections.deque(seen)
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, y + dy)
                if not self.inside(n) or n in seen:
                    continue
                if JUMPS.get(self.cells[n][3]) == (dx, dy):
                    landing = (n[0] + dx, n[1] + dy)
                    if walkable(landing) and landing not in seen:
                        seen.add(landing)
                        queue.append(landing)
                elif walkable(n) and elevation_ok((x, y), n):
                    seen.add(n)
                    queue.append(n)
        return seen

    def render(self, marks=()):
        marks = dict(marks)
        lines = ['    ' + ''.join(str(x % 10) for x in range(self.w))]
        for y in range(self.h):
            row = ''
            for x in range(self.w):
                if (x, y) in marks:
                    row += marks[(x, y)]
                    continue
                cls = self.tile_class((x, y))
                row += {WATER: '~', BLOCKED: '#'}.get(cls, '"' if self.cells[(x, y)][3] == 'MB_TALL_GRASS' else '.')
            lines.append(f'{y:3d} ' + row)
        return '\n'.join(lines)


def map_path(name):
    return os.path.join(ROOT, 'data', 'maps', name, 'map.json')


def species_exists(species):
    text = open(os.path.join(ROOT, 'include', 'constants', 'species.h')).read()
    return re.search(r'(#define\s+|^\s*)SPECIES_%s\b' % re.escape(species), text, re.M) is not None


def build_objects(map_name, map_json, placements, errors):
    grid = Grid(map_json['layout'])
    reachable = grid.player_reachable(map_json)
    occupied = {(o['x'], o['y']) for o in map_json['object_events']
                if not str(o.get('local_id', '')).startswith(LOCALID_PREFIX)}
    used = set()
    objects = []
    for i, p in enumerate(placements, 1):
        where = f'{map_name} #{i} ({p["species"]} at {p["x"]},{p["y"]})'
        pos = (p['x'], p['y'])
        movement = p.get('movement', 'wander')
        rx, ry = (p.get('range_x', 1), p.get('range_y', 1)) if movement == 'wander' else (0, 0)
        if movement not in MOVEMENT_TYPES:
            errors.append(f'{where}: unknown movement "{movement}"')
            continue
        if not species_exists(p['species']):
            errors.append(f'{where}: unknown species')
        if not grid.inside(pos):
            errors.append(f'{where}: outside the map')
            continue
        cls = grid.tile_class(pos)
        if cls == OPEN and pos in reachable:
            errors.append(f'{where}: open tile the player can reach')
        if pos in occupied or pos in used:
            errors.append(f'{where}: tile already taken by another object')
        used.add(pos)
        # Every tile in range that has the spawn tile's class must also be unreachable for open spawns.
        for x in range(pos[0] - rx, pos[0] + rx + 1):
            for y in range(pos[1] - ry, pos[1] + ry + 1):
                q = (x, y)
                if grid.inside(q) and grid.tile_class(q) == cls and cls == OPEN and q in reachable:
                    errors.append(f'{where}: movement range touches player-reachable ground at {x},{y}')
        objects.append({
            'local_id': f'{LOCALID_PREFIX}{map_name.upper()}_{i}',
            'graphics_id': f'OBJ_EVENT_GFX_SPECIES({p["species"]})',
            'x': p['x'],
            'y': p['y'],
            'elevation': grid.cells[pos][2] if grid.cells[pos][2] not in (0, 15) else 3,
            'movement_type': MOVEMENT_TYPES[movement],
            'movement_range_x': rx,
            'movement_range_y': ry,
            'trainer_type': 'TRAINER_TYPE_NONE',
            'trainer_sight_or_berry_tree_id': '0',
            'script': '0x0',
            'flag': '0',
        })
    return grid, objects


def run(apply):
    config = json.load(open(CONFIG))
    errors = []
    for map_name, placements in config['maps'].items():
        path = map_path(map_name)
        map_json = json.load(open(path))
        _, objects = build_objects(map_name, map_json, placements, errors)
        if apply:
            kept = [o for o in map_json['object_events'] if not str(o.get('local_id', '')).startswith(LOCALID_PREFIX)]
            map_json['object_events'] = kept + objects
            with open(path, 'w', newline='\n') as f:
                json.dump(map_json, f, indent=2, ensure_ascii=False)
                f.write('\n')
        print(f'{map_name}: {len(objects)} ambient Pokemon')
    for e in errors:
        print('ERROR:', e)
    return 1 if errors else 0


def show(map_name):
    map_json = json.load(open(map_path(map_name)))
    grid = Grid(map_json['layout'])
    marks = {(o['x'], o['y']): ('A' if str(o.get('local_id', '')).startswith(LOCALID_PREFIX) else 'o')
             for o in map_json['object_events']}
    print(grid.render(marks))
    print('legend: # blocked  ~ water  " tall grass  . open  o object  A ambient Pokemon')


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] in ('apply', 'check'):
        sys.exit(run(sys.argv[1] == 'apply'))
    if len(sys.argv) == 3 and sys.argv[1] == 'show':
        show(sys.argv[2])
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
