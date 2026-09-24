# Contributing

1. Fork, then branch from `main` (`feat/...`, `fix/...`).
2. Keep `pytest` green — CI runs it on every push.
3. Never commit tokens, `.env`, or `data/` — config comes from `.env.example`.
4. The default is `DRY_RUN=1`: new enforcement behavior must be proven in
   dry-run cases before it can flip enforcement.
5. Open a pull request; describe what a reviewer can actually verify.
