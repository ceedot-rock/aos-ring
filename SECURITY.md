# Security Policy

aos-ring is volatile, in-memory infrastructure for agents. Its security
promises are narrow and physical: a read goes through the documented channel
model, a killed page leaves no remnant, a decohered page is unreadable.

## Reporting a vulnerability

Please do not open a public issue for security problems.

- Use GitHub's private vulnerability reporting on this repository
  (Security tab, "Report a vulnerability")

Include the affected endpoint or file, steps or inputs to reproduce, and what
you expected versus what happened.

You can expect an acknowledgement within 3 business days. We will keep you
updated while we investigate and credit you in the changelog unless you prefer
to stay anonymous.

## In scope

- Read integrity: a read that does not pass through the documented channel
  model, or crosstalk/noise behavior that contradicts `SIM_NOTES.md`
- Delete guarantees: a `kill` that leaves a recoverable remnant, or a
  `decohere` whose content is reconstructable from the response
- Query leakage: associative recall that reveals pages the query should not
  match

## Out of scope

- The volatile-by-design property itself (a restart clears the ring; that is
  the model, not a bug)
- Deployments we do not run
- Social engineering, spam, or denial-of-service against the hosted demo
