"""Shogun 2 ability patch: lets an effect unlock an ability for ONE unit type, on units that exist.

Usage (from this folder, with the venv):
  .venv/bin/python patch.py status            # is the game DLL vanilla, patched or unknown?
  .venv/bin/python patch.py apply             # back up the vanilla DLL, then patch it in place
  .venv/bin/python patch.py restore           # put the vanilla DLL back
  .venv/bin/python patch.py show              # print the patch bytes, disassembled (changes nothing)
  apply/restore refuse a DLL that is neither vanilla nor patched by this script (--force overrides)

What it changes (empire.retail.dll, Steam build sha256 022fae2e...f874f5):
  The unit-capabilities builder (FUN_1019e580) walks a unit type's ability list and grants each
  ability that has requires_effect_enabling == False, or whose clan/army bonus "enable" is set.
  Mods attach CLONE ability records to unit types (abilities.py): key "vuNN_<ability>" with
  supersedes_ability = the real ability and requires_effect_enabling = True. The engine ignores
  unknown ability keys, so without the patch clones do nothing. With the patch, when a clone fails
  the vanilla check, bit NN of the unit type's general_aoe_mod bonus (same bonus list) decides: if
  it is set - and, for an ability that itself needs research, the research is done, unless the
  key is "vuNNf<ability>", which waives it - the REAL ability is granted in the clone's place. Real abilities, natives and units without clones are
  never affected.
"""
import hashlib, os, shutil, struct, sys

import capstone, keystone, pefile

from abilities import MAX_BITS, SNIPE_BIT, CAMO_BIT, GUERRILLA_BIT

GAME = os.environ.get("SHOGUN2_DIR", os.path.expanduser(
    "~/.local/share/Steam/steamapps/common/Total War SHOGUN 2"))
DLL = os.path.join(GAME, "empire.retail.dll")
BACKUP = DLL + ".vanilla"

VANILLA_SHA256 = "022fae2e2da92b59b8b1b8ee52887003c624e3c8eca060b209f5d792a7f874f5"
BASE = 0x10000000

# The loop in FUN_1019e580 (esp offsets are inside the loop; see README):
#   [esp+0x10..0x1b] locals only used after the loop -> our scratch slots
#   [esp+0x24] the unit type's ability vector (unit_record + 0xfc), [esp+0x28] the bonus list
#   ebx = cursor into the vector, edi = *ebx (UNIT_ABILITY_RECORD*)
#   1019e635 mov ecx,[esp+0x28] / push 0 / push edi / call 0x10bcf3e0 (IsEnabled) / test eax,eax
#   1019e643 je 0x1019e6f2        ; HOOK 1: not enabled -> our routine
#   1019e649 ...                  ; grant path: appends *ebx to the output
#   1019e6f2 mov edx,[esp+0x24]   ; HOOK 2: next element (both paths end here)
#   1019e6f6 add ebx,4
#   1019e6f9 ...
HOOK_VA = 0x1019E643
HOOK_ORIG = bytes.fromhex("0f84a9000000")
GRANT_VA = 0x1019E649
SKIP_VA = 0x1019E6F2
HOOK2_VA = 0x1019E6F2
HOOK2_ORIG = bytes.fromhex("8b54242483c304")
HOOK2_RESUME = 0x1019E6F9

IS_ENABLED_FN = 0x10BCF3E0     # thiscall int(list, ability, 0): the vanilla research/skill check
BONUS_LOOKUP_FN = 0x10BD5EE0   # thiscall int(list, category, record, 0, bonus_id) -> round(value)
# (key order as in the engine's own wrappers, e.g. 0x10bcf460 for unit_record and 0x10bcf3e0 for abilities)
CAT_UNIT_RECORD = 0x10         # bonus category 16 = unit_record
BONUS_GENERAL_AOE = 9          # index of general_aoe_mod in the unit_record bonus list
UNIT_ABILITIES_OFFSET = 0xFC   # unit record: ability vector (cap, count, data)
ABILITY_SUPERSEDES = 0x1C      # UNIT_ABILITY_RECORD: resolved supersedes_ability pointer
ABILITY_GATED = 0x20           # UNIT_ABILITY_RECORD: requires_effect_enabling
# UNIT_ABILITY_RECORD starts with its key, a UniString { length, capacity, UTF-16 data* }
KEY_LENGTH, KEY_DATA = 0x0, 0x8

TEXT_VSIZE_PATCHED = 0x159FE00  # .text VirtualSize grown to its raw size, so the tail is code
CAVE_VA = BASE + 0x1000 + 0x159FC40
CAVE2_OFFSET = 0xC4             # hook-2 routine
STATS_OFFSET = 0xDC             # per-unit-type stat routines (v4)
SIGNATURE_OFFSET = 0x150        # ASCII signature + version, for mods to detect the patch (fixed since v2)
PARSE_OFFSET = 0x164            # bonus-name parser extension + its name table (v4)
CAVE_END = 0x1C0                # end of the .text tail
SIGNATURE = b"VU_ABILITY_PATCH 4\0"

# v4: per-unit-type stats. The land unit stats builder FUN_10151f10 adds clan bonuses to a unit's stats
# from the unit's class (category 13) or category (14) only. Each hooked call below still makes that
# lookup, then also adds the unit_record (16) bonus with id = the original id + 0x10, for the unit
# record in esi (the builder keeps it there at all five calls).
#   (call site, original target, kind, bonus name the parser accepts at unit_record scope)
BONUS_LOOKUP_FLOAT_FN = 0x10BD5E70   # thiscall float(list, category, record, 0, bonus_id), in st(0)
CAT_UNIT_CLASS, CAT_UNIT_CATEGORY = 0x0D, 0x0E
STAT_ID_SHIFT = 0x10
STAT_HOOKS = [
    (0x10152620, 0x10BCF440, "charge", 0x0B, "charge_bonus"),            # class 11 -> charge (+ fire while hidden)
    (0x1015270D, 0x10BCF440, "int", 0x04, "reload"),                     # class 4  -> reload skill %
    (0x10152814, 0x10BCF2C0, "range", 0x07, "range_mod"),                # class 7  -> range bonus (added)
    (0x10152846, 0x10BCF2A0, "category_f", 0x09, "mod_land_movement_battle"),  # category 9 -> speed %
    (0x10152878, 0x10BCF2C0, "class_f", 0x08, "ammo_mod"),               # class 8  -> ammo %
]
STAT_BONUSES = {name: orig_id + STAT_ID_SHIFT for _, _, _, orig_id, name in STAT_HOOKS}
# Range: the builder multiplies the stats field +0x40 by (1 + class range_mod %), but that field is an
# ADDITIVE range bonus that starts at 0 (battle unit +0x170 = stats +0x40, the battle unit holding the
# stats at +0x130; the range_effect ability adds _kv special_ability_bonus_range_increase_max_range to
# it), so the vanilla class bonus never did anything. The range routine adds class + unit_record bonus
# to the field instead, and returns 0 so the builder's multiply keeps it. At the call, the field is
# the builder's [esp+0xb8] (after the call returns), i.e. [esp+0xc4] at the routine's entry.
RANGE_FIELD_AT_ENTRY = 0xC4
RANGE_VA = 0x100B5B20          # in the 56 bytes of int3 padding at 0x100b5b18..0x100b5b4f
RANGE_PAD_END = 0x100B5B50
# Unit attributes and bonus vs cavalry. The stats struct holds unit_stats_land's flags as bytes (the
# constructor FUN_10c0ac90 copies them from the record): hide_medium_woodland/scrub/long_grass/
# buildings at +0x4f..+0x52, can_snipe at +0x54, guerrilla_deployment at +0x69; and
# melee_bonus_vs_cavalry (int) at +0x1c. The charge call's routine (charge as the other int stats)
# also reads the unit type's general_aoe_mod bits 21-23 and sets those flags, and adds a new
# unit_record bonus "bonus_vs_cavalry" (id BONUS_VS_CAVALRY) to +0x1c. At that call the struct is the
# builder's [esp+0x78] (charge, +0xf0, is its [esp+0x168]), i.e. [esp+0x84] at the routine's entry.
# The routine is too big for one gap, so it runs through three int3 padding gaps, joined by jumps.
STRUCT_AT_ENTRY = 0x84
FLAG_SNIPE, FLAG_HIDE4, FLAG_GUERRILLA, FIELD_VS_CAVALRY = 0x54, 0x4F, 0x69, 0x1C
BONUS_VS_CAVALRY = 0x20
VS_CAVALRY_NAME = b"bonus_vs_cavalry\0"
CHARGE_GAPS = [(0x1127FE32, 0x1127FE60),   # (start, end) of each gap: part 1 = the charge routine's entry
               (0x107413E1, 0x10741410),
               (0x10E13B23, 0x10E13B50)]   # part 3, then the bonus name
# The engine's own copies of those names (the unit_class/unit_category name tables point at them).
NAME_VA = {"charge_bonus": 0x1164EA58, "reload": 0x1164EAD4, "range_mod": 0x1164EAEC,
           "mod_land_movement_battle": 0x1164EA68, "ammo_mod": 0x1164DD98}
# FUN_10bd3d30 maps a unit_record bonus name to its id (13 names; 13 = not found). Its not-found exit
#   10bd3d5d pop edi / mov eax,0xd / pop esi / ret
# jumps to our extension, which also accepts the five names above.
PARSE_HOOK_VA = 0x10BD3D5D
PARSE_HOOK_ORIG = bytes.fromhex("5fb80d0000005ec3")
NAME_MATCH_FN = 0x100EE2D0           # thiscall bool(UniString*, const char*): the parser's comparison
UNIT_RECORD_BONUS_COUNT = 0x0D

# v4: drop-in battles off. A drop-in battle is an online battle against another player, so with a
# modified game file it risks a Valve Anti-Cheat ban. Both ways in are cut, whether or not the mod is
# enabled (the mod also hides the buttons):
#   * invitations to join someone else's battle: the multiplayer message handler for "drop-in match
#     candidate found" (0x11153f10, a virtual in the table at 0x11715364) only tells the UI, which
#     then shows the "Drop-in battle available" panel. It now returns before that. The patch starts
#     after its first instruction, which holds a relocated address.
#   * hosting (another player takes over the AI army): the campaign's "drop-in battles" flag
#     ([obj+0x50]) is computed at 0x111860a8 as "not multiplayer, and the allow_drop_in_battles
#     preference (id 0x67, on by default)"; with it on, the first battle tried to host and was
#     cancelled. It is now always computed as off, and its setter (0x11189000, virtual; also writes
#     the preference) always stores off. As a backstop, CampaignUI.PlayDropInBattle (0x11143680) calls
#     0x111242b0 (its only caller) to start matchmaking; that now returns 0 (not started).
DROPIN_PATCHES = [
    (0x111860BD, bytes.fromhex("b001"), bytes.fromhex("30c0")),               # mov al,1 -> xor al,al
    (0x11189001, bytes.fromhex("8a5c2408"), bytes.fromhex("31db9090")),       # mov bl,[esp+8] -> xor ebx,ebx
    (0x11153F16, bytes.fromhex("83ec246a00"), bytes.fromhex("31c0c20400")),   # xor eax,eax / ret 4
    (0x111242B0, bytes.fromhex("568bf18b86"), bytes.fromhex("31c0c20800")),   # xor eax,eax / ret 8
]

ASM = f"""
    test eax, eax
    jnz grant
    mov edx, dword ptr [edi + {ABILITY_SUPERSEDES:#x}]
    test edx, edx
    jz skip
    cmp dword ptr [edi + {KEY_LENGTH:#x}], 5
    jb skip
    mov ecx, dword ptr [edi + {KEY_DATA:#x}]
    cmp word ptr [ecx], 0x76
    jne skip
    cmp word ptr [ecx + 2], 0x75
    jne skip
    cmp word ptr [ecx + 8], 0x5f
    je key_ok
    cmp word ptr [ecx + 8], 0x66
    jne skip
key_ok:
    movzx eax, word ptr [ecx + 4]
    sub eax, 0x30
    cmp eax, 9
    ja skip
    imul eax, eax, 10
    movzx ecx, word ptr [ecx + 6]
    sub ecx, 0x30
    cmp ecx, 9
    ja skip
    add eax, ecx
    cmp eax, {MAX_BITS}
    jae skip
    push edx
    push eax
    mov ecx, dword ptr [esp + 0x30]
    mov eax, dword ptr [esp + 0x2c]
    sub eax, {UNIT_ABILITIES_OFFSET:#x}
    push {BONUS_GENERAL_AOE}
    push 0
    push eax
    push {CAT_UNIT_RECORD:#x}
    call {BONUS_LOOKUP_FN:#x}
    pop ecx
    bt eax, ecx
    jnc skip1
    mov eax, dword ptr [edi + {KEY_DATA:#x}]
    cmp word ptr [eax + 8], 0x66
    je substitute
    mov eax, dword ptr [esp]
    cmp byte ptr [eax + {ABILITY_GATED:#x}], 0
    je substitute
    mov ecx, dword ptr [esp + 0x2c]
    push 0
    push eax
    call {IS_ENABLED_FN:#x}
    test eax, eax
    jz skip1
substitute:
    pop eax
    mov dword ptr [esp + 0x10], eax
    mov dword ptr [esp + 0x14], ebx
    lea ebx, [esp + 0x10]
grant:
    jmp {GRANT_VA:#x}
skip1:
    add esp, 4
skip:
    jmp {SKIP_VA:#x}
"""
# Clone check: supersedes set, key "vuNN_..." or "vuNNf..." (UTF-16 'v','u', two digits, '_' or 'f'), NN < MAX_BITS.
# Stack bookkeeping: at hook 1 esp is as at 1019e635 (vector [esp+0x24], list [esp+0x28]).
# After `push edx` (real ability) they are at +0x28/+0x2c; after `push eax` (bit) at +0x2c/+0x30.
# Substitution: the grant path appends *ebx, so ebx is pointed at a scratch local holding the real
# ability; hook 2 puts the saved cursor back before the loop advances.

ASM2 = f"""
    lea eax, [esp + 0x10]
    cmp ebx, eax
    jne advance
    mov ebx, dword ptr [esp + 0x14]
advance:
    mov edx, dword ptr [esp + 0x24]
    add ebx, 4
    jmp {HOOK2_RESUME:#x}
"""
# eax is free at hook 2: the instruction after the resume point (1019e6fc) reloads it.

# Stat routines replace `call <class/category lookup wrapper>` (thiscall(record, id), ret 8). Each one
# makes the wrapper's own lookup, then adds the unit_record lookup for id + 0x10 (record = esi).
# Every caller reloads ecx before its next call and keeps nothing in edx, so both are free here.
ASM_STATS = f"""
stat_int:
    push ecx
    push dword ptr [esp + 0xc]
    push 0
    push dword ptr [esp + 0x10]
    push {CAT_UNIT_CLASS:#x}
    call {BONUS_LOOKUP_FN:#x}
    pop ecx
    push eax
    mov eax, dword ptr [esp + 0xc]
    add eax, {STAT_ID_SHIFT:#x}
    push eax
    push 0
    push esi
    push {CAT_UNIT_RECORD:#x}
    call {BONUS_LOOKUP_FN:#x}
    pop edx
    add eax, edx
    ret 8
stat_f:
    pop eax
    push ecx
    push dword ptr [esp + 0xc]
    push 0
    push dword ptr [esp + 0x10]
    push eax
    call {BONUS_LOOKUP_FLOAT_FN:#x}
    pop ecx
    push eax
    fstp dword ptr [esp]
    mov eax, dword ptr [esp + 0xc]
    add eax, {STAT_ID_SHIFT:#x}
    push eax
    push 0
    push esi
    push {CAT_UNIT_RECORD:#x}
    call {BONUS_LOOKUP_FLOAT_FN:#x}
    fadd dword ptr [esp]
    pop eax
    ret 8
stat_category_f:
    push {CAT_UNIT_CATEGORY:#x}
    jmp stat_f
stat_class_f:
    push {CAT_UNIT_CLASS:#x}
    jmp stat_f
"""
# Stack at entry: [esp] return, [esp+4] class/category record, [esp+8] bonus id. After `push ecx` they
# are +4/+8/+0xc; the first two pushes for the lookup move the record to +0x10. After `pop ecx` and
# `push eax` (the first result, or a slot for it) the id is at +0xc again.

ASM_RANGE = f"""
    push dword ptr [esp + 8]
    push dword ptr [esp + 8]
    call STAT_CLASS_F
    fadd dword ptr [esp + {RANGE_FIELD_AT_ENTRY:#x}]
    fstp dword ptr [esp + {RANGE_FIELD_AT_ENTRY:#x}]
    fldz
    ret 8
"""
ASM_CHARGE = [f"""
    push ecx
    push dword ptr [esp + 0xc]
    push dword ptr [esp + 0xc]
    call STAT_INT
    pop ecx
    push eax
    push ecx
    push {BONUS_GENERAL_AOE}
    push 0
    push esi
    push {CAT_UNIT_RECORD:#x}
    call {BONUS_LOOKUP_FN:#x}
    lea edx, [esp + {STRUCT_AT_ENTRY + 8:#x}]
    jmp PART2
""", f"""
    shl eax, {32 - SNIPE_BIT}
    jnc no_snipe
    mov byte ptr [edx + {FLAG_SNIPE:#x}], 1
no_snipe:
    shl eax, 1
    jnc no_camo
    mov dword ptr [edx + {FLAG_HIDE4:#x}], 0x01010101
no_camo:
    shl eax, 1
    jnc no_guerrilla
    mov byte ptr [edx + {FLAG_GUERRILLA:#x}], 1
no_guerrilla:
    pop ecx
    push edx
    jmp PART3
""", f"""
    push {BONUS_VS_CAVALRY:#x}
    push 0
    push esi
    push {CAT_UNIT_RECORD:#x}
    call {BONUS_LOOKUP_FN:#x}
    pop edx
    add dword ptr [edx + {FIELD_VS_CAVALRY:#x}], eax
    pop eax
    ret 8
"""]
# Part 1: charge as stat_int (class + unit_record), keeping the container; then [esp] = container,
# [esp+4] = charge result, so the struct is at [esp + 8 + STRUCT_AT_ENTRY]. Part 2: shifting the bits
# out of eax tests 23 (fire while hidden), 22 (hide everywhere: four bytes), 21 (guerrilla); edx
# (the struct) is saved over the next lookup. Part 3: bonus vs cavalry, then return the charge.

# The two pushes repeat the routine's own arguments (class record, bonus id) for stat_class_f, which
# returns class + unit_record bonus in st(0) and pops them.

# Parser extension. Table entries: int32 (name VA - entry VA, so no relocation is needed under ASLR),
# then the id byte; a zero int32 ends it. esi/edi are the parser's (callee-saved, pushed on entry).
ASM_PARSE = f"""
    call here
here:
    pop esi
    add esi, TABLE_DELTA
next_name:
    mov eax, dword ptr [esi]
    test eax, eax
    jz not_found
    add eax, esi
    push eax
    mov ecx, edi
    call {NAME_MATCH_FN:#x}
    test al, al
    jnz found
    add esi, 5
    jmp next_name
found:
    movzx eax, byte ptr [esi + 4]
    jmp done
not_found:
    mov eax, {UNIT_RECORD_BONUS_COUNT:#x}
done:
    pop edi
    pop esi
    ret
"""


def _ks():
    return keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)


def _asm(src, va):
    return bytes(_ks().asm(src, va)[0])


def stat_labels():
    """Entry point of each stat routine kind, as VAs."""
    va = CAVE_VA + STATS_OFFSET
    # keystone has no symbol export: assemble the code up to each label to get its offset (the entry
    # stubs come last, so every prefix only refers back to labels it contains)
    labels = {}
    for kind in ("int", "category_f", "class_f"):
        prefix = ASM_STATS.split(f"stat_{kind}:")[0]
        labels[kind] = va + len(_asm(prefix, va)) if prefix.strip() else va
    labels["range"] = RANGE_VA
    labels["charge"] = CHARGE_GAPS[0][0]
    return labels


def charge_parts():
    """[(VA, bytes)] of the charge routine's three parts, the last followed by the bonus name."""
    (a1, e1), (a2, e2), (a3, e3) = CHARGE_GAPS
    src = [ASM_CHARGE[0].replace("STAT_INT", hex(stat_labels()["int"])).replace("PART2", hex(a2)),
           ASM_CHARGE[1].replace("PART3", hex(a3)), ASM_CHARGE[2]]
    parts = [(va, _asm(code, va)) for va, code in zip((a1, a2, a3), src)]
    parts[2] = (a3, parts[2][1] + VS_CAVALRY_NAME)
    for (va, code), (_, end) in zip(parts, CHARGE_GAPS):
        assert va + len(code) <= end, f"charge part at {va:#x} is {len(code):#x} bytes"
    return parts


def vs_cavalry_name_va():
    a3, code = charge_parts()[2]
    return a3 + len(code) - len(VS_CAVALRY_NAME)


def range_routine():
    code = _asm(ASM_RANGE.replace("STAT_CLASS_F", hex(stat_labels()["class_f"])), RANGE_VA)
    assert RANGE_VA + len(code) <= RANGE_PAD_END, f"range routine is {len(code):#x} bytes"
    return code


def parse_routine():
    """Parser extension + name table, at PARSE_OFFSET."""
    va = CAVE_VA + PARSE_OFFSET
    here = va + 5                               # after the 5-byte call
    code = _asm(ASM_PARSE.replace("TABLE_DELTA", "0x7f"), va)   # imm8 placeholder sizes the add
    table_va = va + len(code)
    code = _asm(ASM_PARSE.replace("TABLE_DELTA", hex(table_va - here)), va)
    assert va + len(code) == table_va, "parser routine size changed with the real delta"
    table = bytearray()
    for name, bonus_id in list(STAT_BONUSES.items()) + [("bonus_vs_cavalry", BONUS_VS_CAVALRY)]:
        entry_va = table_va + len(table)
        name_va = vs_cavalry_name_va() if name == "bonus_vs_cavalry" else NAME_VA[name]
        table += struct.pack("<iB", name_va - entry_va, bonus_id)
    return code + bytes(table) + struct.pack("<i", 0)


def assemble():
    """Patch area bytes: routine 1, routine 2, stat routines, signature, parser extension."""
    code = _asm(ASM, CAVE_VA)
    code2 = _asm(ASM2, CAVE_VA + CAVE2_OFFSET)
    stats = _asm(ASM_STATS, CAVE_VA + STATS_OFFSET)
    parse = parse_routine()
    assert len(code) <= CAVE2_OFFSET, f"routine 1 is {len(code):#x} bytes"
    assert CAVE2_OFFSET + len(code2) <= STATS_OFFSET, f"routine 2 is {len(code2):#x} bytes"
    assert STATS_OFFSET + len(stats) <= SIGNATURE_OFFSET, f"stat routines are {len(stats):#x} bytes"
    assert SIGNATURE_OFFSET + len(SIGNATURE) <= PARSE_OFFSET
    assert PARSE_OFFSET + len(parse) <= CAVE_END, f"parser extension is {len(parse):#x} bytes"
    out = bytearray(b"\xcc" * PARSE_OFFSET)
    out[:len(code)] = code
    out[CAVE2_OFFSET:CAVE2_OFFSET + len(code2)] = code2
    out[STATS_OFFSET:STATS_OFFSET + len(stats)] = stats
    out[SIGNATURE_OFFSET:SIGNATURE_OFFSET + len(SIGNATURE)] = SIGNATURE
    return bytes(out) + parse


def routines():
    """(name, VA, bytes) of each piece of new code/data, for show and docs."""
    cave = assemble()
    return [("routine 1 (abilities)", CAVE_VA, cave[:CAVE2_OFFSET].rstrip(b"\xcc")),
            ("routine 2 (abilities)", CAVE_VA + CAVE2_OFFSET, cave[CAVE2_OFFSET:STATS_OFFSET].rstrip(b"\xcc")),
            ("stat routines", CAVE_VA + STATS_OFFSET, cave[STATS_OFFSET:SIGNATURE_OFFSET].rstrip(b"\xcc")),
            ("parser extension", CAVE_VA + PARSE_OFFSET, cave[PARSE_OFFSET:])]


def jmp_bytes(src, dst, length):
    return b"\xe9" + struct.pack("<i", dst - (src + 5)) + b"\x90" * (length - 5)


def call_bytes(src, dst):
    return b"\xe8" + struct.pack("<i", dst - (src + 5))


def hooks():
    labels = stat_labels()
    out = [(HOOK_VA, HOOK_ORIG, jmp_bytes(HOOK_VA, CAVE_VA, len(HOOK_ORIG))),
           (HOOK2_VA, HOOK2_ORIG, jmp_bytes(HOOK2_VA, CAVE_VA + CAVE2_OFFSET, len(HOOK2_ORIG)))]
    for site, target, kind, _, _ in STAT_HOOKS:
        out.append((site, call_bytes(site, target), call_bytes(site, labels[kind])))
    code = range_routine()
    out.append((RANGE_VA, b"\xcc" * len(code), code))
    for va, code in charge_parts():
        out.append((va, b"\xcc" * len(code), code))
    out += DROPIN_PATCHES
    out.append((PARSE_HOOK_VA, PARSE_HOOK_ORIG,
                jmp_bytes(PARSE_HOOK_VA, CAVE_VA + PARSE_OFFSET, len(PARSE_HOOK_ORIG))))
    return out


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def offsets(pe):
    text = pe.sections[0]
    assert text.Name.rstrip(b"\0") == b".text"
    va2off = lambda va: va - BASE - text.VirtualAddress + text.PointerToRawData
    vsize_off = text.get_file_offset() + 8  # IMAGE_SECTION_HEADER.Misc.VirtualSize
    return text, va2off, vsize_off


def check_relocs(pe, ranges):
    """No base relocation may touch the bytes we overwrite (the DLL is ASLR-enabled)."""
    pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_BASERELOC"]])
    for block in pe.DIRECTORY_ENTRY_BASERELOC:
        for e in block.entries:
            if e.type == 0:
                continue
            va = BASE + e.rva
            for lo, hi in ranges:
                if lo - 3 <= va < hi:
                    raise SystemExit(f"relocation at {va:#x} overlaps the patch range {lo:#x}-{hi:#x}")


def va2off_any(pe, va):
    """File offset of a VA in any section (the bonus names live in .rdata)."""
    return pe.get_offset_from_rva(va - BASE)


def file_offsets(data=None):
    """File offsets a mod script can read to detect the patch."""
    if data is None:
        with open(BACKUP if os.path.exists(BACKUP) else DLL, "rb") as f:
            data = f.read()
    _, va2off, _ = offsets(pefile.PE(data=data, fast_load=True))
    return {"hook": va2off(HOOK_VA), "signature": va2off(CAVE_VA) + SIGNATURE_OFFSET}


def patched_image(data):
    pe = pefile.PE(data=data, fast_load=True)
    text, va2off, vsize_off = offsets(pe)
    cave = assemble()
    for va, orig, _ in hooks():
        assert data[va2off(va):va2off(va) + len(orig)] == orig, f"unexpected bytes at {va:#x}"
    cave_off = va2off(CAVE_VA)
    assert text.Misc_VirtualSize <= CAVE_VA - BASE - text.VirtualAddress
    assert CAVE_VA + len(cave) <= BASE + text.VirtualAddress + TEXT_VSIZE_PATCHED
    assert set(data[cave_off:cave_off + len(cave)]) <= {0}, "cave area is not empty"
    for name, va in NAME_VA.items():
        assert data[va2off_any(pe, va):va2off_any(pe, va) + len(name) + 1] == name.encode() + b"\0", name
    check_relocs(pe, [(va, va + len(orig)) for va, orig, _ in hooks()])
    out = bytearray(data)
    for va, _, new in hooks():
        out[va2off(va):va2off(va) + len(new)] = new
    out[cave_off:cave_off + len(cave)] = cave
    struct.pack_into("<I", out, vsize_off, TEXT_VSIZE_PATCHED)
    return bytes(out)


def disasm(code, va):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for ins in md.disasm(code, va):
        print(f"  {ins.address:08x}  {ins.bytes.hex():<16} {ins.mnemonic} {ins.op_str}")


def cmd_show():
    for va, orig, new in hooks():
        print(f"hook @ {va:#x}: {orig.hex()} -> {new.hex()}")
        disasm(new, va)
    for name, va, code in routines():
        print(f"{name} @ {va:#x}:")
        disasm(code, va)
    print(f"signature @ {CAVE_VA + SIGNATURE_OFFSET:#x}: {SIGNATURE!r}")
    print("file offsets for detection:", {k: hex(v) for k, v in file_offsets().items()})


def state():
    h = sha256(DLL)
    if h == VANILLA_SHA256:
        return "vanilla"
    src = BACKUP if os.path.exists(BACKUP) else DLL
    with open(src, "rb") as f:
        base = f.read()
    if hashlib.sha256(base).hexdigest() == VANILLA_SHA256 and h == hashlib.sha256(patched_image(base)).hexdigest():
        return "patched"
    return "unknown (an older revision of this patch, or another change)"


def ours(path):
    """Does this DLL carry our signature (any patch version)? Then it was made from the vanilla backup."""
    try:
        with open(path, "rb") as f:
            f.seek(file_offsets()["signature"])
            return f.read(len(b"VU_ABILITY_PATCH ")) == b"VU_ABILITY_PATCH "
    except OSError:
        return False


def cmd_status():
    print(f"{DLL}\n  state: {state()}")
    print(f"  backup: {'present' if os.path.exists(BACKUP) else 'none'} ({BACKUP})")


def cmd_apply(force=False):
    """Patch from the vanilla bytes. The game DLL must be vanilla, or patched by this script (any
    revision; then the vanilla backup is the source). Anything else - e.g. a Steam update - is refused
    unless --force, so a stale backup never overwrites a newer DLL."""
    if state() == "patched":
        print("already patched"); return
    dll_vanilla = sha256(DLL) == VANILLA_SHA256
    if not (dll_vanilla or ours(DLL) or force):
        raise SystemExit("the game DLL is neither vanilla nor patched by this script (a Steam update?); "
                         "refusing. Verify the game files in Steam, or pass --force")
    if dll_vanilla:
        shutil.copy2(DLL, BACKUP)
    if not (os.path.exists(BACKUP) and sha256(BACKUP) == VANILLA_SHA256):
        raise SystemExit("no vanilla backup; use Steam 'Verify integrity of game files' first")
    src = BACKUP
    with open(src, "rb") as f:
        out = patched_image(f.read())
    tmp = DLL + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, DLL)
    print("patched:", DLL)
    print("vanilla backup:", BACKUP)


def cmd_restore(force=False):
    if sha256(DLL) == VANILLA_SHA256:
        print("already vanilla"); return
    if not (ours(DLL) or force):
        raise SystemExit("the game DLL isn't patched by this script (a Steam update?); refusing to replace it "
                         "with the backup. Use Steam 'Verify integrity of game files', or pass --force")
    if not os.path.exists(BACKUP):
        raise SystemExit("no backup; use Steam 'Verify integrity of game files' instead")
    if sha256(BACKUP) != VANILLA_SHA256:
        raise SystemExit("backup doesn't match the vanilla hash; use Steam 'Verify integrity' instead")
    shutil.copy2(BACKUP, DLL)
    print("restored vanilla DLL")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    force = "--force" in sys.argv
    if cmd in ("apply", "restore"):
        {"apply": cmd_apply, "restore": cmd_restore}[cmd](force)
    else:
        {"status": cmd_status, "show": cmd_show}[cmd]()
