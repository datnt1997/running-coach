# Research: VDOT level assessment

Status: R2 and R2b partly done. Items marked **OPEN** need something only the user can supply (the book, a live Strava token).

## R1. Age adjustment (done)

Read from Tables 5.6 to 5.8 (printed pp. 151, 154, 155-159) in `references/daniels.txt` and the PDF page images.

- Table 5.6 thresholds (level 1 to 10), evenly spaced:
  - male: 35.0 + 5.0 x (level - 1), so 35.0 up to 80.0
  - female: 31.4 + 4.4 x (level - 1), so 31.4 up to 71.0
- Table 5.8 (pp. 156-159): ages 18-38 use the Table 5.6 values. From age 39 each year lowers every threshold. Level 1 and level 10 thresholds per age are stored in `app/vdot.py`; levels between are interpolated linearly. Check: the female age-58 column (13.7 to 53.8) gives 35.98 for level 6, printed 36.0.
- Table 5.7 (pp. 154-155): ages 6-17, same method, within about 0.2 VDOT of the printed values (10-year-old girl, level 6: 38.47 against 38.6).
- Ages above 58 are not in the book; we use the age-58 values. Ages below 6 use the age-6 values.
- Book examples (now tests):
  - Woman aged 58: 7:00 on 1600 m is VDOT 40.5, level 7 (Table 5.8); at 18-38 the same VDOT is level 3. The book's text says her young equivalent is 5:04; Table 5.6 prints 5:07 for level 7, so the book is slightly inconsistent.
  - Girl aged 10: 7:18 on 1600 m is VDOT 38.6, level 6, equal to an 18-year-old woman at 5:28 (53.4, level 6).

## R3. Level to label (decided 2026-11-08)

- The UI shows the book's numbered level ("Cap N", Table 5.6) so the runner can check it in the book. The book's text never says which levels belong to which group name (novice, intermediate, good, elite) and the page headers are not aligned to columns, so we do not show group names.
- The planner keeps `fitness_level`, derived internally: levels 1-2 beginner, 3-5 intermediate, 6-10 advanced. Our choice, not the book's.
- Sex not given: male column. Age not given: no age adjustment.

## R2. Strava best efforts

### Verified against Strava's docs (https://developers.strava.com/docs/reference/)

- `GET /activities/{id}` returns `DetailedActivity`. Its `best_efforts` field is "A collection of DetailedSegmentEffort objects". It sits next to `splits_metric`, `splits_standard` and `laps`, which the docs mark "(for runs)".
- `best_efforts` belongs to the **detailed** activity only. The list endpoint (`GET /athlete/activities`) returns `SummaryActivity`, which has no `best_efforts`. Getting efforts for N runs therefore costs N extra detail calls plus the list calls.
- Best efforts are **per activity**: the fastest 5K (etc.) inside that one run. There is no all-time or current-fitness endpoint in the public API.
- Scope: `GET /activities/{id}` and `GET /athlete/activities` need `activity:read`; `activity:read_all` also returns "Only Me" activities. We already request `activity:read_all` (`app/api/strava.py:50`), so no scope change is needed.
- `GET /athlete/activities` params: `before` and `after` (epoch seconds), `page` (default 1), `per_page` (default 30). Sort order is not documented; do not rely on it.
- `SummaryActivity.workout_type` is an integer "The activity's workout type". Runs: 0 default, 1 race, 2 long run, 3 workout. The run mapping comes from older Strava docs (strava.github.io/api/v3/activities); a Strava community thread notes it is not in the current reference and could change. Treat it as a hint, never a requirement. The field is often `null`.
- Rate limits (default, per application, https://developers.strava.com/docs/rate-limits/): overall 200 per 15 min and 2,000 per day; non-upload (all our read calls) 100 per 15 min and 1,000 per day. Headers `X-ReadRateLimit-Limit` and `X-ReadRateLimit-Usage` carry "15-minute, daily" values.
- Our `StravaClient.get_activity` (`app/strava/client.py:53`) currently keeps only `id`, `start_date_local`, `distance`, `moving_time`, `average_heartrate`, `type`. It ignores `best_efforts`, so task 6 must extend it.

### OPEN

- The exact set of distances and `name` strings in `best_efforts` (expected: roughly 400 m through half marathon, but the docs do not list them). Needs a live payload.
- A redacted sample payload (the plan's verify step for R2). Needs one real `GET /activities/{id}` of a run. Ask the user before calling Strava with their token. Fastest path: they run one `curl` themselves with their token and paste the `best_efforts` array (no PII in it beyond activity ids).
- Whether `best_efforts` appears for every run or only runs recorded with GPS or a long enough distance (a 3 km run cannot contain a 5K).

## R2b. Recency window

### Why it matters

Best efforts are per activity, so any estimate must aggregate over a time range. With no cut-off, an old PR dominates and the estimate describes the runner they were, not who they are now. A cut-off also protects against the opposite error: a user returning from a long break who has one old fast race.

### From the book

- **Table 15.1, p. 382** (checked in `references/daniels.txt`, Vietnamese edition, text on pp. 381-383): it gives a multiplier on VDOT for **days of not running** (a break), not for time passing while the user keeps training.
  - Two columns: FVDOT-1 (no cross-training) and FVDOT-2 (the user did aerobic cross-training that uses the legs).
  - Up to 5 days off: multiplier 1.000. Beyond that it falls roughly linearly, then floors at 72 days or more.
  - Compact fit to the table (checked against every row, within about 0.0005):
    - FVDOT-1 = max(0.800, 1 − 0.003 × (days − 5))
    - FVDOT-2 ≈ max(0.900, 1 − 0.0015 × (days − 5))
  - Book examples to use as tests: 42 days off gives 0.889 (FVDOT-1) and 0.944 (FVDOT-2); the book's own text says about 11% loss without cross-training and about half that with it; the maximum loss is about 20% (p. 382).
  - Weight adjustment (Figure 15.2, p. 383): adjusted VDOT = (weight before × VDOT before) / current weight. Book example: 60 kg, VDOT 50, now 63.1 kg gives 47.5. Apply the table multiplier to this adjusted value.
  - Table 15.2 (p. 384-385) is about how much weekly volume to resume with, not about VDOT estimation; out of scope here.
- **What this means for the Strava estimate**: the table only helps when the user is **currently** coming back from a break (days since their last run is 6 or more). It says nothing about a PR from 2 years ago followed by a year of steady running, because fitness has been rebuilt since. So the table does not replace the recency window; it adds a correction on top of it.
- **Which race to use** (pp. 336 and 321; the same sentence appears in two marathon programs; checked in `references/daniels.txt`): when using VDOT to set M, T, I and R paces, use a VDOT from a long race of at least 10K; the longer and the more recent the race, the better.
  - Supports: minimum effort distance of 10K, and preferring recent efforts. It gives **no number of weeks**, so the 12-week window stays our own assumption.
  - Does not apply to level assessment: the same passage tells marathon-program runners to start 6 weeks at a VDOT one unit below their recent race VDOT (or 2 below the marathon estimate), then raise it. That is about setting training paces, not about the user's level. The OCR of that sentence is garbled, so do not code it without re-reading the page.

### Recommended rule (to validate)

1. Fetch runs with `after = now - 6 weeks` using `GET /athlete/activities` (per_page 100, so about 1 to 3 pages).
2. Keep only `sport_type == "Run"` (exclude `TrailRun`, because elevation breaks the pace-to-VDOT model), and only runs long enough to contain at least the 1K effort, with moving time at least 90% of elapsed time to drop paused or stop-and-go runs.
3. Fetch detail only for runs that might contain a useful effort: any run at least 10 km, plus all `workout_type` 1 (race) runs. This caps calls. Budget: 12 weeks x about 4 runs is under 50 detail calls, within the 100-per-15-minutes read limit but not by a wide margin, so cache and page the work.
4. From each run's `best_efforts` take only efforts of 10K or longer (10K, 15K, 20K, half marathon, whichever Strava returns; the list is still **OPEN** until we see a real payload). The book says to use a race of at least 10K, and the longer the better. Cost: a user who has only raced 5K gets `insufficient_data` and falls back to the questions.
5. Compute VDOT per effort and take the **highest** in the window. Training runs understate fitness, so a race effort wins ties and is flagged as `source: race`.
6. Qualify only if at least 3 runs in the window and at least 15 km per week averaged over the last 4 weeks. Otherwise return `insufficient_data` and the chat falls back to the question flow.
7. If days since the user's last run is 6 or more, multiply the chosen VDOT by the Table 15.1 factor for that many days (FVDOT-2 if Strava shows recent non-run aerobic activity such as a ride, else FVDOT-1). This is the only place the table applies; a long-ago effort followed by regular running gets no reduction. Revisit rule 6 once this is in: a long break now lowers VDOT instead of only failing the volume check, so decide whether very long breaks (72 days or more) should still return an estimate or fall back to the questions.
8. Return `{vdot, effort_date, effort_distance, source, window_weeks, days_since_last_run, break_adjustment}`. The UI shows the date and asks the user to confirm or override. Never silently apply it.

Why 6 weeks (user's decision, 2026-11-08): the book says that a runner who has trained at the same intensity for 4 to 6 weeks without added stress can raise intensity a little even with no race to confirm it (p. 44; checked in `references/daniels.txt`). So the book treats 4 to 6 weeks as the time over which fitness changes enough to matter. We use the upper end, 6 weeks, as the window. **Limit of this source**: the passage is about when to raise training intensity, not about how old a race result may be, so 6 weeks is an inference from it, not a stated rule. Keep it as a tunable constant (`STRAVA_WINDOW_WEEKS`, default 6).

### Web research on the period (2026-11-08)

No source found, official or academic, states a number of weeks for how old a result may be when calculating VDOT.

- **Daniels' book** (read by the user): no period. Only "the longer and more recent the race, the better", and Table 15.1 for breaks.
- **Official V.O2 site (Daniels' app), support FAQ** (https://support.vdoto2.com/?p=8275, undated): "Ideally, every athlete is using a recent race result that accurately represents their current fitness." No number. If there is no recent race, it says to estimate a finish time, or enter typical easy pace.
- **Official V.O2 support post** (https://support.vdoto2.com/?p=2769, 14 Aug 2019): "attempt a race or time trial to ensure your VDOT score accurately represents your current fitness." No number.
- **Third-party sites** (not from Daniels; none cite his book). I opened four pages on 2026-11-08:
  - https://sport-calculator.com/blog/jack-daniels-running-table (author is a software developer): "Enter a recent race time (within 4-8 weeks)" and "Update VDOT every 4-8 weeks as fitness changes". **This is the only page where I confirmed the 4 to 8 week figure.**
  - https://en.run-motion.com/vdot-calculator-jack-daniels/, https://www.brenoamelo.com/blog/jack-daniels-vdot-explained, https://runculture.com/tools/vdot-calculator/: all say "recent" with no number. The first gives "six months ago" only as an example of a result that may no longer represent current fitness, not as a cutoff.
  - Earlier search summaries also mentioned "within 6 weeks" and "best race from the last 2 to 3 months" from other sites. I did **not** open those pages, so they are unverified and not relied on.
- **Detraining research** (Mujika & Padilla, *Sports Med* 2000, Parts I and II; a 2024 systematic review, doi 10.3389/fphys.2023.1334766): fitness loss is real and starts within weeks of stopping, but the studies measure VO2max after complete cessation, not how long a race result stays valid. A secondary summary of Coyle et al. (1984) reports about 7% VO2max loss at 21 days and 16% at 56 days; Table 15.1 shows a similar order of loss (0.952 to 0.976 at 21 days; 0.847 to 0.923 at 56 days). This supports using Table 15.1 for breaks. It does not set a window for continued training.

**What this means for the design**
- Say plainly in the spec that the 6-week window is inferred from the 4 to 6 week passage, not a rule Daniels states for race recency.
- The only confirmed outside figure is 4 to 8 weeks from one non-authoritative site; 12 weeks is looser. The tradeoff: a shorter window is more current but returns `insufficient_data` more often, since few casual runners race 10K+ every two months.
- Default window is 6 weeks (this supersedes the earlier 12-week draft). Always show the effort's date, and let the user confirm or override. Expect more `insufficient_data` results, since few casual runners record a 10K+ effort every 6 weeks; the question flow is the fallback. Revisit with real data once task 6 runs.

### Verification: hand-built histories (expected outcomes under the rule)

| History | Data | Expected result |
|---|---|---|
| Steady runner | 4 runs per week for 6 weeks, about 35 km per week, one 10K parkrun-style effort 3 weeks ago | `qualified`; VDOT from the best 5K/10K effort in the window; `effort_date` about 3 weeks ago |
| Returning after a break | Fast 10K race 2 years ago; nothing for 6 months; 3 easy runs of 3 to 4 km in the last 2 weeks | `insufficient_data` (fewer than 3 qualifying runs, under 15 km per week, no 10K+ effort in window); the old race is ignored |
| One old PR, low volume | Half-marathon PR 14 months ago; last 6 weeks: 2 runs per week, 5 km each, easy | `insufficient_data` (no 10K+ effort in the window); the PR is ignored |

These become the fixtures for task 6's tests ("enough data, too little data, no connection").

### Open design question for the user

Suggestion the user confirms, or value applied automatically? Recommendation: confirm. A good window can still be wrong after injury or illness, and the user can see the date and distance of the effort used.

## Sources

- https://developers.strava.com/docs/reference/
- https://developers.strava.com/docs/rate-limits/
- https://strava.github.io/api/v3/activities/ (run `workout_type` values)
