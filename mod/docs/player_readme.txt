VETERAN UPGRADES: PATCHED EDITION @VERSION@
Total War: Shogun 2 - single-player only

What it is
----------
Your clan earns points from battles and spends them on upgrades per unit type:
  - stats: melee attack and defence, armour, morale, accuracy, charge, speed, reload, ammunition,
    range, bonus vs cavalry
  - traits: fire while hidden, camouflage, guerrilla deployment, fatigue resistance, Scare Enemies
  - abilities such as War Cry, Rally, Inspire, Rapid Volley, Fire by Rank, Pike Wall or Wedge
Upgrades apply to every unit of that type, including the ones already in your armies.

Most upgrades need a small patch to the game (included); without it only the basic stats, Scare
Enemies and fatigue resistance work. This is NOT the Steam Workshop "Veteran Upgrades" mod - don't
enable both at once.

IMPORTANT - read before installing
----------------------------------
* The patch modifies one game file, empire.retail.dll. Shogun 2's multiplayer is protected by
  Valve Anti-Cheat, and modified game files can get a Steam account banned. While this mod is
  enabled its multiplayer buttons are switched off, and the patch switches drop-in battles off
  (other players joining your campaign battles, or you joining theirs). But the PATCH stays in the
  game files until you remove it: ALWAYS restore the game (see below) before playing multiplayer.
* It only works with the Steam Windows version of the game (Windows, or Linux through Proton). It
  does not work with the native Mac/Linux versions.
* The patcher only patches the exact game version it knows. If Steam updates the game, it refuses
  until a new version of this mod is released.
* Use at your own risk; this is an unofficial mod, not supported by Creative Assembly or SEGA.

Install
-------
1. Quit Shogun 2 (and its launcher).
2. Copy veteran_upgrades_patched.pack and veteran_upgrades_patched.png into the game's data
   folder, usually:  C:\Program Files (x86)\Steam\steamapps\common\Total War SHOGUN 2\data
3. Patch the game:
   Windows:  open the "patcher" folder and double-click "Install patch.bat".
             If Windows warns about the file, click "More info", then "Run anyway" (or, before
             unzipping, right-click the zip > Properties > tick "Unblock").
   Linux/Proton or with Python:  python3 patcher/patch_game.py install
   The patcher finds the game through Steam, checks the file, saves the original as
   empire.retail.dll.vanilla, and patches it. "Patch status.bat" shows whether it is patched.
   If it can't find the game: patch_game.ps1 -GameDir "<your Total War SHOGUN 2 folder>"
   (or --game-dir for the Python version).
4. Start the game's launcher, enable "veteran_upgrades_patched" in the mod list, and play.
   The "Veterans" button is below the advisor button on the campaign map. Unit types with many
   upgrades have a second page ("Page 1 of 2" in the panel's bottom bar).

Updating from 1.0: replace the two files in data, then run "Install patch.bat" again - version 2.0
needs patch version 4, and the patcher replaces the old patch. Your upgrades carry over.

Uninstall / before playing multiplayer
--------------------------------------
1. Quit the game.
2. Double-click "Restore game.bat" (or: python3 patcher/patch_game.py restore).
   Steam's "Verify integrity of game files" (Library > Shogun 2 > Properties > Installed Files)
   also restores the original file.
3. Disable the mod in the launcher (multiplayer needs everyone to have the same mods anyway).

Problems
--------
The mod writes vu_log.txt in the game folder - include it when reporting a problem.
