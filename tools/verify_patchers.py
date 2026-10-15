"""Check the player patchers against the source - no game files needed (also runs in CI).

1. Re-assembles the patch from the readable assembly in patch.py (keystone) and checks that the bytes
   embedded in player/patch_game.py and player/patch_game.ps1 are exactly those, at the offsets
   patch.py says, and that both patchers carry identical data.
2. Checks the bytes the patchers expect to find before patching are the vanilla instructions patch.py
   names (the two hooked instructions) or empty space (the unused tail of the code section).
3. Scans player/ for anything that reaches the network, starts programs, touches the registry for
   writing, or decodes hidden code - the patchers only read/write empire.retail.dll and its backup.
4. docs/PATCH.md (every change, disassembled) is generated from patch.py: --write-doc rewrites it,
   and the default run fails if it is out of date.
Usage: .venv/bin/python tools/verify_patchers.py [--write-doc]   (exit code 1 on any problem)
"""
import importlib.util, os, re, struct, sys

sys.dont_write_bytecode = True   # loading player/patch_game.py must not leave a __pycache__ there

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import patch  # noqa: E402

PLAYER = os.path.join(ROOT, "player")
# empire.retail.dll layout (Steam build 022fae2e...): .text at VA 0x1000, raw offset 0x400; its section
# header's VirtualSize field at file offset 0x260. patch.py asserts these against the real DLL.
TEXT_VA, TEXT_RAW, VSIZE_OFFSET, VSIZE_VANILLA = 0x1000, 0x400, 0x260, 0x159FC3E


def va2off(va):
    return va - patch.BASE - TEXT_VA + TEXT_RAW


def expected_changes():
    """{file offset: (vanilla byte or None if unknown-but-asserted, patched byte)} from patch.py."""
    out = {}
    for va, orig, new in patch.hooks():
        for i, (a, b) in enumerate(zip(orig, new)):
            out[va2off(va) + i] = (a, b)
    cave = patch.assemble()
    for i, b in enumerate(cave):
        out[va2off(patch.CAVE_VA) + i] = (0, b)
    old, new = struct.pack("<I", VSIZE_VANILLA), struct.pack("<I", patch.TEXT_VSIZE_PATCHED)
    for i in range(4):
        out[VSIZE_OFFSET + i] = (old[i], new[i])
    return out


def load_py_edits():
    spec = importlib.util.spec_from_file_location("patch_game", os.path.join(PLAYER, "patch_game.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return [(o, bytes.fromhex(a), bytes.fromhex(b)) for o, a, b in m.EDITS], m


def load_ps_edits():
    text = open(os.path.join(PLAYER, "patch_game.ps1"), encoding="utf-8-sig").read()
    return [(int(o), bytes.fromhex(a), bytes.fromhex(b)) for o, a, b in re.findall(r"@\((\d+), '([0-9a-f]*)', '([0-9a-f]*)'\)", text)], text


FORBIDDEN = [  # network, downloads, launching programs, registry writes, hidden code
    r"Invoke-WebRequest", r"Invoke-RestMethod", r"\bcurl\b", r"\bwget\b", r"Net\.WebClient", r"HttpClient",
    r"DownloadString", r"DownloadFile", r"BitsTransfer", r"Start-Process", r"Invoke-Expression", r"\biex\b",
    r"FromBase64String", r"-EncodedCommand", r"Set-ItemProperty", r"New-ItemProperty", r"Remove-Item",
    r"\burllib\b", r"\brequests\b", r"\bsocket\b", r"\bhttp\.client\b", r"\bsubprocess\b", r"os\.system",
    r"\bexec\(", r"\beval\(", r"base64", r"SetValueEx", r"CreateKey",
]


def disasm(code, va):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    return "\n".join(f"{i.address:08x}  {i.bytes.hex():<16} {i.mnemonic} {i.op_str}".rstrip() for i in md.disasm(code, va))


def patch_doc():
    """docs/PATCH.md: what every changed byte is."""
    hook_names = {patch.HOOK_VA: "Hook 1, unit-ability builder: a 6-byte branch now jumps to routine 1",
                  patch.HOOK2_VA: "Hook 2, same loop: a 7-byte instruction pair now jumps to routine 2",
                  patch.PARSE_HOOK_VA: "Parser hook: the unit_record bonus-name parser's not-found exit "
                                       "jumps to the parser extension"}
    hook_names[patch.DROPIN_PATCHES[0][0]] = ("Drop-in off: the campaign's drop-in battles flag is always "
                                              "computed as off (the preference defaults to on)")
    hook_names[patch.DROPIN_PATCHES[1][0]] = ("Drop-in off: the drop-in flag's setter always stores off")
    hook_names[patch.DROPIN_PATCHES[2][0]] = ("Drop-in off: the handler for a drop-in invitation (\"Drop-in battle "
                                              "available\") returns before telling the UI")
    hook_names[patch.DROPIN_PATCHES[3][0]] = ("Drop-in off: starting to host a drop-in battle "
                                              "(CampaignUI.PlayDropInBattle) returns 0, not started")
    hook_names[patch.RANGE_VA] = ("Range routine, in unused int3 padding: adds the class + unit_record range "
                                  "bonus to the unit's additive range field (the vanilla code multiplied it, "
                                  "and it starts at 0)")
    hook_names[patch.CHARGE_VA] = ("Charge routine, in unused int3 padding: the charge lookup as the other stat "
                                   "routines, and sets the unit's \"can fire while hidden\" flag when bit "
                                   f"{patch.SNIPE_BIT} of the unit type's general_aoe_mod bonus is set")
    for site, _, _, orig_id, name in patch.STAT_HOOKS:
        hook_names[site] = (f"Stat hook, land unit stats builder: a `call` now goes to a stat routine "
                            f"(`{name}`, unit_record id {orig_id + patch.STAT_ID_SHIFT:#x})")
    rows = "\n".join(f"| {hook_names[va]} | `{va2off(va):#x}` |" for va, _, _ in patch.hooks())
    hooks = "\n\n".join(f"Original at {va:#x} (file offset {va2off(va):#x}):\n{disasm(orig, va)}\n"
                         f"Patched:\n{disasm(new, va)}" for va, orig, new in patch.hooks())
    sources = {"routine 1 (abilities)": patch.ASM, "routine 2 (abilities)": patch.ASM2,
               "stat routines": patch.ASM_STATS, "parser extension": patch.ASM_PARSE}
    blocks = []
    for name, va, code in patch.routines():
        text = disasm(code, va)
        if name == "parser extension":   # code, then the name table (data)
            n = len(patch._asm(patch.ASM_PARSE.replace("TABLE_DELTA", "0x7f"), va))
            text = disasm(code[:n], va) + "\n\nName table (int32 name VA minus entry VA, then the id byte; 0 ends it):\n"
            text += "\n".join(f"{va + n + 5 * i:08x}  {code[n + 5 * i:n + 5 * i + 5].hex()}  {nm} -> {bid:#x}"
                              for i, (nm, bid) in enumerate(patch.STAT_BONUSES.items()))
        blocks.append(f"## {name[0].upper() + name[1:]} (`{va:#x}`)\n\n```\n{text}\n```\n\n"
                      f"Source (keystone syntax, from patch.py):\n\n```\n{sources[name].strip()}\n```\n")
    stats = "\n".join(f"| `{name}` | {what} |" for name, what in [
        ("charge_bonus", "charge bonus, added to the unit class's"),
        ("reload", "reload skill %, added to the unit class's"),
        ("range_mod", "missile range, added to the unit's range bonus (the field the Increased Range ability raises)"),
        ("mod_land_movement_battle", "battle speed %, added to the unit category's"),
        ("ammo_mod", "ammunition %, added to the unit class's")])
    places = len(patch.hooks()) + 2
    return f"""# What the patch changes

Generated from [patch.py](../patch.py) by `tools/verify_patchers.py --write-doc` - do not edit.
The player patchers ([player/](../player/)) write exactly these bytes; `tools/verify_patchers.py`
re-assembles them from the source below and checks that, on every push (GitHub Actions).

The patch is for `empire.retail.dll` of the Steam Windows build (SHA-256 `{patch.VANILLA_SHA256}`).
It changes {sum(1 for a, b in expected_changes().values() if a != b)} bytes in {places} places and nothing else:

| What | File offset |
|---|---|
| `.text` section header, VirtualSize: {VSIZE_VANILLA:#x} -> {patch.TEXT_VSIZE_PATCHED:#x}, so the section's unused tail (zero bytes already in the file) becomes part of the code | `{VSIZE_OFFSET:#x}` |
{rows}
| New code in the unused tail: the routines below and the signature `{patch.SIGNATURE.rstrip(bytes(1)).decode()}` | `{va2off(patch.CAVE_VA):#x}` |

What it does, in words:

* **Abilities.** When the game builds a unit's list of battle abilities, an ability that needs
  unlocking and isn't unlocked normally gets skipped. Hook 1 sends that case to routine 1, which only
  acts on the mod's own "clone" ability records (keys `vuNN_...`): it reads the unit type's
  `general_aoe_mod` bonus, and if bit NN is set (and any research the real ability needs is done) it
  adds the real ability instead of skipping. Hook 2 restores the loop's position afterwards.
* **Stats.** The game adds clan bonuses to a land unit's charge, reload, range, speed and ammunition
  only per unit class or category (and its class range bonus never worked: it multiplied a field that
  starts at 0). Each stat hook keeps that lookup and also adds the same kind of
  bonus for the unit's own type (unit_record). The parser extension lets effects name these bonuses
  for a unit type (see the table below).
* **Fire while hidden.** The charge routine also sets the unit's "can fire while hidden" flag (as
  `can_snipe` in the unit's stats) when bit 23 of the unit type's `general_aoe_mod` bonus is set.
* **Drop-in battles off.** A drop-in battle is an online battle against another player, so with a
  modified game file it could get the player's Steam account banned (Valve Anti-Cheat). Invitations
  to join someone else's battle are never shown, and battles are never offered to other players
  (the game's drop-in setting is treated as off; hosting is refused as a backstop).

The stat bonuses:

| unit_record bonus | adds |
|---|---|
{stats}

The new code calls only the game's own functions (its bonus lookups, its research check and the name
comparison the parser already uses), allocates nothing, and touches no files, network or other programs.
It uses no absolute addresses, so it works wherever Windows loads the DLL.

## Hooks

```
{hooks}
```

""" + "\n".join(blocks)


def main():
    problems = []
    doc_path = os.path.join(ROOT, "docs", "PATCH.md")
    doc = patch_doc()
    if "--write-doc" in sys.argv:
        os.makedirs(os.path.dirname(doc_path), exist_ok=True)
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(doc)
        print("wrote docs/PATCH.md")
    elif not os.path.exists(doc_path) or open(doc_path, encoding="utf-8").read() != doc:
        problems.append("docs/PATCH.md is out of date - run tools/verify_patchers.py --write-doc")
    exp = expected_changes()
    py, mod = load_py_edits()
    ps, ps_text = load_ps_edits()
    if py != ps:
        problems.append("patch_game.py and patch_game.ps1 carry different edits")
    covered = set()
    for off, old, new in py:
        if len(old) != len(new):
            problems.append(f"edit at {off:#x}: original and new lengths differ")
        for i, (a, b) in enumerate(zip(old, new)):
            o = off + i
            covered.add(o)
            if o in exp:
                ea, eb = exp[o]
                if b != eb:
                    problems.append(f"byte {o:#x}: patcher writes {b:#04x}, source assembles {eb:#04x}")
                if a != ea:
                    problems.append(f"byte {o:#x}: patcher expects {a:#04x}, vanilla has {ea:#04x}")
            elif a != b:
                problems.append(f"byte {o:#x}: patcher changes a byte patch.py doesn't")
    missing = [o for o, (a, b) in exp.items() if a != b and o not in covered]
    if missing:
        problems.append(f"{len(missing)} bytes of the patch are missing from the patchers (first {missing[0]:#x})")
    sig = patch.SIGNATURE.rstrip(b"\0").decode().split()[-1]
    if str(mod.PATCH_VERSION) != sig or mod.SIGNATURE_OFFSET != va2off(patch.CAVE_VA) + patch.SIGNATURE_OFFSET:
        problems.append("signature version/offset in patch_game.py doesn't match patch.py")
    for name in sorted(os.listdir(PLAYER)):
        if not os.path.isfile(os.path.join(PLAYER, name)):
            continue
        text = open(os.path.join(PLAYER, name), encoding="utf-8-sig").read()
        for pat in FORBIDDEN:
            for m in re.finditer(pat, text, re.I):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{name}:{line}: contains '{m.group(0)}'")
    n = sum(len(a) for _, a, _ in py)
    changed = sum(1 for o, (a, b) in exp.items() if a != b)
    print(f"{len(py)} edits ({n} bytes, {changed} changed) - checked against the assembly in patch.py")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  " + p)
        return 1
    print("OK: both patchers write exactly the bytes patch.py assembles, and nothing else;")
    print("    no network, downloads, program launches, registry writes or hidden code in player/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
