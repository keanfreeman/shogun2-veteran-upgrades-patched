# Veteran Upgrades: Patched Edition - Shogun 2 ability patch

A small patch to `empire.retail.dll` (Total War: Shogun 2, Steam/Windows build) that lets an effect
unlock an ability for **one unit type** in one clan. Units you already have gain it: no unit copies,
no retraining. A local experiment for Veteran Upgrades; not distributed.

## How the engine decides abilities

When a battle is set up (and for the pre-battle unit cards), the campaign builds each unit's
`unit_capabilities` in `FUN_1019e580` from its unit type's ability list (`unit_record + 0xfc`):

```c
for (ability in unit_record->abilities)
    if (!ability->requires_effect_enabling || BonusLookup(list, UNIT_ABILITY, ability, 0, enable))
        grant(ability);
```

The bonus list holds the clan/army's active effects, keyed (category, record, 0, bonus id). Ability
unlocks are keyed by ability only, so vanilla can't unlock one for a single unit type. Abilities are
a hard-coded engine list: an ability record with a new key is dropped when the battle maps names
to the engine enum.

## The clone design (patch v3)

A mod attaches a **clone** record to a unit type instead of the real ability:

| table | row |
|---|---|
| `unit_abilities` | `vu07_warcry`: copy of `warcry` with `supersedes_ability = warcry`, `requires_effect_enabling = True` |
| `unit_special_abilities`, `unit_info_card_abilities_strings` | copies of the real rows under the clone key (safety) |
| `unit_to_unit_abilities_junctions` | (unit, `vu07_warcry`) |

The key carries the bit: `vuNN_<ability>` (NN = 00-23). The unlock is an ordinary effect:
`general_aoe_mod` on the unit record, with the bundle value a bitmask (bonus values are floats, so 24
bits). Bits only need to be unique among the clones of one unit type, so any number of abilities can be
offered overall ([abilities.py](abilities.py) `assign_bits` colours them).

The patch hooks the "not enabled" branch. For a clone (key `vuNN_`/`vuNNf`, `supersedes` set) it
reads the unit type's `general_aoe_mod`; if bit NN is set, and the real ability's own research is
done if it needs any (Banzai, fire arrows, ...) - waived for `vuNNf...` keys, for abilities a campaign
has no research for - it grants the **real** ability in the clone's place. Everything else - real
abilities, native holders, generals, custom battles - behaves as vanilla. Without the patch, clones are
dropped by the engine, so a mod built this way is harmless on an unpatched game.

Patch layout (`patch.py show` prints it all):

- hook 1 `0x1019e643` (6 bytes): `je skip` -> `jmp routine 1`
- hook 2 `0x1019e6f2` (7 bytes): `mov edx,[esp+0x24]; add ebx,4` -> `jmp routine 2`
- routine 1 `0x115a0c40`: clone/key check, bitmask lookup, research check, substitution. The grant
  path appends `*ebx`, so `ebx` is pointed at a scratch local (`[esp+0x10]`, unused by the loop)
  holding the real ability; the cursor is saved in `[esp+0x14]`.
- routine 2 `0x115a0d20`: restores the cursor before the loop advances.
- signature `VU_ABILITY_PATCH 3` at `0x115a0d90` (file offset `0x15a0190`).
- `.text` VirtualSize 0x159fc3e -> 0x159fe00 so the tail counts as code.

All position-independent (the DLL is ASLR-enabled); the patcher checks no relocation touches a hook.

## Use

```
python3 -m venv .venv && .venv/bin/pip install keystone-engine capstone pefile
.venv/bin/python patch.py show      # disassembly, changes nothing
.venv/bin/python patch.py status    # vanilla / patched / patched (diagnostic) / unknown
.venv/bin/python patch.py apply     # backs up empire.retail.dll.vanilla, then patches from it
.venv/bin/python patch.py restore   # puts the vanilla DLL back
```

The patcher only works from the known vanilla build (sha256 `022fae2e...f874f5`); Steam's "Verify
integrity of game files" also restores vanilla.

Mods detect the patch with [detect.lua](detect.lua) (reads the signature from the DLL file).

## Test pack

`testpack/build_testpack.py [--install]` builds `ability_patch_test.pack`; its docstring lists what
to expect in game. Needs the Veteran Upgrades lab checkout for its DB tools.

## Player patchers (`player/`)

What players run - no installs needed, and no modified DLL is ever distributed: the patchers carry
only our bytes and edit the player's own copy.

- `patch_game.ps1` + `Install patch.bat` / `Restore game.bat` / `Patch status.bat`: Windows
  PowerShell 5.1+ (built into Windows 10/11); the .bat files run it with `-ExecutionPolicy Bypass`.
- `patch_game.py`: any Python 3 (Linux/Proton, or Windows with Python).

Both find the game through Steam (`libraryfolders.vdf`; `-GameDir` / `--game-dir` to override), only
patch the exact vanilla DLL (SHA-256), back it up as `empire.retail.dll.vanilla`, verify the result's
hash, and refuse unknown DLLs unless forced. They are generated from `patch.py` by
`tools/make_patchers.py` (templates in `tools/patcher_templates/`); `--check` verifies they're current.

## Veteran Upgrades: Patched Edition (`mod/`)

A copy of Veteran Upgrades 1.1.0 that uses the patch instead of unit copies (see `mod/README.md`):
`cd mod/veteran_upgrades && <lab venv python> build.py` builds `veteran_upgrades_patched.pack`;
`<lab venv python> mod/tests/run_tests.py` runs its tests (patched and unpatched).
`cd mod && <lab venv python> tools/release.py` builds the release: `mod/dist/` and
`Veteran Upgrades - Patched Edition <version>.zip` (pack, thumbnail, `patcher/`, player README).
While enabled, the mod switches the main menu's multiplayer buttons off ("Off to keep your account safe").

## Results

- 2026-10-14, v1 (gated real abilities): Shimazu Yari Ashigaru gained War Cry, Second Wind, Rapid
  Advance (bit / aoe / melee rules) and Stand Firm (always) in the pre-battle preview and in battle;
  other clans' Yari Ashigaru only Stand Firm.
- 2026-10-14, edition (patch v2): abilities bought in the panel appeared on existing units in battle.
- v3 (bits in the clone key, research waiver, every-unit catalogue): pending.
- 2026-10-14, v2 (clones, diagnostic build): Shimazu Yari Ashigaru had War Cry, Second Wind, Rapid
  Advance and Stand Firm in battle; Banzai (bit set, not researched) correctly absent.
