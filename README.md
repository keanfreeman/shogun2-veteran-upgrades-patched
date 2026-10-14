# Shogun 2 ability patch (experimental)

A small patch to `empire.retail.dll` (Total War: Shogun 2, Steam/Windows build) that lets an effect
unlock a research-gated ability for **one unit type**. Units you already have gain it, with no unit
copies and no retraining. This is a local experiment for Veteran Upgrades; it is not distributed.

## How the engine decides abilities

When a battle is set up (and probably for unit cards), the campaign builds each unit's
`unit_capabilities` list in `FUN_1019e580` from its unit type's ability list (`unit_record + 0xfc`):

```c
for (ability in unit_record->abilities)
    if (!ability->requires_effect_enabling || BonusLookup(list, UNIT_ABILITY, ability, enable))
        grant(ability);
```

The bonus list is the clan/army's active effects, keyed by (category, record, bonus id). Abilities
are only keyed by ability, so vanilla can't enable one for a single unit type.

## What the patch does

At the "not enabled" branch (`0x1019e643`) it jumps to 76 bytes of new code in the unused tail of
`.text` (`0x115a0c40`), which:

1. converts the ability to its engine enum (`0x101b1670`) and maps it to a bit (`abilities.py`);
2. looks up the **unit type's** `general_aoe_mod` bonus (category 16, bonus id 9) in the same list;
3. grants the ability if that bit is set, otherwise skips it as before.

So the data side is ordinary effects: an effect with `general_aoe_mod` on a unit record, in a bundle
whose value is the bitmask (bit N = line N of `abilities.py`). The patch never touches abilities
whose `requires_effect_enabling` is False, nor the vanilla enable path.

197 bytes change: the 6-byte hook, the routine + 70-byte table, and `.text` VirtualSize
(0x159fc3e -> 0x159fe00) so the tail counts as code. Everything is position-independent (the DLL is
ASLR-enabled) and the patcher checks no relocation touches the hook.

## Use

```
python3 -m venv .venv && .venv/bin/pip install keystone-engine capstone pefile
.venv/bin/python patch.py show      # disassembly of the patch, changes nothing
.venv/bin/python patch.py status    # vanilla / patched / unknown
.venv/bin/python patch.py apply     # backs up empire.retail.dll.vanilla, then patches
.venv/bin/python patch.py restore   # puts the vanilla DLL back
```

It refuses any DLL other than the known vanilla build (sha256 `022fae2e...f874f5`). Steam's
"Verify integrity of game files" also restores the vanilla DLL.

## Test pack

`testpack/build_testpack.py [--install]` builds `ability_patch_test.pack` (needs the Veteran
Upgrades lab checkout for its DB tools; see the docstring for what it changes and what to expect).

## Caveats

- `general_aoe_mod` is borrowed as the signal. Vanilla uses it on generals' bodyguards (the aura
  radius); a bodyguard with an aura bonus and a gated ability attached would also read it as bits.
- Unverified: whether the bonus list there also includes the army's general (vanilla general skills
  that unlock Wedge suggest it does), and when the builder's unfiltered path runs (likely custom/MP).
