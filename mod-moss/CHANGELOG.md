# Changelog

## Patched Edition for MoSS 1.0.0 (not yet tested in game)
First version: the Patched Edition 2.0.0's mechanics for Master of Strategy Sengoku, with the data
handling of Veteran Upgrades for MoSS 1.1.0. Needs patch version 4 (the Patched Edition's, included).
- Sengoku Jidai only, built from the game's data with MoSS's Database and Original Clans packs laid
  over it: MoSS's recruitable units (same-name variants such as the Ikko Ikki ones form one unit type),
  MoSS's names and portraits, MoSS's clans (its added clans too); the list sorts each column by
  recruitment building tier, then cost.
- Abilities as the Patched Edition's clone lines on the units you already have: no unit copies,
  recruitment locks or retraining, and AI clans buy abilities too.
- Abilities follow MoSS: its names (Flaming Arrows, High Volley, Rapid Volley for guns, ...) and
  research; nothing MoSS switched off (the bow Rapid Volley); arrow and grenade abilities only for bow
  and sling units; formations and kit only for the kinds of unit that carry them in MoSS, yari
  formations only for spear units; the multiplayer trees' range skills give no ability (MoSS's
  range_effect is Flaming Arrows), the Range stat covers range.
- Stat prices are relative to MoSS's units (the spread of each stat over the unit types covered).
- The multiplayer buttons' labels ship in a small loc file of their own
  (vu_ui_component_localisation.loc), so MoSS's ui_component_localisation.loc is left alone.
- Don't enable it together with any other Veteran Upgrades pack.
