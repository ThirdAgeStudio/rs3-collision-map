-- main.lua: Collision Map: walking collision for map squares, derived offline from the game
-- cache (tools/collision), for plugins that path on the client's tiles
-- it does nothing by itself: a plugin lists it as a dependency and asks about tiles or squares
-- the main.lua return value is what dependents see, cloned per dependent
-- the collision is the map's static collision: live doors and gates, and objects the server
-- spawns, come from the API (LocList) and are the dependent's to add

-- one data file per group of 4x4 map squares, data/<gx>_<gz>.lua (gx = sx // 4), returning a table
-- keyed by (sx % 4) * 4 + sz % 4, each entry four strings (levels 0-3): grouped because a zip pays
-- per file, so one file per square doubled the download
-- a square with wall corners that change movement has four more strings (levels 0-3 again) for them
-- each string run-length encodes the square's 4,096 tiles, x-major with z fastest: a character
-- for the tile's collision bits, then the run length as a varint (5 bits a character, 32 = more
-- follows), in the 64-letter alphabet below (tools/collision/encode.py writes it)
-- bits: 1 blocked, 2 north wall, 4 east, 8 south, 16 west
-- a corner string holds a tile's corners shifted down by 5, so it fits the same alphabet: 32 NW,
-- 64 NE, 128 SE and 256 SW once shifted back
-- the files hold the whole map, so a group is only read, and a level decoded, the first time
-- it's asked for; a square missing from its group has no collision (open ground, or nothing there)
local FORMAT = 2
local NPCS = require("npcs")
local ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

local VALUE = {}
for i = 1, #ALPHABET do VALUE[ALPHABET:byte(i)] = i - 1 end

local files = {}
local decoded = {}
local MISSING = {}

-- turns one level's run string into the flat x, z, bits list of its non-zero tiles
local function decode(text, sx, sz, valueShift)
    local out, n = {}, 0
    local pos, index, length = 1, 0, #text
    local x0, z0 = sx * 64, sz * 64
    while pos <= length do
        local value = VALUE[text:byte(pos)]
        pos = pos + 1
        local run, shift = 0, 0
        repeat
            local c = VALUE[text:byte(pos)]
            pos = pos + 1
            run = run | ((c & 31) << shift)
            shift = shift + 5
        until c < 32
        if value ~= 0 then
            for k = index, index + run - 1 do
                out[n + 1], out[n + 2], out[n + 3] = x0 + k // 64, z0 + k % 64, value << valueShift
                n = n + 3
            end
        end
        index = index + run
    end
    return out
end

local GROUP = 4

local function file(sx, sz)
    local key = (sx // GROUP) .. "_" .. (sz // GROUP)
    local data = files[key]
    if data == nil then
        local ok, result = pcall(require, "data/" .. key)
        data = (ok and type(result) == "table") and result or MISSING
        files[key] = data
    end
    if data == MISSING then return nil end
    return data[(sx % GROUP) * GROUP + sz % GROUP]
end

local CORNER_SHIFT = 5

-- ORs a second x, z, bits list into the first: a tile with corners usually has no walls, so most
-- corners are new entries
local function merge(list, extra)
    local at = {}
    for i = 1, #list - 2, 3 do at[list[i] * 65536 + list[i + 1]] = i end
    for i = 1, #extra - 2, 3 do
        local key = extra[i] * 65536 + extra[i + 1]
        local existing = at[key]
        if existing ~= nil then
            list[existing + 2] = list[existing + 2] | extra[i + 2]
        else
            list[#list + 1], list[#list + 2], list[#list + 3] = extra[i], extra[i + 1], extra[i + 2]
        end
    end
    return list
end

-- the flat x, z, bits list for one level of one map square, or nil when it has no collision
-- callers must not change the list: it's shared with every other caller
local function square(level, sx, sz)
    local key = level .. "_" .. sx .. "_" .. sz
    local list = decoded[key]
    if list == nil then
        local data = file(sx, sz)
        local text = data and data[level + 1]
        list = (type(text) == "string" and text ~= "") and decode(text, sx, sz, 0) or {}
        local corners = data and data[level + 5]
        if type(corners) == "string" and corners ~= "" then list = merge(list, decode(corners, sx, sz, CORNER_SHIFT)) end
        if #list == 0 then list = MISSING end
        decoded[key] = list
    end
    if list == MISSING then return nil end
    return list
end

-- per-tile lookups: a square's list turned into a table keyed by local tile (lx * 64 + lz), built
-- the first time a tile in that square is asked about
local tiles = {}

local BLOCKED = 1
local SIDE = { N = 2, E = 4, S = 8, W = 16 }
local OPPOSITE = { [SIDE.N] = SIDE.S, [SIDE.S] = SIDE.N, [SIDE.E] = SIDE.W, [SIDE.W] = SIDE.E }
local CORNER = { NW = 32, NE = 64, SE = 128, SW = 256 }
local OPPOSITE_CORNER = { [CORNER.NW] = CORNER.SE, [CORNER.SE] = CORNER.NW, [CORNER.NE] = CORNER.SW, [CORNER.SW] = CORNER.NE }

-- a tile's collision bits (1 blocked, 2 north wall, 4 east, 8 south, 16 west, then corners 32 NW,
-- 64 NE, 128 SE, 256 SW), 0 when it has none
local function bits(level, x, z)
    local sx, sz = x >> 6, z >> 6
    local key = level .. "_" .. sx .. "_" .. sz
    local map = tiles[key]
    if map == nil then
        map = {}
        local list = square(level, sx, sz)
        if list ~= nil then
            for i = 1, #list - 2, 3 do map[(list[i] & 63) * 64 + (list[i + 1] & 63)] = list[i + 2] end
        end
        tiles[key] = map
    end
    return map[(x & 63) * 64 + (z & 63)] or 0
end

-- whether a tile can't be stood on
local function blocked(level, x, z)
    return bits(level, x, z) & BLOCKED ~= 0
end

-- whether a wall stands on one side of a tile; side is "N", "E", "S" or "W"
-- a wall is stored on one tile only, so the neighbour across it doesn't report it: canMove
-- checks both
local function wall(level, x, z, side)
    local bit = SIDE[side]
    return bit ~= nil and bits(level, x, z) & bit ~= 0
end

local function sideOf(dx, dz)
    if dx == 1 then return SIDE.E elseif dx == -1 then return SIDE.W
    elseif dz == 1 then return SIDE.N else return SIDE.S end
end

local function orthogonal(level, x, z, dx, dz)
    local side = sideOf(dx, dz)
    return bits(level, x, z) & side == 0 and bits(level, x + dx, z + dz) & (OPPOSITE[side] | BLOCKED) == 0
end

local function cornerOf(dx, dz)
    if dz == 1 then return dx == 1 and CORNER.NE or CORNER.NW end
    return dx == 1 and CORNER.SE or CORNER.SW
end

-- whether one step from x, z by dx, dz (each -1, 0 or 1) is open, by the client's rule: a straight
-- step needs no wall on the edge crossed and an unblocked tile to land on; a diagonal step needs
-- both straight steps round its corner open, so it never cuts past a blocked tile or a wall
-- a corner piece (a post or pillar) also stops a diagonal through its corner, though its tile
-- can be stood on; it's stored on one of the two tiles the diagonal joins, so both are checked
local function canMove(level, x, z, dx, dz)
    if dx == 0 and dz == 0 then return true end
    if dx == 0 or dz == 0 then return orthogonal(level, x, z, dx, dz) end
    local corner = cornerOf(dx, dz)
    return orthogonal(level, x, z, dx, 0) and orthogonal(level, x, z, 0, dz)
        and orthogonal(level, x + dx, z, 0, dz) and orthogonal(level, x, z + dz, dx, 0)
        and bits(level, x, z) & corner == 0 and bits(level, x + dx, z + dz) & OPPOSITE_CORNER[corner] == 0
end

-- whether an NPC blocks the player's steps, by its current config ID (npcs.lua)
local function blocksNpc(configID)
    return NPCS[configID] ~= nil
end

return {
    format = FORMAT,
    -- the raw data for one 64x64 map square on one level: a flat x, z, bits list, or nil
    square = square,
    bits = bits,
    blocked = blocked,
    wall = wall,
    canMove = canMove,
    blocksNpc = blocksNpc,
    BLOCKED = BLOCKED,
    SIDE = SIDE,
    CORNER = CORNER,
}
