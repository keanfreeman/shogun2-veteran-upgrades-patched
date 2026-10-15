# Changelog

## Patched Edition 2.0.0
Needs patch version 4 (included; run `Install patch.bat` again when updating from 1.0).
- New stat upgrades per unit type: Charge, Speed, Reload, Ammunition, Range (metres added to the
  unit's range) and Bonus vs Cavalry (foot melee units).
- New traits: Fire While Hidden, Camouflage (hide in every terrain), Guerrilla Deployment, Fatigue
  Resistant (no patch needed).
- Fire by Rank for every foot unit with a musket or rifle.
- Drop-in battles are off: the patch stops invitations and hosting, and the mod hides the pre-battle
  drop-in button.
- Upgrade panel pages: unit types with more than 24 upgrades get a second page (nothing is dropped).
- Pricing: the same upgrade costs the same in every campaign; fixed steps per stat (the multiplayer
  trees' steps made similar units pay up to double); one-level traits 6-10 points; Range, Reload and
  Speed priced up for their value.
- Sharper ability icons (the 51x51 battle buttons instead of 22x22 icons).

## Patched Edition 1.0.0
First release: Veteran Upgrades 1.1.0 for a game patched to grant abilities per unit type (patch
version 3). Abilities as effect bundles on existing units, every ability that suits a unit, AI buys
abilities, multiplayer buttons switched off.


## 1.1.0
- Compatibility with overhauls that replace the campaign scripts (e.g. Master of Strategy Sengoku):
  the mod no longer ships `scripting.lua`; its code is appended to `export_advice.lua` instead.
- Unit, effect and effect-bundle names ship as separate `vu_*.loc` files instead of full copies of
  the game's, so other mods' texts are no longer replaced.
- Unit copies use `unique_index` 31000+ (they collided with ten of MoSS's new units).
- Debug builds (`VU_DEBUG=1`): engine-call trace, `vu_skip.txt`, 100 points per session.

## 1.0.0 (2026-10-07)
First public release.
- Clan-wide veteran upgrades for every recruitable land unit type, built from the multiplayer
  skill trees; units without one borrow the tree of a unit of the same class.
- Sengoku Jidai, Rise of the Samurai and Fall of the Samurai.
- Clan points: 1 per battle fought; repeatable stat upgrades priced by value; abilities as unit
  copies with recruitment switching; Retrain one army or all armies; respec for 2 points.
- AI clans earn and spend points on stat upgrades.
