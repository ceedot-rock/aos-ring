#!/usr/bin/env python3
"""aos-ring: the aOs (agent operating system) optical Ring as a
network service. Agent Rider infrastructure.

The Ring: 8 laser tubes span a ring end to end across diameters;
every diameter crosses at the center, so the center IS the Ring.
Each tube houses lasers at 2 colors x 2 fine freqs x 2 polarizations x
3 OAM (orbital angular momentum) modes = 192 simultaneously-live
channels. Data pages are 64x64-bit interference patterns addressed by
(tube, color, freq, pol, oam).

Reads on /v1/ring/read go through the simulated channel model (optical_mem.py):
crosstalk between channels + phase-jitter / shot / thermal noise, then
thresholding. This is a real ring, not a dict: reads are physical.
(/v1/ring/query instead correlates the query pattern against the stored
bits directly — no channel model on that path.)

VOLATILE BY DESIGN. Ring state lives in memory only. A restart
clears it — it models RAM, not disk. Nothing here is persisted.

Channel math: see SIM_NOTES.md — it documents every physical assumption
of the in-repo channel model.
"""
import base64
import os
import threading

import numpy as np
from flask import Flask, jsonify, request

import optical_mem as om

# ---------------------------------------------------------------------------
# Ring geometry (fixed at boot)
# ---------------------------------------------------------------------------
T, C, F, P, L = 8, 2, 2, 2, 3          # tubes, colors, freqs, pols, OAM modes
N_CH = T * C * F * P * L               # 192 live channels
H, WD = om.DEFAULTS["page_shape"]      # 64 x 64
BITS_PER_PAGE = H * WD                 # 4096
SPACING = 180.0 / T                    # tube orientations t*22.5 deg

# Default channel (noise) parameters used on every read. Documented in
# API.md; these are the design-point values from the sim (SIM_NOTES.md).
CHANNEL = {
    "angle_spacing_deg": SPACING,
    "beam_width_deg": om.DEFAULTS["beam_width_deg"],
    "color_leakage": om.DEFAULTS["color_leakage"],
    "freq_leakage": om.DEFAULTS["freq_leakage"],
    "pol_leakage": om.DEFAULTS["pol_leakage"],
    "oam_leakage": om.DEFAULTS["oam_leakage"],
    "photons_per_bit": om.DEFAULTS["photons_per_bit"],
    "jitter_sigma": om.DEFAULTS["jitter_sigma"],
    "drift_sigma_deg": om.DEFAULTS["drift_sigma_deg"],
    "threshold": om.DEFAULTS["threshold"],
}

app = Flask(__name__)
_lock = threading.Lock()
_rng = np.random.default_rng()         # unseeded: a real ring has real noise

# Volatile state. Restart clears it. That's the point.
_store = {}                            # (t,c,f,p,l) -> uint8 (H,WD) intended bits
_active_tubes = set(range(T))           # lit diameters; dark tubes carry nothing


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _addr_ok(a):
    return (isinstance(a, (list, tuple)) and len(a) == 5 and
            all(isinstance(x, int) for x in a) and
            0 <= a[0] < T and 0 <= a[1] < C and 0 <= a[2] < F and
            0 <= a[3] < P and 0 <= a[4] < L)


def _key(a):
    return tuple(int(x) for x in a)


def _parse_bits(bits, encoding="bitstring"):
    """-> uint8 (H,WD) array, or raises ValueError."""
    if encoding == "bitstring":
        s = bits.strip()
        if len(s) != BITS_PER_PAGE or any(ch not in "01" for ch in s):
            raise ValueError(f"bitstring must be exactly {BITS_PER_PAGE} chars of 0/1")
        return np.array([ord(ch) - 48 for ch in s], dtype=np.uint8).reshape(H, WD)
    if encoding == "base64":
        raw = base64.b64decode(bits)
        if len(raw) * 8 < BITS_PER_PAGE:
            raise ValueError(f"base64 must decode to >= {BITS_PER_PAGE // 8} bytes")
        return np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:BITS_PER_PAGE].reshape(H, WD)
    raise ValueError("encoding must be 'bitstring' or 'base64'")


def _bits_out(arr):
    return "".join(str(int(b)) for b in np.asarray(arr, dtype=np.uint8).ravel())


def _intended_array():
    """Full 7D intended-bits ring, dark tubes zeroed (lasers off)."""
    s = np.zeros((T, C, F, P, L, H, WD), dtype=np.uint8)
    for k, v in _store.items():
        if k[0] in _active_tubes:
            s[k] = v
    return s


def _readout(intended):
    """Push the ring through the optics. Returns (values, decisions)."""
    return om.simulate_readout(intended, rng=_rng,
                               angle_spacing_deg=CHANNEL["angle_spacing_deg"],
                               beam_width_deg=CHANNEL["beam_width_deg"],
                               color_leakage=CHANNEL["color_leakage"],
                               freq_leakage=CHANNEL["freq_leakage"],
                               pol_leakage=CHANNEL["pol_leakage"],
                               oam_leakage=CHANNEL["oam_leakage"],
                               photons_per_bit=CHANNEL["photons_per_bit"],
                               jitter_sigma=CHANNEL["jitter_sigma"],
                               drift_sigma_deg=CHANNEL["drift_sigma_deg"],
                               threshold=CHANNEL["threshold"])


def _err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    with _lock:
        return jsonify({
            "ok": True,
            "service": "aos-ring",
            "volatile": True,
            "volatility_note": "ring state lives in memory only; a restart clears it (RAM, not disk)",
            "ring": {"tubes": T, "colors": C, "freq": F, "pol": P, "oam_modes": L,
                        "channels": N_CH, "page_bits": BITS_PER_PAGE},
            "stored_pages": len(_store),
            "active_tubes": sorted(_active_tubes),
        })


@app.post("/v1/ring/write")
def write():
    body = request.get_json(force=True, silent=True) or {}
    pages = body.get("pages")
    if not isinstance(pages, list) or not pages:
        return _err("pages: non-empty list required")
    written = []
    with _lock:
        for pg in pages:
            a = pg.get("address")
            if not _addr_ok(a):
                return _err(f"bad address {a}: need [tube<{T}, color<{C}, freq<{F}, pol<{P}, oam<{L}]")
            try:
                bits = _parse_bits(pg.get("bits", ""), pg.get("encoding", "bitstring"))
            except ValueError as e:
                return _err(str(e))
            _store[_key(a)] = bits
            written.append(list(a))
    return jsonify({"ok": True, "written": len(written), "addresses": written})


@app.post("/v1/ring/read")
def read():
    body = request.get_json(force=True, silent=True) or {}
    addrs = body.get("addresses")
    if not isinstance(addrs, list) or not addrs:
        return _err("addresses: non-empty list required")
    for a in addrs:
        if not _addr_ok(a):
            return _err(f"bad address {a}")
    with _lock:
        intended = _intended_array()
        _, decisions = _readout(intended)
        out, diag = [], {}
        for a in addrs:
            k = _key(a)
            t, c, f, p, l = k
            got = decisions[t, c, f, p, l]
            out.append({"address": list(k), "bits": _bits_out(got),
                        "tube_lit": t in _active_tubes})
            if k in _store and t in _active_tubes:
                diag[f"{t},{c},{f},{p},{l}"] = round(om.ber(_store[k], got), 6)
    return jsonify({"ok": True, "pages": out,
                    "channel": CHANNEL,
                    "ber_vs_written": diag,
                    "note": "read through the channel model (crosstalk + noise); "
                            "ber_vs_written is diagnostic only"})


@app.post("/v1/ring/query")
def query():
    """Associative lookup: correlate a (possibly noisy) query pattern
    against all live entries simultaneously; winner-take-all."""
    body = request.get_json(force=True, silent=True) or {}
    try:
        q = _parse_bits(body.get("bits", ""), body.get("encoding", "bitstring"))
    except ValueError as e:
        return _err(str(e))
    flips = body.get("flips", 0.0)
    if not isinstance(flips, (int, float)) or not 0.0 <= flips < 1.0:
        return _err("flips must be in [0, 1)")
    with _lock:
        entries = [(k, v) for k, v in _store.items() if k[0] in _active_tubes]
    if not entries:
        return _err("ring empty: nothing to match against", 404)
    qf = q.astype(float).ravel().copy()
    if flips > 0:
        m = _rng.random(qf.size) < flips
        qf[m] = 1.0 - qf[m]
    best, best_score = None, -1.0
    for k, v in entries:
        score = float(np.mean(qf == v.astype(float).ravel()))
        if score > best_score:
            best, best_score = k, score
    return jsonify({"ok": True, "address": list(best),
                    "score": round(best_score, 6),
                    "entries_searched": len(entries),
                    "flips_applied": flips})


@app.post("/v1/ring/route")
def route():
    """Activate/deactivate tube diameters. Dark tubes carry nothing."""
    body = request.get_json(force=True, silent=True) or {}
    tubes = body.get("tubes")
    if not isinstance(tubes, list) or any(not isinstance(t, int) or not 0 <= t < T for t in tubes):
        return _err(f"tubes: list of tube ids 0..{T - 1} required")
    with _lock:
        _active_tubes.clear()
        _active_tubes.update(tubes)
        active = sorted(_active_tubes)
    return jsonify({"ok": True, "active_tubes": active,
                    "note": "deactivated diameters are dark: reads return zeros"})


@app.post("/v1/ring/delete")
def delete():
    """kill = lasers off (no forensic remnant); decohere = phases
    scrambled (presence detectable, content unrecoverable)."""
    body = request.get_json(force=True, silent=True) or {}
    addrs = body.get("addresses")
    mode = body.get("mode", "kill")
    if mode not in ("kill", "decohere"):
        return _err("mode must be 'kill' or 'decohere'")
    if not isinstance(addrs, list) or not addrs:
        return _err("addresses: non-empty list required")
    for a in addrs:
        if not _addr_ok(a):
            return _err(f"bad address {a}")
    n = 0
    with _lock:
        for a in addrs:
            k = _key(a)
            if k in _store:
                if mode == "kill":
                    del _store[k]
                else:
                    _store[k] = _rng.integers(0, 2, size=(H, WD)).astype(np.uint8)
                n += 1
    return jsonify({"ok": True, "deleted": n, "mode": mode,
                    "note": "kill: indistinguishable from never-written; "
                            "decohere: present-but-unreadable (see SIM_NOTES.md)"})


@app.get("/v1/ring/glow")
def glow():
    """Machine-only-readability demo: the integrated 'human view' glow vs
    the decomposed machine readout. The glow leaks total brightness only;
    the information lives in the decomposition."""
    with _lock:
        intended = _intended_array()
        values, _ = _readout(intended)
        g = om.human_view(values)                       # (64,64) glow
        small = g.reshape(8, 8, 8, 8).mean(axis=(1, 3))  # 8x8 downsample
        tube_power = [round(float(values[t].sum()), 1) for t in range(T)]
        total = round(float(g.sum()), 1)
    return jsonify({
        "ok": True,
        "glow_total": total,
        "glow_8x8": [[round(float(x), 2) for x in row] for row in small],
        "tube_power": tube_power,
        "note": "this is what a bare sensor (or an eye) sees: total light. "
                "Two different stored states with equal bright-bit counts are "
                "indistinguishable here; the full per-channel decomposition "
                "(see /v1/ring/read) separates them cleanly. Machine-only readable.",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)
