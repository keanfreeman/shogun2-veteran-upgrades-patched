"""Run the Veteran Upgrades Lua against the mock engine.

Build first (veteran_upgrades/build.py writes veteran_upgrades_ap.pack), then:
    .venv/bin/python tests/run_tests.py
Runs tests/scenarios.lua (full flows) on Sengoku and tests/smoke.lua on every campaign.
Needs lupa (pip install lupa). Exit code 1 if any check fails.
"""
import os, sys, tempfile
import lupa.lua51 as lua51

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN_KEYS = {"sengoku": "jap_shogun", "gempei": "jap_gempei", "boshin": "jap_boshin"}
RUNS = [  # (campaign, scenario, player clan, game DLL patched?)
    ("sengoku", "scenarios.lua", "shimazu", True),
    ("sengoku", "unpatched.lua", "shimazu", False),
    ("sengoku", "smoke.lua", "shimazu", True),
    ("gempei", "smoke.lua", "gem_minamoto_kamakura", True),
    ("boshin", "smoke.lua", "bos_satsuma", True),
]
SIGNATURE_OFFSET = 0x15a0190   # detect.lua / patch.py show
SIGNATURE = b"VU_ABILITY_PATCH 3\0"


def fake_dll(patched):
    """vu.lua detects the patch by reading empire.retail.dll in the working directory: a sparse file
    with the signature at its file offset stands in for the patched DLL."""
    if patched:
        with open("empire.retail.dll", "wb") as f:
            f.seek(SIGNATURE_OFFSET)
            f.write(SIGNATURE)


sys.path.insert(0, ROOT)
from tools_packread import extract
ADVICE_SRC = extract(os.path.join(ROOT, "veteran_upgrades", "veteran_upgrades_ap.pack"), "export_advice.lua").decode("utf-8")


def run(campaign, scenario, player, patched):
    os.chdir(tempfile.mkdtemp(prefix="vu_tests_"))   # vu.lua writes vu_log.txt to the working directory
    fake_dll(patched)
    lua = lua51.LuaRuntime()
    lua.execute(f'MOCK_PLAYER = "{player}"')
    # As in the game: the campaign script requires export_advice (CA's module with our hook appended,
    # taken from the built pack) and then calls SetCampaign.
    lua.execute(open(os.path.join(ROOT, "tests", "mock_engine.lua"), encoding="utf-8").read())
    lua.globals().package.preload["export_advice"] = lua.execute(
        "local src = ... return function(name) local f = assert(loadstring(src, '@export_advice.lua')) return f(name) end",
        ADVICE_SRC)
    lua.execute('require "export_advice"')
    lua.execute(f'EpisodicScripting.SetCampaign("{CAMPAIGN_KEYS[campaign]}")')
    lua.execute(open(os.path.join(ROOT, "tests", scenario), encoding="utf-8").read())
    result = lua.globals().RESULT
    failures = list(result.failures.values())
    log = open("vu_log.txt").read() if os.path.exists("vu_log.txt") else ""
    errors = [l for l in log.splitlines() if "!!" in l]
    print(f"{campaign:8} {scenario:14} {player:22} {'patched' if patched else 'vanilla':8} {result.passed:3} passed, {len(failures)} failed, "
          f"{len(errors)} Lua errors   (log: {os.path.abspath('vu_log.txt')})")
    for f in failures:
        print("    FAIL:", f)
    for e in errors:
        print("    ERROR:", e)
    return not failures and not errors


def main():
    ok = [run(*r) for r in RUNS]
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
