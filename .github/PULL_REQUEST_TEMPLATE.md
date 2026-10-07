## What changed

<!-- One or two sentences. -->

## Endpoints touched

<!-- e.g. POST /v1/ring/read, GET /, or "none" -->

## Checks

- [ ] CI (Audited checks) is green
- [ ] Any change to the channel model (`optical_mem.py`) or the read path
      (`server.py`) is documented in `SIM_NOTES.md` / `API.md`
- [ ] `GET /` root route still describes every endpoint
- [ ] Volatile-by-design holds: nothing new is persisted across restarts
