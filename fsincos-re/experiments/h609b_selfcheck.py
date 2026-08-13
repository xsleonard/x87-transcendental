#!/usr/bin/env python3
"""h609b: self-check the merged reference predictor against
locked predictions from the record: h606_locked.json (V5 keys,
must match 100 percent) and h603_locked.json restricted to
keys that h604/h606 did NOT refit (h602_full carried over —
must match 100 percent)."""
import json
from multiprocessing import Pool
from h606_v5_blind import bfeat
from h609_ref_predictor import load_model, predict, V5_KEYS

W1_REFIT = set()
for k in json.load(open("h604_model_v3.json"))["fits"]:
    key, xd12 = eval(k)
    W1_REFIT.add(tuple(key))
E602 = set()
for k in json.load(open(
        "/Users/steve/llm/x87-transcendental/fsincos-re/"
        "experiments/h602_model_full.json"))["fits"]:
    key, xd12 = eval(k)
    E602.add(tuple(key))
CARRIED = E602 & W1_REFIT  # identical iff fits equal; check


def main():
    fits, cbest = load_model()
    v3 = json.load(open("h604_model_v3.json"))
    e602 = json.load(open(
        "/Users/steve/llm/x87-transcendental/fsincos-re/"
        "experiments/h602_model_full.json"))
    same = [k for k in e602["fits"]
            if k in v3["fits"] and e602["fits"][k] ==
            v3["fits"][k]]
    same_keys = {tuple(eval(k)[0]) for k in same}
    changed_keys = {tuple(eval(k)[0]) for k in e602["fits"]
                    if k not in same}
    stable = same_keys - changed_keys - V5_KEYS
    print(f"stratum-sides unchanged v3 vs 602: {len(stable)}")
    for name, locked_file in (("h606", "h606_locked.json"),
                              ("h603", "h603_locked.json")):
        sel = json.load(open(locked_file))
        use = [rec for rec in sel
               if (name == "h606") or
               (tuple(rec["key"]) in stable)]
        with Pool(14) as pool:
            bf = pool.map(bfeat, [(rec["m"], rec["key"][2],
                                   rec["key"][3])
                                  for rec in use],
                          chunksize=50)
        ok = tot = nopred = 0
        for rec, feat in zip(use, bf):
            (ra, rb, Vlow, kf, rfv, tau, mf, xd12, st,
             strat) = feat
            key = tuple(rec["key"])
            p = predict(fits, cbest, key, xd12, mf, st, tau,
                        Vlow, kf, rfv)
            if p is None:
                nopred += 1
                continue
            tot += 1
            ok += p[0] == rec["pred"]
        print(f"{name}: {ok}/{tot} match locked preds "
              f"(uncovered {nopred}, rows used {len(use)})")


if __name__ == "__main__":
    main()
