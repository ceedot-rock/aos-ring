# Contributing to aos-ring

Thanks for helping build memory made of light.

## Ground rules

- The Ring is volatile by design. Ring state lives in memory only; a restart
  clears it. Never add persistence to the service — if you need a snapshot
  mechanism, propose it in an issue first.
- Reads go through the physical channel model (`optical_mem.py`): crosstalk,
  phase-jitter/shot/thermal noise, then thresholding. A change that makes
  reads exact where the model says they should be noisy is a behavior change,
  not a fix — discuss it first.
- BER (bit error rate) and associative-recall claims in docs must carry the
  measurement: seed or run conditions, what was written, what came back.

## Quick checks (before you push)

```sh
python3 -c "import optical_mem; import server; print('imports OK')"
PORT=8080 python3 server.py &
curl -sf localhost:8080/ | grep '"service":"aos-ring"'
curl -sf localhost:8080/health | grep '"ok":true'
```

CI boots the server and exercises every endpoint (`/`, `/health`,
`/v1/ring/write|read|query|route|delete`, `/v1/ring/glow`) on every pull
request. It must be green before merge.

## Changing the channel model or the read path

1. Document every changed physical assumption in `SIM_NOTES.md`.
2. Update `API.md` if any response shape changes.
3. Keep `GET /`'s endpoint list in sync — it is the service's self-description.
4. Open a pull request using the template.

## Licensing

aos-ring is dual-licensed (AGPL-3.0-or-later or the Slid Phi Labs Commercial
License). By contributing you agree your contribution may be distributed under
both.
