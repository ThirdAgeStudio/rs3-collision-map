ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
CHARACTER_VALUES = {character: value for value, character in enumerate(ALPHABET)}

SQUARE_SIZE = 64
TILES_PER_LEVEL = SQUARE_SIZE * SQUARE_SIZE
LEVELS = 4
GROUP_SIZE = 4
MAX_TILE_VALUE = 31
CORNER_SHIFT = 5
RUN_CHUNK_BITS = 5
RUN_CHUNK_MASK = (1 << RUN_CHUNK_BITS) - 1
MORE_CHUNKS_FOLLOW = 1 << RUN_CHUNK_BITS


def encode_run_length(length):
    characters = []
    while True:
        chunk = length & RUN_CHUNK_MASK
        length >>= RUN_CHUNK_BITS
        characters.append(ALPHABET[chunk | (MORE_CHUNKS_FOLLOW if length else 0)])
        if not length:
            return "".join(characters)


def encode_level(values):
    if not any(values):
        return ""
    parts = []
    start = 0
    while start < TILES_PER_LEVEL:
        value = values[start]
        end = start
        while end < TILES_PER_LEVEL and values[end] == value:
            end += 1
        parts.append(ALPHABET[value] + encode_run_length(end - start))
        start = end
    return "".join(parts)


def decode_level(text):
    values = []
    position = 0
    while position < len(text):
        value = CHARACTER_VALUES[text[position]]
        position += 1
        length = shift = 0
        while True:
            chunk = CHARACTER_VALUES[text[position]]
            position += 1
            length |= (chunk & RUN_CHUNK_MASK) << shift
            shift += RUN_CHUNK_BITS
            if chunk < MORE_CHUNKS_FOLLOW:
                break
        values.extend([value] * length)
    return values or [0] * TILES_PER_LEVEL


def level_values(square_x, square_z, tiles, shift):
    values = [0] * TILES_PER_LEVEL
    for (x, z), bits in tiles.items():
        value = bits >> shift
        if value << shift != bits or value > MAX_TILE_VALUE:
            raise ValueError(f"tile {x},{z} has bits {bits}, which the format can't hold")
        values[(x - square_x * SQUARE_SIZE) * SQUARE_SIZE + (z - square_z * SQUARE_SIZE)] = value
    return values


def square_strings(square_x, square_z, walls, corners=None):
    corners = corners or {}
    wall_strings = [encode_level(level_values(square_x, square_z, walls.get(level, {}), 0)) for level in range(LEVELS)]
    corner_strings = [encode_level(level_values(square_x, square_z, corners.get(level, {}), CORNER_SHIFT))
                      for level in range(LEVELS)]
    if not any(wall_strings) and not any(corner_strings):
        return None
    return wall_strings + corner_strings if any(corner_strings) else wall_strings


def group_key(square_x, square_z):
    return f"{square_x // GROUP_SIZE}_{square_z // GROUP_SIZE}"


def index_in_group(square_x, square_z):
    return (square_x % GROUP_SIZE) * GROUP_SIZE + square_z % GROUP_SIZE


def group_files(squares):
    groups = {}
    for (square_x, square_z), strings in sorted(squares.items()):
        quoted = ",".join(f'"{string}"' for string in strings)
        entry = f"[{index_in_group(square_x, square_z)}]={{{quoted}}}"
        groups.setdefault(group_key(square_x, square_z), []).append(entry)
    return {f"{key}.lua": f"return {{{','.join(entries)}}}\n" for key, entries in groups.items()}
