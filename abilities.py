"""Abilities the patch can unlock per unit type, and the bit each one uses.

The patch reads a unit type's `general_aoe_mod` bonus (unit_record scope) as a bitmask: if bit N is
set, the ability on line N is granted to that unit type even when its clan/army hasn't enabled it.
Bonus values are floats, so at most 24 bits (exact integers up to 2^24).

The enum values come from the engine's hard-coded ability list (empire.retail.dll, name/value pairs
at 0x115b3b98); `requires_effect_enabling` must be True on these abilities for the gate to run.
"""

# (ability key, engine enum value); the list position is the bit.
ABILITIES = [
    ("warcry", 45),
    ("rally", 36),
    ("inspire_unit", 35),
    ("stand_firm", 44),
    ("rapid_volley", 40),
    ("range_effect", 34),
    ("banzai", 32),
    ("blinding_grenade", 22),
    ("flaming_arrows_ability", 23),
    ("flaming_arrows_long_range_ability", 24),
    ("flaming_arrows_extreme_range_ability", 25),
    ("whistling_arrows_ability", 26),
    ("whistling_arrows_long_range_ability", 27),
    ("whistling_arrows_extreme_range_ability", 28),
    ("second_wind", 41),
    ("rapid_advance", 39),
    ("kneel_fire_ability", 57),
    ("suppression_fire", 61),
    ("wedge_formation", 2),
    ("we_stand_and_fight", 43),
    ("pike_wall_formation", 6),
    ("spear_wall", 42),
    ("cantabrian_circle", 9),
    ("active_hiding", 29),
]
assert len(ABILITIES) <= 24

ENUM_COUNT = 70  # values 0..69 (69 = "none")


def bit(ability):
    """The bit (0-23) for an ability key."""
    return [k for k, _ in ABILITIES].index(ability)


# Rule per table entry (top 3 bits of the byte; low 5 bits = the ability's bit):
MODE_BIT = 0         # grant if the unit type's general_aoe_mod has this ability's bit (the real rule)
MODE_ALWAYS = 1      # diagnostic: always grant (proves the routine runs for this ability)
MODE_AOE_ANY = 2     # diagnostic: grant if general_aoe_mod is non-zero (proves that lookup works)
MODE_MELEE_ANY = 3   # diagnostic: grant if melee_attack_mod is non-zero (proves unit_record lookups work)

# Diagnostic build (patch.py apply --diag): see testpack/build_testpack.py for what each one tests.
DIAG_MODES = {"stand_firm": MODE_ALWAYS, "second_wind": MODE_AOE_ANY, "rapid_advance": MODE_MELEE_ANY}


def enum_to_bit_table(modes=None):
    """70-byte lookup: engine enum value -> (mode << 5) | bit, 0xFF if the patch doesn't handle it."""
    modes = modes or {}
    table = bytearray([0xFF] * ENUM_COUNT)
    for i, (key, enum) in enumerate(ABILITIES):
        table[enum] = (modes.get(key, MODE_BIT) << 5) | i
    return bytes(table)
