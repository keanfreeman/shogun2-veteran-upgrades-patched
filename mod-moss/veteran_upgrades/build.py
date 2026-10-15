"""Build veteran_upgrades_moss_patched.pack: Veteran Upgrades: Patched Edition for MoSS.

The Patched Edition's mechanics (../mod) for Master of Strategy Sengoku (MoSS): Sengoku Jidai only,
generated from the game's data with MoSS's packs laid over it (MOSS_PACKS, as in the MoSS edition), so
it covers the units and clans a MoSS campaign actually has. Abilities are the Patched Edition's clone
lines (no unit copies), offered only where they work under MoSS (fits()).

Clan-wide upgrades per unit family, modelled on the multiplayer veteran skill trees:
  * upgrade lines + per-level values come from the MP avatar_skill tables
  * stat lines: only bonuses proven to work at unit_record scope in campaign; each
    (family, line, level) is an effect bundle that the Lua side applies/removes
  * ability lines: need the ability patch (repo root, patch.py). Each ability gets a CLONE record
    (vuNN_<ability>, supersedes_ability = the real one)
    attached to the family's unit types; an ability line is an effect bundle setting the unit
    types' general_aoe_mod to the ability's bit (abilities.py), and the patched game grants the
    real ability to every unit of those types, existing ones included. No unit copies, no
    retraining, no recruitment locks. Without the patch the clones are ignored by the engine.
Outputs veteran_upgrades_moss_patched.pack (mod type) next to this file.
"""
import collections, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", ".."))   # the patch repo: abilities.py (the patch's bit table)
from abilities import MAX_BITS, SNIPE_BIT, CAMO_BIT, GUERRILLA_BIT, assign_bits, clone_key as patch_clone_key
from tools_packread import extract, read_index
from tools_packwrite import write_pack
import tools_db
from tools_db import load, load_file, encode, GAME_DATA
from tools_loc import read_loc, write_loc

# MoSS packs the data is read from, in the game's load order: a later pack's file replaces an earlier
# one with the same path. The Database pack must come after the clan pack: both have a
# db\\building_units_allowed_tables\\building_units_allowed, and the clan pack's lists only Uesugi temple
# units (MoSS campaigns recruit from the Database pack's, so that one wins in game).
MOSS_PACKS = ["MoSS_Must_clans_Original_PICK_ONLY_ONE.pack", "MoSS_Must_database.pack"]
# Packs searched for unit portraits and ability icons (MoSS's are in its "files" packs).
UI_PACKS = ["data.pack", "data_fots.pack"] + MOSS_PACKS + [f"MoSS_Must_files_{i}.pack" for i in range(1, 5)]
for _p in UI_PACKS:
    if not os.path.exists(os.path.join(GAME_DATA, _p)):
        raise SystemExit(f"{_p} not found in {GAME_DATA}: subscribe to MoSS's mandatory items and let the "
                         "launcher copy them into the data folder (see README)")
tools_db.OVERLAY[:] = MOSS_PACKS

DATA = os.path.join(GAME_DATA, "data.pack")
LOCAL = os.path.join(GAME_DATA, "local_en.pack")

# Families are generated from the multiplayer units of each campaign's era: each <Unit>_MP has its
# own skill list, and its campaign equivalent is <Unit> plus clan variants (<Unit>_Oda, ...).
# Recruitable land units without an MP tree borrow the tree of an MP unit of the same class.
SKIP = re.compile(r"(^|_)(Gen_|Heavy_Ship|Medium_Ship|Light_Ship|Cannon_Ship|Corvette|Frigate|Ironclad|Gun_Boat|Torpedo_Boat)")
EXCLUDE = re.compile(r"(_MP|_Tutorial|_Tutorial_No_Cap)$")
# Per campaign: script, MP products, which unit keys and clans belong to it, and the list columns
# (category id, label, heading emblem to clone, tooltip) in display order.
CAMPAIGNS = [   # MoSS is a Sengoku Jidai overhaul: no Rise or Fall of the Samurai here
    {"id": "sengoku", "script": "campaigns\\jap_shogun\\scripting.lua", "pack": "data.pack",
     "products": {"shogun2"}, "unit_prefixes": None, "clan_prefix": None,
     "categories": [("spear", "Spear", "melee", "Spear and polearm infantry"), ("sword", "Sword", "melee", "Sword infantry"),
                    ("bow", "Bow", "ranged", "Bow infantry"), ("gun", "Firearms", "ranged", "Matchlock and other firearm infantry"),
                    ("cavalry", "Cavalry", "physical", "Cavalry"),
                    ("siege_stealth", "Siege & Special", "leadership", "Artillery, siege weapons and special units")]},
]
SENGOKU_FOREIGN = ("Genpei_", "Boshin_")   # other campaigns' unit prefixes

# MP avatar effect -> (campaign bonus_value_id, label). Only bonuses verified at unit_record scope.
BONUS = {
    "mod_marksmanship":  ("accuracy_mod",      "Accuracy"),   # MP calls it marksmanship
    "mod_melee_attack":  ("melee_attack_mod",  "Melee Attack"),
    "mod_melee_defence": ("melee_defence_mod", "Melee Defence"),
    "mod_armour":        ("armour_mod",        "Armour"),
    "mod_unit_morale":   ("morale",            "Morale"),
    # (No reload: "reload" per unit record is ignored - the card stayed at the base value after +60%,
    #  v0.19; the game only honours it at unit_class scope.)
}
# MP "enable ability" effects -> campaign unit ability to clone (gated) for the family.
ABILITY_MAP = {
    "enable_ability_banzai": "banzai", "enable_ability_inspire": "inspire_unit", "enable_ability_rally": "rally",
    "enable_ability_fire_arrows": "flaming_arrows_ability", "enable_ability_stand_and_fight": "we_stand_and_fight",
    "enable_ability_whistling_arrows": "whistling_arrows_ability", "enable_ability_second_wind": "second_wind",
    "enable_ability_blind_grenades": "blinding_grenade", "enable_ability_heroic_assault": "heroic_assault",
    "enable_ability_ganbatte": "ganbatte", "enable_ability_cantabrian_circle": "cantabrian_circle",
    "enable_ability_rapid_volley": "rapid_volley", "enable_ability_warcry": "warcry",
    "enable_ability_kneel_fire": "kneel_fire_ability", "enable_ability_suppressive_fire": "suppression_fire",
    "ability_stand_firm": "stand_firm", "mod_ability_stand_firm": "stand_firm",
}
# MP effects that are passive unit_record bonuses in campaign.
PASSIVE_MAP = {"enable_ability_scare_enemies": ("scares_men", "Scare Enemies", 1.0)}
# Abilities offered to every unit type they suit, on top of the MP trees (the patch makes any of them
# per unit type). What suits a unit (unit_kind = class, missile weapon, mounted):
RULE_ANY = {"warcry", "rally", "inspire_unit", "stand_firm", "second_wind", "banzai", "ganbatte",   # shouts, buffs:
            "heroic_assault", "rapid_advance", "we_stand_and_fight"}                              # any non-artillery unit
RULE_MISSILE = {"rapid_volley", "range_effect"}                    # anything that shoots (not artillery)
RULE_BOW = {"flaming_arrows_ability", "whistling_arrows_ability"}   # they swap the unit's arrows
RULE_GUN_INFANTRY = {"rank_fire"}   # any foot unit with a musket or rifle (bows already fire every rank)
RULE_SAME_KIND = {"pike_wall_formation", "pike_square_formation", "wedge_formation", "cantabrian_circle",
                  "kneel_fire_ability", "suppression_fire",
                  "active_hiding", "blinding_grenade", "shrapnel_shot"}   # formations/kit: only unit kinds that have it in MoSS
# Not offered: bamboo_wall and pavisse_deployable. FUN_1019e580 allows these deployables only in some
# battle types by comparing the LIST ENTRY's key with those names; a clone (vuNN_...) never matches,
# so it would be granted in every battle type.
RULE_ABILITIES = RULE_ANY | RULE_MISSILE | RULE_BOW | RULE_GUN_INFANTRY | RULE_SAME_KIND
# MoSS renames and repurposes abilities (from its unit_abilities / unit_special_abilities): range_effect
# is "Flaming Arrows" (arrow_flaming_long_range projectile), flaming_arrows_ability "High Volley",
# suppression_fire "Rapid Volley" (unlocked by Gunpowder Mastery), shrapnel_shot another "Flaming
# Arrows"; the bow Rapid Volley (rapid_volley) is gated with nothing enabling it. So on top of the rules
# above, every ability - from a tree or a rule - must pass fits(): a gated ability needs something in
# MoSS that enables it, and one that swaps the projectile needs the matching weapon. RULE_SAME_KIND's
# kinds are those of the units MoSS's buildings recruit (not the multiplayer records, the vanilla units
# MoSS no longer recruits or its _g variants), with the melee weapon as part of the kind: MoSS's classes
# are loose (its Imagawa Yari Retainer and Naginata Nun are infantry_matchlock).
PROJECTILE_WEAPON = {"arrow": "bow", "grenade": "sling"}
# The yari formations also need a spear: MoSS gives Yari Wall to its Teppo Ashigaru Hero, which would
# otherwise make it a kit of every matchlock unit.
SPEAR_FORMATIONS, SPEAR_WEAPONS = {"pike_wall_formation", "pike_square_formation"}, {"spear", "pike", "long_pike"}
# The MP skill-tree popup: 4 columns (headings), and 6 rows fit above its button bar (2026-10-14
# screenshot: a 7th row sits on the bar). 24 slots; the popup itself has 28 nodes.
COLUMNS = ["leadership", "ranged", "physical", "melee"]
MAX_ROWS = 6
SPILL_ORDER = ["physical", "ranged", "leadership", "melee"]   # where lines go when their column is full
MAX_LINES = len(COLUMNS) * MAX_ROWS   # per page
MAX_PAGES = 2   # the upgrade panel pages through a unit type's lines (vu.lua page button)
# Upgrades EVERY unit type gets, whether or not its multiplayer tree has them (from the MoSS edition):
#   (bonus_value_id, label, icon, step per level or None = median of the trees that have it, missile units only)
UNIVERSAL_STATS = [
    # Fixed steps for every unit type (the MP trees' steps of 1-6 made similar units pay very different
    # amounts for the same stat; review 2026-10-14).
    ("melee_attack_mod", "Melee Attack", "skill_melee_attack", 1.0, False),
    ("melee_defence_mod", "Melee Defence", "skill_melee_defence", 1.0, False),
    ("armour_mod", "Armour", "skill_armour", 1.0, False),
    ("morale", "Morale", "skill_morale", 1.0, False),
    ("accuracy_mod", "Accuracy", "skill_accuracy", 3.0, True),
    # Patch v4 stats (the game applies these per unit type only with the patch). Steps from vanilla
    # values: charge +1..10 (skills, retainers), battle speed +5..15% (techs, skills), reload +5..10%,
    # ammunition +50% (techs); range is metres added to the unit's range (Increased Range: +25).
    ("charge_bonus", "Charge", "skill_charge", 2.0, False),
    ("mod_land_movement_battle", "Speed", "skill_speed", 2.0, False),
    ("reload", "Reload", "skill_reload", 5.0, True),
    ("ammo_mod", "Ammunition", "skill_ammo_quantity", 10.0, True),
    ("range_mod", "Range", "skill_range", 5.0, True),
    # +2 per level, +20 at 10 (Yari Ashigaru have 20, MP trees +3..+15). Foot units only (below).
    ("bonus_vs_cavalry", "Bonus vs Cavalry", "skill_bonus_vs_cavalry", 2.0, False),
]
MELEE_ROLE_ONLY = {"bonus_vs_cavalry"}   # foot units that fight in melee (melee_role below)
PATCH_STATS = {"charge_bonus", "mod_land_movement_battle", "reload", "ammo_mod", "range_mod", "bonus_vs_cavalry",
               "general_aoe_mod"}   # need patch v4 (general_aoe_mod here: the attribute bits 21-23)
NOT_FOR_ARTILLERY = {"melee_attack_mod", "melee_defence_mod", "charge_bonus"}   # crews aren't meant to fight (unless their tree says so)
# Panel column (popup heading container) per bonus / ability.
COLUMN = {"morale": "leadership", "accuracy_mod": "ranged", "reload": "ranged", "armour_mod": "physical",
          "melee_attack_mod": "melee", "melee_defence_mod": "melee", "scares_men": "leadership",
          "charge_bonus": "melee", "mod_land_movement_battle": "physical", "ammo_mod": "ranged", "range_mod": "ranged",
          "general_aoe_mod": "ranged", "bonus_vs_cavalry": "melee", "fatigue_resistance": "physical"}
ABILITY_COLUMN = {"rally": "leadership", "inspire_unit": "leadership", "stand_firm": "leadership",
                  "we_stand_and_fight": "leadership", "ganbatte": "leadership",
                  "warcry": "melee", "banzai": "melee", "heroic_assault": "melee", "rapid_advance": "melee",
                  "pike_wall_formation": "melee", "pike_square_formation": "melee",
                  "flaming_arrows_ability": "ranged", "whistling_arrows_ability": "ranged", "rapid_volley": "ranged",
                  "range_effect": "ranged", "kneel_fire_ability": "ranged", "suppression_fire": "ranged",
                  "rank_fire": "ranged", "cantabrian_circle": "ranged", "shrapnel_shot": "ranged",
                  "second_wind": "physical", "wedge_formation": "physical", "blinding_grenade": "physical",
                  "active_hiding": "physical", "bamboo_wall": "physical", "pavisse_deployable": "physical"}
# Costs (clan points; the clan earns a flat amount per battle, vu.lua VU_POINTS_PER_BATTLE).
ABILITY_COST = 5   # unit abilities, unless listed in ABILITY_COSTS
# Priced by reach (self / up to 3 units / every friendly in range), strength and recharge, from
# unit_special_abilities + _kv_special_ability_effects (2026-10-14). A point is one battle.
ABILITY_COSTS = {
    # 7-6: area buffs on every friendly unit nearby
    "ganbatte": 7,            # 150 m: +10 accuracy, +2 melee attack, +2 morale, +10 reload; 30 s every 120 s
    "heroic_assault": 6,      # 75 m: fatigue reset, +4 morale, +55% speed; 20 s every 120 s
    # 5: strong, or affects several units
    "rally": 5,               # 75 m: rallies routing units
    "inspire_unit": 5,        # self: +10 morale, +3 melee attack, +15 accuracy, +10 reload for 60 s
    "warcry": 5,              # 4 enemies: -4 morale, -2 melee defence, -35% speed for 45 s
    "range_effect": 5,        # self: +25 range for 50 s
    "suppression_fire": 5,    # self +20 reload; target -20 accuracy, -4 morale
    "pike_wall_formation": 5, "cantabrian_circle": 5,   # formations with big combat bonuses
    "blinding_grenade": 5,    # target: -75 accuracy, -10 melee attack
    "shrapnel_shot": 5,       # artillery ammunition, 5 uses
    # 4: self buffs, or need research / a general's skill as well
    "banzai": 4, "rapid_volley": 4, "flaming_arrows_ability": 4, "whistling_arrows_ability": 4,
    "we_stand_and_fight": 4, "rank_fire": 4, "pike_square_formation": 4, "wedge_formation": 4, "active_hiding": 4,
    # 3: small or situational
    "stand_firm": 3,          # up to 3 units: +3 melee defence for 30 s
    "second_wind": 3,         # up to 3 units: fatigue reset
    "rapid_advance": 3,       # self: +40% speed for 40 s
    "kneel_fire_ability": 3, "bamboo_wall": 3, "pavisse_deployable": 3,
}
# MoSS's repurposed abilities (RULE_* comment), priced like the vanilla abilities they have become.
# (Their effect values weren't compared: MoSS's _kv_special_ability_effects isn't read by the build.)
ABILITY_COSTS.update({
    "range_effect": 4,        # MoSS: "Flaming Arrows" (vanilla fire arrows: 4)
    "shrapnel_shot": 4,       # MoSS: "Flaming Arrows"
    "suppression_fire": 4,    # MoSS: "Rapid Volley" for guns (vanilla Rapid Volley: 4)
})
# Stat picks are priced by value: a pick's size as a share of that stat's spread (max - min) across
# all unit types the mod covers; pick n costs max(1, round(PRICE_K * share * n)).
PRICE_K = 16
STAT_FIELD = {"melee_attack_mod": "melee_attack", "melee_defence_mod": "melee_defence", "morale": "morale",
              "accuracy_mod": "core_marksmanship", "armour_mod": "armour", "charge_bonus": "charge_bonus",
              "bonus_vs_cavalry": "melee_bonus_vs_cavalry"}
PERCENT_SPREAD = {"reload": 63.0,   # percent (or metre) bonuses: a pick's share of this much
                  # priced by value (about 100 points to max range, 70 speed, 70 reload; review 2026-10-14):
                  # permanent +50 m range or +20% speed are strong; extra ammunition matters less
                  "ammo_mod": 300.0, "mod_land_movement_battle": 25.0, "range_mod": 44.0}
# How a stat's value reads: (unit after the number in tooltips, effect description text)
STAT_UNIT = {"reload": ("%", "%+n%% reload skill"), "ammo_mod": ("%", "%+n%% ammunition"),
             "mod_land_movement_battle": ("%", "%+n%% battle speed"), "range_mod": (" m", "%+n m range"),
             "charge_bonus": ("", "%+n charge bonus"),
             "bonus_vs_cavalry": ("", "%+n bonus vs cavalry")}
PASSIVE_COST = 6   # passive unlocks such as Scare Enemies
STAT_MAX_LEVEL = 10   # each stat line can be bought this many times...
STAT_MAX_FACTOR = 2   # ...and buying it that often gives about twice the multiplayer maximum
# ...and pick n costs n points (1+2+...+10 = 55 to max one stat), so stacking one stat gets expensive.
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
# Fallback icon per bonus when the MP skill's own icon file doesn't exist.
STAT_ICON = {"reload": "skill_reload", "accuracy_mod": "skill_accuracy", "melee_attack_mod": "skill_melee_attack", "melee_defence_mod": "skill_melee_defence",
             "armour_mod": "skill_armour", "morale": "skill_morale", "charge_bonus": "skill_charge",
             "mod_land_movement_battle": "skill_speed", "ammo_mod": "skill_ammo_quantity", "range_mod": "skill_range"}
ICON = "data/ui/campaign ui/pips/effect_admiral.tga"
START_POINTS = 0  # points come from battles (vu.lua: VU_OnUnitCompletedBattle)
TITLE = "Veteran Upgrades: Patched Edition for MoSS"
VERSION = "1.0.0"   # Patched Edition 2.0.0's mechanics with the MoSS edition 1.1.0's data handling; needs patch v4
PACK_NAME = "veteran_upgrades_moss_patched.pack"
DEBUG = os.environ.get("VU_DEBUG") == "1"   # debug build: logs the panel's UI tree + tooltips (tools/vu_ui_audit.py)

# Vanilla turns the MP trees' missile range skills into Increased Range (range_effect). MoSS made
# range_effect "Flaming Arrows", so they become nothing here: the Range stat line (patch v4) is the
# range upgrade, and range_effect is offered as MoSS's Flaming Arrows (RULE_MISSILE + fits()).
RANGE_ABILITY = "range_effect"
RANGE_EFFECTS = set()


def pack_files(prefix):
    """Lower-case base names of the files under prefix in every UI_PACKS pack (vanilla and MoSS's)."""
    return {n.lower().split("\\")[-1] for p in UI_PACKS for n, _, _ in read_index(os.path.join(GAME_DATA, p))
            if n.lower().startswith(prefix)}


def icon_files():
    return {n[:-4] for n in pack_files("ui\\frontend ui\\skills\\")}


def icon_path(mp_icon, bonus, available):
    """MP icon '/UI/Frontend UI/Skills/skill_x.tga' -> 'data/ui/frontend ui/skills/skill_x.tga' if it exists."""
    name = mp_icon.lower().split("/")[-1][:-4]
    if name not in available:
        name = STAT_ICON[bonus]
    return f"data/ui/frontend ui/skills/{name}.tga"


def portraits():
    return [n[:-4] for n in pack_files("ui\\units\\icons_square\\") if n.endswith(".tga")]


def family_portrait(base_key, square):
    """Square portrait: try the unit key's trailing tokens, longest first (Inf_Spear_Yari_Ashigaru -> *_yari_ashigaru)."""
    if base_key.lower() in square:   # MoSS names its icons exactly after the unit key
        return f"data/ui/units/icons_square/{base_key.lower()}.tga"
    tokens = base_key.lower().split("_")
    for k in range(len(tokens) - 1, 1, -1):   # at least two words: "_hero" alone matched other heroes
        suffix = "_" + "_".join(tokens[-k:])
        hits = sorted((n for n in square if n.endswith(suffix)), key=len)
        if hits:
            return f"data/ui/units/icons_square/{hits[0]}.tga"
    return None


_UNIT_NAMES = {}


def loc_strings(file_prefix, key_prefix):
    """{key without key_prefix: text} from the English loc files whose name starts with file_prefix
    (text\\db\\<file_prefix>*.loc), MoSS's (any such file name) over the game's."""
    out = {}
    for path in [LOCAL] + [os.path.join(GAME_DATA, p) for p in MOSS_PACKS]:
        for n, _, _ in read_index(path):
            nl = n.lower()
            if nl.startswith("text\\db\\" + file_prefix) and nl.endswith(".loc"):
                for k, v, _ in read_loc(extract(path, n))[1]:
                    if k.startswith(key_prefix):
                        out[k[len(key_prefix):]] = v
    return out


def unit_names():
    """{unit key: on-screen name}: MoSS's names (it renames many units, and names its own in its loc files)."""
    if not _UNIT_NAMES:
        _UNIT_NAMES.update(loc_strings("", "units_on_screen_name_"))
    return _UNIT_NAMES


ABIL_JUNC, ABILITIES, ICON_FILES, BUTTON_FILES = [], {}, set(), set()


def ability_icon(ab):
    """The ability's 51x51 battle button (sharp in the 48-pixel skill slot), else its 22x22 button icon
    (blurry when scaled up), else a stat icon. MoSS ships its own for the abilities it repurposes
    (button_range_effect_* is a flaming arrow): the path is the same, and its pack's file wins in game."""
    button = f"button_{ab}_unselected.tga"
    if button in BUTTON_FILES:
        return f"data/ui/battle ui/buttons/{button}"
    name = f"{ab}_icon.tga"
    return f"data/ui/battle ui/button icons/{name}" if name in ICON_FILES else STAT_ICON_PATH


def campaign_unit(camp, key):
    if camp["unit_prefixes"]:
        return key.startswith(camp["unit_prefixes"])
    return not key.startswith(SENGOKU_FOREIGN)


STATS, NATIVE_KINDS, SCARES, PROJECTILE, ENABLED = {}, {}, set(), {}, set()


def unit_kind(key):
    """(class, missile weapon, mounted, melee weapon): decides which formation/kit abilities make sense
    for a unit."""
    s = STATS.get(key) or {}
    return (UNITS_CLASS.get(key), s.get("primary_missile_weapon"), s.get("mount_model") is not None, s.get("melee_weapon_type"))


def same_kind(ab, keys):
    """RULE_SAME_KIND: every unit of the family is of a kind that carries the ability in MoSS."""
    if ab in SPEAR_FORMATIONS and not all(unit_kind(k)[3] in SPEAR_WEAPONS for k in keys):
        return False
    return all(unit_kind(k) in NATIVE_KINDS.get(ab, ()) for k in keys)


def is_artillery(keys):
    return any((STATS.get(k) or {}).get("artillery_model") or (STATS.get(k) or {}).get("siege_gun") for k in keys)


def has_missiles(keys):
    """Any unit of the family with a missile weapon or artillery (Accuracy does nothing otherwise)."""
    return any((STATS.get(k) or {}).get("primary_missile_weapon") or (STATS.get(k) or {}).get("artillery_model")
               or (STATS.get(k) or {}).get("siege_gun") for k in keys)


def already_scares(key):
    return key in SCARES or bool((STATS.get(key) or {}).get("fear_effect"))


def enabled_abilities():
    """Gated abilities something in the game (MoSS's data) can enable: an enabling effect used by a
    technology (the custom-battle one too), building, character skill, trait or effect bundle. A gated
    ability nothing enables is one MoSS switched off (the bow Rapid Volley, Spear Square Formation)."""
    used = set()
    for table, field in (("technology_effects_junction_tables", "effect"), ("building_effects_junction_tables", "effect"),
                         ("building_factionwide_effects_junctions_tables", "effect"),
                         ("character_skill_level_to_effects_junctions_tables", "effect_key"),
                         ("effect_bundles_to_effects_junctions_tables", "effect_key"), ("trait_level_effects_tables", "effect")):
        used |= {r[field] for r in load(table)}
    return {r["unit_ability"] for r in load("effect_bonus_value_unit_ability_junctions_tables") if r["effect"] in used}


def fits(ab, keys):
    """Does the ability work for every unit of the family under MoSS (from the MoSS edition's
    ability_fits)? Not if MoSS switched it off (gated, nothing enables it); one that swaps the projectile
    only for the matching weapon (MoSS's range_effect fires flaming arrows: bows only)."""
    if ab not in ABILITIES or (ABILITIES[ab]["requires_effect_enabling"] and ab not in ENABLED):
        return False
    projectile = (PROJECTILE.get(ab) or "").lower()
    for part, weapon in PROJECTILE_WEAPON.items():
        if part in projectile and not all(unit_kind(k)[1] == weapon for k in keys):
            return False
    return True


def rule_fits(ab, keys):
    """Does a RULE_* ability suit every unit of the family?"""
    if not fits(ab, keys):
        return False
    artillery = is_artillery(keys)
    weapons = {(STATS.get(k) or {}).get("primary_missile_weapon") for k in keys}
    if ab in RULE_ANY:
        return not artillery
    if ab in RULE_MISSILE:
        return not artillery and None not in weapons
    if ab in RULE_BOW:
        return weapons == {"bow"}
    if ab in RULE_GUN_INFANTRY:
        return not artillery and weapons <= {"musket", "rifle"} and not any(unit_kind(k)[2] for k in keys)
    if ab in RULE_SAME_KIND:
        return same_kind(ab, keys)
    return False


def tree_fits(ab, keys):
    """An ability from the unit's MP tree: fits(), and formations/kit (RULE_SAME_KIND) only for the kinds
    of unit that carry it in MoSS (MoSS gives Swooping Crane to bow cavalry, not gun cavalry)."""
    return fits(ab, keys) and (ab not in RULE_SAME_KIND or same_kind(ab, keys))


def campaign_enablers(camp):
    """{gated ability: what unlocks it in this campaign}, e.g. pike_square_formation ->
    "Yari Tactics (research)". Sources: MoSS's technologies (not the custom-battle one) and Sengoku
    generals' skills (not the gem_/bos_ ones), named from MoSS's loc files over the game's. A gated ability
    with none (only the custom-battle tech enables it: Kneel Fire) has its research waived ('f' clone)."""
    tech_prefix = "shogun_"
    names = {**loc_strings("technologies", ""), **loc_strings("character_skills", "")}
    how = collections.defaultdict(set)   # effect -> descriptions
    for r in load("technology_effects_junction_tables"):
        if r["technology"].startswith(tech_prefix) and r["technology"] != "shogun_custom_battle_tech":
            how[r["effect"]].add(names.get("technologies_onscreen_name_" + r["technology"], r["technology"]).strip() + " (research)")
    for r in load("character_skill_level_to_effects_junctions_tables"):
        k = r["character_skill_key"]
        if not k.startswith(("gem_", "bos_")):
            skill = names.get("character_skills_localised_name_" + k, k).strip()
            how[r["effect_key"]].add(f"a general with the {skill} skill in the army")
    out = collections.defaultdict(set)
    for r in load("effect_bonus_value_unit_ability_junctions_tables"):
        out[r["unit_ability"]] |= how.get(r["effect"], set())
    return {ab: " or ".join(sorted(v)) for ab, v in out.items() if v}


def building_tier(level, levels):
    """Tier of a building level: the number in its name (SHO_aa_castle_1_fort -> 1; MoSS's own
    'level' field is out of order, e.g. its Fort is level 4), else that field."""
    m = re.search(r"_(\d+)_", level[4:] if level.startswith("SHO_") else level)
    return int(m.group(1)) if m else levels.get(level, {}).get("level", 99)


def recruit_tiers():
    """{unit key: lowest tier of a building that recruits it}."""
    levels = {r["level_name"]: r for r in load("building_levels_tables")}
    tiers = {}
    for r in load("building_units_allowed_tables"):
        t = building_tier(r["building"], levels)
        tiers[r["unit"]] = min(t, tiers.get(r["unit"], t))
    return tiers


UNITS_CLASS = {}


def build_catalog(camp):
    global ABIL_JUNC, ABILITIES, ICON_FILES, BUTTON_FILES
    ABIL_JUNC = load("unit_to_unit_abilities_junctions_tables")
    ABILITIES = {r["key"]: r for r in load("unit_abilities_tables")}
    STATS.clear(); STATS.update({r["key"]: r for r in load("unit_stats_land_tables")})
    units = {r["key"]: r for r in load("units_tables")}
    UNITS_CLASS.clear(); UNITS_CLASS.update({k: r["class"] for k, r in units.items()})
    PROJECTILE.clear(); PROJECTILE.update({r["key"]: r.get("activated_projectile") for r in load("unit_special_abilities_tables")})
    ENABLED.clear(); ENABLED.update(enabled_abilities())
    buildable = {r["unit"] for r in load("building_units_allowed_tables")}
    NATIVE_KINDS.clear()   # the units MoSS recruits (RULE_* comment)
    for r in ABIL_JUNC:
        if r["unit_name"] in STATS and r["unit_name"] in buildable and not EXCLUDE.search(r["unit_name"]):
            NATIVE_KINDS.setdefault(r["ability"], set()).add(unit_kind(r["unit_name"]))
    SCARES.clear(); SCARES.update(r["unit_record_key"] for r in load("effect_bonus_value_unit_record_junctions_tables")
                                  if r["bonus_value_id"] == "scares_men")
    enablers = campaign_enablers(camp)
    ICON_FILES = pack_files("ui\\battle ui\\button icons\\")
    BUTTON_FILES = pack_files("ui\\battle ui\\buttons\\")
    available = icon_files()
    square = portraits()
    skills = {r["key"]: r for r in load("avatar_skills_tables")}
    effects = collections.defaultdict(list)
    for e in load("avatar_skill_effects_juncs_tables"):
        effects[e["skill"]].append(e)
    unit_skills = collections.defaultdict(list)
    for r in load("avatar_skills_to_units_juncs_tables"):
        unit_skills[r["unit"]].append(r["skill"])
    native_of = collections.defaultdict(set)
    for r in ABIL_JUNC:
        native_of[r["unit_name"]].add(r["ability"])

    avatars = sorted(load("avatar_units_tables"), key=lambda r: r["unit_ui_category_order"])
    sources = []   # (base unit, its keys, MP unit whose skills it uses, MP avatar row)
    names = unit_names()
    for av in avatars:
        mp = av["key"]
        if av["product"] not in camp["products"] or not mp.endswith("_MP") or SKIP.search(mp):
            continue
        base = mp[:-3]
        if base not in units or not campaign_unit(camp, base):
            continue
        keys = sorted(k for k in units if (k == base or k.startswith(base + "_")) and not EXCLUDE.search(k)
                      and k in buildable)   # MoSS drops most vanilla units from recruitment
        if keys:
            sources.append((base, keys, mp, av))
    # Recruitable land units of this campaign without an MP tree: borrow one from an MP unit of the
    # same class (preferring this campaign's era).
    covered = {k for _, keys, _, _ in sources for k in keys}
    land = {r["key"] for r in load("unit_stats_land_tables")}
    by_class = collections.defaultdict(list)
    for av in avatars:
        b = av["key"][:-3]
        if av["key"].endswith("_MP") and b in units and not SKIP.search(av["key"]) and unit_skills[av["key"]]:
            by_class[units[b]["class"]].append((av["product"] not in camp["products"], av))
    # Units with the same in-game name and class form one family (MoSS's <unit>_ikko variants).
    groups = collections.defaultdict(list)
    for k in sorted(units):
        if (k in covered or k not in land or k not in buildable or not campaign_unit(camp, k)
                or EXCLUDE.search(k) or SKIP.search(k) or "Citizenry" in k):
            continue
        groups[(names.get(k, units[k]["on_screen_name"]), units[k]["class"])].append(k)
    for (name, cls), keys in sorted(groups.items(), key=lambda g: sorted(g[1], key=len)[0]):
        k = sorted(keys, key=len)[0]
        cands = sorted(by_class.get(cls, []), key=lambda x: (x[0], x[1]["unique_index"]))
        if cands:
            sources.append((k, sorted(keys), cands[0][1]["key"], cands[0][1]))
            print(f"  {camp['id']}: {', '.join(keys)} borrow the MP tree of {cands[0][1]['key']}")
        else:
            print(f"  {camp['id']}: {', '.join(keys)} - no MP tree of its class, not covered")

    catalog = []
    for base, keys, mp, av in sources:
        lines = collections.OrderedDict()
        for sk in sorted((skills[s] for s in unit_skills[mp] if s in skills),
                         key=lambda s: (s["advanced_skill"], s["skill_sub_chain"], s["level"])):
            for e in effects.get(sk["key"], []):
                if e["effect"] not in BONUS or e["effect_value"] <= 0:
                    continue
                bonus, label = BONUS[e["effect"]]
                line = lines.setdefault(sk["skill_sub_chain"], {
                    "key": sk["skill_sub_chain"], "label": label + (" (Advanced)" if sk["advanced_skill"] else ""),
                    "bonus": bonus, "advanced": bool(sk["advanced_skill"]),
                    "icon": icon_path(sk["icon"], bonus, available), "levels": []})
                line["levels"].append(e["effect_value"])
        # Ability unlocks from the same MP skill list (one single-level line each), if they work under
        # MoSS (tree_fits). Abilities every unit of the family already has are skipped.
        native_all = set.intersection(*(native_of[k] for k in keys))
        abilities = []
        for sk in sorted((skills[s] for s in unit_skills[mp] if s in skills), key=lambda s: s["key"]):
            for e in effects.get(sk["key"], []):
                if e["effect"] in PASSIVE_MAP:
                    bonus, label, value = PASSIVE_MAP[e["effect"]]
                    lines.setdefault("passive_" + bonus, {"key": "passive_" + bonus, "label": label, "bonus": bonus,
                        "advanced": True, "icon": STAT_ICON_PATH, "levels": [value], "kind": "passive"})
                ab = RANGE_ABILITY if e["effect"] in RANGE_EFFECTS else ABILITY_MAP.get(e["effect"])
                if ab and ab not in native_all and ab not in abilities and tree_fits(ab, keys):
                    abilities.append(ab)
        # ...then every RULE_* ability that suits the unit type (MP-tree ones first, kept as they are).
        for ab in sorted(RULE_ABILITIES):
            if ab not in abilities and ab not in native_all and rule_fits(ab, keys):
                abilities.append(ab)
        # One "Flaming Arrows" etc. per unit: MoSS gives different abilities the same name, so skip an
        # ability whose name another ability of the family's units, or an earlier one here, already has.
        taken = {ABILITIES[a]["bullet_text"]: a for k in keys for a in native_of[k] if a in ABILITIES}
        kept = []
        for ab in abilities:
            if taken.get(ABILITIES[ab]["bullet_text"], ab) == ab:
                taken[ABILITIES[ab]["bullet_text"]] = ab
                kept.append(ab)
        abilities = kept
        lines = add_universal_lines(merge_stat_lines(lines), keys, available)
        room = MAX_PAGES * MAX_LINES - len(lines)
        if len(abilities) > room:
            print(f"  WARNING {camp['id']}: {base}: {len(abilities)} abilities, room for {room}; dropped {abilities[room:]}")
            abilities = abilities[:max(room, 0)]
        fam_stub = {"units": keys}
        abilities = [ab for ab in abilities if ability_targets(fam_stub, ab)]   # every unit has it natively: nothing to sell
        for ab in abilities:
            gated = bool(ABILITIES[ab]["requires_effect_enabling"])
            lines["ab_" + ab] = {"key": "ab_" + ab, "label": ABILITIES[ab]["bullet_text"], "bonus": "ability",
                "ability": ab, "advanced": True, "icon": ability_icon(ab), "levels": [1.0], "kind": "ability",
                "desc": ABILITIES[ab]["info_card_tooltip_text"],
                # Gated abilities need what normally unlocks them when this campaign has it; otherwise
                # the clone waives it (else they could never be used).
                "gated": gated and ab in enablers, "no_research": gated and ab not in enablers,
                "requires": enablers.get(ab, "") if gated else ""}
        if not lines:
            continue
        # One line per row under each heading, in line order (stats, passives, abilities); a line whose
        # column is full (MAX_ROWS) goes to the emptiest other column (SPILL_ORDER breaks ties), and
        # when every column of the page is full, onto the next page.
        page, per_column = 1, collections.Counter()
        for line in lines.values():
            kind = line.get("kind", "stat")
            line.setdefault("kind", kind)
            col = (ABILITY_COLUMN.get(line.get("ability"), "melee") if kind == "ability"
                   else line.get("column") or COLUMN.get(line["bonus"], "melee"))
            if per_column[col] >= MAX_ROWS:
                spill = min(SPILL_ORDER, key=lambda c: (per_column[c], SPILL_ORDER.index(c)))
                if per_column[spill] >= MAX_ROWS:
                    page, per_column = page + 1, collections.Counter()
                else:
                    col = spill
            assert page <= MAX_PAGES, f"{base}: more than {MAX_PAGES * MAX_LINES} lines"
            line["column"], line["row"], line["page"] = col, per_column[col], page
            per_column[col] += 1
        catalog.append({"id": base.lower(), "display": names.get(base, units[base]["on_screen_name"]),
                        "portrait": family_portrait(base, square), "category": av["unit_ui_category"],
                        "units": keys, "names": sorted({names.get(k, units[k]["on_screen_name"]) for k in keys}),
                        "lines": list(lines.values()), "abilities": abilities})
    cat_ids = [c[0] for c in camp["categories"]]
    for f in catalog:
        # Mounted units go under Cavalry even when they borrow a foot unit's tree (Yumi Sohei Ki).
        if "cavalry" in cat_ids and any(unit_kind(k)[2] for k in f["units"]):
            f["category"] = "cavalry"
        if f["category"] not in cat_ids:   # categories outside the campaign's columns go to the last column
            f["category"] = cat_ids[-1]
    # Within a column: easiest to get first - lowest recruitment building tier, then cost, then name.
    order = {c: i for i, c in enumerate(cat_ids)}
    tier = recruit_tiers()
    catalog.sort(key=lambda f: (order.get(f["category"], 99), min(tier.get(k, 99) for k in f["units"]),
                                min(units[k]["create_cost"] for k in f["units"]), f["display"]))
    family_factions(catalog, camp)   # before pricing: the stat spreads are over the unit types covered
    for fam in [f for f in catalog if not f["factions"]]:
        print(f"   (dropped {fam['display']} - {', '.join(fam['units'])}: no clan can recruit it under MoSS)")
    catalog[:] = [f for f in catalog if f["factions"]]
    fill_median_steps(catalog)
    price_stats(catalog)
    return catalog


def stat_spreads(catalog):
    """{bonus: (min, mean, max)} of each stat across the units this edition covers (as the MoSS
    edition): MoSS rebalanced its units (melee attack up to 40, bonus vs cavalry at most 10), so a pick
    is priced against MoSS's units, not vanilla's. (The Patched Edition uses every land unit of the game,
    so an upgrade costs the same in all three campaigns; this edition has one.)"""
    stats = {r["key"]: r for r in load("unit_stats_land_tables")}
    keys = [u for f in catalog for u in f["units"] if u in stats]
    out = {}
    for bonus, field in STAT_FIELD.items():
        vals = [stats[k][field] for k in keys if not (field == "core_marksmanship" and stats[k][field] == 0)]
        out[bonus] = (min(vals), sum(vals) / len(vals), max(vals))
    return out


def price_stats(catalog):
    """line["costs"][n-1] = price of pick n, from the pick's size relative to the stat's spread."""
    spreads = stat_spreads(catalog)
    for fam in catalog:
        for line in fam["lines"]:
            if line["kind"] != "stat":
                continue
            step = line["levels"][0]
            spread = PERCENT_SPREAD.get(line["bonus"]) or (spreads[line["bonus"]][2] - spreads[line["bonus"]][0])
            share = step / spread
            line["costs"] = [max(1, round(PRICE_K * share * n)) for n in range(1, len(line["levels"]) + 1)]


def merge_stat_lines(lines):
    """One repeatable line per stat: the MP basic + advanced chains of a bonus become a single line of
    STAT_MAX_LEVEL equal steps. STAT_MAX_LEVEL picks give about STAT_MAX_FACTOR x the MP maximum."""
    out, by_bonus = collections.OrderedDict(), collections.OrderedDict()
    for key, line in lines.items():
        if line.get("kind", "stat") != "stat":
            continue
        by_bonus.setdefault(line["bonus"], []).append(line)
    for bonus, group in by_bonus.items():
        basic = [l for l in group if not l["advanced"]] or group
        mp_max = max(max(l["levels"]) for l in group)
        step = max(1, round(mp_max * STAT_MAX_FACTOR / STAT_MAX_LEVEL))
        out["stat_" + bonus] = {"key": "stat_" + bonus, "label": BONUS[next(k for k, v in BONUS.items() if v[0] == bonus)][1]
                                if bonus in {v[0] for v in BONUS.values()} else basic[0]["label"],
                                "bonus": bonus, "advanced": False, "icon": basic[0]["icon"], "kind": "stat",
                                "levels": [float(step * i) for i in range(1, STAT_MAX_LEVEL + 1)]}
    for key, line in lines.items():
        if line.get("kind", "stat") != "stat":
            out[key] = line
    return out


def add_universal_lines(lines, keys, available):
    """Every unit type's stat lines (UNIVERSAL_STATS, in that order) and Scare Enemies, after the lines
    its own tree gives (those keep the tree's step). Accuracy only for units that shoot; Scare Enemies
    not for units that already frighten; no melee lines for artillery."""
    out = collections.OrderedDict()
    artillery = is_artillery(keys)
    for bonus, label, icon, step, missile_only in UNIVERSAL_STATS:
        if missile_only and not has_missiles(keys):
            continue
        if bonus in MELEE_ROLE_ONLY and not melee_role(keys):
            continue
        key = "stat_" + bonus
        if artillery and bonus in NOT_FOR_ARTILLERY and key not in lines:
            continue
        # The unit's own tree line for this stat (if any) is replaced: one fixed step for everyone.
        out[key] = {"key": key, "label": label, "bonus": bonus, "advanced": False, "kind": "stat",
                    "icon": f"data/ui/frontend ui/skills/{icon if icon in available else 'skill_morale'}.tga",
                    "levels": None if step is None else [step * i for i in range(1, STAT_MAX_LEVEL + 1)]}
    for key, line in lines.items():
        if key not in out and line.get("kind", "stat") == "stat":
            out[key] = line
    if "passive_scares_men" not in lines and not artillery and not any(already_scares(k) for k in keys):
        out["passive_scares_men"] = {"key": "passive_scares_men", "label": "Scare Enemies", "bonus": "scares_men",
                                     "advanced": True, "icon": STAT_ICON_PATH, "levels": [1.0], "kind": "passive"}
    for key, label, bonus, value, cost, icon, column, desc, text, fits in ATTRIBUTE_LINES:
        if fits(keys):
            out[key] = {"key": key, "label": label, "bonus": bonus, "advanced": True, "kind": "passive",
                        "cost": cost, "column": column, "levels": [float(value)], "desc": desc, "effect_text": text,
                        "icon": f"data/ui/frontend ui/skills/{icon if icon in available else 'skill_morale'}.tga"}
    for key, line in lines.items():
        if key not in out:
            out[key] = line
    return out


def melee_role(keys):
    """Bonus vs Cavalry: foot units, not artillery, that fight in melee (no missile weapon) or already
    have a bonus vs cavalry."""
    if is_artillery(keys) or any(unit_kind(k)[2] for k in keys):
        return False
    return all(not (STATS.get(k) or {}).get("primary_missile_weapon") or (STATS.get(k) or {}).get("melee_bonus_vs_cavalry", 0) > 0
               for k in keys)


def lacks_any_hide(keys):
    """Camouflage: non-artillery units that can't already hide in every terrain."""
    return not is_artillery(keys) and not all(all((STATS.get(k) or {}).get(f) for f in HIDE_FIELDS) for k in keys)


def can_take_guerrilla(keys):
    return not is_artillery(keys) and not all((STATS.get(k) or {}).get("guerrilla_deployment") for k in keys)


def can_take_fatigue(keys):
    return not is_artillery(keys) and not all((STATS.get(k) or {}).get("fatigue_resistant") for k in keys)


# (Attributes are offered unless every unit of the family already has them; units that do are unchanged.)
# Unit attribute upgrades (one level each): (line key, label, bonus, value, cost, icon, panel column,
# tooltip, effect text, who can take it). The general_aoe_mod ones are bits patch v4 turns into the
# unit's flags; fatigue_resistance is a vanilla unit-type bonus (sets the fatigue_resistant flag).
ATTRIBUTE_LINES = [
    ("passive_snipe", "Fire While Hidden", "general_aoe_mod", 1 << SNIPE_BIT, 8, "skill_snipe", "ranged",
     "This unit stays hidden while it shoots, as long as it isn't spotted.", "Can fire while hidden",
     lambda keys: can_take_snipe(keys)),
    ("passive_camo", "Camouflage", "general_aoe_mod", 1 << CAMO_BIT, 6, "skill_spot_distance", "physical",
     "This unit can hide in woodland, scrub, long grass and buildings.", "Can hide in every terrain",
     lambda keys: lacks_any_hide(keys)),
    ("passive_guerrilla", "Guerrilla Deployment", "general_aoe_mod", 1 << GUERRILLA_BIT, 10, "skill_guerilla_deployment",
     "leadership", "This unit can deploy anywhere on the battlefield that the enemy can't see.", "Guerrilla deployment",
     lambda keys: can_take_guerrilla(keys)),
    ("passive_fatigue", "Fatigue Resistant", "fatigue_resistance", 1, 6, "skill_stamina", "physical",
     "This unit tires more slowly.", "Fatigue resistant", lambda keys: can_take_fatigue(keys)),
]

SNIPE_WEAPONS = {"bow", "musket", "rifle", "sling"}
HIDE_FIELDS = ("hide_medium_woodland", "hide_scrub", "hide_long_grass", "hide_buildings")


def can_take_snipe(keys):
    """Fire While Hidden: units with bows, guns or slings (not rockets, mortars or bombs) that can hide
    somewhere and can't already."""
    stats = [STATS.get(k) or {} for k in keys]
    return (all(s.get("primary_missile_weapon") in SNIPE_WEAPONS for s in stats) and not is_artillery(keys)
            and all(any(s.get(f) for f in HIDE_FIELDS) for s in stats) and not all(s.get("can_snipe") for s in stats))


def fill_median_steps(catalog):
    """Lines a unit's tree doesn't give (levels None) use the median step of the trees that do."""
    steps = collections.defaultdict(list)
    for fam in catalog:
        for line in fam["lines"]:
            if line.get("from_tree") and line["levels"]:
                steps[line["bonus"]].append(line["levels"][0])
    for fam in catalog:
        for line in fam["lines"]:
            if line["kind"] == "stat" and line["levels"] is None:
                vals = sorted(steps[line["bonus"]]) or [1.0]
                step = vals[len(vals) // 2]
                line["levels"] = [step * i for i in range(1, STAT_MAX_LEVEL + 1)]


def bundle_key(fam, line, level):
    return f"vu_{fam}__{line['key']}_{level}"


def effect_key(bonus, unit):
    return f"vu_{bonus}__{unit}"


def build(catalog):
    """Effects and bundles for the stat and passive lines. Each effect targets one unit record, so
    the family's copies get their own effects and every bundle covers originals and copies alike."""
    eff_rows, junc_rows, bundle_rows, bjunc_rows = [], [], [], []
    eff_loc, bundle_loc = [], []
    seen_effects = set()
    for fam in catalog:
        disp = fam["display"]
        for line in fam["lines"]:
            if line["kind"] == "ability":
                ability_bundle(fam, line, eff_rows, junc_rows, bundle_rows, bjunc_rows, eff_loc, bundle_loc, seen_effects)
                continue
            effect_keys = []
            for u in fam["units"] + fam["copy_keys"]:
                # attribute lines sharing general_aoe_mod get effects of their own (one bit each)
                ek = effect_key(line["key"] if line["bonus"] == "general_aoe_mod" else line["bonus"], u)
                effect_keys.append(ek)
                if ek not in seen_effects:
                    seen_effects.add(ek)
                    eff_rows.append({"effect": ek, "icon": ICON, "priority": 900})
                    junc_rows.append({"bonus_value_id": line["bonus"], "effect": ek, "unit_record_key": u})
                    text = (line.get("effect_text") or (STAT_UNIT[line["bonus"]][1] if line["bonus"] in STAT_UNIT
                            else f"%+n {BONUS_LABEL.get(line['bonus'], line['label'])}"))
                    eff_loc.append(("effects_description_" + ek, f"{text} for {disp} (veteran upgrades)"))
            for lvl, value in enumerate(line["levels"], 1):
                bk = bundle_key(fam["id"], line, lvl)
                title = f"Veterans: {disp} {line['label']}" + (f" {ROMAN[lvl]}" if len(line["levels"]) > 1 else "")
                bundle_rows.append({"key": bk, "localised_description": title, "localised_title": title,
                                    "ui_icon": "bos_effect_faction_aizu.tga"})
                bundle_loc += [("effect_bundles_localised_title_" + bk, title),
                               ("effect_bundles_localised_description_" + bk, title)]
                for ek in effect_keys:
                    bjunc_rows.append({"effect_bundle_key": bk, "effect_key": ek, "value": float(value)})
    return {"effects": eff_rows, "junc": junc_rows, "bundles": bundle_rows, "bjunc": bjunc_rows,
            "eff_loc": eff_loc, "bundle_loc": bundle_loc}


BITS = {}   # ability -> bit (assign_ability_bits)


def assign_ability_bits(catalog):
    """Bits per ability, unique among the abilities of each unit type (abilities.assign_bits)."""
    per_unit = collections.defaultdict(set)
    for fam in catalog:
        for line in fam["lines"]:
            if line["kind"] == "ability":
                for u in ability_targets(fam, line["ability"]):
                    per_unit[u].add(line["ability"])
    BITS.clear(); BITS.update(assign_bits(per_unit))
    print(f"ability bits: {len(BITS)} abilities in {max(BITS.values()) + 1} bits; most on one unit type: "
          f"{max(len(v) for v in per_unit.values())}")


def clone_key(line):
    return patch_clone_key(BITS[line["ability"]], line["ability"], line.get("no_research", False))


def ability_targets(fam, ab):
    """The family's unit keys that get the ability's clone: those that don't have the ability natively."""
    native = collections.defaultdict(set)
    for r in ABIL_JUNC:
        native[r["unit_name"]].add(r["ability"])
    return [u for u in fam["units"] if ab not in native[u]]


def ability_bundle(fam, line, eff_rows, junc_rows, bundle_rows, bjunc_rows, eff_loc, bundle_loc, seen_effects):
    """An ability line = one bundle: general_aoe_mod += 2^bit on each target unit type (one effect per
    (ability, unit), shared by nothing else). Bits of different abilities add up to the unit's mask."""
    ab, disp = line["ability"], fam["display"]
    bk = bundle_key(fam["id"], line, 1)
    title = f"Veterans: {disp} {line['label']}"
    bundle_rows.append({"key": bk, "localised_description": title, "localised_title": title,
                        "ui_icon": "bos_effect_faction_aizu.tga"})
    bundle_loc += [("effect_bundles_localised_title_" + bk, title), ("effect_bundles_localised_description_" + bk, title)]
    for u in ability_targets(fam, ab):
        ek = f"vu_ab_{ab}__{u}"
        if ek not in seen_effects:
            seen_effects.add(ek)
            eff_rows.append({"effect": ek, "icon": ICON, "priority": 900})
            junc_rows.append({"bonus_value_id": "general_aoe_mod", "effect": ek, "unit_record_key": u})
            eff_loc.append(("effects_description_" + ek, f"{line['label']} ability for {disp} (veteran upgrades)"))
        bjunc_rows.append({"effect_bundle_key": bk, "effect_key": ek, "value": float(1 << BITS[ab])})


def clone_tables(catalog):
    """Clone ability records (one per clone key in use: bit, ability, research waived) and their attachments."""
    used = {}
    for f in catalog:
        for l in f["lines"]:
            if l["kind"] == "ability":
                used[clone_key(l)] = l["ability"]
    out = collections.defaultdict(list)
    for table in ("unit_abilities_tables", "unit_special_abilities_tables", "unit_info_card_abilities_strings_tables"):
        rows = {r["key"]: r for r in load(table)}
        for ck, ab in sorted(used.items()):
            if ab in rows:
                r = dict(rows[ab], key=ck)
                if table == "unit_abilities_tables":
                    r.update(supersedes_ability=ab, requires_effect_enabling=True)
                out[table].append(r)
    seen = set()
    for fam in catalog:
        for line in fam["lines"]:
            if line["kind"] == "ability":
                for u in ability_targets(fam, line["ability"]):
                    row = (u, clone_key(line))
                    if row not in seen:
                        seen.add(row)
                        out["unit_to_unit_abilities_junctions_tables"].append({"unit_name": u, "ability": row[1]})
    return out


BONUS_LABEL = {v[0]: v[1] for v in BONUS.values()}
BONUS_LABEL["scares_men"] = "Scare Enemies"
BONUS_LABEL.update({"bonus_vs_cavalry": "bonus vs cavalry", "charge_bonus": "charge bonus", "mod_land_movement_battle": "battle speed", "reload": "reload skill",
                    "ammo_mod": "ammunition", "range_mod": "range"})
STAT_ICON_PATH = "data/ui/frontend ui/skills/skill_melee_attack.tga"


def table_file_full(table, extra_rows):
    """Full copy of the vanilla table file plus our rows, under the vanilla file name (replaces it)."""
    path = f"db\\{table}\\{table[:-len('_tables')]}"
    ver, header, rows = load_file(DATA, path)
    return path, encode(table, ver, rows + extra_rows, header)


def new_table(table, name, rows):
    """A separately named table file holding only our rows (merging is confirmed to work)."""
    ver, header, _ = load_file(DATA, f"db\\{table}\\{table[:-len('_tables')]}")
    return f"db\\{table}\\{name}", encode(table, ver, rows, header)


def loc_file(vanilla_path, name, extra):
    """Our rows only, in a loc file of our own name next to the vanilla one: the game merges every
    .loc file (MoSS names its new artillery only in text\\db\\yogi_art_units.loc). Shipping a full copy
    of the vanilla file instead would wipe out another mod's texts (or theirs ours)."""
    ver, _ = read_loc(extract(LOCAL, vanilla_path))
    return vanilla_path.rsplit("\\", 1)[0] + "\\" + name, write_loc([(k, v, 1) for k, v in extra], ver)


# Multiplayer is switched off while this edition is enabled: it needs the DLL patch, and a modified game
# DLL risks a VAC ban online (Shogun 2 is VAC-secured); multiplayer campaigns also need identical data.
# The main menu's C++ looks its buttons up by name with null checks (FUN_10fe27xx set-up, 0x10fe2f98
# clicks), so renaming the two multiplayer buttons in our copy of the menu layout (same length, so the
# binary layout stays valid) leaves them visible but dead. Labels come from ui_component_localisation.
MENU_LAYOUT = "ui\\frontend ui\\main"
MENU_RENAMES = {b"multiplayer": b"vu_mp_off_1", b"mp_campaign": b"vu_mp_off_2"}   # Avatar Conquest, MP campaign
MENU_TEXTS = {
    "ui_component_localisation_localised_string_mp_tx_NewState_Text_75002f": "Multiplayer: off (VU Patched)",
    "ui_component_localisation_localised_string_button_txt_NewState_Text_5b006e": "Off to keep your account safe",
    "ui_component_localisation_localised_string_button_txt_NewState_Text_430007": "Off to keep your account safe",
}


def multiplayer_off_files():
    """Our copy of the main-menu layout with the multiplayer buttons renamed (MoSS doesn't change the
    layout), and their new labels in a loc file of our own name holding only those rows. Not a full copy
    of ui_component_localisation.loc as in the Patched Edition: MoSS's clan packs ship their own, and a
    copy would replace it (or carry MoSS's texts in our pack). Which of two loc files wins for the same
    key is untested; if ours loses, the buttons are still dead but keep their usual labels."""
    layout = extract(DATA, MENU_LAYOUT)
    for old, new in MENU_RENAMES.items():
        assert len(old) == len(new)
        prefixed = len(old).to_bytes(2, "little") + old   # the layout's length-prefixed strings only
        n = layout.count(prefixed)
        # multiplayer: the button's own name + the mp_campaign button's link to it; mp_campaign: its name
        assert n == {b"multiplayer": 2, b"mp_campaign": 1}[old], (old, n)
        layout = layout.replace(prefixed, len(new).to_bytes(2, "little") + new)
    path = "text\\db\\ui_component_localisation.loc"
    _, rows = read_loc(extract(LOCAL, path))
    missing = set(MENU_TEXTS) - {k for k, _, _ in rows}
    assert not missing, missing
    return [(MENU_LAYOUT, layout), loc_file(path, "vu_ui_component_localisation.loc", list(MENU_TEXTS.items()))]


def lua_value(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, (int, float)): return repr(v)
    if isinstance(v, str): return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list): return "{ " + ", ".join(lua_value(x) for x in v) + " }"
    if isinstance(v, dict): return "{ " + ", ".join(f"{k} = {lua_value(x)}" for k, x in v.items()) + " }"
    raise TypeError(v)


def check_lua(script, name):
    """Compile a script with Lua 5.1, if lupa is available."""
    try:
        import lupa.lua51 as lua51
    except ImportError:
        print(f"WARNING: lupa not installed - {name} NOT compile-checked")
        return
    err = lua51.LuaRuntime().eval("function(s) local f, e = loadstring(s) return e end")(script.decode("utf-8"))
    if err:
        raise SystemExit(f"{name} does not compile: " + err)
    print(f"{name} compiles (Lua 5.1)")


# Our code is appended to CA's export_advice.lua instead of shipping a campaign scripting.lua: every
# campaign script requires export_advice (nothing else does) and then calls
# EpisodicScripting.SetCampaign("<campaign>"), and overhauls such as MoSS replace scripting.lua but not
# export_advice. Wrapping SetCampaign starts our code for whichever campaign script is running.
ADVICE = "export_advice.lua"
HOOK = """
-- Veteran Upgrades: Patched Edition for MoSS: generated by veteran_upgrades/build.py and appended to CA's export_advice.lua.
-- Starts the mod's code for the campaign the running campaign script names in SetCampaign.
do
local vu_campaigns = {}
%s
local ok_es, es = pcall(require, "EpisodicScripting")
if ok_es and type(es) == "table" and type(es.SetCampaign) == "function" then
	local set_campaign = es.SetCampaign
	es.SetCampaign = function(campaign, ...)
		set_campaign(campaign, ...)
		local main = vu_campaigns[campaign]
		if not main then return end
		local ok, err = pcall(main)
		if not ok then
			pcall(function()
				local f = io.open("vu_log.txt", "a")
				f:write("!! Veteran Upgrades: Patched Edition for MoSS failed to start: " .. tostring(err) .. "\\n")
				f:close()
			end)
		end
	end
end
end
"""


def campaign_key(camp):
    """The key the campaign script passes to SetCampaign: its folder (campaigns\\jap_shogun\\...)."""
    return camp["script"].split("\\")[1]


def family_factions(catalog, camp):
    """fam["factions"] = campaign clans that can recruit at least one of the family's units: the clan's
    military_group must be one of the unit's groupings (if it has any), and exclusive permissions must not bar it
    (allowed=False excludes a clan; any allowed=True row restricts the unit to the listed clans)."""
    groups = {r["key"]: r["military_group"] for r in load("factions_tables")}
    unit_groups = collections.defaultdict(set)
    for r in load("units_to_groupings_military_permissions_tables"):
        unit_groups[r["unit"]].add(r["military_group"])
    allow, deny = collections.defaultdict(set), collections.defaultdict(set)
    for r in load("units_to_exclusive_faction_permissions_tables"):
        (allow if r["allowed"] else deny)[r["key"]].add(r["faction"])
    buildable = {r["unit"] for r in load("building_units_allowed_tables")}   # no building: script/reward only
    clans = campaign_factions(camp)
    for fam in catalog:
        ok = set()
        for u in fam["units"]:
            if u not in buildable:
                continue
            for f in clans:
                in_group = not unit_groups[u] or groups.get(f) in unit_groups[u]   # no rows: no group limit
                if in_group and f not in deny[u] and (not allow[u] or f in allow[u]):
                    ok.add(f)
        fam["factions"] = sorted(ok)


def campaign_factions(camp):
    """Campaign clan keys (rebels, custom-battle and tutorial factions excluded)."""
    keys = [r["key"] for r in load("factions_tables") if not r["is_rebel"]]
    if camp["clan_prefix"]:
        return [k for k in keys if k.startswith(camp["clan_prefix"]) and not k.startswith("bos_cb_")]
    return [k for k in keys if not k.startswith(("bos_", "gem_", "mp_", "tut", "movie"))]


def lua_data(catalog, camp):
    fams = []
    for fam in catalog:
        lines = []
        for line in fam["lines"]:
            ability = line["kind"] == "ability"
            lines.append({"key": line["key"], "label": line["label"], "advanced": line["advanced"], "icon": line["icon"],
                          "bonus": line["bonus"], "stat": BONUS_LABEL.get(line["bonus"], line["label"]),
                          "unit": STAT_UNIT.get(line["bonus"], ("",))[0],
                          "needs_patch": ability or line["bonus"] in PATCH_STATS,   # fatigue_resistance: vanilla
                          "kind": line["kind"], "column": line["column"], "row": line["row"], "page": line["page"],
                          "desc": line.get("desc", ""), "gated": line.get("gated", False), "requires": line.get("requires", ""),
                          "levels": [{"bundle": bundle_key(fam["id"], line, i), "value": v,
                                      "cost": ABILITY_COSTS.get(line.get("ability"), ABILITY_COST) if ability
                                      else (line.get("cost", PASSIVE_COST) if line["kind"] == "passive" else line["costs"][i - 1])}
                                     for i, v in enumerate(line["levels"], 1)]})
        fams.append({"id": fam["id"], "name": fam["display"], "portrait": fam["portrait"] or STAT_ICON_PATH,
                     "category": fam["category"], "names": fam["names"], "units": fam["units"], "lines": lines,
                     "abilities": ["ab_" + ab for ab in fam["abilities"]], "copies": fam["copies"],
                     "factions": fam["factions"]})
    return ("-- generated by veteran_upgrades/build.py\n"
            f"local VU_START_POINTS = {START_POINTS}\n"
            + f"local VU_VERSION = {lua_value(VERSION)}\n"
            + f"local VU_TITLE = {lua_value(TITLE)}\n"
            + ("local VU_DEBUG = true\n" if DEBUG else "local VU_DEBUG = false\n")
            + f"local VU_CAMPAIGN = {lua_value(camp['id'])}\n"
            + "local VU_FACTIONS = " + lua_value(campaign_factions(camp)) + "\n"
            + "local VU_CATEGORY_LIST = " + lua_value([{"id": c[0], "label": c[1], "tpl": c[2], "tip": c[3]}
                                                       for c in camp["categories"]]) + "\n"
            + "local VU_FAMILIES = {\n" + "".join(f"\t{lua_value(f)},\n" for f in fams) + "}\n")


if __name__ == "__main__":
    catalogs, scripts = {}, []
    for camp in CAMPAIGNS:
        print(f"== {camp['id']}")
        catalog = build_catalog(camp)
        for fam in catalog:   # no unit copies in this edition
            fam["copies"], fam["copy_keys"] = [], []
        for fam in catalog:
            print(f"   {fam['display']:<34} {fam['category']:<18} {len(fam['units'])} keys, {len(fam['lines'])} lines, "
                  f"{len(fam['copy_keys'])} copies, {len(fam['factions'])} clans, portrait={'yes' if fam['portrait'] else 'NO'}")
        catalogs[camp["id"]] = catalog
    every = [f for c in CAMPAIGNS for f in catalogs[c["id"]]]
    ids = [f["id"] for f in every]
    assert len(ids) == len(set(ids)), "family ids must be unique across campaigns"
    assign_ability_bits(every)
    b = build(every)
    ct = clone_tables(every)
    files = [
        new_table("effects_tables", "veteran_upgrades", b["effects"]),
        new_table("effect_bonus_value_unit_record_junctions_tables", "veteran_upgrades", b["junc"]),
        new_table("effect_bundles_tables", "veteran_upgrades", b["bundles"]),
        new_table("effect_bundles_to_effects_junctions_tables", "veteran_upgrades", b["bjunc"]),
        loc_file("text\\db\\effects.loc", "vu_effects.loc", b["eff_loc"]),
        loc_file("text\\db\\effect_bundles.loc", "vu_effect_bundles.loc", b["bundle_loc"]),
    ]
    files += [new_table(t, "vu_ability_clones", rows) for t, rows in ct.items()]
    files += multiplayer_off_files()
    # The patch-detection snippet from the patch repo, as a local function.
    detect = open(os.path.join(HERE, "..", "..", "detect.lua")).read().replace(
        "function ability_patch_version()", "local function ability_patch_version()")
    vu_lua = detect + "\n" + open(os.path.join(HERE, "vu.lua")).read()
    mains = []
    for camp in CAMPAIGNS:
        catalog = catalogs[camp["id"]]
        n_ab = sum(1 for f in catalog for l in f["lines"] if l["kind"] == "ability")
        print(f"{camp['id']}: {len(catalog)} families, {n_ab} ability unlocks")
        our_script = lua_data(catalog, camp) + vu_lua
        # Each campaign's code runs in its own function (Lua 5.1 allows 200 locals per function).
        mains.append(f"vu_campaigns[{lua_value(campaign_key(camp))}] = function()\n{our_script}\nend")
    hook = HOOK % "\n".join(mains)
    vanilla = extract(DATA, ADVICE).rstrip()
    script = vanilla + b"\r\n" + hook.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    check_lua(script, ADVICE)
    files.append((ADVICE, script))
    out = os.path.join(HERE, PACK_NAME)
    write_pack(out, files, pack_type="mod")
    print(f"{len(b['effects'])} effects, {len(b['bundles'])} bundles, {len(ct['unit_abilities_tables'])} ability clones, "
          f"{len(ct['unit_to_unit_abilities_junctions_tables'])} clone attachments, {len(files)} files -> {out}")
