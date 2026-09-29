# SIM_NOTES.md — the in-repo channel model

This documents what `optical_mem.py` actually simulates. It is a software
model of free-space optical crosstalk + detector noise, not a claim about
built hardware. Every number below is a default in `DEFAULTS`
(`optical_mem.py`); `server.py` overrides `angle_spacing_deg` with the
live tube geometry (180° / 8 tubes = 22.5°).

## What a "read" does

`simulate_readout(pages)` pushes stored bit pages through:

1. **Full product-space crosstalk** (`channel_matrix`): every channel
   leaks into every other channel across five axes —
   - angle: Gaussian beam overlap (spacing 22.5° live, beam 1/e² radius
     0.77° → adjacent crosstalk ~1.2e-3)
   - color: 1e-3 coarse-band leakage (dichroic / detector imperfection)
   - fine frequency: 3e-3 into adjacent channels (~25 dB isolation,
     100 GHz DWDM-class)
   - polarization: 1e-3 H↔V (PBS extinction ~1000:1)
   - OAM: 2e-2 into adjacent modes (~-17 dB sorter), /10 per further mode
2. **Gaussian noise** combining phase jitter (σ=0.05 of signal) and shot
   noise (1e4 photons per bright pixel per readout)
3. **Thermal angle wander**: σ=0.05° per page beam per readout
4. **Hard threshold** at 0.5 → bit decisions

## Geometry

8 laser-tube diameters × 2 colors × 2 freqs × 2 pols × 3 OAM modes =
192 simultaneously-live channels. Pages are 64×64 bits (4096 bits),
addressed by (tube, color, freq, pol, oam).

## Honest limits

- `/v1/ring/query` does **not** go through this model — it correlates the
  query pattern against stored bits directly.
- "Reading is exact" means: spot checks (write → read) have come back
  bit-identical, and the query path scores 1.0 on unflipped patterns.
  But the model contains real noise terms, so exactness is statistical,
  not guaranteed by construction. No test pins an error rate.
- State is volatile RAM: a restart clears the ring.
- The full laboratory optical sim (tube physics, interference patterns)
  is not in this repo.
