"""Build ability_patch_test.pack: data for the first in-game test of the DLL patch.

What the pack does (vanilla Sengoku campaign, no other mods):
  - War Cry becomes research-gated (requires_effect_enabling = True). Vanilla has no research that
    enables it, so without the patch NOBODY has War Cry (the warrior monks lose theirs).
  - War Cry is attached to Yari Ashigaru and to Yari Samurai (control).
  - Shimazu's clan trait bundle (t_shimazu) gains an effect that sets general_aoe_mod = 1 (bit 0 =
    War Cry, see abilities.py) on Yari Ashigaru.
Expected with the patch: Shimazu Yari Ashigaru have War Cry (existing and new ones); other clans'
Yari Ashigaru don't; nobody's Yari Samurai do; warrior monks don't.

Usage: .venv/bin/python testpack/build_testpack.py [--install]
Needs the Veteran Upgrades lab checkout for its DB/pack tools (SHOGUN2_LAB, default ~/projects/shogun2_modding).
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LAB = os.environ.get("SHOGUN2_LAB", os.path.expanduser("~/projects/shogun2_modding"))
sys.path[:0] = [ROOT, LAB]

from abilities import bit
from tools_db import GAME_DATA, encode, load_file, extract
from tools_loc import read_loc, write_loc
from tools_packwrite import write_pack

DATA = os.path.join(GAME_DATA, "data.pack")
LOCAL = os.path.join(GAME_DATA, "local_en.pack")
PACK = "ability_patch_test.pack"
NAME = "abpatch_test"

ABILITY = "warcry"
GRANTED_UNIT = "Inf_Spear_Yari_Ashigaru"
CONTROL_UNIT = "Inf_Spear_Yari_Samurai"
CLAN_BUNDLE = "t_shimazu"
EFFECT = "abpatch_test_yari_warcry"


def vanilla(table):
    return load_file(DATA, f"db\\{table}\\{table[:-len('_tables')]}")


def full_copy(table, rows_fn):
    """The whole vanilla table, edited, under the vanilla file name (replaces it)."""
    ver, header, rows = vanilla(table)
    return f"db\\{table}\\{table[:-len('_tables')]}", encode(table, ver, rows_fn(rows), header)


def ours(table, rows):
    """A separately named table file with only our rows (merges with vanilla)."""
    ver, header, _ = vanilla(table)
    return f"db\\{table}\\{NAME}", encode(table, ver, rows, header)


def gate(rows):
    for r in rows:
        if r["key"] == ABILITY:
            r["requires_effect_enabling"] = True
    assert any(r["key"] == ABILITY for r in rows)
    return rows


def build():
    _, _, effects = vanilla("effects_tables")
    template = next(r for r in effects if r["effect"] == "clan_trait_shimazu_cheap_samurai")
    files = [
        full_copy("unit_abilities_tables", gate),
        ours("unit_to_unit_abilities_junctions_tables", [
            {"unit_name": GRANTED_UNIT, "ability": ABILITY},
            {"unit_name": CONTROL_UNIT, "ability": ABILITY},
        ]),
        ours("effects_tables", [dict(template, effect=EFFECT)]),
        ours("effect_bonus_value_unit_record_junctions_tables", [
            {"bonus_value_id": "general_aoe_mod", "effect": EFFECT, "unit_record_key": GRANTED_UNIT},
        ]),
        ours("effect_bundles_to_effects_junctions_tables", [
            {"effect_bundle_key": CLAN_BUNDLE, "effect_key": EFFECT, "value": float(1 << bit(ABILITY))},
        ]),
    ]
    ver, _ = read_loc(extract(LOCAL, "text\\db\\effects.loc"))
    files.append(("text\\db\\abpatch_test_effects.loc", write_loc(
        [("effects_description_" + EFFECT, "Ability patch test: Yari Ashigaru gain War Cry", 1)], ver)))
    out = os.path.join(HERE, PACK)
    write_pack(out, files, pack_type="mod")
    print("wrote", out)
    for name, data in sorted(files):
        print(f"  {name} ({len(data)} bytes)")
    return out


if __name__ == "__main__":
    out = build()
    if "--install" in sys.argv:
        shutil.copy2(out, os.path.join(GAME_DATA, PACK))
        print("installed to", GAME_DATA)
