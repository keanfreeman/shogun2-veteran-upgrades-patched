"""Generate the player-facing patchers in player/ from patch.py (the developer tool).

The player patchers carry the patch as data - (file offset, original bytes, new bytes) edits plus the
vanilla and patched SHA-256 - so they need nothing installed:
  player/patch_game.ps1   Windows PowerShell 5.1+ (every Windows 10/11), launched by the .bat files
  player/patch_game.py    any Python 3 (Linux/Proton, or Windows with Python)
Run after changing the patch:  .venv/bin/python tools/make_patchers.py
tools/check_patchers.py (or `--check`) verifies player/ is up to date.
"""
import hashlib, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import patch  # noqa: E402

PLAYER = os.path.join(ROOT, "player")
TEMPLATES = os.path.join(ROOT, "tools", "patcher_templates")


def edits(vanilla):
    """Contiguous runs of changed bytes: [(offset, original, new)]."""
    new = patch.patched_image(vanilla)
    assert len(new) == len(vanilla)
    runs, i = [], 0
    while i < len(vanilla):
        if vanilla[i] != new[i]:
            j = i
            while j < len(vanilla) and vanilla[j] != new[j]:
                j += 1
            if runs and i - runs[-1][1] <= 32:   # merge nearby runs (the new code contains zero bytes)
                runs[-1][1] = j
            else:
                runs.append([i, j])
            i = j
        else:
            i += 1
    return [(a, vanilla[a:b], new[a:b]) for a, b in runs], hashlib.sha256(new).hexdigest()


def render(vanilla):
    eds, patched_sha = edits(vanilla)
    sig_off = patch.file_offsets(vanilla)["signature"]
    version = patch.SIGNATURE.rstrip(b"\0").decode().split()[-1]
    subs = {
        "@VANILLA_SHA256@": patch.VANILLA_SHA256,
        "@PATCHED_SHA256@": patched_sha,
        "@SIGNATURE_OFFSET@": str(sig_off),
        "@PATCH_VERSION@": version,
        "@EDITS_PY@": "\n".join(f"    ({o}, \"{a.hex()}\", \"{b.hex()}\")," for o, a, b in eds),
        "@EDITS_PS@": ",\n".join(f"    @({o}, '{a.hex()}', '{b.hex()}')" for o, a, b in eds),
    }
    files = {}
    for name in sorted(os.listdir(TEMPLATES)):
        text = open(os.path.join(TEMPLATES, name), encoding="utf-8").read()
        for k, v in subs.items():
            text = text.replace(k, v)
        files[name] = text
    return files, eds, patched_sha


def main():
    with open(patch.BACKUP if os.path.exists(patch.BACKUP) else patch.DLL, "rb") as f:
        vanilla = f.read()
    assert hashlib.sha256(vanilla).hexdigest() == patch.VANILLA_SHA256, "need the vanilla DLL (or its backup)"
    files, eds, patched_sha = render(vanilla)
    check = "--check" in sys.argv
    stale = []
    os.makedirs(PLAYER, exist_ok=True)
    for name, text in files.items():
        path = os.path.join(PLAYER, name)
        # .bat/.ps1 with CRLF for Windows; .py with LF
        data = text.replace("\r\n", "\n")
        if name.endswith((".bat", ".ps1", ".txt")):
            data = data.replace("\n", "\r\n")
        data = data.encode("utf-8-sig" if name.endswith(".ps1") else "utf-8")
        old = open(path, "rb").read() if os.path.exists(path) else None
        if old != data:
            stale.append(name)
            if not check:
                with open(path, "wb") as f:
                    f.write(data)
    print(f"{len(eds)} edits, {sum(len(a) for _, a, _ in eds)} bytes; patched sha256 {patched_sha[:16]}...")
    if check:
        print("player/ is up to date" if not stale else f"STALE: {stale} - run tools/make_patchers.py")
        return 1 if stale else 0
    print("wrote", ", ".join(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
