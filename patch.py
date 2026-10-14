"""Shogun 2 ability patch: lets an effect unlock a research-gated ability for ONE unit type.

Usage (from this folder, with the venv):
  .venv/bin/python patch.py status            # is the game DLL vanilla, patched or unknown?
  .venv/bin/python patch.py apply             # back up the vanilla DLL, then patch it in place
  .venv/bin/python patch.py restore           # put the vanilla DLL back
  .venv/bin/python patch.py show              # print the patch bytes, disassembled (changes nothing)
  add --diag to apply/show for the diagnostic table (abilities.DIAG_MODES)

What it changes (empire.retail.dll, Steam build sha256 022fae2e...f874f5):
  The unit-capabilities builder (FUN_1019e580) grants a unit an ability from its unit type's list if
  the ability has requires_effect_enabling == False, or the clan/army bonus "ability X: enable" is set.
  At its "not enabled -> skip" branch (0x1019e643) we jump to a small routine (in the unused tail of
  .text) that also checks the unit type's general_aoe_mod bonus in the same bonus list and grants the
  ability if that value has the ability's bit set (see abilities.py).
"""
import hashlib, os, shutil, struct, sys

import capstone, keystone, pefile

from abilities import DIAG_MODES, enum_to_bit_table

GAME = os.environ.get("SHOGUN2_DIR", os.path.expanduser(
    "~/.local/share/Steam/steamapps/common/Total War SHOGUN 2"))
DLL = os.path.join(GAME, "empire.retail.dll")
BACKUP = DLL + ".vanilla"

VANILLA_SHA256 = "022fae2e2da92b59b8b1b8ee52887003c624e3c8eca060b209f5d792a7f874f5"
BASE = 0x10000000

# The gate in FUN_1019e580 (see README for the decompiled loop):
#   1019e635 mov ecx,[esp+0x28]   ; bonus list (clan/army effects)
#   1019e639 push 0 / push edi    ; edi = UNIT_ABILITY_RECORD*
#   1019e63c call 0x10bcf3e0      ; IsEnabled(ability)
#   1019e641 test eax,eax
#   1019e643 je 0x1019e6f2        ; <- hooked: not enabled -> skip
#   1019e649 ...                  ; grant path
HOOK_VA = 0x1019E643
HOOK_ORIG = bytes.fromhex("0f84a9000000")
GRANT_VA = 0x1019E649
SKIP_VA = 0x1019E6F2

ABILITY_ENUM_FN = 0x101B1670   # cdecl int(UniString* key) -> engine enum (0x45 = none)
BONUS_LOOKUP_FN = 0x10BD5EE0   # thiscall int(list, category, record, bonus_id, extra) -> round(value)
CAT_UNIT_RECORD = 0x10         # bonus category 16 = unit_record
BONUS_GENERAL_AOE = 9          # index of general_aoe_mod in the unit_record bonus list
UNIT_ABILITIES_OFFSET = 0xFC   # unit record: ability vector (cap, count, data)

TEXT_VSIZE_PATCHED = 0x159FE00  # .text VirtualSize grown to its raw size, so the tail is code
CAVE_VA = BASE + 0x1000 + 0x159FC40
TABLE_OFFSET = 0x80             # enum->bit table sits at CAVE_VA + 0x80

BONUS_MELEE_ATTACK = 4          # index of melee_attack_mod (diagnostic mode 3)

ASM = f"""
    test eax, eax
    jnz grant
    push edi
    call {ABILITY_ENUM_FN:#x}
    add esp, 4
    cmp eax, 70
    jae skip
    call getpc
getpc:
    pop edx
    movzx eax, byte ptr [edx + eax + TABLE_DISP]
    cmp al, 0xff
    je skip
    mov edx, eax
    shr edx, 5
    and eax, 0x1f
    cmp edx, 1
    je grant
    push eax
    push edx
    mov ecx, dword ptr [esp + 0x30]
    mov eax, dword ptr [esp + 0x2c]
    sub eax, {UNIT_ABILITIES_OFFSET:#x}
    push 0
    cmp edx, 3
    mov edx, {BONUS_GENERAL_AOE}
    jne push_id
    mov edx, {BONUS_MELEE_ATTACK}
push_id:
    push edx
    push eax
    push {CAT_UNIT_RECORD:#x}
    call {BONUS_LOOKUP_FN:#x}
    pop edx
    pop ecx
    test edx, edx
    jz bit_test
    test eax, eax
    jnz grant
    jmp skip
bit_test:
    bt eax, ecx
    jnc skip
grant:
    jmp {GRANT_VA:#x}
skip:
    jmp {SKIP_VA:#x}
"""
# Stack: at the hook esp is exactly as at 1019e635, where the bonus list is [esp+0x28] and the unit's
# ability vector (param_2) is [esp+0x24]; after our two pushes both are 8 further away.
# Table byte = (mode << 5) | bit (abilities.py): mode 0 tests the bit in general_aoe_mod; modes 1-3
# are diagnostics (always / general_aoe_mod != 0 / melee_attack_mod != 0).


def assemble(diag=False):
    """Patch routine bytes (code + padding + table), assembled for CAVE_VA."""
    ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)
    disp = 0
    for _ in range(3):  # TABLE_DISP depends on where getpc lands
        enc, _ = ks.asm(ASM.replace("TABLE_DISP", hex(disp)), CAVE_VA)
        code = bytes(enc)
        i = code.index(b"\xe8\x00\x00\x00\x00\x5a")
        getpc = CAVE_VA + i + 5
        new = (CAVE_VA + TABLE_OFFSET) - getpc
        if new == disp:
            break
        disp = new
    assert len(code) <= TABLE_OFFSET, len(code)
    return code + b"\xcc" * (TABLE_OFFSET - len(code)) + enum_to_bit_table(DIAG_MODES if diag else None)


def hook_bytes():
    rel = CAVE_VA - (HOOK_VA + 5)
    return b"\xe9" + struct.pack("<i", rel) + b"\x90"


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


def patched_image(data, diag=False):
    pe = pefile.PE(data=data, fast_load=True)
    text, va2off, vsize_off = offsets(pe)
    cave = assemble(diag)
    hook = hook_bytes()
    assert data[va2off(HOOK_VA):va2off(HOOK_VA) + 6] == HOOK_ORIG, "unexpected bytes at the hook"
    cave_off = va2off(CAVE_VA)
    assert text.Misc_VirtualSize <= CAVE_VA - BASE - text.VirtualAddress
    assert CAVE_VA + len(cave) <= BASE + text.VirtualAddress + TEXT_VSIZE_PATCHED
    assert set(data[cave_off:cave_off + len(cave)]) <= {0}, "cave area is not empty"
    check_relocs(pe, [(HOOK_VA, HOOK_VA + 6)])
    out = bytearray(data)
    out[va2off(HOOK_VA):va2off(HOOK_VA) + 6] = hook
    out[cave_off:cave_off + len(cave)] = cave
    struct.pack_into("<I", out, vsize_off, TEXT_VSIZE_PATCHED)
    return bytes(out)


def disasm(code, va):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    for ins in md.disasm(code, va):
        print(f"  {ins.address:08x}  {ins.bytes.hex():<16} {ins.mnemonic} {ins.op_str}")


def cmd_show(diag=False):
    print(f"hook @ {HOOK_VA:#x}: {HOOK_ORIG.hex()} -> {hook_bytes().hex()}")
    disasm(hook_bytes(), HOOK_VA)
    cave = assemble(diag)
    print(f"routine @ {CAVE_VA:#x} ({TABLE_OFFSET} bytes code area + {len(cave) - TABLE_OFFSET}-byte table):")
    disasm(cave[:TABLE_OFFSET].rstrip(b"\xcc"), CAVE_VA)
    print("  table:", cave[TABLE_OFFSET:].hex())


def state():
    h = sha256(DLL)
    if h == VANILLA_SHA256:
        return "vanilla"
    with open(BACKUP if os.path.exists(BACKUP) else DLL, "rb") as f:
        base = f.read()
    if hashlib.sha256(base).hexdigest() == VANILLA_SHA256:
        for diag, name in ((False, "patched"), (True, "patched (diagnostic)")):
            if h == hashlib.sha256(patched_image(base, diag)).hexdigest():
                return name
    return "unknown"


def cmd_status():
    s = state()
    print(f"{DLL}\n  state: {s}")
    print(f"  backup: {'present' if os.path.exists(BACKUP) else 'none'} ({BACKUP})")


def cmd_apply(diag=False):
    s = state()
    want = "patched (diagnostic)" if diag else "patched"
    if s == want:
        print("already", want); return
    if s.startswith("patched"):
        cmd_restore()
        s = state()
    if s != "vanilla":
        raise SystemExit("the DLL is not the known vanilla build; refusing to patch (Steam 'Verify integrity' restores it)")
    with open(DLL, "rb") as f:
        data = f.read()
    if not os.path.exists(BACKUP):
        shutil.copy2(DLL, BACKUP)
    assert sha256(BACKUP) == VANILLA_SHA256
    out = patched_image(data, diag)
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
