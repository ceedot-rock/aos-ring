# aos-ring

The aOs (agent operating system) optical Ring, deployed as Agent
Rider infrastructure on Fly. Live at `https://aos-ring.fly.dev`.

## What it is

A network service wrapping the free-space optical memory simulator
(`../optical-memory-sim/`): 8 laser-tube diameters × 2 colors × 2 fine
frequencies × 2 polarizations × 3 OAM (orbital angular momentum) modes =
192 simultaneously-live channels, all crossing at the ring's center.
Data pages (4096 bits each) are addressed by
`(tube, color, freq, pol, oam)`.

Every read goes through the channel model — crosstalk plus
phase-jitter/shot/thermal noise, then thresholding. It is a real ring, not a dict. It also speaks the aOs operations natively:
**route** (light/deactivate tube diameters), **query** (associative
lookup, no address bus), **delete** (`kill` = no forensic remnant,
`decohere` = present-but-unreadable), and **glow** (the
machine-only-readability demo).

## Volatility

Ring state lives **in memory only**. A machine restart clears it.
This is the design, not a limitation: the ring models RAM (sustained
interference patterns), not disk. Do not treat it as storage.

## Layout

- `server.py` — Flask service (the whole API)
- `optical_mem.py` — channel model, copied from `../optical-memory-sim/`
- `API.md` — endpoint reference
- `Dockerfile` — reference container build (the live deploy uses the
  Fly Machines API with this code embedded in the machine config)

## Local run

```
pip install numpy flask
python3 server.py          # PORT=8080 by default
curl localhost:8080/health
```

## Deploy (Fly)

App `aos-ring`, org `corey-tasz-761`, region `ewr`, shared 1 CPU /
256 MB RAM, `restart: always`, shared IPv4. The machine config embeds
`server.py` + `optical_mem.py` via the Machines API `files` section and
boots with `pip install numpy flask && python3 /srv/server.py`, so a
restart rebuilds a clean (empty — volatile!) ring from scratch.
