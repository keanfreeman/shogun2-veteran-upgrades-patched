"""Shogun 2 ability patch: lets an effect unlock an ability for ONE unit type, on units that exist.

Usage (from this folder, with the venv):
  .venv/bin/python patch.py status            # is the game DLL vanilla, patched or unknown?
  .venv/bin/python patch.py apply             # back up the vanilla DLL, then patch it in place
  .venv/bin/python patch.py restore           # put the vanilla DLL back
  .venv/bin/python patch.py show              # print the patch bytes, disassembled (changes nothing)
  add --diag to apply/show for the diagnostic table (abilities.DIAG_MODES)

What it changes (empire.retail.dll, Steam build sha256 022fae2e...f874f5):
  The unit-capabilities builder (FUN_1019e580) walks a unit type's ability list and grants each
  ability that has requires_effect_enabling == False, or whose clan/army bonus "enable" is set.
  Mods attach a CLONE ability record to a unit type: a new unit_abilities row (e.g. vu_warcry) with
  requires_effect_enabling = True and supersedes_ability = the real ability. The engine ignores
  unknown ability keys, so without the patch clones do nothing. With the patch, when a clone fails
  the vanilla check, the unit type's general_aoe_mod bonus (same bonus list) is read as a bitmask
  (abilities.py); if the real ability's bit is set - and, for an ability that itself needs research,
  the research is done - the REAL ability is granted in the clone's place.
  Real abilities, natives and units without clones are never affected.
"""
import hashlib, os, shutil, struct, sys

import capstone, keystone, pefile

from abilities import DIAG_MODES, ENUM_COUNT, enum_to_bit_table

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

ABILITY_ENUM_FN = 0x101B1670   # cdecl int(UniString* key) -> engine enum (0x45 = none)
IS_ENABLED_FN = 0x10BCF3E0     # thiscall int(list, ability, 0): the vanilla research/skill check
BONUS_LOOKUP_FN = 0x10BD5EE0   # thiscall int(list, category, record, 0, bonus_id) -> round(value)
# (key order as in the engine's own wrappers, e.g. 0x10bcf460 for unit_record and 0x10bcf3e0 for abilities)
ENUM_NONE = 0x45
CAT_UNIT_RECORD = 0x10         # bonus category 16 = unit_record
BONUS_GENERAL_AOE = 9          # index of general_aoe_mod in the unit_record bonus list
BONUS_MELEE_ATTACK = 4         # index of melee_attack_mod (diagnostic mode 3)
UNIT_ABILITIES_OFFSET = 0xFC   # unit record: ability vector (cap, count, data)
ABILITY_SUPERSEDES = 0x1C      # UNIT_ABILITY_RECORD: resolved supersedes_ability pointer
ABILITY_GATED = 0x20           # UNIT_ABILITY_RECORD: requires_effect_enabling

TEXT_VSIZE_PATCHED = 0x159FE00  # .text VirtualSize grown to its raw size, so the tail is code
CAVE_VA = BASE + 0x1000 + 0x159FC40
TABLE_OFFSET = 0xD0             # enum->bit table
CAVE2_OFFSET = 0x120            # hook-2 routine
SIGNATURE_OFFSET = 0x150        # ASCII signature + version, for mods to detect the patch
SIGNATURE = b"VU_ABILITY_PATCH 2\0"

ASM = f"""
    test eax, eax
    jnz grant
    push edi
    call {ABILITY_ENUM_FN:#x}
    add esp, 4
    cmp eax, {ENUM_NONE:#x}
    jne skip
    mov eax, dword ptr [edi + {ABILITY_SUPERSEDES:#x}]
    test eax, eax
    jz skip
    push eax
    push eax
    call {ABILITY_ENUM_FN:#x}
    add esp, 4
    cmp eax, {ENUM_COUNT}
    jae skip1
    call getpc
getpc:
    pop edx
    movzx eax, byte ptr [edx + eax + TABLE_DISP]
    cmp al, 0xff
    je skip1
    mov edx, eax
    shr edx, 5
    and eax, 0x1f
    cmp edx, 1
    je unlocked
    push eax
    push edx
    mov ecx, dword ptr [esp + 0x34]
    mov eax, dword ptr [esp + 0x30]
    sub eax, {UNIT_ABILITIES_OFFSET:#x}
    cmp edx, 3
    mov edx, {BONUS_GENERAL_AOE}
    jne push_id
    mov edx, {BONUS_MELEE_ATTACK}
push_id:
    push edx
    push 0
    push eax
    push {CAT_UNIT_RECORD:#x}
    call {BONUS_LOOKUP_FN:#x}
    pop edx
    pop ecx
    test edx, edx
    jz bit_test
    test eax, eax
    jnz unlocked
    jmp skip1
bit_test:
    bt eax, ecx
    jnc skip1
unlocked:
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
# Stack bookkeeping: at hook 1 esp is as at 1019e635 (vector [esp+0x24], list [esp+0x28]).
# After `push eax` (real ability) they are at +0x28/+0x2c; after the bit/mode pushes at +0x30/+0x34.
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


def _ks():
    return keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)


def assemble(diag=False):
    """Patch area bytes: routine 1, padding, enum->bit table, routine 2, signature."""
    ks = _ks()
    disp = 0
    for _ in range(4):  # TABLE_DISP depends on where getpc lands
        code = bytes(ks.asm(ASM.replace("TABLE_DISP", hex(disp)), CAVE_VA)[0])
        getpc = CAVE_VA + code.index(b"\xe8\x00\x00\x00\x00\x5a") + 5
        new = (CAVE_VA + TABLE_OFFSET) - getpc
        if new == disp:
            break
        disp = new
    else:
        raise RuntimeError("TABLE_DISP did not settle")
    table = enum_to_bit_table(DIAG_MODES if diag else None)
    code2 = bytes(ks.asm(ASM2, CAVE_VA + CAVE2_OFFSET)[0])
    assert len(code) <= TABLE_OFFSET and TABLE_OFFSET + len(table) <= CAVE2_OFFSET
    assert CAVE2_OFFSET + len(code2) <= SIGNATURE_OFFSET
    out = bytearray(b"\xcc" * SIGNATURE_OFFSET)
    out[:len(code)] = code
    out[TABLE_OFFSET:TABLE_OFFSET + len(table)] = table
    out[CAVE2_OFFSET:CAVE2_OFFSET + len(code2)] = code2
    return bytes(out) + SIGNATURE


def jmp_bytes(src, dst, length):
    return b"\xe9" + struct.pack("<i", dst - (src + 5)) + b"\x90" * (length - 5)


def hooks():
    return [(HOOK_VA, HOOK_ORIG, jmp_bytes(HOOK_VA, CAVE_VA, len(HOOK_ORIG))),
            (HOOK2_VA, HOOK2_ORIG, jmp_bytes(HOOK2_VA, CAVE_VA + CAVE2_OFFSET, len(HOOK2_ORIG)))]


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


def file_offsets(data=None):
    """File offsets a mod script can read to detect the patch."""
    if data is None:
        with open(BACKUP if os.path.exists(BACKUP) else DLL, "rb") as f:
            data = f.read()
    _, va2off, _ = offsets(pefile.PE(data=data, fast_load=True))
    return {"hook": va2off(HOOK_VA), "signature": va2off(CAVE_VA) + SIGNATURE_OFFSET}


def patched_image(data, diag=False):
    pe = pefile.PE(data=data, fast_load=True)
    text, va2off, vsize_off = offsets(pe)
    cave = assemble(diag)
    for va, orig, _ in hooks():
        assert data[va2off(va):va2off(va) + len(orig)] == orig, f"unexpected bytes at {va:#x}"
    cave_off = va2off(CAVE_VA)
    assert text.Misc_VirtualSize <= CAVE_VA - BASE - text.VirtualAddress
    assert CAVE_VA + len(cave) <= BASE + text.VirtualAddress + TEXT_VSIZE_PATCHED
    assert set(data[cave_off:cave_off + len(cave)]) <= {0}, "cave area is not empty"
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


def cmd_show(diag=False):
    for va, orig, new in hooks():
        print(f"hook @ {va:#x}: {orig.hex()} -> {new.hex()}")
        disasm(new, va)
    cave = assemble(diag)
    print(f"routine 1 @ {CAVE_VA:#x}:")
    disasm(cave[:TABLE_OFFSET].rstrip(b"\xcc"), CAVE_VA)
    print(f"table @ {CAVE_VA + TABLE_OFFSET:#x}:", cave[TABLE_OFFSET:TABLE_OFFSET + ENUM_COUNT].hex())
    print(f"routine 2 @ {CAVE_VA + CAVE2_OFFSET:#x}:")
    disasm(cave[CAVE2_OFFSET:SIGNATURE_OFFSET].rstrip(b"\xcc"), CAVE_VA + CAVE2_OFFSET)
    print(f"signature @ {CAVE_VA + SIGNATURE_OFFSET:#x}: {SIGNATURE!r}")
    print("file offsets for detection:", {k: hex(v) for k, v in file_offsets().items()})


def state():
    h = sha256(DLL)
    if h == VANILLA_SHA256:
        return "vanilla"
    src = BACKUP if os.path.exists(BACKUP) else DLL
    with open(src, "rb") as f:
        base = f.read()
    if hashlib.sha256(base).hexdigest() == VANILLA_SHA256:
        for diag, name in ((False, "patched"), (True, "patched (diagnostic)")):
            if h == hashlib.sha256(patched_image(base, diag)).hexdigest():
                return name
    return "unknown (an older revision of this patch, or another change)"


def cmd_status():
    print(f"{DLL}\n  state: {state()}")
    print(f"  backup: {'present' if os.path.exists(BACKUP) else 'none'} ({BACKUP})")


def cmd_apply(diag=False):
    """Patch from the vanilla bytes: the backup if there is one (so a DLL patched by an older
    revision of this script is simply replaced), otherwise the current DLL if it is vanilla."""
    want = "patched (diagnostic)" if diag else "patched"
    if state() == want:
        print("already", want); return
    if os.path.exists(BACKUP) and sha256(BACKUP) == VANILLA_SHA256:
        src = BACKUP
    elif sha256(DLL) == VANILLA_SHA256:
        shutil.copy2(DLL, BACKUP)
        src = BACKUP
    else:
        raise SystemExit("no vanilla DLL or backup; use Steam 'Verify integrity of game files' first")
    with open(src, "rb") as f:
        out = patched_image(f.read(), diag)
    tmp = DLL + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, DLL)
    print(want + ":", DLL)
    print("vanilla backup:", BACKUP)


def cmd_restore():
    if not os.path.exists(BACKUP):
        raise SystemExit("no backup; use Steam 'Verify integrity of game files' instead")
    if sha256(BACKUP) != VANILLA_SHA256:
        raise SystemExit("backup doesn't match the vanilla hash; use Steam 'Verify integrity' instead")
    shutil.copy2(BACKUP, DLL)
    print("restored vanilla DLL")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    diag = "--diag" in sys.argv
    if cmd in ("apply", "show"):
        {"apply": cmd_apply, "show": cmd_show}[cmd](diag)
    else:
        {"status": cmd_status, "restore": cmd_restore}[cmd]()
