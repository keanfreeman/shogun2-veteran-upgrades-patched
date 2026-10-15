"""Run the patch's own routines in an emulated x86 CPU (unicorn) - no game, no game files.

Each test maps only the patch's code (cave + padding gaps, from patch.py) and small stand-ins for the
game functions it calls, sets up the registers and stack as the hooked call site would, runs one
routine until it returns, and checks:
  * the result (eax, or st(0) for the float routines) and any stats-struct changes,
  * the stack is back where it was (the routine's `ret 8` etc.), esi/edi/ebx/ebp untouched,
  * the x87 stack holds exactly what the caller expects,
  * every game lookup got the bonus list in ecx and the expected (category, record, id).
The stand-ins clobber ecx and edx, as real game functions may. Everything runs twice: at the real
addresses and shifted by 0x1230000, as Windows might load the DLL (ASLR) - code with an absolute
address would break there.

What this can't check: that our assumptions about the game (registers and stack at each call site,
the stats struct's layout) are right - only playing does.
Usage: .venv/bin/python tools/emulate_patch.py   (exit code 1 on any failure)
"""
import os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import patch  # noqa: E402
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,  # noqa: E402
                               UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP)

HARNESS, DATA, STACK_TOP = 0x20000000, 0x21000000, 0x30008000
SLOT_INT, SLOT_F, SLOT_B = DATA, DATA + 4, DATA + 8          # stand-ins return these
RES_EAX, RES_F, RES_SW = DATA + 0x10, DATA + 0x14, DATA + 0x18
UNIT, CONTAINER, CLASS_REC, CATEGORY_REC, NAME_OBJ = 0x0BADC0DE, 0x0C0FFEE0, 0x0C1A5500, 0x0CA7E600, 0x0A4E0B10
SENTINELS = {UC_X86_REG_EBX: 0xB0B0B0B0, UC_X86_REG_EBP: 0xBEBEBEBE, UC_X86_REG_EDI: 0x5ED15ED1}
CLOBBER = "mov ecx, 0xdeadbeef\n mov edx, 0xdeadbeef\n"


class Emu:
    def __init__(self, delta):
        self.delta = delta
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.calls, self.values, self.name = [], {}, None
        regions = [(patch.CAVE_VA, patch.CAVE_VA + patch.CAVE_END), (HARNESS, HARNESS + 0x1000), (DATA, DATA + 0x1000),
                   (STACK_TOP - 0x8000, STACK_TOP + 0x1000),
                   (patch.BONUS_LOOKUP_FN, patch.BONUS_LOOKUP_FN + 0x40),
                   (patch.BONUS_LOOKUP_FLOAT_FN, patch.BONUS_LOOKUP_FLOAT_FN + 0x40),
                   (patch.NAME_MATCH_FN, patch.NAME_MATCH_FN + 0x40)]
        regions += [(va, va + len(new)) for va, _, new in patch.hooks() if new[:1] != b"\xe8"]   # gap code
        regions += [(va, va + len(n) + 1) for n, va in patch.NAME_VA.items()]
        pages = set()
        for lo, hi in regions:
            lo, hi = self.a(lo) if lo < HARNESS else lo, self.a(hi) if lo < HARNESS else hi
            pages.update(range(lo & ~0xfff, (hi + 0xfff) & ~0xfff, 0x1000))
        for p in sorted(pages):
            self.uc.mem_map(p, 0x1000)
        # the patch's code, unchanged (it must not care where it is loaded)
        self.uc.mem_write(self.a(patch.CAVE_VA), patch.assemble())
        for va, _, new in patch.hooks():
            if new[:1] != b"\xe8" and va >= 0x10000000 and new[:1] != b"\xe9":
                self.uc.mem_write(self.a(va), new)
        for n, va in patch.NAME_VA.items():
            self.uc.mem_write(self.a(va), n.encode() + b"\0")
        # stand-ins for the game's functions (thiscall, callee-cleaned)
        self.stub(patch.BONUS_LOOKUP_FN, f"{CLOBBER} mov eax, dword ptr [{SLOT_INT:#x}]\n ret 0x10", self.on_lookup)
        self.stub(patch.BONUS_LOOKUP_FLOAT_FN, f"{CLOBBER} fld dword ptr [{SLOT_F:#x}]\n ret 0x10", self.on_lookup_f)
        self.stub(patch.NAME_MATCH_FN, f"{CLOBBER} mov al, byte ptr [{SLOT_B:#x}]\n ret 4", self.on_name)

    def a(self, va):
        return va + self.delta

    def stub(self, va, src, cb):
        self.uc.mem_write(self.a(va), patch._asm(src, self.a(va)))
        self.uc.hook_add(UC_HOOK_CODE, lambda uc, addr, size, _: cb(), begin=self.a(va), end=self.a(va))

    def u32(self, addr):
        return struct.unpack("<I", self.uc.mem_read(addr, 4))[0]

    def args(self, n):
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        return [self.u32(esp + 4 * (i + 1)) for i in range(n)]

    def on_lookup(self, float_=False):
        cat, rec, zero, bid = self.args(4)
        ecx = self.uc.reg_read(UC_X86_REG_ECX)
        self.calls.append((cat, rec, zero, bid, ecx))
        v = self.values.get((cat, rec, bid), 0)
        self.uc.mem_write(SLOT_F if float_ else SLOT_INT, struct.pack("<f" if float_ else "<i", v))

    def on_lookup_f(self):
        self.on_lookup(float_=True)

    def on_name(self):
        ptr, = self.args(1)
        s = bytes(self.uc.mem_read(ptr, 40)).split(b"\0")[0].decode()
        self.calls.append(("name", s, self.uc.reg_read(UC_X86_REG_ECX)))
        self.uc.mem_write(SLOT_B, bytes([s == self.name]))

    def run(self, body, setup=""):
        """Harness: set registers, `body` (pushes + call), then store eax / x87 status; returns esp delta."""
        src = (f"mov esi, {UNIT:#x}\n mov edi, {SENTINELS[UC_X86_REG_EDI]:#x}\n mov ebx, {SENTINELS[UC_X86_REG_EBX]:#x}\n"
               f" mov ebp, {SENTINELS[UC_X86_REG_EBP]:#x}\n mov ecx, {CONTAINER:#x}\n {setup}\n {body}\n"
               f" mov dword ptr [{RES_EAX:#x}], eax\n fnstsw ax\n mov word ptr [{RES_SW:#x}], ax\n nop")
        code = patch._asm(src, HARNESS)
        self.uc.mem_write(HARNESS, code)
        self.uc.reg_write(UC_X86_REG_ESP, STACK_TOP)
        try:
            self.uc.emu_start(HARNESS, HARNESS + len(code) - 1, count=10000)
        except UcError as ex:   # e.g. a bad `ret` jumped into unmapped memory
            return f"crashed ({ex})"
        return self.uc.reg_read(UC_X86_REG_ESP) - STACK_TOP


def x87_depth(sw):
    top = (sw >> 11) & 7
    return (8 - top) % 8


class Checks:
    def __init__(self):
        self.failures, self.passed = [], 0

    def __call__(self, cond, what):
        if cond:
            self.passed += 1
        else:
            self.failures.append(what)


def regs_ok(e, check, label, esi=True):
    for reg, v in SENTINELS.items():
        check(e.uc.reg_read(reg) == v, f"{label}: callee-saved register changed")
    if esi:
        check(e.uc.reg_read(UC_X86_REG_ESI) == UNIT, f"{label}: esi (the unit record) changed")


def lookups_ok(e, check, label, expected):
    got = [(c, r, b) for c, r, z, b, ecx in e.calls if isinstance(c, int)]
    check(got == expected, f"{label}: lookups {[(hex(c), hex(r), hex(b)) for c, r, b in got]}")
    check(all(z == 0 and ecx == CONTAINER for c, r, z, b, ecx in e.calls if isinstance(c, int)),
          f"{label}: a lookup didn't get the bonus list in ecx (or a 0 third key)")


def call_site(target, rec, bid):
    return f"push {bid:#x}\n push {rec:#x}\n call {target:#x}"


def test_all(delta, check):
    labels = patch.stat_labels()
    t = {k: v + delta for k, v in labels.items()}
    tag = f"[delta {delta:#x}] "
    S0 = STACK_TOP   # the caller's esp after the call returns (the builder's esp)

    # int stat (reload site): class bonus + unit_record bonus (id + 0x10)
    e = Emu(delta)
    e.values = {(patch.CAT_UNIT_CLASS, CLASS_REC, 4): 7, (patch.CAT_UNIT_RECORD, UNIT, 0x14): 5}
    d = e.run(call_site(t["int"], CLASS_REC, 4))
    check(e.u32(RES_EAX) == 12, tag + f"int stat: returned {e.u32(RES_EAX)}, expected 7 + 5")
    check(d == 0, tag + f"int stat: stack off by {d}")
    check(x87_depth(e.u32(RES_SW)) == 0, tag + "int stat: x87 stack not empty")
    regs_ok(e, check, tag + "int stat")
    lookups_ok(e, check, tag + "int stat", [(patch.CAT_UNIT_CLASS, CLASS_REC, 4), (patch.CAT_UNIT_RECORD, UNIT, 0x14)])

    # float stats: class (ammo site) and category (speed site); result in st(0)
    for kind, cat, rec, bid in (("class_f", patch.CAT_UNIT_CLASS, CLASS_REC, 8),
                                ("category_f", patch.CAT_UNIT_CATEGORY, CATEGORY_REC, 9)):
        e = Emu(delta)
        e.values = {(cat, rec, bid): 2.5, (patch.CAT_UNIT_RECORD, UNIT, bid + 0x10): 4.0}
        d = e.run(call_site(t[kind], rec, bid) + f"\n fstp dword ptr [{RES_F:#x}]")
        f = struct.unpack("<f", e.uc.mem_read(RES_F, 4))[0]
        check(f == 6.5, tag + f"{kind}: returned {f}, expected 2.5 + 4.0")
        check(d == 0, tag + f"{kind}: stack off by {d}")
        check(x87_depth(e.u32(RES_SW)) == 0, tag + f"{kind}: x87 stack unbalanced (should hold exactly the result)")
        regs_ok(e, check, tag + kind)
        lookups_ok(e, check, tag + kind, [(cat, rec, bid), (patch.CAT_UNIT_RECORD, UNIT, bid + 0x10)])

    # range: adds class + unit_record range to the builder's field at [esp+0xb8], returns 0.0
    e = Emu(delta)
    e.values = {(patch.CAT_UNIT_CLASS, CLASS_REC, 7): 10.0, (patch.CAT_UNIT_RECORD, UNIT, 0x17): 40.0}
    field = S0 + 0xB8
    e.uc.mem_write(field, struct.pack("<f", 0.0))
    d = e.run(call_site(t["range"], CLASS_REC, 7) + f"\n fstp dword ptr [{RES_F:#x}]")
    f = struct.unpack("<f", e.uc.mem_read(RES_F, 4))[0]
    rng = struct.unpack("<f", e.uc.mem_read(field, 4))[0]
    check(rng == 50.0, tag + f"range: field is {rng}, expected 0 + 10 + 40")
    check(f == 0.0, tag + f"range: returned {f}, expected 0 (so the builder's multiply keeps the field)")
    check(d == 0, tag + f"range: stack off by {d}")
    check(x87_depth(e.u32(RES_SW)) == 0, tag + "range: x87 stack unbalanced")
    regs_ok(e, check, tag + "range")

    # charge: class + unit_record charge; general_aoe_mod bits 21-23 -> flags; bonus vs cavalry added
    struct_base = S0 + 0x78
    for bits, want in ((0, (0, 0, 0)), (5 | (1 << patch.SNIPE_BIT), (1, 0, 0)), (1 << patch.CAMO_BIT, (0, 1, 0)),
                       (1 << patch.GUERRILLA_BIT, (0, 0, 1)), ((7 << 21) | 0x1FFFFF, (1, 1, 1))):
        e = Emu(delta)
        e.values = {(patch.CAT_UNIT_CLASS, CLASS_REC, 0xB): 3, (patch.CAT_UNIT_RECORD, UNIT, 0x1B): 4,
                    (patch.CAT_UNIT_RECORD, UNIT, patch.BONUS_GENERAL_AOE): bits,
                    (patch.CAT_UNIT_RECORD, UNIT, patch.BONUS_VS_CAVALRY): 6}
        e.uc.mem_write(struct_base, bytes(0x110))
        e.uc.mem_write(struct_base + patch.FIELD_VS_CAVALRY, struct.pack("<i", 20))
        d = e.run(call_site(t["charge"], CLASS_REC, 0xB))
        mem = bytes(e.uc.mem_read(struct_base, 0x110))
        label = tag + f"charge (bits {bits:#x})"
        check(e.u32(RES_EAX) == 7, label + f": returned {e.u32(RES_EAX)}, expected 3 + 4")
        snipe = mem[patch.FLAG_SNIPE]
        hide = mem[patch.FLAG_HIDE4:patch.FLAG_HIDE4 + 4]
        guer = mem[patch.FLAG_GUERRILLA]
        check(snipe == want[0], label + f": fire-while-hidden flag {snipe}")
        check(hide == bytes([want[1]] * 4), label + f": hide flags {hide.hex()}")
        check(guer == want[2], label + f": guerrilla flag {guer}")
        vs = struct.unpack_from("<i", mem, patch.FIELD_VS_CAVALRY)[0]
        check(vs == 26, label + f": bonus vs cavalry {vs}, expected 20 + 6")
        others = bytearray(mem)
        for off, n in ((patch.FLAG_SNIPE, 1), (patch.FLAG_HIDE4, 4), (patch.FLAG_GUERRILLA, 1), (patch.FIELD_VS_CAVALRY, 4)):
            others[off:off + n] = bytes(n)
        check(not any(others), label + ": wrote outside the four fields")
        check(d == 0, label + f": stack off by {d}")
        check(x87_depth(e.u32(RES_SW)) == 0, label + ": x87 stack not empty")
        regs_ok(e, check, label)
        lookups_ok(e, check, label, [(patch.CAT_UNIT_CLASS, CLASS_REC, 0xB), (patch.CAT_UNIT_RECORD, UNIT, 0x1B),
                                     (patch.CAT_UNIT_RECORD, UNIT, patch.BONUS_GENERAL_AOE),
                                     (patch.CAT_UNIT_RECORD, UNIT, patch.BONUS_VS_CAVALRY)])

    # parser extension: entered at the parser's not-found exit with [esp] = saved edi, [esp+4] = saved
    # esi, edi = the name; returns the id (13 = not found) and restores esi/edi
    names = list(patch.STAT_BONUSES.items()) + [("bonus_vs_cavalry", patch.BONUS_VS_CAVALRY), ("no_such_bonus", 0xD)]
    for name, want in names:
        e = Emu(delta)
        e.name = name
        ext = patch.CAVE_VA + patch.PARSE_OFFSET + delta
        # what the vanilla parser does before reaching its exit: push esi / push edi / edi = name
        body = f"call enter\n jmp after\nenter:\n push esi\n push edi\n mov edi, {NAME_OBJ:#x}\n mov esi, 13\n jmp {ext:#x}\nafter:"
        d = e.run(body)
        label = tag + f"parser '{name}'"
        check(e.u32(RES_EAX) == want, label + f": returned {e.u32(RES_EAX):#x}, expected {want:#x}")
        check(d == 0, label + f": stack off by {d}")
        check(e.uc.reg_read(UC_X86_REG_ESI) == UNIT and e.uc.reg_read(UC_X86_REG_EDI) == SENTINELS[UC_X86_REG_EDI],
              label + ": esi/edi not restored")
        check(all(c[2] == NAME_OBJ for c in e.calls if c[0] == "name"), label + ": name compare didn't get the name in ecx")
        seen = [c[1] for c in e.calls if c[0] == "name"]
        check(name not in dict(names[:-1]) or seen[-1] == name, label + f": compared {seen}")


def main():
    check = Checks()
    for delta in (0, 0x1230000):
        test_all(delta, check)
    print(f"{check.passed} checks passed, {len(check.failures)} failed (emulated, at the real addresses and shifted)")
    for f in check.failures:
        print("  FAIL:", f)
    return 1 if check.failures else 0


if __name__ == "__main__":
    sys.exit(main())
