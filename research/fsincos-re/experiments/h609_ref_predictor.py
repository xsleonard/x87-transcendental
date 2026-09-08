#!/usr/bin/env python3
"""h609: THE UNIFIED ROUND-57 REFERENCE PREDICTOR.

Merged model = h604_model_v3.json (h602_full with W1 refit)
overridden by h606_v5_model.json for its ten pocket
stratum-sides (V5 zones = (xd12, mf16)).  Predict semantics =
h606_v5_blind.predict: j = round(q*tau + a*mf + b + c(zone,
st)); req2_pred = (4*Vlow - j*rfv) >> (kf+2); fire iff req2p ==
+1 (up) / -1 (dn).  Returns (pred_fire, req2_pred, source) or
None when the (stratum-side, zone) has no fit (uncovered).

Feature contract (h598/h602/h606):
  tau = t4 / 2^s4; mf = (m & (2^63-1)) / 2^63;
  xd12 = min(11, (rdisc * 12) >> rsh);
  st = ((S + C) >> max(rsh - 59, 0)) & 63   (h588 winner tree);
  side = 'up' if theta <= 0 else 'dn'.
"""
import json

V5_KEYS = {(8, 1, -72, "up"), (8, 2, -72, "up"),
           (8, 4, -72, "up"), (8, 5, -72, "up"),
           (8, 6, -72, "up"), (8, 7, -72, "up"),
           (9, 1, -73, "up"), (9, 2, -73, "up"),
           (9, 4, -73, "dn"), (9, 5, -73, "dn")}


def load_model(base="."):
    v3 = json.load(open(f"{base}/h604_model_v3.json"))
    v5 = json.load(open(f"{base}/h606_v5_model.json"))
    fits, cbest = {}, {}
    for k, v in v3["fits"].items():
        key, xd12 = eval(k)
        if tuple(key) in V5_KEYS:
            continue
        fits[(tuple(key), xd12)] = tuple(v)
    for k, c in v3["cbest"].items():
        (key, xd12), st = eval(k)
        if tuple(key) in V5_KEYS:
            continue
        cbest[((tuple(key), xd12), st)] = c
    for k, v in v5["fits"].items():
        key, xd12, mf16 = eval(k)
        fits[(tuple(key), xd12, mf16)] = tuple(v)
    for k, c in v5["cbest"].items():
        (key, xd12, mf16), st = eval(k)
        cbest[((tuple(key), xd12, mf16), st)] = c
    return fits, cbest


def predict(fits, cbest, key, xd12, mf, st, tau, Vlow, kf, rfv):
    if key in V5_KEYS:
        zid = (key, xd12, min(15, int(mf * 16)))
        src = "v5"
    else:
        zid = (key, xd12)
        src = "v3"
    f = fits.get(zid)
    if f is None:
        return None
    q, a, b = f
    x = q * tau + a * mf + b + cbest.get((zid, st), 0)
    j = round(x)
    req2p = (4 * Vlow - j * rfv) >> (kf + 2)
    side = key[3]
    fire = 1 if req2p == (1 if side == "up" else -1) else 0
    return fire, req2p, src


if __name__ == "__main__":
    fits, cbest = load_model()
    keys = sorted({z[0] for z in fits}, key=str)
    print(f"zones {len(fits)}, offsets {len(cbest)}, "
          f"stratum-sides {len(keys)}")
    for k in keys:
        nz = sum(1 for z in fits if z[0] == k)
        print(f"  {k}: {nz} zones")
