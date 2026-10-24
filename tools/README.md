# Building the data

How `data/` gets made from the game cache, so you can check it or rebuild it after a game update. It takes about 10 minutes the first time (mostly building rs3cache and dumping the cache) and under a minute after that.

## 1. Build rs3cache

[rs3cache](https://github.com/mejrs/rs3cache) (mejrs, MIT) decodes the cache. It's written in Rust, so you'll need [Rust](https://rustup.rs) installed. It needs a patch for four object config opcodes added since it was last updated, otherwise dumping the object configs fails.

```
git clone https://github.com/mejrs/rs3cache
cd rs3cache
git checkout d96a12b
git apply path/to/collision-map/tools/rs3cache.patch
cargo build --release --bin rs3 --features=rs3
```

The repo pins its own nightly Rust version, and rustup fetches it on the first build.

## 2. Copy the cache

Only three of the cache files are needed. Copy them from your RuneScape cache folder (`C:\ProgramData\Jagex\RuneScape` on Windows) into a folder called `cache` inside the rs3cache folder. Work on copies, since the game might be running and holding the originals open:

- `js5-5`: map squares (each square's tiles and the objects placed on them)
- `js5-16`: object configs (size, and whether they block)
- `js5-2`: general configs rs3cache needs alongside them

The game downloads the whole map in the background, so a cache from a client you've played on for a while should have every square.

## 3. Dump it

```
cargo run --release --bin rs3 --features=rs3 -- --input cache --output dump --dump locations_each
cargo run --release --bin rs3 --features=rs3 -- --input cache --output dump --dump tiles_each
cargo run --release --bin rs3 --features=rs3 -- --input cache --output dump --dump location_configs
```

This writes `dump/tiles/`, `dump/locations/` and `dump/location_configs.json`. The tiles are pretty-printed JSON and come to about 11 GB.

## 4. Build the collision

This step needs Python 3. From this repo's folder:

```
python tools/world.py path/to/dump
```

This replaces everything in `data/`. For each map square, `build.py` works out the collision from the rules in the main README's "How it's made", and `encode.py` turns it into the compact strings the plugin reads. To compare a rebuild with the current data instead, add `--output` with another folder and compare the two folders afterwards.

## The data format

Each file in `data/` is named after the group of 4×4 map squares it holds: square `sx, sz` is in `data/<sx // 4>_<sz // 4>.lua`. The file returns a Lua table keyed by the square's place in its group, `(sx % 4) * 4 + sz % 4`, and each entry holds four strings, one per level:

```lua
return {[6]={"BBEBA-_D","","",""}}
```

A level with no collision is an empty string. A square with no collision at all is left out, and a group with none gets no file.

Each string is the level's 4,096 tiles in order (x outer, z inner: index `x * 64 + z` within the square), stored as runs of identical tiles:

1. **One character for the tile's value**, its collision bits from 0 to 31: 1 blocked, 2 north wall, 4 east, 8 south, 16 west. The characters are the 64-letter [base64url](https://www.rfc-editor.org/rfc/rfc4648#section-5) alphabet, `A` = 0 up to `_` = 63, so the strings sit in plain Lua quotes.
2. **The run length, 5 bits per character**, lowest bits first. A character of 32 or more means another one follows (the same idea as [LEB128](https://en.wikipedia.org/wiki/LEB128) varints, with 5-bit chunks instead of 7).

Decoding `"BBEBA-_D"`:

| Characters | Meaning |
|---|---|
| `B` `B` | value 1 (blocked), run of 1 tile |
| `E` `B` | value 4 (east wall), run of 1 tile |
| `A` `-_D` | value 0 (nothing), run of 30 + 31×32 + 3×1024 = 4,094 tiles |

1 + 1 + 4,094 = 4,096: the whole level. This is [run-length encoding](https://en.wikipedia.org/wiki/Run-length_encoding), and most of the map is long runs of open ground or solid rock, so it's small to begin with. Zipping it (deflate) takes it the rest of the way, to about 1.4 MB for the whole map.

## The files

| File | What it does |
|---|---|
| `rs3cache.patch` | Teaches rs3cache the new object config opcodes (206 to 209, and 108 to 111) |
| `build.py` | The collision rules: blocked tiles, bridges, walls by shape and rotation, object footprints |
| `encode.py` | Run-length encodes each square's tiles and groups 4×4 squares per file |
| `world.py` | Runs both over every square and writes `data/` |

One thing in `build.py` that comes from rs3cache rather than the game: an object's clip type (the API's `blockWalk`) is set by two config opcodes that rs3cache doesn't name, so it stores them as `unknown_17` and `unknown_27`. Opcode 17 means clip type 0 (doesn't block), 27 means clip type 1, and an object with neither has the default, 2.
