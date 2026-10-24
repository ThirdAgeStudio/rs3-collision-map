import json
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

SQUARE_SIZE = 64
LEVELS = 4

BLOCKED = 1
NORTH, EAST, SOUTH, WEST = 2, 4, 8, 16
WALL_SIDE_BY_ROTATION = {0: WEST, 1: NORTH, 2: EAST, 3: SOUTH}
NEXT_SIDE_CLOCKWISE = {WEST: NORTH, NORTH: EAST, EAST: SOUTH, SOUTH: WEST}

STRAIGHT_WALL = 0
L_WALLS = {2, 23}
DIAGONAL_WALL = 9
CENTREPIECES = {10, 11}
GROUND_DECORATION = 22
FOOTPRINT_SHAPES = {DIAGONAL_WALL, GROUND_DECORATION, *CENTREPIECES}

TILE_BLOCKED_SETTING = 0x1
BRIDGE_SETTING = 0x2
BRIDGE_LEVEL = 1

NEIGHBOURS_REACHING_IN = ((-1, 0), (0, -1), (-1, -1))

CLIP_TYPE_0_FLAG = "unknown_17"
CLIP_TYPE_1_FLAG = "unknown_27"
DEFAULT_CLIP_TYPE = 2


class ObjectConfig(NamedTuple):
    width: int
    length: int
    clip_type: int


class PlacedObject(NamedTuple):
    config_id: int
    x: int
    z: int
    level: int
    shape: int
    rotation: int


class Square(NamedTuple):
    settings: list
    objects: list


def clip_type(config):
    if CLIP_TYPE_0_FLAG in config:
        return 0
    if CLIP_TYPE_1_FLAG in config:
        return 1
    return DEFAULT_CLIP_TYPE


def read_json(path):
    with open(path) as file:
        return json.load(file)


def square_names(dump_folder):
    return sorted(tuple(map(int, path.stem.split("_"))) for path in (Path(dump_folder) / "tiles").glob("*.json"))


class MapDump:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.configs = {
            config["id"]: ObjectConfig(config.get("dim_x") or 1, config.get("dim_y") or 1, clip_type(config))
            for config in read_json(self.folder / "location_configs.json")
        }
        self.square = lru_cache(maxsize=32)(self.load_square)

    def load_square(self, square_x, square_z):
        name = f"{square_x}_{square_z}.json"
        tiles_path = self.folder / "tiles" / name
        objects_path = self.folder / "locations" / name
        settings = [tile["settings"] or 0 for tile in read_json(tiles_path)["data"]] if tiles_path.exists() else []
        objects = [
            PlacedObject(placed["id"], square_x * SQUARE_SIZE + placed["x"], square_z * SQUARE_SIZE + placed["y"],
                         placed["plane"], placed["type"], placed["rotation"])
            for placed in (read_json(objects_path) if objects_path.exists() else [])
        ]
        return Square(settings, objects)


def tile_setting(settings, level, local_x, local_z):
    if not settings:
        return 0
    return settings[(level * SQUARE_SIZE + local_x) * SQUARE_SIZE + local_z]


def footprint(placed, config):
    if placed.rotation in (1, 3):
        return config.length, config.width
    return config.width, config.length


def blocks_walking(placed, config):
    if placed.shape == GROUND_DECORATION:
        return config.clip_type == 1
    return config.clip_type != 0


def collide_square(dump, square_x, square_z):
    origin_x, origin_z = square_x * SQUARE_SIZE, square_z * SQUARE_SIZE
    collision = {}

    def add(level, x, z, bits):
        if origin_x <= x < origin_x + SQUARE_SIZE and origin_z <= z < origin_z + SQUARE_SIZE:
            tiles = collision.setdefault(level, {})
            tiles[(x, z)] = tiles.get((x, z), 0) | bits

    def add_object(placed):
        config = dump.configs[placed.config_id]
        if placed.level < 0 or not blocks_walking(placed, config):
            return
        if placed.shape == STRAIGHT_WALL:
            add(placed.level, placed.x, placed.z, WALL_SIDE_BY_ROTATION[placed.rotation])
        elif placed.shape in L_WALLS:
            side = WALL_SIDE_BY_ROTATION[placed.rotation]
            add(placed.level, placed.x, placed.z, side | NEXT_SIDE_CLOCKWISE[side])
        elif placed.shape in FOOTPRINT_SHAPES:
            width, length = footprint(placed, config)
            for dx in range(width):
                for dz in range(length):
                    add(placed.level, placed.x + dx, placed.z + dz, BLOCKED)

    square = dump.square(square_x, square_z)
    for level in range(LEVELS):
        for local_x in range(SQUARE_SIZE):
            for local_z in range(SQUARE_SIZE):
                if tile_setting(square.settings, level, local_x, local_z) & TILE_BLOCKED_SETTING:
                    under_bridge = tile_setting(square.settings, BRIDGE_LEVEL, local_x, local_z) & BRIDGE_SETTING
                    walking_level = level - 1 if under_bridge else level
                    if walking_level >= 0:
                        add(walking_level, origin_x + local_x, origin_z + local_z, BLOCKED)

    for placed in square.objects:
        add_object(placed)

    for offset_x, offset_z in NEIGHBOURS_REACHING_IN:
        for placed in dump.square(square_x + offset_x, square_z + offset_z).objects:
            if placed.shape in FOOTPRINT_SHAPES:
                add_object(placed)

    return collision
