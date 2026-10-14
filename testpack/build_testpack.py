"""Build ability_patch_test.pack: data for in-game tests of the DLL patch.

Vanilla Sengoku campaign as Shimazu, no other mods. Nothing vanilla is changed: the pack adds CLONE
ability records (abilities.clone_key) and attaches them to Yari Ashigaru (and one to Yari Samurai
as a control). Shimazu's clan trait bundle (t_shimazu) sets general_aoe_mod on Yari Ashigaru to the
bits of War Cry and Banzai.

Expected with the patch, on Shimazu Yari Ashigaru (old and new units):
  War Cry   bit set                          -> granted
  Banzai    bit set, but research not done   -> NOT granted (until Banzai is researched)
Other clans' Yari Ashigaru and everyone's Yari Samurai: nothing new. Warrior monks keep their own
War Cry. Without the patch: nothing changes at all.

Usage: <lab venv python> testpack/build_testpack.py [--install]
Needs the Veteran Upgrades lab checkout for its DB/pack tools (SHOGUN2_LAB, default ~/projects/shogun2_modding).
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LAB = os.environ.get("SHOGUN2_LAB", os.path.expanduser("~/projects/shogun2_modding"))
sys.path[:0] = [ROOT, LAB]

from abilities import clone_key as _clone_key
from tools_db import GAME_DATA, encode, load_file, extract
from tools_loc import read_loc, write_loc
from tools_packwrite import write_pack

DATA = os.path.join(GAME_DATA, "data.pack")
LOCAL = os.path.join(GAME_DATA, "local_en.pack")
PACK = "ability_patch_test.pack"
NAME = "abpatch_test"

GRANTED_UNIT = "Inf_Spear_Yari_Ashigaru"
CONTROL_UNIT = "Inf_Spear_Yari_Samurai"
CLAN_BUNDLE = "t_shimazu"
BIT_ABILITIES = ["warcry", "banzai"]   # bits 0 and 1, both set for Shimazu Yari Ashigaru
PROBES = []
CONTROL_ABILITY = "warcry"
EFFECT = "abpatch_test_yari_bits"
MELEE_EFFECT = "abpatch_test_yari_melee"


def bit(ability):
    return BIT_ABILITIES.index(ability)


def clone_key(ability):
    return _clone_key(bit(ability), ability)


def vanilla(table):
    return load_file(DATA, f"db\\{table}\\{table[:-len('_tables')]}")


def ours(table, rows):
    """A separately named table file with only our rows (merges with vanilla)."""
    ver, header, _ = vanilla(table)
    return f"db\\{table}\\{NAME}", encode(table, ver, rows, header)


def clone_rows(table, abilities, edit=None):
    """Copies of the real abilities' rows in `table`, keyed by the clone key."""
    _, _, rows = vanilla(table)
    by_key = {r["key"]: r for r in rows}
    out = []
    for a in abilities:
        if a in by_key:
            r = dict(by_key[a], key=clone_key(a))
            out.append(edit(r, a) if edit else r)
    return out


def build():
    clones = sorted(set(BIT_ABILITIES + PROBES + [CONTROL_ABILITY]))
    _, _, effects = vanilla("effects_tables")
    template = next(r for r in effects if r["effect"] == "clan_trait_shimazu_cheap_samurai")
    mask = sum(1 << bit(a) for a in BIT_ABILITIES)
    ability_rows = clone_rows("unit_abilities_tables", clones,
                              lambda r, a: dict(r, supersedes_ability=a, requires_effect_enabling=True))
    assert len(ability_rows) == len(clones)
    files = [
        ours("unit_abilities_tables", ability_rows),
        ours("unit_special_abilities_tables", clone_rows("unit_special_abilities_tables", clones)),
        ours("unit_info_card_abilities_strings_tables", clone_rows("unit_info_card_abilities_strings_tables", clones)),
        ours("unit_to_unit_abilities_junctions_tables",
             [{"unit_name": GRANTED_UNIT, "ability": clone_key(a)} for a in BIT_ABILITIES + PROBES]
             + [{"unit_name": CONTROL_UNIT, "ability": clone_key(CONTROL_ABILITY)}]),
        ours("effects_tables", [dict(template, effect=EFFECT), dict(template, effect=MELEE_EFFECT)]),
        ours("effect_bonus_value_unit_record_junctions_tables", [
            {"bonus_value_id": "general_aoe_mod", "effect": EFFECT, "unit_record_key": GRANTED_UNIT},
            {"bonus_value_id": "melee_attack_mod", "effect": MELEE_EFFECT, "unit_record_key": GRANTED_UNIT},
        ]),
        ours("effect_bundles_to_effects_junctions_tables", [
            {"effect_bundle_key": CLAN_BUNDLE, "effect_key": EFFECT, "value": float(mask)},
            {"effect_bundle_key": CLAN_BUNDLE, "effect_key": MELEE_EFFECT, "value": 1.0},
        ]),
    ]
    ver, _ = read_loc(extract(LOCAL, "text\\db\\effects.loc"))
    files.append(("text\\db\\abpatch_test_effects.loc", write_loc(
        [("effects_description_" + EFFECT, "Ability patch test: Yari Ashigaru unlock War Cry and Banzai", 1),
         ("effects_description_" + MELEE_EFFECT, "%+n melee attack for Yari Ashigaru (ability patch test)", 1)], ver)))
    out = os.path.join(HERE, PACK)
    write_pack(out, files, pack_type="mod")
    print("wrote", out, f"(general_aoe_mod mask {mask})")
    for name, data in sorted(files):
        print(f"  {name} ({len(data)} bytes)")
    return out


if __name__ == "__main__":
    out = build()
    if "--install" in sys.argv:
        shutil.copy2(out, os.path.join(GAME_DATA, PACK))
        print("installed to", GAME_DATA)
