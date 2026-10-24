ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
CHARACTER_VALUES = {character: value for value, character in enumerate(ALPHABET)}

SQUARE_SIZE = 64
TILES_PER_LEVEL = SQUARE_SIZE * SQUARE_SIZE
LEVELS = 4
GROUP_SIZE = 4
MAX_TILE_VALUE = 31
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


def square_strings(square_x, square_z, levels):
    strings = []
    for level in range(LEVELS):
        values = [0] * TILES_PER_LEVEL
        for (x, z), bits in levels.get(level, {}).items():
            if bits > MAX_TILE_VALUE:
                raise ValueError(f"tile {x},{z} level {level} has bits {bits}, more than the format holds")
            values[(x - square_x * SQUARE_SIZE) * SQUARE_SIZE + (z - square_z * SQUARE_SIZE)] = bits
        strings.append(encode_level(values))
    return strings if any(strings) else None


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
