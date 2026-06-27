# AMD Developer Hackathon: ACT II — Submission Checklist

What's done, and what only you can finish. Kickoff is Jul 6, 2026; submissions
close Jul 11, 2026 (provisional — see item 4 below).

---

## Already done

- **Pushed to GitHub.** All pivot and submission commits are confirmed live on
  `github.com/Levvvinnn/TuneFlow`'s `main` branch — the Qwen→Fireworks rename,
  the AMD/product-first repositioning, and the submission assets (cover image,
  slide deck, draft text, this checklist).
- **`docs/architecture.png` regenerated.** It was still rendering the old
  pre-pivot diagram (Qwen Cloud, Alibaba Cloud) even though the Mermaid source
  (`docs/architecture.mmd`) was already correct. Both available rendering paths
  (local headless Chromium, mermaid.ink's hosted API) are blocked by this
  sandbox's network restrictions, so it's been hand-rebuilt as SVG directly from
  the `.mmd` source's current node/edge/color structure and rendered to PNG —
  no more Qwen/Alibaba content anywhere in the public repo. If you ever edit
  `docs/architecture.mmd` again, the regeneration command in the README still
  applies: `npx @mermaid-js/mermaid-cli -i docs/architecture.mmd -o docs/architecture.png -b "#0f1117" -w 1400 -H 900`.
- Slide deck, cover image, submission draft text, content QA, and the test
  suite — all from earlier in this checklist's history, still good.

---

## 1. Get a real Fireworks AI API key

`.env.example` documents `FIREWORKS_API_KEY` but there's no real key anywhere
in this sandbox (correctly — it shouldn't be). Sign up at
[fireworks.ai](https://fireworks.ai), generate a key, and put it in your local
`.env`. If AMD's hackathon program grants free Fireworks credits at kickoff
(common for these events), watch for that announcement on Jul 6 — it may
replace or supplement a self-funded key.

## 2. Confirm the model slugs once AMD announces its hackathon model catalog

`FIREWORKS_TEXT_MODEL`, `FIREWORKS_OPTIMIZER_MODEL`, and
`FIREWORKS_VISION_MODEL` in `.env.example` are currently placeholders/best
guesses. AMD/Fireworks typically publish an approved model list at kickoff —
swap in the real slugs once that's public.

## 3. Run a full end-to-end smoke test with real LLM calls

This sandbox has **no Docker at all** (confirmed, not just docker-compose
unavailable), so I could not produce a fresh real run with actual Fireworks
responses. Once you have a key and slugs:

```bash
docker-compose up -d
docker-compose run --rm seed
curl -X POST http://localhost:8080/runs -H "Content-Type: application/json" \
  -d '{"mode":"multi_agent","max_iterations":15,"vus":100,"load_duration_seconds":30}'
curl -X POST http://localhost:8080/runs -H "Content-Type: application/json" \
  -d '{"mode":"baseline","max_iterations":15,"vus":100,"load_duration_seconds":30}'
```

This both validates the pivot actually works against the real Fireworks API
(not just unit tests with mocked clients) and gives you fresh, real run data
to reference live during your video recording.

Note: `persistence/store.py` has one uncommitted local change —
`max_iterations` default went from `15` to `10` in `create_run`. It's harmless
either way (callers can always pass an explicit value, as the smoke-test
commands above do), but it's been left uncommitted pending your call on
whether you actually want that default changed. Decide and either commit it
or revert it before this run.

## 4. Record the demo video

Script is ready at `docs/demo_script.md` (shot-by-shot, ~3 minutes). This
needs your screen, your voice, and a live dashboard — not something I can
produce. Do this after step 3 so you have a real run to show, not a stale one.

## 5. Resolve the Demo Application URL question

The submission form asks for a **Demo Application Platform + URL**. TuneFlow
runs locally via `docker-compose up` by design — there's no hosted instance.
Two paths, and this is your call because one costs money / creates new public
infrastructure:

- **Find out if lablab.ai accepts a local-only setup** with the demo video as
  evidence instead of a live URL. Many hackathon platforms do — worth checking
  the submission form itself or asking in the event's Discord/community before
  assuming you need a hosted deployment.
- **Stand up a real hosted demo** (e.g., redeploy via `infra/alibaba/deploy.sh`,
  or a fresh AMD Developer Cloud instance once that's available at kickoff).
  This spends real money/credits — needs your explicit go-ahead, and I have not
  done this without it.

## 6. Sign up / register

- AMD AI Developer Program (likely required to access Fireworks credits or the
  hackathon's AMD platform track).
- Register for "AMD Developer Hackathon: ACT II" on lablab.ai, Unicorn Track.

## 7. Confirm the actual deadline

lablab.ai's event page listed the Event Schedule as "To be announced" as of
this writing. Confirm the exact submission cutoff once it's published —
treat Jul 11, 2026 as provisional until then.

## 8. Decide solo vs. team

Informational only — doesn't block anything, but lablab.ai will ask.

## 9. Review the drafted submission content before pasting anywhere

Everything below is **drafted from already-verified project content** — no
fabricated claims, no invented numbers — but none of it is final until you
read it and decide it's right:

- `docs/submission_draft.md` — project title options, short/long description,
  tag list, paste-ready for the lablab.ai form.
- `docs/cover_image.png` / `.svg` — 1200×630 cover image.
- `docs/TuneFlow_Pitch_Deck.pptx` — 9-slide deck (problem, solution,
  architecture, real comparison data, completeness, AMD platform usage,
  roadmap, closing). Visually QA'd; open it once yourself before uploading.
- `docs/architecture.png` — just regenerated; take a quick look to confirm it
  renders the way you want before it goes in front of judges.

## 10. Submit

Once 1–9 are done: paste the title/descriptions/tags, upload the cover image,
upload or link the video, attach the slide deck, link the public repo, fill in
the demo URL from step 5, and submit.

---

## Lower priority / optional, not required for this submission

- `infra/alibaba/deploy.sh` and `verify_deployment.py` — legacy path from the
  original Alibaba Cloud hackathon target. Not used for the AMD submission,
  kept in the repo for reference only. Ignore unless you specifically want to
  revisit that deployment.
- Personally reading through `agents/judge_agent.py` and `agents/graph.py` if
  you want a refresher on the veto-loop logic before answering judge questions
  about it live.
