"""Clone records and bits, shared by the patch, the test pack and the mod.

A mod attaches a CLONE ability record to a unit type: key "vuNN_<ability>" (NN = 00-20, the bit),
supersedes_ability = <ability>, requires_effect_enabling = True. The patched engine grants the real
<ability> to units of that type when bit NN is set in the type's general_aoe_mod bonus (and any
research the real ability needs is done - a key "vuNNf<ability>" waives that). Anything may follow
the five-character prefix. Bonus values are floats, so bits 0-23 (exact up to 2^24); bits 21-23 are
not abilities but unit attributes patch v4 sets (GUERRILLA_BIT, CAMO_BIT, SNIPE_BIT).

Bits only have to be unique among the clones of ONE unit type, so a mod can offer any number of
abilities overall: assign_bits() colours the abilities so no unit type has two with the same bit.
"""
import collections

MAX_BITS = 21        # ability bits 0-20
GUERRILLA_BIT = 21   # general_aoe_mod bits for unit attributes (patch v4): guerrilla deployment,
CAMO_BIT = 22        # hide in every terrain,
SNIPE_BIT = 23       # fire while hidden


def clone_key(bit, ability, no_research=False):
    assert 0 <= bit < MAX_BITS
    return f"vu{bit:02d}{'f' if no_research else '_'}{ability}"


def assign_bits(abilities_per_unit, order=None):
    """{ability: bit} so that no unit type has two abilities with the same bit (greedy colouring,
    most-shared abilities first). abilities_per_unit: {unit key: iterable of ability keys}."""
    conflicts = collections.defaultdict(set)
    count = collections.Counter()
    for abs_ in abilities_per_unit.values():
        abs_ = set(abs_)
        for a in abs_:
            count[a] += 1
            conflicts[a] |= abs_ - {a}
    bits = {}
    for a in order or sorted(count, key=lambda a: (-len(conflicts[a]), -count[a], a)):
        taken = {bits[b] for b in conflicts[a] if b in bits}
        bit = next(i for i in range(MAX_BITS + 1) if i not in taken)
        if bit >= MAX_BITS:
            raise ValueError(f"more than {MAX_BITS} abilities on one unit type (at {a})")
        bits[a] = bit
    return bits
