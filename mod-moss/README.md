# Veteran Upgrades: Patched Edition for MoSS

*A single-player mod for **Total War: Shogun 2** with the **Master of Strategy Sengoku (MoSS)** overhaul*

> **Not tested in game yet.** Version 1.0.0 is built and tested against a recording of the game's and
> MoSS's data, on a mock of the campaign engine. Nobody has played it yet. Until someone has (see
> [What still needs a play test](#what-still-needs-a-play-test)), expect rough edges.

This is the [Patched Edition](../README.md) of Veteran Upgrades rebuilt for MoSS's units and clans.
Your clan earns points from every battle it fights and spends them on **upgrades for each unit type**:

- **Stats:** melee attack and defence, armour, morale, accuracy, charge, speed, reload, ammunition,
  range and bonus vs cavalry.
- **Traits:** fire while hidden, camouflage (hide in any terrain), guerrilla deployment, fatigue
  resistance and Scare Enemies.
- **Battle abilities**, under the names MoSS gives them: Inspire Unit, Hold Firm, Rally, Warcry,
  Banzai, Rapid Volley (MoSS's version, for guns and some bows), Flaming Arrows, Whistling Arrows,
  Yari Wall, Stealth and more. A unit type is only offered abilities that work for it under MoSS (see below).

Upgrades apply to every unit of that type straight away, including the units already in your armies.
There are no "(Upgraded)" unit copies and no retraining. AI clans (MoSS's added clans too) earn and
spend points as well.

Like the Patched Edition, most of this needs a **small, reversible patch** to one game file (the same
patch, version 4). Without it the mod still works, but only for the basic stats (melee attack and
defence, armour, morale, accuracy), Scare Enemies and fatigue resistance.

## Before you start

- You need the **Steam version of Shogun 2 on Windows** (or on Linux through Steam's Proton).
- You need **MoSS's mandatory packs**: subscribe to them on the Steam Workshop and enable them in the
  launcher, so that these are in the game's `data` folder:
  `MoSS_Must_database.pack`, `MoSS_Must_files_1.pack` to `MoSS_Must_files_4.pack` and
  `MoSS_Must_clans_Original_PICK_ONLY_ONE.pack` (**Original Clans**; MoSS's New Clans pack isn't supported).
- **Sengoku Jidai campaign only.** Start a new campaign after enabling the mod.
- **Use only one Veteran Upgrades mod.** Don't enable this together with the Patched Edition
  (`veteran_upgrades_patched.pack`), Veteran Upgrades for MoSS (`veteran_upgrades_moss.pack`), the
  Workshop's Veteran Upgrades, or any other Veteran Upgrades pack: they all add their code to the same
  game file (`export_advice.lua`), so only one of them would run.
- **Single-player only.** Shogun 2's multiplayer uses Valve Anti-Cheat, and a changed game file could
  get your Steam account banned. The mod turns the multiplayer buttons off while it's enabled, the patch
  switches drop-in battles off, and you must **restore the game before playing multiplayer** (see
  [Uninstalling](#uninstalling--before-playing-multiplayer)).

## Installing

1. **Get the release zip** (`Veteran-Upgrades-Patched-Edition-for-MoSS-<version>.zip`) and extract it.
   On Windows, first right-click the zip → **Properties** → tick **Unblock** → OK.
2. **Quit Shogun 2** and its launcher.
3. **Copy the mod into the game:** put `veteran_upgrades_moss_patched.pack` and
   `veteran_upgrades_moss_patched.png` into the game's `data` folder (in Steam: right-click Shogun 2 →
   **Manage** → **Browse local files**, then open `data`).
4. **Patch the game:** in the extracted `patcher` folder, double-click **`Install patch.bat`**
   (Linux/Proton: `python3 patcher/patch_game.py install`). It should end with *"Patched (patch version 4)"*.
   It is the same patcher as the Patched Edition's; if your game is already patched to version 4,
   it says *"Already patched."* and changes nothing.
5. **Enable the mods:** in the launcher's mod list, tick MoSS's packs and
   **veteran_upgrades_moss_patched**, and start a new Sengoku Jidai campaign.

## Playing

- On the campaign map, a **Veterans** button sits below the advisor button. It lists the unit types
  your clan can recruit under MoSS, cheapest buildings first; pick one to open its upgrade tree.
- Click upgrades to choose them, then **OK** (✓) to buy. **Reset** refunds everything for that unit
  type for a small fee. Unit types with many upgrades have a second page: click **Page 1 of 2** in the
  bottom bar.
- You earn **1 point per battle** your clan fights in, win or lose.
- Some abilities also need what normally unlocks them in MoSS: for example Yari Square needs the
  *Yari Tactics I* research and Rapid Volley *Gunpowder Mastery*. The upgrade's tooltip names it.

## Uninstalling / before playing multiplayer

1. Quit the game.
2. In the `patcher` folder, double-click **`Restore game.bat`** (Linux: `python3 patcher/patch_game.py restore`).
   Steam's **Verify integrity of game files** also puts the original file back.
3. Untick the mod in the launcher.

## Compatibility

- MoSS's Original Clans pack: the mod's copy of `text\db\ui_component_localisation.loc` (for the
  multiplayer buttons' labels) is made from that pack's own copy, so MoSS's texts stay. Other clan
  packs, and mods that change that file, the main-menu layout (`ui\frontend ui\main`) or
  `export_advice.lua`, conflict.
- Unit types are MoSS's: the build reads MoSS's database. A MoSS update that adds or renames units
  needs a new build of this mod.

## What still needs a play test

Built and tested only against recorded data and a mock engine. To check in game:

- MoSS's renamed abilities are granted as the abilities their names say: Flaming Arrows (`range_effect`,
  bows only), High Volley (`flaming_arrows_ability`), Rapid Volley (`suppression_fire`, including on
  bow units), Stealth (`active_hiding`) on the unit types that MoSS doesn't give it to.
- Gated abilities stay off until the MoSS research or general's skill the tooltip names (Yari Tactics I/II,
  Advanced Battle Tactics, Gunpowder Mastery, Kabura-Ya, Infantry Leader / Inspirator).
- Unit portraits and ability icons in the panel (MoSS's own icons for Flaming Arrows, High Volley and
  Rapid Volley). Five unit types have no portrait of their own and show a stat icon: Benkei's Blades,
  Seigen's Swordmasters, Gozen's Hime Heroines, Tokitaka's Tanegashima, Komo Morutaru.
- AI clans, MoSS's added ones included, earn points and buy upgrades.
- The multiplayer buttons' labels read "Off to keep your account safe" with MoSS's texts elsewhere
  intact.
- Prices: stats are priced against MoSS's units, which makes Bonus vs Cavalry dear (MoSS's spears have
  at most +10).

---

## For developers

The Patched Edition's build (`../mod`) with the data handling of
[Veteran Upgrades for MoSS](https://github.com/keanfreeman/shogun2-veteran-upgrades-moss) 1.1.0.
Same patch (version 4, `../patch.py`, `../abilities.py`, `../detect.lua`), same clone design (see the
repository README), same `vu.lua`.

From the MoSS edition (`veteran_upgrades/build.py`):

- **Overlay:** `MOSS_PACKS` (the clans pack, then the database pack - order matters, see its comment)
  laid over the game's packs by `tools_db.OVERLAY` (`tools_db.py` here supports it); `UI_PACKS`
  (the game's packs, MoSS's and its Files 1-4) for portraits and ability icons.
- **Units:** the units MoSS's buildings recruit (`building_units_allowed`); same-name, same-class units
  form one unit type (MoSS's `_ikko` variants); units without a multiplayer tree borrow one of their
  class; unit types no clan can recruit are dropped. Names from MoSS's loc files. Each list column is
  sorted by recruitment building tier, then cost; mounted units go under Cavalry.
- **Clans:** `VU_FACTIONS` from MoSS's factions table, so MoSS's added clans are included.
- **Abilities (`fits()`):** a gated ability nothing in MoSS enables isn't offered (MoSS switched off the
  bow Rapid Volley and Spear Square Formation); an ability that swaps the projectile only for the
  matching weapon (MoSS's `range_effect` fires flaming arrows: bows only); one name per unit type (MoSS
  gives several abilities the same name). Formations and kit (`RULE_SAME_KIND`) only for the kinds of
  unit that carry them among the units MoSS recruits; the kind includes the melee weapon, and the yari
  formations need a spear. The multiplayer trees' range skills no longer become `range_effect`
  ("Increased Range" in vanilla, "Flaming Arrows" in MoSS); the Range stat line covers range.
- **Research:** the tooltips' "Only usable once you also have" names MoSS's technologies and skills
  (from its loc files). Abilities only the custom-battle tech enables would get the research waiver
  (`vuNNf`); under MoSS no offered ability needs it.
- Not carried over: unit copies, recruitment locks, Retrain, the single "Abilities" line (`ab_all`),
  copy encyclopedia pages, the copies' names.

From the Patched Edition: stats, traits and their pricing, the RULE_* abilities and their prices
(MoSS's repurposed ones priced as what they became), two pages, drop-in hiding, multiplayer off,
AI purchasing (abilities too), saves keyed by line key, `needs_patch` gating. **Stat prices** use the
spread of each stat over the unit types this edition covers (as the MoSS edition), not over every
land unit of the game.

### Building and testing

Needs Python 3.10+, `pip install -r requirements.txt`, RPFM's Shogun 2 schema and the game with
MoSS's packs in `data` (see `../mod/README.md` for `RPFM_SCHEMA` / `SHOGUN2_DATA`). Without the game,
build from a recorded snapshot (kept private, see `../tools/snapshot.py`):

```
python ../tools/snapshot.py replay <snapshot> -- veteran_upgrades/build.py   # or just veteran_upgrades/build.py with the game
python tests/run_tests.py
```

`tests/run_tests.py` loads the built pack's `export_advice.lua` against a mock engine: the full flows
with MoSS's Yari and Yumi Ashigaru on a patched and an unpatched game, data checks (MoSS's ability
names and research, no unit copies), and a smoke test for Shimazu, the Ikko Ikki and Akamatsu (one of
MoSS's clans). `tools/release.py` builds a release zip like the Patched Edition's (needs the game:
the thumbnail uses its unit art). `VU_DEBUG=1` builds log the panel to `vu_log.txt`
(`tools/vu_ui_audit.py`).
Engine notes (what crashes it, what merges): `../mod/docs/ENGINE_NOTES.md`.
