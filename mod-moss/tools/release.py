"""Make a Veteran Upgrades: Patched Edition for MoSS release: build, test, and assemble dist/.

    <lab venv python> tools/release.py            # build + test + dist/ + zip
    <lab venv python> tools/release.py --install  # ...and copy pack + thumbnail into the game's data folder

dist/ gets (and the zip "Veteran-Upgrades-Patched-Edition-for-MoSS-<version>.zip" holds the same):
  veteran_upgrades_moss_patched.pack        the mod (release build, no debug logging)
  veteran_upgrades_moss_patched.png / .jpg  launcher thumbnail (made from the game's own unit art)
  patcher/                             the game patcher: patch_game.ps1 + .bat launchers (Windows),
                                       patch_game.py (any Python 3), from ../player (tools/make_patchers.py)
  README.txt                           install / uninstall / safety notes for players (docs/player_readme.txt)
  SHA256SUMS.txt                       checksums of the zip and every file in it (attach to the release)
"""
import hashlib, io, os, re, shutil, subprocess, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools_db import GAME_DATA            # noqa: E402
from tools_packread import extract        # noqa: E402

DIST = os.path.join(ROOT, "dist")
NAME = "veteran_upgrades_moss_patched"
PACK = os.path.join(ROOT, "veteran_upgrades", NAME + ".pack")
PLAYER = os.path.join(os.path.dirname(ROOT), "player")
ART = ["ashigaru_inf_yari_ashigaru", "samurai_inf_katana_samurai", "ashigaru_inf_bow_ashigaru",
       "ashigaru_inf_matchlock_ashigaru", "samurai_cav_yari_cavalry", "samurai_inf_nodachi_samurai"]
FONTS = ["/usr/share/fonts/dejavu/DejaVuSerif-Bold.ttf", "C:\\Windows\\Fonts\\georgiab.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
         "/usr/share/fonts/google-noto/NotoSerif-Bold.ttf", "/usr/share/fonts/liberation-serif-fonts/LiberationSerif-Bold.ttf"]


def run(*cmd):
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True, env={k: v for k, v in os.environ.items() if k != "VU_DEBUG"})


def thumbnail(path, size=512):
    """Six unit portraits on a dark red field, with the title below."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (size, size), (34, 10, 10))
    draw = ImageDraw.Draw(img)
    for y in range(size):   # vertical gradient
        c = int(34 + 40 * y / size)
        draw.line([(0, y), (size, y)], fill=(c, 12, 12))
    data = os.path.join(GAME_DATA, "data.pack")
    w, h, gap = 76, 140, 6
    x0 = (size - (len(ART) * w + (len(ART) - 1) * gap)) // 2
    for i, name in enumerate(ART):
        pic = Image.open(io.BytesIO(extract(data, f"ui\\units\\info\\{name}.tga"))).convert("RGBA")
        pic = pic.resize((w, h), Image.LANCZOS)
        img.paste(pic, (x0 + i * (w + gap), 70), pic)
    font = next((f for f in FONTS if os.path.exists(f)), None)
    big = ImageFont.truetype(font, 54) if font else ImageFont.load_default()
    small = ImageFont.truetype(font, 22) if font else ImageFont.load_default()
    for text, f, y, colour in (("VETERAN", big, 250, (232, 196, 120)), ("UPGRADES", big, 308, (232, 196, 120)),
                               ("PATCHED EDITION FOR MoSS", small, 380, (240, 120, 90)),
                               ("for Master of Strategy Sengoku", small, 420, (220, 210, 200)),
                               ("Needs the included game patch", small, 450, (220, 210, 200))):
        tw = draw.textlength(text, font=f)
        draw.text(((size - tw) / 2, y), text, font=f, fill=colour)
    draw.rectangle([6, 6, size - 7, size - 7], outline=(150, 110, 60), width=3)
    img.save(path, "JPEG", quality=90)


def version():
    return re.search(r'^VERSION = "([^"]+)"', open(os.path.join(ROOT, "veteran_upgrades", "build.py")).read(), re.M).group(1)


def main():
    install = "--install" in sys.argv
    run(sys.executable, "veteran_upgrades/build.py")
    run(sys.executable, "tests/run_tests.py")
    run(os.path.join(os.path.dirname(ROOT), ".venv", "bin", "python"), "../tools/make_patchers.py", "--check")
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(os.path.join(DIST, "patcher"))
    shutil.copy(PACK, DIST)
    thumbnail(os.path.join(DIST, NAME + ".jpg"))
    from PIL import Image
    Image.open(os.path.join(DIST, NAME + ".jpg")).save(os.path.join(DIST, NAME + ".png"))
    for f in sorted(os.listdir(PLAYER)):
        shutil.copy(os.path.join(PLAYER, f), os.path.join(DIST, "patcher", f))
    text = open(os.path.join(ROOT, "docs", "player_readme.txt"), encoding="utf-8").read().replace("@VERSION@", version())
    with open(os.path.join(DIST, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    zname = os.path.join(DIST, f"Veteran-Upgrades-Patched-Edition-for-MoSS-{version()}.zip")   # no spaces: GitHub renames them
    with zipfile.ZipFile(zname, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, files in os.walk(DIST):
            for f in files:
                p = os.path.join(dirpath, f)
                if p != zname and not f.endswith(".zip"):
                    z.write(p, os.path.relpath(p, DIST))
    sums = []
    for dirpath, _, files in os.walk(DIST):
        for f in sorted(files):
            if f != "SHA256SUMS.txt":
                p = os.path.join(dirpath, f)
                sums.append(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {os.path.relpath(p, DIST)}")
    with open(os.path.join(DIST, "SHA256SUMS.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(sums, key=lambda l: l.split("  ", 1)[1])) + "\n")
    print("dist/:", ", ".join(sorted(os.listdir(DIST))), "| zip:", os.path.basename(zname))
    if install:
        if subprocess.run("ps -eo comm | grep -qi shogun", shell=True).returncode == 0:
            print("Shogun 2 is running: not installing (quit the game first)")
            return 1
        for name in (NAME + ".pack", NAME + ".jpg", NAME + ".png"):
            shutil.copy(os.path.join(DIST, name), os.path.join(GAME_DATA, name))
        print(f"installed pack + thumbnail into {GAME_DATA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
