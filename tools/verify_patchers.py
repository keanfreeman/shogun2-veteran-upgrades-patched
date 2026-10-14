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
    cave = patch.assemble()
    r1 = cave[:patch.CAVE2_OFFSET].rstrip(b"\xcc")
    r2 = cave[patch.CAVE2_OFFSET:patch.SIGNATURE_OFFSET].rstrip(b"\xcc")
    hooks = "\n\n".join(f"Original at {va:#x} (file offset {va2off(va):#x}):\n{disasm(orig, va)}\n"
                         f"Patched:\n{disasm(new, va)}" for va, orig, new in patch.hooks())
    return f"""# What the patch changes

Generated from [patch.py](../patch.py) by `tools/verify_patchers.py --write-doc` - do not edit.
The player patchers ([player/](../player/)) write exactly these bytes; `tools/verify_patchers.py`
re-assembles them from the source below and checks that, on every push (GitHub Actions).

The patch is for `empire.retail.dll` of the Steam Windows build (SHA-256 `{patch.VANILLA_SHA256}`).
It changes {sum(1 for a, b in expected_changes().values() if a != b)} bytes in four places and nothing else:

| Where | File offset | What |
|---|---|---|
| `.text` section header, VirtualSize | `{VSIZE_OFFSET:#x}` | {VSIZE_VANILLA:#x} -> {patch.TEXT_VSIZE_PATCHED:#x}: the section's unused tail (zero bytes already in the file) becomes part of the code |
| Hook 1, in the unit-ability builder | `{va2off(patch.HOOK_VA):#x}` | a 6-byte branch now jumps to routine 1 |
| Hook 2, same loop | `{va2off(patch.HOOK2_VA):#x}` | a 7-byte instruction pair now jumps to routine 2 |
| New code in the unused tail | `{va2off(patch.CAVE_VA):#x}` | routine 1, routine 2 and the signature `{patch.SIGNATURE.rstrip(bytes(1)).decode()}` |

What it does, in words: when the game builds a unit's list of battle abilities, an ability that needs
unlocking and isn't unlocked normally gets skipped. Hook 1 sends that case to routine 1, which only acts
on the mod's own "clone" ability records (keys `vuNN_...`): it reads the unit type's `general_aoe_mod`
bonus, and if bit NN is set (and any research the real ability needs is done) it adds the real ability
instead of skipping. Hook 2 restores the loop's position afterwards. The new code calls only two of the
game's own functions (its bonus lookup and its research check), allocates nothing, and touches no files,
network or other programs.

## Hooks

```
{hooks}
```

## Routine 1 (`{patch.CAVE_VA:#x}`)

```
{disasm(r1, patch.CAVE_VA)}
```

Source (keystone syntax, from patch.py):

```
{patch.ASM.strip()}
```

## Routine 2 (`{patch.CAVE_VA + patch.CAVE2_OFFSET:#x}`)

```
{disasm(r2, patch.CAVE_VA + patch.CAVE2_OFFSET)}
```

Source:

```
{patch.ASM2.strip()}
```
"""


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
