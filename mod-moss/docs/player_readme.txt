VETERAN UPGRADES: PATCHED EDITION FOR MoSS @VERSION@
Total War: Shogun 2 + Master of Strategy Sengoku (MoSS) - single-player only

What it is
----------
The Patched Edition of Veteran Upgrades for MoSS's units and clans. Your clan earns points from
battles and spends them on upgrades per unit type:
  - stats: melee attack and defence, armour, morale, accuracy, charge, speed, reload, ammunition,
    range, bonus vs cavalry
  - traits: fire while hidden, camouflage, guerrilla deployment, fatigue resistance, Scare Enemies
  - abilities, with MoSS's names: Inspire Unit, Hold Firm, Rally, Warcry, Banzai, Rapid Volley,
    Flaming Arrows, Whistling Arrows, Yari Wall, Stealth and more
Upgrades apply to every unit of that type, including the ones already in your armies.

Most upgrades need a small patch to the game (included); without it only the basic stats, Scare
Enemies and fatigue resistance work.

Not tested in game yet: this first version was built and tested without the game. Please report
problems (see the end).

Needs
-----
* MoSS's mandatory packs, enabled in the launcher: MoSS_Must_database.pack, MoSS_Must_files_1.pack
  to MoSS_Must_files_4.pack and MoSS_Must_clans_Original_PICK_ONLY_ONE.pack (Original Clans; the
  New Clans pack isn't supported).
* The Sengoku Jidai campaign; start a new campaign after enabling the mod.
* ONLY ONE Veteran Upgrades mod: don't enable this together with veteran_upgrades_patched.pack,
  veteran_upgrades_moss.pack or the Workshop's Veteran Upgrades. They all add their code to the same
  game file (export_advice.lua), so only one of them would run.

IMPORTANT - read before installing
----------------------------------
* The patch modifies one game file, empire.retail.dll. Shogun 2's multiplayer is protected by
  Valve Anti-Cheat, and modified game files can get a Steam account banned. While this mod is
  enabled its multiplayer buttons are switched off, and the patch switches drop-in battles off
  (other players joining your campaign battles, or you joining theirs). But the PATCH stays in the
  game files until you remove it: ALWAYS restore the game (see below) before playing multiplayer.
* It only works with the Steam Windows version of the game (Windows, or Linux through Proton).
* The patcher only patches the exact game version it knows. If Steam updates the game, it refuses
  until a new version of this mod is released.
* Use at your own risk; this is an unofficial mod, not supported by Creative Assembly or SEGA, and
  not made by MoSS's authors.

Install
-------
1. Quit Shogun 2 (and its launcher).
2. Copy veteran_upgrades_moss_patched.pack and veteran_upgrades_moss_patched.png into the game's
   data folder, usually:  C:\Program Files (x86)\Steam\steamapps\common\Total War SHOGUN 2\data
3. Patch the game (the same patch as the Patched Edition's; "Already patched." if it is):
   Windows:  open the "patcher" folder and double-click "Install patch.bat".
             If Windows warns about the file, click "More info", then "Run anyway" (or, before
             unzipping, right-click the zip > Properties > tick "Unblock").
   Linux/Proton or with Python:  python3 patcher/patch_game.py install
   If it can't find the game: patch_game.ps1 -GameDir "<your Total War SHOGUN 2 folder>"
   (or --game-dir for the Python version).
4. Start the game's launcher, enable MoSS's packs and "veteran_upgrades_moss_patched", and start a
   new Sengoku Jidai campaign. The "Veterans" button is below the advisor button on the campaign map.

Uninstall / before playing multiplayer
--------------------------------------
1. Quit the game.
2. Double-click "Restore game.bat" (or: python3 patcher/patch_game.py restore).
   Steam's "Verify integrity of game files" also restores the original file.
3. Disable the mod in the launcher.

Problems
--------
The mod writes vu_log.txt in the game folder - include it when reporting a problem.
