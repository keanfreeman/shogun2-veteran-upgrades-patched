# Veteran Upgrades: Patched Edition

*A single-player mod for **Total War: Shogun 2***

[![Verify patchers](https://github.com/keanfreeman/shogun2-veteran-upgrades-patched/actions/workflows/verify.yml/badge.svg)](https://github.com/keanfreeman/shogun2-veteran-upgrades-patched/actions/workflows/verify.yml)

Your clan earns points from every battle it fights and spends them on **upgrades for each unit type**:
better stats, Scare Enemies, and **battle abilities** such as War Cry, Rally, Inspire, Rapid Volley,
Pike Wall or Wedge. Upgrades apply to every unit of that type straight away - including the units
already in your armies. AI clans earn and spend points too. Works in all three campaigns (Sengoku,
Rise of the Samurai, Fall of the Samurai).

Giving abilities to one unit type isn't something the game normally allows, so this edition comes with
a **small, reversible patch** to one game file. Without the patch the mod still works, but only for stats.

> Looking for the version on the Steam Workshop? That's [Veteran Upgrades](https://github.com/keanfreeman/shogun2-veteran-upgrades),
> which needs no patch and works in a different way. Don't enable both at once.

## Before you start

- You need the **Steam version of Shogun 2 on Windows** (or on Linux through Steam's Proton).
  The native Mac and Linux versions aren't supported.
- **Single-player only.** Shogun 2's multiplayer uses Valve Anti-Cheat, and a changed game file could
  get your Steam account banned. The mod turns the multiplayer buttons off while it's enabled, and you
  must **restore the game before playing multiplayer** (see [Uninstalling](#uninstalling--before-playing-multiplayer)).
- If Steam updates the game, the patcher may refuse to run until this mod is updated too. That's on
  purpose: it only patches the exact game version it was made for.

## Installing

1. **Download** the latest zip from the [Releases page](https://github.com/keanfreeman/shogun2-veteran-upgrades-patched/releases)
   (under "Assets": `Veteran-Upgrades-Patched-Edition-<version>.zip`).
2. **Unblock it** (Windows): right-click the zip → **Properties** → tick **Unblock** → OK.
   This stops Windows warning about the patcher later. Then extract the zip.
3. **Quit Shogun 2** and its launcher.
4. **Copy the mod into the game.** Put `veteran_upgrades_patched.pack` and `veteran_upgrades_patched.png`
   into the game's `data` folder. To find it: in Steam, right-click Shogun 2 → **Manage** →
   **Browse local files**, then open `data`. Usually that's
   `C:\Program Files (x86)\Steam\steamapps\common\Total War SHOGUN 2\data`.
5. **Patch the game.** In the extracted `patcher` folder, double-click **`Install patch.bat`**.
   A window opens and should end with *"Patched (patch version 3)"*. Press a key to close it.
   - If Windows says *"Windows protected your PC"*, click **More info** → **Run anyway**.
   - If it says *Shogun 2 not found*, see [Troubleshooting](#troubleshooting).
6. **Enable the mod.** Start Shogun 2 from Steam; in the launcher's mod list, tick
   **veteran_upgrades_patched** and play.

**Linux / Proton:** do steps 1, 3, 4 and 6 the same way; for step 5 run
`python3 patcher/patch_game.py install` in the extracted folder.

## Playing

- On the campaign map, a **Veterans** button sits below the advisor button. It lists your unit types;
  pick one to open its upgrade tree.
- Click upgrades to choose them, then **OK** (✓) to buy. **Reset** refunds everything for that unit
  type for a small fee.
- You earn **1 point per battle** your clan fights in, win or lose.
- A few abilities also need what normally unlocks them - for example Yari Square needs the
  *Spear Expertise* research, and Stand and Fight needs a general with the *Infantry Leader* skill.
  The upgrade's tooltip says so.

## Uninstalling / before playing multiplayer

1. Quit the game.
2. In the `patcher` folder, double-click **`Restore game.bat`** (Linux: `python3 patcher/patch_game.py restore`).
   Steam's **Verify integrity of game files** (right-click Shogun 2 → Properties → Installed Files)
   also puts the original file back.
3. Untick the mod in the launcher. (To remove it completely, delete the two files from `data`.)

`Patch status.bat` tells you whether the game is currently patched.

## Troubleshooting

| Problem | What to do |
|---|---|
| *"Shogun 2 not found"* | Run the patcher with your game folder: open PowerShell in the `patcher` folder and run `powershell -ExecutionPolicy Bypass -File patch_game.ps1 install -GameDir "D:\SteamLibrary\steamapps\common\Total War SHOGUN 2"` (your path). |
| *"Refusing: the game DLL is unknown"* | Your game version differs from the one this release supports (usually a Steam update). Run Steam's *Verify integrity of game files* and try again; if it still refuses, wait for an updated release. |
| *"Shogun 2 is running"* | Quit the game and its launcher first. |
| No Veterans button / no intro movie | Fully restart the game after installing or updating the mod, and make sure only one Veteran Upgrades mod is enabled. |
| Abilities show *"Needs the game patch"* | The patch isn't installed (or Steam restored the file): run `Install patch.bat` again. |
| Anything else | Open an [issue](https://github.com/keanfreeman/shogun2-veteran-upgrades-patched/issues) and attach `vu_log.txt` from the game folder. |

---

## Is it safe? What exactly does the patch change?

The patcher ([player/](player/)) is two short, readable scripts - nothing compiled, nothing downloaded:

- **It changes one file:** the game's `empire.retail.dll`, after saving the original next to it as
  `empire.retail.dll.vanilla`. 348 bytes change in four places; [docs/PATCH.md](docs/PATCH.md) lists
  every one, disassembled and explained. It writes nothing else (apart from a temporary copy it
  renames into place) and no registry keys; it only *reads* Steam's install path to find the game.
- **It only patches the exact game file it knows** (checked by SHA-256 before and after) and refuses
  anything else, such as a file changed by a Steam update.
- **It's reversible:** `Restore game.bat` (or Steam's "Verify integrity of game files") puts the
  original back.
- **No network, no admin rights, no other programs:** the scripts never connect anywhere, download,
  or start anything. Windows' PowerShell is used only to read and write that one file.
- **No modified game file is distributed.** The patchers contain only our own bytes and edit your
  own copy.

**Checking it yourself.** The bytes in the patchers come from the readable assembly in
[patch.py](patch.py). [tools/verify_patchers.py](tools/verify_patchers.py) re-assembles that source and
checks the patchers contain exactly those bytes at those places, and nothing that reaches the network,
launches programs, writes the registry or decodes hidden code. It needs no game files and runs on every
change (the badge at the top). Each release lists SHA-256 checksums of its files (`SHA256SUMS.txt`).

This is an unofficial mod, not supported by Creative Assembly or SEGA. Use it at your own risk.

## Why patch the game at all?

Shogun 2 can unlock an ability for a whole clan (through research) or a whole army (through a general's
skill), but never for one unit type, and its list of abilities is fixed inside the game's code. The
regular Workshop mod works around that by adding upgraded *copies* of units, which you have to recruit
or retrain into (losing veterancy). The patch adds the one missing check to the game, so the units you
already have simply gain the ability. How that works is below.

---

## For developers

### How the game decides a unit's abilities

When a battle is set up (and for the pre-battle unit cards), the campaign builds each unit's
`unit_capabilities` in `FUN_1019e580` from its unit type's ability list (`unit_record + 0xfc`):

```c
for (ability in unit_record->abilities)
    if (!ability->requires_effect_enabling || BonusLookup(list, UNIT_ABILITY, ability, 0, enable))
        grant(ability);
```

The bonus list holds the clan/army's active effects, keyed (category, record, 0, bonus id). Ability
unlocks are keyed by ability only, so the game can't unlock one for a single unit type. Abilities are
a hard-coded engine list: an ability record with a new key is dropped when the battle maps names to the
engine's enum.

### The clone design (patch v3)

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
reads the unit type's `general_aoe_mod`; if bit NN is set, and the real ability's own research is done
if it needs any (Banzai, fire arrows, ...) - waived for `vuNNf...` keys, for abilities a campaign has no
research for - it grants the **real** ability in the clone's place. Everything else - real abilities,
native holders, generals, custom battles - behaves as vanilla. Without the patch, clones are dropped by
the engine, so a mod built this way is harmless on an unpatched game.

Patch layout ([docs/PATCH.md](docs/PATCH.md) has the full disassembly):

- hook 1 `0x1019e643` (6 bytes): `je skip` -> `jmp routine 1`
- hook 2 `0x1019e6f2` (7 bytes): `mov edx,[esp+0x24]; add ebx,4` -> `jmp routine 2`
- routine 1 `0x115a0c40`: clone/key check, bitmask lookup, research check, substitution. The grant
  path appends `*ebx`, so `ebx` is pointed at a scratch local (`[esp+0x10]`, unused by the loop)
  holding the real ability; the cursor is saved in `[esp+0x14]`.
- routine 2 `0x115a0d20`: restores the cursor before the loop advances.
- signature `VU_ABILITY_PATCH 3` at `0x115a0d90` (file offset `0x15a0190`); mods detect the patch with
  [detect.lua](detect.lua).
- `.text` VirtualSize 0x159fc3e -> 0x159fe00 so the section's unused tail counts as code.

All position-independent (the DLL is ASLR-enabled); the patcher checks no relocation touches a hook.

### Repository layout

| Path | What |
|---|---|
| [patch.py](patch.py) | Developer patcher: the patch as readable assembly (assembled with keystone), plus `show` / `status` / `apply` / `restore` |
| [player/](player/) | What players run: `patch_game.ps1` + `.bat` launchers (Windows PowerShell 5.1+), `patch_game.py` (Python 3). Generated by `tools/make_patchers.py`; no dependencies |
| [tools/verify_patchers.py](tools/verify_patchers.py) | Re-assembles the patch and checks `player/` and `docs/PATCH.md` against it (CI) |
| [abilities.py](abilities.py), [detect.lua](detect.lua) | Clone keys and bit assignment; patch detection for mod scripts |
| [mod/](mod/) | The mod: a copy of Veteran Upgrades 1.1.0 using the patch (`mod/README.md`) |
| [testpack/](testpack/) | A minimal test mod for the patch (`build_testpack.py`) |

### Building

```
python3 -m venv .venv && .venv/bin/pip install keystone-engine capstone pefile
.venv/bin/python patch.py show                 # the patch, disassembled (changes nothing)
.venv/bin/python patch.py apply|restore|status # patch your own game (needs the vanilla DLL)
.venv/bin/python tools/make_patchers.py        # regenerate player/ after changing the patch
.venv/bin/python tools/verify_patchers.py      # check player/ + docs/PATCH.md (--write-doc rewrites the doc)
```

The mod itself is built with the Veteran Upgrades tooling (it reads the game's data packs and RPFM's
schema, which isn't redistributed): `cd mod && <python with requirements> tools/release.py` builds the
release (`mod/dist/` and the zip), and `mod/tests/run_tests.py` runs its tests against a mock engine.

### Test history

- v1 (gated real abilities): Shimazu Yari Ashigaru gained War Cry, Second Wind, Rapid Advance and Stand
  Firm in the pre-battle preview and in battle; other clans' Yari Ashigaru didn't.
- v2 (clones): the same, with nothing vanilla changed; Banzai (bit set, not researched) correctly absent.
  The mod's purchases appeared on existing units in battle.
- v3 (bit in the clone key, any number of abilities): abilities bought in the mod appeared on existing
  units; abilities needing research or a general's skill stayed off until unlocked.
