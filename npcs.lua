-- npcs.lua: NPCs that block the player, listed by hand
-- neither the cache nor the API says which NPCs block, so each entry was found in game
-- the game's route ignores them at first: the player walks up to one, and when the next step
-- would land on it the game routes again from there, round it (Large Jellyfish, 2026-10-24)
-- keyed by the NPC's current config ID: for a multi-NPC that's the form showing, not its parent
return {
    [22083] = "Large Jellyfish, underwater at 5192, 771",
    [31110] = "Icthlarin, Sanctum of Rebirth",
    [31098] = "Vermyx, Brood Mother, Sanctum of Rebirth hard mode",
    [31099] = "Coilspawn, Sanctum of Rebirth hard mode",
}
