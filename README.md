# aos-ring

[![Audited checks](https://github.com/ceedot-rock/aos-ring/actions/workflows/audited-checks.yml/badge.svg)](https://github.com/ceedot-rock/aos-ring/actions/workflows/audited-checks.yml)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)

## What the Ring is

The Ring is memory made of light. Instead of writing data onto a disk or a chip, it holds data as sustained patterns of laser beams interfering with each other — the angle of a beam decides where a piece of data lives, and the color of the beam decides which channel it belongs to. Different colors don't interfere with each other, so many channels can share the same space at once.

Here is why that matters. Ordinary storage is a thing — a magnetized spot, a trapped charge — and things can be forensically recovered after you delete them. The Ring's storage is a pattern, sustained moment to moment by the beams. Kill the beams and the pattern dissolves. There is nothing left to recover, because there was never a thing there — only light, held in formation.

Reading is exact: write data in, read the identical bits back out. And the Ring can do something disks can't — associative recall. Give it a partial or damaged query and it finds the closest stored pattern, the way you recognize a half-remembered face. In testing, a query with 20% of its bits flipped still returned the right address.

It is volatile by nature, like RAM rather than a hard drive: restart the service and the patterns are gone. That is a feature, not a bug — memory that truly forgets.

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

## The vault

The ring is a **gated vault**: every `/v1/` route requires the vault
password (`X-Vault-Password` header, or `Authorization: Bearer`),
set server-side via `AOS_VAULT_PASSWORD`. No password configured →
the vault fails closed (503). `/health` and `/` stay open; they expose
metadata only, never ring contents.

## Volatility

Default mode: ring state lives **in memory only** — a restart clears
it; the ring models RAM (sustained interference patterns), not disk.
With `AOS_DATA_DIR` set, a persistence layer snapshots every mutation
to disk (atomic write-through) and restores it at boot. The Docker
deployment (below) runs in this persistent mode.

## Layout

- `server.py` — Flask service (the whole API)
- `optical_mem.py` — channel model, copied from `../optical-memory-sim/`
- `API.md` — endpoint reference
- `Dockerfile` — reference container build (the live deploy uses the
  Fly Machines API with this code embedded in the machine config)

## Local run

```
pip install numpy flask
AOS_VAULT_PASSWORD=<password> python3 server.py   # PORT=8080 by default
curl localhost:8080/health
curl -H "X-Vault-Password: <password>" -X POST localhost:8080/v1/ring/read ...
```

## Run (Docker, persistent + gated)

```
cp .env.example .env       # set AOS_VAULT_PASSWORD in .env
docker compose up -d       # state persists in the aos-ring-data volume
```

## Deploy (Fly)

App `aos-ring`, org `corey-tasz-761`, region `ewr`, shared 1 CPU /
256 MB RAM, `restart: always`, shared IPv4. Deploys from this repo via
`fly.toml` + `Dockerfile` (`fly deploy`), so a restart rebuilds a clean
(empty — volatile!) ring from scratch.
