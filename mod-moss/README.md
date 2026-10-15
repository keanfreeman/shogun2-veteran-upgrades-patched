# Veteran Upgrades: Patched Edition for MoSS

A single-player mod for **Total War: Shogun 2** with **Master of Strategy Sengoku (MoSS)**. It is the
[Patched Edition](../README.md) of Veteran Upgrades, built for MoSS's units and clans.

Your clan earns 1 point per battle and spends it on upgrades for each unit type:

- **Stats:** melee attack/defence, armour, morale, accuracy, charge, speed, reload, ammunition, range,
  bonus vs cavalry
- **Traits:** fire while hidden, camouflage, guerrilla deployment, fatigue resistance, Scare Enemies
- **Abilities**, with MoSS's names (Rally, Hold Firm, Rapid Volley, Flaming Arrows, Yari Wall, ...)

Upgrades apply at once to every unit of that type, including the ones already in your armies. AI clans
earn and spend points too.

**Status:** early. Stats, points and AI purchases have been seen working in game; abilities have not
been tested in game yet.

## You need

- Shogun 2 from Steam, on Windows (or Linux through Proton)
- MoSS's mandatory packs: Database, Files 1-4 and Original Clans (New Clans isn't supported)
- The game patch (included), version 4. Without it only the basic stats, Scare Enemies and fatigue
  resistance work.

**Use only one Veteran Upgrades mod at a time.** They all change the same game file, so only one would run.

## Install

1. Quit the game. Copy `veteran_upgrades_moss_patched.pack` into Shogun 2's `data` folder.
2. Patch the game: run `patcher/Install patch.bat` (Linux: `python3 patcher/patch_game.py install`).
   It should say "Patched (patch version 4)" or "Already patched."
3. In the launcher, enable MoSS's packs and `veteran_upgrades_moss_patched`, then start a **new**
   Sengoku Jidai campaign.
4. On the campaign map, click **Veterans** (below the advisor button).

Some abilities also need their usual MoSS research or general's skill; the tooltip says which.

## Before playing multiplayer

The patch changes a game file, and online play uses Valve Anti-Cheat. The mod switches the multiplayer
buttons off, but **restore the game before going online**: run `patcher/Restore game.bat`, or Steam's
"Verify integrity of game files".

## Problems

Attach `vu_log.txt` from the game folder when reporting a problem.

## For developers

`veteran_upgrades/build.py` is the Patched Edition's build (`../mod`) with the data handling of
[Veteran Upgrades for MoSS](https://github.com/keanfreeman/shogun2-veteran-upgrades-moss): it reads
the game's data with MoSS's packs laid over it, and only offers abilities that work under MoSS
(see `fits()`). `vu.lua` is the Patched Edition's.

```
python veteran_upgrades/build.py      # needs the game with MoSS's packs and RPFM's schema (see ../mod/README.md)
python tests/run_tests.py
```

Without the game, build from a recorded snapshot: `python ../tools/snapshot.py replay <snapshot> -- veteran_upgrades/build.py`.
