"""
Self-check for Lab 1 (Logical Agents).

Runs every code cell of the notebook, then tests the classes, `evaluate` and
`query` against all 10 examples from the notebook plus the full three-valued
truth tables. The autograder uses NEW examples, so all 10 should pass, not
just yours.

Usage:
    python3 check_lab1.py                      # checks "Lab1_Logical_Agents 2025.ipynb"
    python3 check_lab1.py path/to/notebook.ipynb
    python3 check_lab1.py --chain my_chain_fn  # also test your Task 3 function
"""
import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).parent
args = sys.argv[1:]
CHAIN_NAME = None
if "--chain" in args:
    i = args.index("--chain")
    CHAIN_NAME = args[i + 1]
    del args[i:i + 2]
NB_PATH = Path(args[0]) if args else HERE / "Lab1_Logical_Agents 2025.ipynb"

passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  PASS  {msg}")


def bad(msg):
    global failed
    failed += 1
    if failed <= 60:
        print(f"  FAIL  {msg}")
    elif failed == 61:
        print("  ...   (further failures not printed)")


def section(title):
    print(f"\n== {title} ==")


# ---------------------------------------------------------------- load notebook
section(f"Running notebook cells: {NB_PATH.name}")
ns = {"__name__": "__main__"}
cells = [c for c in json.loads(NB_PATH.read_text())["cells"] if c["cell_type"] == "code"]
for idx, cell in enumerate(cells):
    src = "".join(cell["source"])
    src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("!", "%")))
    try:
        exec(compile(src, f"<cell {idx}>", "exec"), ns)
    except Exception:
        bad(f"code cell {idx} raised an exception:")
        traceback.print_exc(limit=2)

missing = [n for n in ("And", "Or", "Not", "Implies", "Equals", "evaluate", "query") if n not in ns]
if missing:
    bad(f"missing required names: {missing}")
    print("\nCannot continue without these.")
    sys.exit(1)

And, Or, Not, Implies, Equals = (ns[n] for n in ("And", "Or", "Not", "Implies", "Equals"))
evaluate, query = ns["evaluate"], ns["query"]

# ---------------------------------------------------------------- classes
section("Tasks 1-2: operator classes")
try:
    s = Implies(And("a", Not("b")), Equals(Or("c", "d"), True))
    r = repr(s)
    if r and " object at 0x" not in r:
        ok(f"nested sentence builds, repr = {r}")
    else:
        bad(f"__repr__ still the default / empty: {r!r}")
except Exception as e:
    bad(f"building a nested sentence failed: {e!r}")

try:
    hash(And("a", "b"))
    {And("a", "b"), Not("a")}
    ok("sentences are hashable (can be stored in a set KB)")
except TypeError as e:
    bad(f"sentences are not hashable -> cannot go in a set KB ({e}). "
        "If you defined __eq__, also define __hash__.")

NARY = True
try:
    And("a", "b", "c")
    Or("a", "b", "c")
    ok("And/Or accept 3+ sub-sentences")
except TypeError:
    NARY = False
    bad("And(a, b, c) / Or(a, b, c) not supported (Task 2) - "
        "a grader on new examples may build sentences this way")


def AND(*xs):
    return And(*xs) if NARY or len(xs) == 2 else And(xs[0], AND(*xs[1:]))


def OR(*xs):
    return Or(*xs) if NARY or len(xs) == 2 else Or(xs[0], OR(*xs[1:]))


section("Task 3: chain function")
if CHAIN_NAME is None:
    print("  skip  (run with --chain <your_function_name> to test it)")
elif CHAIN_NAME not in ns:
    bad(f"no function named {CHAIN_NAME!r} in the notebook")
else:
    chain = ns[CHAIN_NAME]
    try:
        c = chain(And, ["x", "y", "z"])
        m = {"x": True, "y": True, "z": False}
        top_ok = isinstance(c, And)
        val_ok = evaluate(c, m) is False and evaluate(c, {**m, "z": True}) is True
        (ok if top_ok and val_ok else bad)(f"chain(And, [x, y, z]) -> {c!r}")
        c1 = chain(Or, ["x"])
        (ok if evaluate(c1, {"x": True}) is True else bad)(f"chain(Or, [x]) -> {c1!r}")
    except Exception as e:
        bad(f"chain raised {e!r}")

# ---------------------------------------------------------------- evaluate basics
section("Task 4: evaluate basics")
for sent, model, exp, desc in [
    (True, {}, True, "literal True"),
    (False, {}, False, "literal False"),
    (None, {}, None, "literal None"),
    ("x", {"x": True}, True, "known variable"),
    ("x", {}, None, "missing variable -> None (no KeyError)"),
]:
    try:
        got = evaluate(sent, model)
        (ok if got is exp else bad)(f"{desc}: got {got!r}, expected {exp!r}")
    except Exception as e:
        bad(f"{desc}: raised {e!r}")

# ---------------------------------------------------------------- three-valued truth tables
section("Task 5: three-valued (True/False/None) truth tables")
V = (True, False, None)


def k_not(a):
    return None if a is None else (not a)


def k_and(a, b):
    return False if False in (a, b) else (None if None in (a, b) else True)


def k_or(a, b):
    return True if True in (a, b) else (None if None in (a, b) else False)


def k_imp(a, b):
    return k_or(k_not(a), b)


def k_eq(a, b):
    return None if None in (a, b) else a == b


def as_var(name, val, model):
    # None is represented by leaving the variable out of the model
    if val is not None:
        model[name] = val
    return name


table_fail = 0
for a in V:
    m = {}
    for label, build, model in ((f"Not({a!r})", lambda: Not(a), {}),
                                (f"Not(p={a!r})", lambda: Not(as_var("p", a, m)), m)):
        try:
            got = evaluate(build(), model)
            if got is not k_not(a):
                table_fail += 1
                bad(f"{label}: got {got!r}, expected {k_not(a)!r}")
        except Exception as e:
            table_fail += 1
            bad(f"{label}: raised {e!r}")
    for b in V:
        for name, cls, fn in (("And", And, k_and), ("Or", Or, k_or),
                              ("Implies", Implies, k_imp), ("Equals", Equals, k_eq)):
            exp = fn(a, b)
            m = {}
            for label, build, model in (
                (f"{name}({a!r}, {b!r})", lambda: cls(a, b), {}),
                (f"{name}(p={a!r}, q={b!r})", lambda: cls(as_var("p", a, m), as_var("q", b, m)), m),
            ):
                try:
                    got = evaluate(build(), model)
                    if got is not exp:
                        table_fail += 1
                        bad(f"{label}: got {got!r}, expected {exp!r}")
                except Exception as e:
                    table_fail += 1
                    bad(f"{label}: raised {e!r}")
if table_fail == 0:
    ok("all 78 truth-table cases correct (literals and variables)")

if NARY:
    for name, cls, fn in (("And", And, k_and), ("Or", Or, k_or)):
        errs = 0
        for a in V:
            for b in V:
                for c in V:
                    exp = fn(fn(a, b), c)
                    try:
                        if evaluate(cls(a, b, c), {}) is not exp:
                            errs += 1
                    except Exception:
                        errs += 1
        (ok if errs == 0 else bad)(f"3-argument {name} truth table ({errs} wrong of 27)")

# ---------------------------------------------------------------- examples
N, I, E = Not, Implies, Equals
EXAMPLES = {
    1: dict(
        model={'rain': True, 'sunny': False, 'umbrella': True, 'snow': False},
        sentences=lambda: [E('rain', N('sunny')), I('rain', 'umbrella'),
                           E(I(N('sunny'), N('umbrella')), False), I(OR('sunny', 'rain'), 'play'),
                           I('sunny', 'play'), E(N('rain'), 'play'), N('play'),
                           E(AND('sunny', 'rain', 'snow'), False)],
        eval_exp=[True, True, True, None, True, None, None, True],
        variables={"rain", "umbrella", "cloudy", "sunny"},
        queries=lambda: [True, E('rain', N('sunny')), AND('play', 'cloudy'), E('sunny', 'play'),
                         E(E('sunny', N('cloudy')), False)],
        query_exp=[(2, 0, 0), (2, 0, 0), (0, 1, 1), (0, 0, 2), (1, 1, 0)]),
    2: dict(
        model={'rain': True, 'sunny': False, 'umbrella': True, 'cloudy': True},
        sentences=lambda: [E('rain', N('sunny')), E('umbrella', 'rain'), E(N('cloudy'), False),
                           I(OR('sunny', 'rain'), 'storm'), E(N('umbrella'), False),
                           I('sunny', 'cloudy'), I(AND('rain', 'cloudy'), 'storm'),
                           OR('rain', 'cloudy', 'storm')],
        eval_exp=[True, True, True, None, True, True, None, True],
        variables={"rain", "sunny", "umbrella", "cloudy"},
        queries=lambda: [True, E('rain', N('sunny')), AND('storm', 'cloudy'), E('sunny', 'storm'),
                         E(E('sunny', N('cloudy')), False)],
        query_exp=[(1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, 1), (0, 1, 0)]),
    3: dict(
        model={'windy': True, 'humid': False, 'power': True, 'alert': False},
        sentences=lambda: [E('windy', N('humid')), I('power', 'alert'),
                           E(I(N('humid'), N('power')), False), I(OR('windy', 'humid'), 'generator'),
                           I('alert', 'windy'), E(N('alert'), False), N('generator'),
                           E(AND('windy', 'humid', 'alert'), False)],
        eval_exp=[True, False, True, None, True, False, None, True],
        variables={"windy", "humid", "power", "alert"},
        queries=lambda: [True, E('windy', N('humid')), AND('power', 'generator'),
                         E('alert', 'generator'), E(E('alert', N('humid')), False)],
        query_exp=[(1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, 1), (0, 1, 0)]),
    4: dict(
        model={'detour': False, 'accident': True, 'traffic': True, 'police': True, 'report': True},
        sentences=lambda: [E('traffic', N('detour')), I('traffic', 'police'),
                           E(I(N('detour'), N('police')), True), I(OR('detour', 'traffic'), 'witness'),
                           I('police', 'report'), E(N('report'), True), N('witness'),
                           E(AND('detour', 'traffic', 'report'), False)],
        eval_exp=[True, True, False, None, True, False, None, True],
        variables={"detour", "accident", "traffic", "police", "report"},
        queries=lambda: [True, E('traffic', N('detour')), AND('police', 'report'),
                         E('police', 'report'), E(E('witness', N('report')), False)],
        query_exp=[(2, 0, 0), (2, 0, 0), (0, 2, 0), (2, 0, 0), (0, 0, 2)]),
    5: dict(
        model={'engine': True, 'battery': False, 'fuel': True, 'starter': True},
        sentences=lambda: [E('engine', N('battery')), I('starter', 'engine'),
                           E(I(N('battery'), N('starter')), True), I(AND('engine', 'fuel'), 'starter'),
                           I('battery', 'alarm'), E(N('engine'), 'alarm'), N('starter'),
                           E(AND('engine', 'starter', 'battery'), False)],
        eval_exp=[True, True, False, True, True, None, False, True],
        variables={"engine", "battery", "fuel", "starter"},
        queries=lambda: [True, E('engine', N('battery')), AND('engine', 'starter'),
                         E('starter', 'alarm'), E(E('starter', N('fuel')), False)],
        query_exp=[(3, 0, 0), (3, 0, 0), (0, 3, 0), (0, 0, 3), (2, 1, 0)]),
    6: dict(
        model={'door': False, 'motion': True, 'alarm': True, 'power': True},
        sentences=lambda: [E('power', N('door')), I('alarm', 'motion'),
                           E(I(N('door'), N('alarm')), False), I(OR('motion', 'door'), 'camera'),
                           I('power', 'camera'), E(N('door'), True), N('camera'),
                           E(AND('door', 'alarm', 'power'), False)],
        eval_exp=[True, True, True, None, None, True, None, True],
        variables={"door", "motion", "alarm", "power"},
        queries=lambda: [True, E('power', N('door')), AND('alarm', 'camera'), E('power', 'camera'),
                         E(E('alarm', N('motion')), False)],
        query_exp=[(1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, 1), (1, 0, 0)]),
    7: dict(
        model={'stocked': True, 'shipment': False, 'crew': True, 'delay': False, 'backup': False},
        sentences=lambda: [E('stocked', N('shipment')), I('crew', 'stocked'),
                           E(I(N('shipment'), 'crew'), True), I(OR('shipment', 'crew'), 'inspection'),
                           I('delay', 'inspection'), E(N('delay'), True), N('inspection'),
                           E(AND('stocked', 'crew', 'backup'), False)],
        eval_exp=[True, True, True, None, True, True, None, True],
        variables={"stocked", "shipment", "crew", "delay", "backup"},
        queries=lambda: [True, E('stocked', N('shipment')), AND('crew', 'backup'),
                         E('crew', 'stocked'), E(E('inspection', N('delay')), False)],
        query_exp=[(3, 0, 0), (3, 0, 0), (0, 3, 0), (3, 0, 0), (0, 0, 3)]),
    8: dict(
        model={'hypothesis': True, 'evidence': True, 'peer_review': False, 'approval': True,
               'funding': False},
        sentences=lambda: [E('hypothesis', N('peer_review')), I('hypothesis', 'approval'),
                           E(I(N('peer_review'), N('approval')), False),
                           I(AND('evidence', 'approval'), 'ethics_clearance'),
                           I('peer_review', 'ethics_clearance'), E(N('approval'), 'ethics_clearance'),
                           N('ethics_clearance'), E(AND('hypothesis', 'evidence', 'funding'), False)],
        eval_exp=[True, True, True, None, True, None, None, True],
        variables={"hypothesis", "evidence", "peer_review", "approval", "funding"},
        queries=lambda: [True, E('hypothesis', N('evidence')), AND('approval', 'peer_review'),
                         E('evidence', 'approval'), E(E('evidence', N('peer_review')), False)],
        query_exp=[(3, 0, 0), (2, 1, 0), (0, 3, 0), (1, 2, 0), (2, 1, 0)]),
    9: dict(
        model={'launch': False, 'fuel': True, 'crew_ready': True, 'weather_clear': False},
        sentences=lambda: [E(N('weather_clear'), N('launch')), I('fuel', 'crew_ready'),
                           E(I(N('weather_clear'), N('fuel')), False),
                           I(OR('launch', 'fuel'), 'abort_signal'), I('crew_ready', 'abort_signal'),
                           E(N('crew_ready'), 'abort_signal'), 'fuel',
                           E(AND('launch', 'fuel', 'crew_ready'), False)],
        eval_exp=[True, True, True, None, None, None, True, True],
        variables={"launch", "fuel", "crew_ready", "weather_clear"},
        queries=lambda: [False, E('launch', N('weather_clear')), AND('crew_ready', 'abort_signal'),
                         E('abort_signal', 'crew_ready'),
                         E(E('abort_signal', N('weather_clear')), False)],
        query_exp=[(0, 1, 0), (0, 1, 0), (0, 0, 1), (0, 0, 1), (0, 0, 1)]),
    10: dict(
        model={'temperature_high': True, 'ac_on': True, 'windows_open': False,
               'humidity_high': True, 'lights_on': False},
        sentences=lambda: ['temperature_high', I('ac_on', 'temperature_high'),
                           E(I(N('windows_open'), N('ac_on')), False),
                           I(AND('temperature_high', 'humidity_high'), 'maintenance_mode'),
                           I('windows_open', 'maintenance_mode'),
                           E(N('temperature_high'), 'maintenance_mode'), N('lights_on'),
                           E(AND('temperature_high', 'humidity_high', 'lights_on'), False)],
        eval_exp=[True, True, True, None, True, None, True, True],
        variables={"temperature_high", "ac_on", "windows_open", "humidity_high", "lights_on"},
        queries=lambda: [True, E('temperature_high', N('ac_on')), AND('lights_on', 'humidity_high'),
                         E('ac_on', 'lights_on'), E(E('ac_on', N('humidity_high')), False)],
        query_exp=[(2, 0, 0), (0, 2, 0), (0, 2, 0), (0, 2, 0), (1, 1, 0)]),
}

section("Task 6: evaluate on all 10 examples")
for k, ex in EXAMPLES.items():
    try:
        sents = ex["sentences"]()
        got = [evaluate(s, dict(ex["model"])) for s in sents]
        wrong = [(i + 1, repr(s), g, e) for i, (s, g, e) in enumerate(zip(sents, got, ex["eval_exp"]))
                 if g is not e]
        if not wrong:
            ok(f"Example {k}: 8/8 sentences")
        else:
            bad(f"Example {k}: " + "; ".join(f"#{i} {s} got {g!r} expected {e!r}"
                                             for i, s, g, e in wrong))
    except Exception as e:
        bad(f"Example {k}: raised {e!r}")

section("Task 7: query return format")
try:
    res = query(AND("a", "b"), {I("a", "b")}, ["a", "b"])
    shape_ok = isinstance(res, tuple) and len(res) == 3 and all(isinstance(x, list) for x in res)
    (ok if shape_ok else bad)(f"returns a tuple of 3 lists (got {type(res).__name__}"
                              f"{'' if not isinstance(res, (tuple, list)) else f' of len {len(res)}'})")
    if shape_ok:
        models = [m for part in res for m in part]
        dict_ok = all(isinstance(m, dict) and set(m) == {"a", "b"} and
                      all(isinstance(v, bool) for v in m.values()) for m in models)
        (ok if dict_ok else bad)("every model is a {variable: bool} dict over exactly the given variables")
        (ok if len({id(m) for m in models}) == len(models) else bad)(
            "each model is a separate dict object (no shared/mutated dict)")
        counts = tuple(map(len, res))
        (ok if counts == (1, 2, 0) else bad)(
            f"KB={{a->b}}, query a&b over [a,b]: (T,F,None) got {counts}, expected (1, 2, 0) "
            "- the model a=T,b=F must be discarded, the other three kept and sorted by the query")
except Exception as e:
    bad(f"query raised {e!r}")

section("Task 7: query on all 10 examples (KB as a set, variables as a set)")
for k, ex in EXAMPLES.items():
    try:
        KB = set(ex["sentences"]())
        fails = []
        for qi, (q, exp) in enumerate(zip(ex["queries"](), ex["query_exp"])):
            got = tuple(map(len, query(q, KB, set(ex["variables"]))))
            if got != exp:
                fails.append(f"query #{qi + 1} {q!r}: (T,F,None) got {got} expected {exp}")
        (ok if not fails else bad)(f"Example {k}: " + ("5/5 queries" if not fails else "; ".join(fails)))
    except Exception as e:
        bad(f"Example {k}: raised {e!r}")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
