"""Build stat_patch_test.pack: data for in-game tests of the v4 per-unit-type stats.

Vanilla Sengoku campaign as Shimazu, no other mods. Shimazu's clan trait bundle (t_shimazu) gets
unit_record bonuses that only patch v4 understands, with large values so the unit cards show them:
  Yari Ashigaru   charge_bonus +50, mod_land_movement_battle +100 (% speed); control melee_attack_mod +5
  Bow Ashigaru    range_mod +200 (%), ammo_mod +100 (%), reload +100 (%); control accuracy_mod +20
Expected with patch v4, on Shimazu's units (old and new), on the unit card and in battle: those
stats raised. Other clans' units and Shimazu's Yari Samurai: unchanged. Without the patch (or with
v3): nothing changes - the game doesn't know these bonus names for unit types.

Usage: <lab venv python> testpack/build_statpack.py [--install]
"""
import os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_testpack as base  # noqa: E402  (sets up the import paths and the vanilla readers)
from tools_db import GAME_DATA  # noqa: E402
from tools_loc import read_loc, write_loc  # noqa: E402
from tools_db import extract  # noqa: E402
from tools_packwrite import write_pack  # noqa: E402

PACK = "stat_patch_test.pack"
base.NAME = "statpatch_test"
CLAN_BUNDLE = "t_shimazu"
BONUSES = [  # (unit, bonus, value, description)
    # controls: per-unit bonuses the vanilla game already supports, read by the same stats builder
    ("Inf_Spear_Yari_Ashigaru", "melee_attack_mod", 5, "%+n melee attack for Yari Ashigaru (stat patch test: control)"),
    ("Inf_Missile_Bow_Ashigaru", "accuracy_mod", 20, "%+n accuracy for Bow Ashigaru (stat patch test: control)"),
    # v4 bonuses
    ("Inf_Spear_Yari_Ashigaru", "charge_bonus", 50, "%+n charge bonus for Yari Ashigaru (stat patch test)"),
    ("Inf_Spear_Yari_Ashigaru", "mod_land_movement_battle", 100, "%+n%% battle speed for Yari Ashigaru (stat patch test)"),
    ("Inf_Missile_Bow_Ashigaru", "range_mod", 200, "%+n%% range for Bow Ashigaru (stat patch test)"),
    ("Inf_Missile_Bow_Ashigaru", "ammo_mod", 100, "%+n%% ammunition for Bow Ashigaru (stat patch test)"),
    ("Inf_Missile_Bow_Ashigaru", "reload", 100, "%+n%% reload skill for Bow Ashigaru (stat patch test)"),
]


def build():
    _, _, effects = base.vanilla("effects_tables")
    template = next(r for r in effects if r["effect"] == "clan_trait_shimazu_cheap_samurai")
    keys = [f"statpatch_{i}_{b}" for i, (_, b, _, _) in enumerate(BONUSES)]
    files = [
        base.ours("effects_tables", [dict(template, effect=k) for k in keys]),
        base.ours("effect_bonus_value_unit_record_junctions_tables",
                  [{"bonus_value_id": b, "effect": k, "unit_record_key": u} for k, (u, b, _, _) in zip(keys, BONUSES)]),
        base.ours("effect_bundles_to_effects_junctions_tables",
                  [{"effect_bundle_key": CLAN_BUNDLE, "effect_key": k, "value": float(v)}
                   for k, (_, _, v, _) in zip(keys, BONUSES)]),
    ]
    ver, _ = read_loc(extract(base.LOCAL, "text\\db\\effects.loc"))
    files.append(("text\\db\\statpatch_test_effects.loc", write_loc(
        [("effects_description_" + k, d, 1) for k, (_, _, _, d) in zip(keys, BONUSES)], ver)))
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
