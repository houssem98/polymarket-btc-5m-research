"""Tests the COMPARISON.md gap claims against the 700 cached windows.

Answers, with numbers instead of assertions:
  Gap 2  is the "micro-hedge" (buying the 1-5c tail) profitable, or just a fee?
  Band   jmazzini buys BTC at 0.94-0.99; our scaffold caps at 0.88. Which band works?
"""
import json
import math
import pathlib

CACHE = pathlib.Path(__file__).parent / "windows_hist.jsonl"
FEE_RATE = 0.07
HALF_SPREAD = 0.005


def load():
    rows = [json.loads(l) for l in CACHE.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in rows if r.get("up_mid") is not None]


def fee(p):
    return FEE_RATE * p * (1 - p)


def report(label, trades):
    if not trades:
        print(f"{label:<26} n=0")
        return
    n = len(trades)
    hit = sum(t["won"] for t in trades) / n
    avg = sum(t["pay"] for t in trades) / n
    pnl = sum(t["pnl"] for t in trades)
    se = math.sqrt(max(avg * (1 - avg), 1e-9) / n)
    z = (hit - avg) / se
    roi = pnl / sum(t["pay"] for t in trades)
    print(f"{label:<26} n={n:<5} hit={hit:6.2%} implied={avg:6.2%} z={z:+5.2f} "
          f"pnl/tr=${pnl/n:+.4f} ROI={roi:+6.2%} tot=${pnl:+.2f}")


def mk(pay, won):
    f = fee(pay)
    return {"pay": pay, "won": won, "pnl": (1.0 - pay - f) if won else (-pay - f)}


def main():
    rows = load()
    print(f"windows: {len(rows)}  (sampled ~T-52s, pay = mid + {HALF_SPREAD})\n")

    fav, dog = [], []
    for r in rows:
        if r["up_mid"] > r["dn_mid"]:
            fs, fm, ds, dm = "UP", r["up_mid"], "DOWN", r["dn_mid"]
        else:
            fs, fm, ds, dm = "DOWN", r["dn_mid"], "UP", r["up_mid"]
        fav.append({**mk(min(fm + HALF_SPREAD, 0.999), fs == r["winner"]), "raw": fm})
        dog.append({**mk(max(dm + HALF_SPREAD, 0.001), ds == r["winner"]), "raw": dm})

    print("GAP 2 — micro-hedge / tail bet (buy the underdog)")
    report("  all underdogs", dog)
    for lo, hi in [(0.0, 0.02), (0.02, 0.05), (0.05, 0.15), (0.15, 0.50)]:
        report(f"  dog mid {lo:.2f}-{hi:.2f}", [t for t in dog if lo <= t["raw"] < hi])
    cheap = [t for t in dog if t["raw"] < 0.05]
    if cheap:
        f = sum(fee(t["pay"]) for t in cheap) / len(cheap)
        p = sum(t["pay"] for t in cheap) / len(cheap)
        print(f"  -> fee on a {p:.3f} tail bet is {f:.5f}/share = {f/p:.1%} of notional")

    print("\nENTRY BAND — favourite")
    report("  jmazzini 0.94-0.99", [t for t in fav if 0.94 <= t["raw"] <= 0.99])
    report("  scaffold <= 0.88", [t for t in fav if t["raw"] <= 0.88])
    report("  0.88-0.94 (no man's)", [t for t in fav if 0.88 < t["raw"] < 0.94])
    report("  > 0.99", [t for t in fav if t["raw"] > 0.99])
    print(f"  coverage: jmazzini band fires on "
          f"{sum(1 for t in fav if 0.94 <= t['raw'] <= 0.99)}/{len(fav)} windows, "
          f"scaffold band on {sum(1 for t in fav if t['raw'] <= 0.88)}/{len(fav)}")

    print("\nz is (hit - implied) / SE. |z| < 2 = indistinguishable from a fair price.")


if __name__ == "__main__":
    main()
