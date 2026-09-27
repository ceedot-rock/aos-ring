# aos-ring API

The aOs (agent operating system) optical Ring as a network service.
Base URL: `https://aos-ring.fly.dev`

**Volatile by design.** Ring state lives in memory only. A restart
clears it — this models RAM, not disk. Writes are sustained interference
patterns, not stored files.

**Ring geometry (fixed):** 8 laser tubes × 2 colors × 2 fine freqs ×
2 polarizations × 3 OAM (orbital angular momentum) modes = **192 live
channels**. Every tube is a diameter of the ring; all diameters cross
at the center, which is the readout ring. A page is 64×64 = **4096
bits**, addressed by `[tube, color, freq, pol, oam]` with
`tube` 0–7, `color` 0–1, `freq` 0–1, `pol` 0–1, `oam` 0–2.

**Bits encoding:** a `bitstring` is exactly 4096 chars of `0`/`1`
(MSB-first, row-major). Alternatively `"encoding": "base64"` with ≥512
bytes (first 4096 bits used).

**Every read is physical.** Reads push the whole ring through the
simulated channel model: crosstalk between channels plus noise, then
thresholding. Default channel parameters (design point from the sim):

| param | value | meaning |
|---|---|---|
| angle_spacing_deg | 22.5 | tube diameter orientations t·22.5° |
| beam_width_deg | 0.77 | page beam angular radius |
| color_leakage | 1e-3 | coarse-band filter leakage |
| freq_leakage | 3e-3 | adjacent fine-channel leakage |
| pol_leakage | 1e-3 | cross-polarization (H↔V) |
| oam_leakage | 2e-2 | adjacent OAM-mode sorter crosstalk (~−17 dB) |
| photons_per_bit | 1e4 | detected photons per bright pixel |
| jitter_sigma | 0.05 | phase-jitter (vibration) amplitude noise |
| drift_sigma_deg | 0.05 | thermal angle wander per beam |
| threshold | 0.5 | detector decision threshold |

## Endpoints

### GET /health
`{"ok":true,"service":"aos-ring","volatile":true,…}` plus ring
dims, stored page count, active tubes.

### POST /v1/ring/write
```json
{"pages":[{"address":[0,0,0,0,0],"bits":"0101…(4096 chars)"},
          {"address":[3,1,0,1,2],"bits":"…","encoding":"base64"}]}
```
→ `{"ok":true,"written":2,"addresses":[[0,0,0,0,0],[3,1,0,1,2]]}`

### POST /v1/ring/read
```json
{"addresses":[[0,0,0,0,0],[3,1,0,1,2]]}
```
→ `{"ok":true,"pages":[{"address":[…],"bits":"…","tube_lit":true}…],
"channel":{…params…},"ber_vs_written":{"0,0,0,0,0":0.0},…}`
`ber_vs_written` is diagnostic only (the ring knows what it was told).

### POST /v1/ring/query
Associative lookup: correlate a possibly-noisy pattern against all live
entries at once; winner-take-all.
```json
{"bits":"0101…","flips":0.1}
```
→ `{"ok":true,"address":[3,1,0,1,2],"score":0.93,"entries_searched":12,"flips_applied":0.1}`
`flips` randomly flips that fraction of query bits first (default 0).
404 if the ring is empty.

### POST /v1/ring/route
```json
{"tubes":[0,3]}
```
→ `{"ok":true,"active_tubes":[0,3],…}`. Deactivated diameters go dark:
their reads return zeros.

### POST /v1/ring/delete
```json
{"addresses":[[0,0,0,0,0]],"mode":"kill"}
```
→ `{"ok":true,"deleted":1,"mode":"kill",…}`.
`kill` = lasers off, readout indistinguishable from never-written.
`decohere` = phases scrambled: presence detectable, content
unrecoverable.

### GET /v1/ring/glow
The machine-only-readability demo: integrated glow total, an 8×8
downsampled glow pattern, and per-tube power. A bare sensor sees only
this; the information lives in the per-channel decomposition that
`/v1/ring/read` returns.
