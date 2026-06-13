# Running Coach AI — Architecture v2.0
# (Hybrid: Time-Based Tiers + Entity State Machine)

> **What changed from v1:** Replaced the static JSONB profile blob with an Entity State Machine
> borrowed from Personal_AI_OS. Added Differential Prompting, memory lifecycle management,
> a Sports Science Module (Node.js-only math), and a raw data lake. The 4-tier structure
> is preserved but each tier is now smarter.

---

## The Core Problem (Restated)

Gemini forgets context when it hits the context window. But there are actually **two sub-problems**:

1. **Volume problem** — months of raw training logs exceed the context window
2. **Staleness problem** — even when data fits in context, old facts (healed injuries, abandoned goals) stay in the prompt and poison the agent's advice

V1 solved problem 1. V2 solves both.

---

## Design Philosophy

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRINCIPLE 1: "Right context" not "all context"                     │
│  Only inject what is currently true and currently relevant.         │
│                                                                     │
│  PRINCIPLE 2: "Node.js does math, Gemini writes poetry"             │
│  ACWR, HR zones, cardiac drift → pure JS functions, never LLM.     │
│  Coaching narrative, advice, motivation → Gemini.                   │
│                                                                     │
│  PRINCIPLE 3: Facts have a lifecycle                                │
│  active (healed injury) → inactive → archived (past query only)    │
│                                                                     │
│  PRINCIPLE 4: Memory grows by change, not by time                   │
│  Differential prompting ensures we only save what is NEW or         │
│  DIFFERENT from the current state. Duplicates never enter the DB.  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The 4-Tier Memory Model

```
Every chat request assembles context from 4 tiers:

┌────────────────────────────────────────────────────────────────────────┐
│                         GEMINI PROMPT                                  │
│                                                                        │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐   │
│  │  TIER 2              │  │  TIER 3                              │   │
│  │  Active Facts        │  │  Temporal Context                   │   │
│  │  (Entity State       │  │                                      │   │
│  │   Machine)           │  │  ├─ Last 4 weekly summaries         │   │
│  │                      │  │  └─ Last 5 training sessions        │   │
│  │  - Current goal      │  │     (with computed metrics)         │   │
│  │  - Active injuries   │  └──────────────────────────────────────┘   │
│  │  - Fitness level     │                                              │
│  │  - Shoe preference   │  ┌──────────────────────────────────────┐   │
│  │  - ...               │  │  TIER 4 (on-demand)                  │   │
│  │                      │  │  Semantic Search via pgvector        │   │
│  │  Only ACTIVE facts.  │  │  + Archived facts via Tool Use       │   │
│  │  Latest state only.  │  └──────────────────────────────────────┘   │
│  └──────────────────────┘                                              │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  TIER 1: Working Memory — last 20 messages (sliding window)      │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

---

### Tier 1 — Working Memory (Current Session)
**What:** The last 20 messages from the current conversation.  
**How:** Sliding window — oldest messages fall off automatically.  
**Why 20:** Enough for conversational coherence within one session, cheap in tokens.

---

### Tier 2 — Active Facts (Entity State Machine)
**What:** Everything currently true about this athlete — goals, injuries, fitness level, preferences, psychology.  
**How:** Key-value rows in `athlete_facts` table. Context injection queries `status = 'active'`, deduplicated by `DISTINCT ON (category)` ordered by `created_at DESC` — so only the latest state of each fact is shown to Gemini.  
**Updated by:** Memory Extraction Agent (runs after Weekly Reflection cron).

This replaces the JSONB blob from v1. The critical difference:

```
V1 (JSONB blob — broken):
injury_history: ["IT band 2024-Q3", "achilles 2025-Q1"]
                                     ↑ this healed but stays in prompt forever

V2 (Entity State Machine — correct):
category: "achilles_injury", fact: "Active, avoid tempo runs",   status: active
category: "achilles_injury", fact: "Fully recovered 2025-Q3",   status: inactive
                                                                  ↑ archived, never injected
```

**Domain partitioning** (fixed, prevents category explosion):

| Domain | Examples |
|---|---|
| `sports` | race goal, weekly mileage, training phase, long run day |
| `health` | active injuries, recovery status, sleep quality |
| `physiological` | max HR, lactate threshold pace, VO2 max estimate |
| `nutrition` | pre-run fueling, race day nutrition plan |
| `psychology` | motivation level, handles hard workouts well, race anxiety |
| `gear` | shoe model, GPS watch model, preferences |

**Injected context example** (~400 tokens):
```
[ACTIVE FACTS — as of 2026-05-01]
sports.race_goal: "Sub-3:30 at HCMC Marathon 2026-12-07"
sports.training_phase: "Base Phase, Week 6 of 12"
sports.current_weekly_mileage: "72km"
health.injury: "None active"
health.recovery: "HRV trending low — monitor this week"
physiological.threshold_pace: "4:35/km"
physiological.easy_pace_range: "5:30–6:10/km"
psychology.notes: "Responds well to polarized training. Needs encouragement on recovery weeks."
gear.shoes: "Asics Nimbus 26 (primary), Adidas Adizero (race)"
```

---

### Tier 3 — Temporal Context (Mid-Term + Short-Term)
**What:** Two sub-layers: narrative weekly summaries (last 4 weeks) + recent sessions (last 5 runs).  
**How:** Weekly summaries from `training_block_summaries` table; sessions from `training_sessions` with pre-computed metrics from the Sports Science Module.

**Weekly summary example** (~600 tokens for 4 weeks):
```
[WEEK 2026-04-28] Build Phase Week 1 — Total 68km
Key session: 28km long run @ 5:50/km, cardiac drift 6.2% (normal), avg HR 145bpm
Tempo: 3x2km @ 4:30/km ✓ HR zone 4 confirmed
ACWR: 0.94 (green zone)
Flag: Left knee mild tightness reported Wed, resolved by Fri
Readiness: Good — entering Build Phase on schedule

[WEEK 2026-04-21] Base Phase Week 6 — Total 72km
...
```

**Recent sessions example** (~400 tokens for 5 sessions):
```
[2026-04-30 Thu] Easy Run — 12km @ 5:52/km, HR 138bpm, cadence 174spm
  Cardiac drift: 3.1% | ACWR contribution: 12km | Zone: Z2 ✓

[2026-04-28 Tue] Tempo — 14km total, 8km @ 4:32/km, HR 168bpm, cadence 182spm
  Aerobic decoupling: 4.8% | HR Zone 4 ✓ | Pace on target
...
```

Note: all numeric analysis (cardiac drift, ACWR, zone) is pre-computed by the Sports Science Module before being passed to Gemini.

---

### Tier 4 — Historical Memory (On-Demand)
**What:** Two retrieval mechanisms for going further back.

**4a — Semantic Search (pgvector):** Triggered on every chat request. Embeds the user's message and finds the 3 most similar past sessions, summaries, or messages. Good for questions like "how was my cadence trending last month?"

**4b — Archived Facts (Tool Use):** Gemini can call `search_historical_facts(topic)` when it detects the user is asking about the past. Queries `athlete_facts` rows with `status = 'inactive'` or `archived`. Good for "how did I handle that knee injury in 2024?"

**Size target:** Top 3 semantic results + archived facts on demand, ~500 tokens combined.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — EDGE & TRIGGERS                                              │
│                                                                         │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────────────┐  │
│  │  Web App     │  │  Telegram Bot │  │  Cron Jobs                  │  │
│  │  (Next.js)   │  │  (Telegraf)   │  │  ├─ Sun 23:00 weekly-summary│  │
│  └──────┬───────┘  └───────┬───────┘  │  ├─ Sun 23:30 memory-extract│  │
│         │                  │          │  ├─ 1st of month memory-decay│  │
│  ┌──────────────────────┐  │          │  └─ Mon 07:00 resting-hr-ask │  │
│  │  Webhooks            │  │          └─────────────────────────────┘  │
│  │  └─ POST /sync/strava│  │                                           │
│  └──────┬───────────────┘  │                                           │
└─────────┼──────────────────┼─────────────────────────────────────────┘
          │                  │
          ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — API (Node.js / Express)                                      │
│                                                                         │
│  POST /chat            POST /sync/strava      POST /api/goals          │
│  GET  /api/goals/:id   PATCH /api/goals/:id   GET  /athlete/:id        │
│  GET  /sessions        GET  /plan                                       │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│  Memory Service  │  │  Gemini Service  │  │  Sync Service            │
│                  │  │                  │  │                          │
│  readActiveFacts │  │  buildPrompt()   │  │  stravaWebhook()         │
│  readSummaries   │  │  callGemini()    │  │  stravaStreams()          │
│  readSessions    │  │  streamReply()   │  │  normalizeActivity()     │
│  semanticSearch  │  │  callTool()      │  │  → sportsScience.*       │
│  writeFact()     │  │                  │  │  → weather.service.*     │
│  archiveFact()   │  └──────────────────┘  │  → datalake.save()       │
│                  │                        └──────────────────────────┘
│  Goal Service    │
│  processGoal()   │
│  archiveGoal()   │
│  updatePhase()   │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — SPORTS SCIENCE MODULE (Pure Node.js — zero LLM)           │
│                                                                      │
│  acwr(acute, chronic)          cardiacDrift(firstHalf, secondHalf)   │
│  hrZones(maxHR)                pacePerKm(distanceM, durationS)       │
│  aerobicDecoupling(hrFirst,    strideLength(cadence, pace)           │
│    hrSecond, paceFirst,        trainingLoad(hr, duration, intensity) │
│    paceSecond)                 weeklyVolumeChange(thisWeek, lastWeek)│
└──────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — STORAGE                                                   │
│                                                                      │
│  PostgreSQL + pgvector                   data/streams/ (Data Lake)  │
│  ├─ athletes                             ├─ strava_{id}.json        │
│  ├─ athlete_facts  (State Machine)       └─ (raw GPS/HR time-series,│
│  ├─ training_goals (goal + phases)           per-second, not in DB) │
│  ├─ training_sessions (computed)                                    │
│  ├─ training_block_summaries                                        │
│  ├─ messages                                                        │
│  └─ memories_semantic (vector)                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

```sql
-- ─────────────────────────────────────────────────
-- Core identity
-- ─────────────────────────────────────────────────
CREATE TABLE athletes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_id TEXT UNIQUE,
  email       TEXT UNIQUE,
  name        TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────
-- Tier 2: Entity State Machine
-- Replaces the JSONB blob from v1.
-- One row per state change per fact.
-- Query always uses DISTINCT ON (category) ORDER BY created_at DESC
-- to get latest state only.
-- ─────────────────────────────────────────────────
CREATE TABLE athlete_facts (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id   UUID REFERENCES athletes(id) ON DELETE CASCADE,
  domain       TEXT NOT NULL,     -- 'sports' | 'health' | 'physiological' | 'nutrition' | 'psychology' | 'gear'
  category     TEXT NOT NULL,     -- snake_case entity name, LLM-generated but domain-constrained
  fact         TEXT NOT NULL,     -- the current truth about this entity
  status       TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'inactive' | 'archived'
  source       TEXT NOT NULL DEFAULT 'chat',    -- 'chat' | 'manual' | 'sync'
  created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_athlete_facts_lookup
  ON athlete_facts (athlete_id, domain, status, created_at DESC);

-- Active facts query (used in every prompt):
-- SELECT DISTINCT ON (category) domain, category, fact
-- FROM athlete_facts
-- WHERE athlete_id = $1 AND status = 'active'
-- ORDER BY category, created_at DESC;

-- ─────────────────────────────────────────────────
-- Training sessions — computed metrics stored, raw data in Data Lake
-- ─────────────────────────────────────────────────
CREATE TABLE training_sessions (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id          UUID REFERENCES athletes(id) ON DELETE CASCADE,
  source              TEXT NOT NULL,           -- 'strava' | 'manual'
  external_id         TEXT,
  session_type        TEXT NOT NULL,           -- 'easy' | 'tempo' | 'long_run' | 'interval' | 'race' | 'rest'
  date                DATE NOT NULL,
  distance_m          INTEGER,
  duration_s          INTEGER,
  avg_pace_s_km       INTEGER,
  avg_hr              INTEGER,
  avg_cadence           INTEGER,
  avg_stride_m          NUMERIC(4,2),
  elevation_m           INTEGER,
  -- Weather from OpenWeatherMap (historical, at run location + start time)
  -- Device-reported temperature from Strava is unreliable — we use weather API instead
  weather_temp_celsius  NUMERIC(4,1),
  weather_humidity_pct  INTEGER,
  -- Pre-computed by Sports Science Module (never delegated to LLM)
  -- ACWR uses TRIMP not km — Banister 1991 / Gabbett 2016
  trimp                    NUMERIC(8,2),      -- training impulse for this session
  acwr_at_session          NUMERIC(5,3),      -- TRIMP-based ACWR at time of session
  cardiac_drift_pct        NUMERIC(5,2),      -- % HR drift first→second half
  cardiac_drift_status     TEXT,              -- 'normal' | 'elevated' | 'high' (temp-adjusted)
  aerobic_decoupling_pct   NUMERIC(5,2),      -- % HR/pace ratio change first→second half
  hr_zone                  INTEGER,           -- dominant zone 1–5
  session_spike_flag       BOOLEAN DEFAULT FALSE, -- true if distance > recentMaxLongRun * 1.10
  spike_risk_increase_pct  INTEGER,           -- estimated % injury risk increase from spike
  datalake_path            TEXT,              -- path to raw JSON time-series file
  created_at               TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(source, external_id)
);

-- ─────────────────────────────────────────────────
-- Tier 3 (mid-term): Weekly coaching narrative summaries
-- ─────────────────────────────────────────────────
CREATE TABLE training_block_summaries (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id          UUID REFERENCES athletes(id) ON DELETE CASCADE,
  week_start          DATE NOT NULL,
  summary             TEXT NOT NULL,       -- coaching narrative, ~300 words
  total_km            NUMERIC(6,1),
  weekly_trimp        NUMERIC(8,2),        -- total TRIMP for week (used for ACWR)
  acwr                NUMERIC(5,3),        -- TRIMP-based ACWR for this week
  zone_distribution   JSONB,               -- { z1: 45, z2: 37, z3: 5, z4: 10, z5: 3 } (% of time)
  low_intensity_pct   INTEGER,             -- z1+z2 combined (target ≥ 80% for polarized)
  high_intensity_pct  INTEGER,             -- z4+z5 combined (target ≥ 15% for polarized)
  is_polarized        BOOLEAN,             -- true if 80/20 distribution met
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(athlete_id, week_start)
);

-- ─────────────────────────────────────────────────
-- Tier 1: Conversation messages
-- ─────────────────────────────────────────────────
CREATE TABLE messages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id  UUID REFERENCES athletes(id) ON DELETE CASCADE,
  role        TEXT NOT NULL,     -- 'user' | 'assistant'
  content     TEXT NOT NULL,
  session_id  TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_session ON messages (athlete_id, session_id, created_at DESC);

-- ─────────────────────────────────────────────────
-- Tier 4: Semantic / vector memory
-- ─────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE memories_semantic (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id  UUID REFERENCES athletes(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,     -- 'session' | 'summary' | 'message' | 'fact'
  source_id   UUID,
  content     TEXT NOT NULL,
  embedding   vector(768),       -- Gemini text-embedding-004
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON memories_semantic
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## Sports Science Module

Pure Node.js. No async, no LLM calls. Every function is deterministic and unit-testable.
All thresholds are sourced from `SPORTS_SCIENCE_RESEARCH.md`.

Functions are grouped into **Tier A** (computed every session) and **Tier B** (estimated every 4–6 weeks).
The final `formatSessionContext()` function produces **Tier C** — the pre-digested string passed to Gemini.

```javascript
// src/science/sports-science.js

// ─────────────────────────────────────────────────────────────
// TIER A — Computed on every session sync
// ─────────────────────────────────────────────────────────────

// TRIMP (Training Impulse) — Banister 1991
// The correct unit for ACWR. Integrates duration × intensity via HR reserve.
// k = 0.64 (male), 0.86 (female) — accounts for disproportionate stress at high intensity.
export const trimp = (durationMin, avgHR, restingHR, maxHR, gender = 'male') => {
  const hrRatio = (avgHR - restingHR) / (maxHR - restingHR);
  const k = gender === 'male' ? 0.64 : 0.86;
  return durationMin * hrRatio * (0.64 * Math.exp(k * hrRatio));
};

// ACWR using TRIMP — Gabbett 2016 (BJSM, PMID 26758673)
// Uses TRIMP not km: a 15km easy run ≠ a 15km tempo run in physiological stress.
// acute = sum of TRIMP over last 7 days
// chronic = sum of TRIMP over last 28 days divided by 4 (to get weekly average)
export const acwr = (trimp7Days, trimp28Days) =>
  trimp28Days === 0 ? 1.0 : trimp7Days / (trimp28Days / 4);

// Thresholds: < 0.8 undertraining | 0.8–1.3 optimal | 1.3–1.5 caution | > 1.5 danger (2.15× injury hazard)
export const acwrStatus = (ratio) => {
  if (ratio < 0.8)  return { zone: 'undertraining', color: 'blue'   };
  if (ratio <= 1.3) return { zone: 'optimal',       color: 'green'  };
  if (ratio <= 1.5) return { zone: 'caution',        color: 'yellow' };
  return              { zone: 'danger',         color: 'red'    };
};

// Single-session spike — stronger injury predictor than weekly ACWR alone
// Research: +10% over recent max long run = +64% injury risk (PMC 11986186, 2025)
export const singleSessionSpike = (currentDistanceM, recentMaxLongRunM) => {
  if (!recentMaxLongRunM || recentMaxLongRunM === 0) return { spike: false, ratio: 1.0, riskIncreasePct: 0 };
  const ratio = currentDistanceM / recentMaxLongRunM;
  return {
    ratio:            Math.round(ratio * 100) / 100,
    spike:            ratio > 1.10,
    riskIncreasePct:  ratio > 1.10 ? Math.round((ratio - 1) * 640) : 0,
  };
};

// HR Zones — standard 5-zone model based on % HRmax
// Seiler & Kjerland (2006): target 80% training time in Z1-Z2, 20% in Z4-Z5
export const hrZones = (maxHR) => ({
  z1: { min: 0,                        max: Math.round(maxHR * 0.60) },
  z2: { min: Math.round(maxHR * 0.60), max: Math.round(maxHR * 0.70) },
  z3: { min: Math.round(maxHR * 0.70), max: Math.round(maxHR * 0.80) },
  z4: { min: Math.round(maxHR * 0.80), max: Math.round(maxHR * 0.90) },
  z5: { min: Math.round(maxHR * 0.90), max: maxHR                    },
});

export const dominantHrZone = (avgHR, maxHR) => {
  const zones = hrZones(maxHR);
  const entry = Object.entries(zones).find(([, z]) => avgHR <= z.max);
  return entry ? parseInt(entry[0].replace('z', '')) : 5;
};

// Cardiac drift — upward HR drift at constant pace (fatigue/heat/dehydration signal)
// Returns raw % drift; use cardiacDriftStatus() to interpret with temperature context.
export const cardiacDrift = (firstHalfAvgHR, secondHalfAvgHR) =>
  ((secondHalfAvgHR - firstHalfAvgHR) / firstHalfAvgHR) * 100;

// Temperature-adjusted drift threshold — research: PMC 5079215, Wiley EP090969
// Friel's 5% threshold assumes cool conditions. At 30°C+ tropical racing, 18% is normal.
export const cardiacDriftThreshold = (tempCelsius) => {
  if (tempCelsius < 20) return 5;
  if (tempCelsius < 25) return 8;
  if (tempCelsius < 30) return 12;
  return 18;
};

export const cardiacDriftStatus = (driftPct, tempCelsius) => {
  const threshold = cardiacDriftThreshold(tempCelsius);
  if (driftPct <= threshold)        return { status: 'normal',   threshold };
  if (driftPct <= threshold * 1.5)  return { status: 'elevated', threshold };
  return                                   { status: 'high',     threshold };
};

// Aerobic decoupling — Joe Friel (TrainingPeaks, 2009)
// HR/pace ratio change from first half to second half of a long run.
// < 5% (cool) = Z2 confirmed. Threshold adjusts with temperature.
export const aerobicDecoupling = (hr1, pace1, hr2, pace2) => {
  const ratio1 = hr1 / pace1;
  const ratio2 = hr2 / pace2;
  return ((ratio2 - ratio1) / ratio1) * 100;
};

export const aerobicDecouplingStatus = (decouplingPct, tempCelsius) => {
  const heatAdjustedThreshold = cardiacDriftThreshold(tempCelsius) * 0.8;
  if (decouplingPct <= 5)                        return 'excellent — Z2 confirmed';
  if (decouplingPct <= heatAdjustedThreshold)    return 'acceptable — near aerobic threshold';
  return 'above threshold — pace too hard or aerobic base underdeveloped';
};

// Pace and stride
export const pacePerKm = (distanceM, durationS) =>
  Math.round(durationS / (distanceM / 1000));

export const strideLength = (cadenceSpm, paceSecPerKm) =>
  (1000 / paceSecPerKm) / (cadenceSpm / 60);

export const formatPace = (secondsPerKm) => {
  const mins = Math.floor(secondsPerKm / 60);
  const secs = Math.round(secondsPerKm % 60);
  return `${mins}:${String(secs).padStart(2, '0')}/km`;
};

// ─────────────────────────────────────────────────────────────
// TIER B — Estimated periodically (every 4–6 weeks)
// ─────────────────────────────────────────────────────────────

// Weekly zone distribution — checks 80/20 polarized compliance
// Input: array of training_sessions rows from last 7 days (each must have avg_hr, duration_s)
// Seiler & Kjerland (2006): 80% Z1-Z2 + 20% Z4-Z5 = polarized target
export const weeklyZoneDistribution = (sessions, maxHR) => {
  const totals = { z1: 0, z2: 0, z3: 0, z4: 0, z5: 0 };
  let totalDuration = 0;

  for (const s of sessions) {
    if (!s.avg_hr || !s.duration_s) continue;
    const zone = dominantHrZone(s.avg_hr, maxHR);
    totals[`z${zone}`] += s.duration_s;
    totalDuration += s.duration_s;
  }

  if (totalDuration === 0) return null;

  const pct = {};
  for (const [k, v] of Object.entries(totals)) {
    pct[k] = Math.round((v / totalDuration) * 100);
  }

  const lowIntensityPct  = pct.z1 + pct.z2;
  const highIntensityPct = pct.z4 + pct.z5;

  return {
    distribution:      pct,
    lowIntensityPct,
    highIntensityPct,
    isPolarized:       lowIntensityPct >= 75 && highIntensityPct >= 15,
    label:             `${lowIntensityPct}% Z1-Z2, ${highIntensityPct}% Z4-Z5`,
  };
};

// Longest run in a rolling window — used for single-session spike detection
export const recentMaxLongRun = (sessions, weeksBack = 6) => {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - weeksBack * 7);
  return sessions
    .filter(s => new Date(s.date) >= cutoff)
    .reduce((max, s) => Math.max(max, s.distance_m || 0), 0);
};

// LT pace from 30-min time trial — no lab required
// Average pace held for 30 min all-out effort ≈ Lactate Threshold pace (TrainingPeaks)
// Input: trialPaceSecPerKm (measured from time trial)
export const ltPaceFromTimeTrial = (trialPaceSecPerKm) => trialPaceSecPerKm;

// VO2max estimate — Jack Daniels & Gilbert (1979) VDOT formula
// Input: best race result (paceSecPerKm + distanceKm)
// Daniels VDOT tables: https://runsmartproject.com/calculator/
export const vo2maxFromRacePace = (paceSecPerKm, distanceKm) => {
  const velocityMMin = (1000 / paceSecPerKm) * 60;
  // Percent of VO2max sustained at given pace (Daniels & Gilbert, 1979)
  const timeMin = (paceSecPerKm * distanceKm) / 60;
  const percentMax = 0.8 + 0.1894393 * Math.exp(-0.012778 * timeMin)
                         + 0.2989558 * Math.exp(-0.1932605 * timeMin);
  const vo2AtPace = -4.60 + 0.182258 * velocityMMin + 0.000104 * velocityMMin ** 2;
  return Math.round((vo2AtPace / percentMax) * 10) / 10;
};

// ─────────────────────────────────────────────────────────────
// TIER C — Formatted context string passed to Gemini
// Gemini receives pre-digested labels, never raw numbers to compute.
// ─────────────────────────────────────────────────────────────

export const formatSessionContext = ({
  acwrRatio,
  sessionTrimp,
  driftPct,
  tempCelsius,
  decouplingPct,
  dominantZone,
  spikeCheck,
  ltPaceSecPerKm,
  weeklyDist,
}) => {
  const status  = acwrStatus(acwrRatio);
  const dStatus = cardiacDriftStatus(driftPct, tempCelsius);
  const dThresh = cardiacDriftThreshold(tempCelsius);
  const dLabel  = aerobicDecouplingStatus(decouplingPct, tempCelsius);

  const lines = [
    `acwrStatus: "${acwrRatio.toFixed(2)} (${status.zone})"`,
    `sessionLoad: "${Math.round(sessionTrimp)} TRIMP"`,
    `drift: "${driftPct.toFixed(1)}% — ${dStatus.status} at ${tempCelsius}°C (threshold ${dThresh}%)"`,
    `decoupling: "${decouplingPct.toFixed(1)}% — ${dLabel}"`,
    `sessionZone: "Zone ${dominantZone}"`,
    ltPaceSecPerKm
      ? `ltPace: "${formatPace(ltPaceSecPerKm)}"`
      : null,
    spikeCheck.spike
      ? `spikeFlag: "⚠ ${((spikeCheck.ratio - 1) * 100).toFixed(0)}% over recent max (~${spikeCheck.riskIncreasePct}% elevated injury risk)"`
      : `spikeFlag: "none"`,
    weeklyDist
      ? `weeklyDistribution: "${weeklyDist.label} (${weeklyDist.isPolarized ? 'polarized ✓' : 'not polarized — review Z3 dominance'})"`
      : null,
  ];

  return lines.filter(Boolean).join('\n');
};
```

**Rule:** If a calculation has a formula, it lives here. Gemini receives the `formatSessionContext()` output, never raw numbers to compute.

**Example Tier C output passed to Gemini:**
```
acwrStatus: "0.94 (optimal)"
sessionLoad: "68 TRIMP"
drift: "7.2% — normal at 28°C (threshold 12%)"
decoupling: "4.8% — excellent — Z2 confirmed"
sessionZone: "Zone 2"
ltPace: "4:52/km"
spikeFlag: "none"
weeklyDistribution: "82% Z1-Z2, 18% Z4-Z5 (polarized ✓)"
```

---

## Differential Prompting (Memory Extraction)

This prevents memory bloat. Runs every Sunday at 23:30 (30 min after weekly summary).

```javascript
// src/cron/memory-extraction.js

async function extractMemoriesFromWeek(athleteId) {
  // Step 1: Load what we already know
  const existingFacts = await db.query(`
    SELECT DISTINCT ON (category) domain, category, fact
    FROM athlete_facts
    WHERE athlete_id = $1 AND status = 'active'
    ORDER BY category, created_at DESC
  `, [athleteId]);

  // Step 2: Load this week's conversation history
  const recentMessages = await getMessagesFromLastNDays(athleteId, 7);
  const weeklySummary = await getLatestWeeklySummary(athleteId);

  // Step 3: Differential extraction prompt
  const prompt = `
You are a memory manager for a marathon coach AI.
Your job: extract ONLY new or changed facts from this week.
Return [] if nothing changed.

[WHAT YOU ALREADY KNOW — do not re-extract these unless they changed]
${existingFacts.rows.map(f => `${f.domain}.${f.category}: "${f.fact}"`).join('\n')}

[THIS WEEK'S ACTIVITY SUMMARY]
${weeklySummary}

[THIS WEEK'S CONVERSATIONS]
${recentMessages.map(m => `${m.role}: ${m.content}`).join('\n')}

Return a JSON array. Each item must have: domain, category, fact, status.
Use status "active" for current truths.
Use status "inactive" for facts that were active but are now resolved/false
  (e.g., an injury that healed — set the old category to inactive with new fact explaining resolution).
Return [] if there is nothing new or changed.

Domains: sports | health | physiological | nutrition | psychology | gear
Categories: snake_case, descriptive (e.g. "achilles_injury", "race_goal", "threshold_pace")
`;

  const extracted = await callGemini(prompt, { responseFormat: 'json' });

  // Step 4: Insert only what changed
  for (const item of extracted) {
    await db.query(`
      INSERT INTO athlete_facts (athlete_id, domain, category, fact, status, source)
      VALUES ($1, $2, $3, $4, $5, 'chat')
    `, [athleteId, item.domain, item.category, item.fact, item.status]);
  }
}
```

---

## Memory Lifecycle

```
                    Memory State Transitions
                    
  [New fact discovered]
          │
          ▼
      ┌────────┐
      │ active │  ← injected into every prompt
      └────┬───┘
           │ fact changes or resolves
           ▼
      ┌──────────┐
      │ inactive │  ← not injected, but accessible via search
      └──────┬───┘
             │ monthly decay job OR 6+ months old
             ▼
      ┌──────────┐
      │ archived │  ← only accessible via explicit Tool Use
      └──────────┘     e.g. "how did I handle that injury in 2024?"
```

**Monthly decay cron** (runs 1st of each month):
```javascript
// src/cron/memory-decay.js
// Mark inactive facts older than 6 months as archived
await db.query(`
  UPDATE athlete_facts
  SET status = 'archived'
  WHERE status = 'inactive'
    AND created_at < NOW() - INTERVAL '6 months'
`);
```

---

## Context Assembly Flow (Per Chat Request)

```javascript
// src/services/memory.service.js

async function assembleContext(athleteId, userMessage) {

  // All 4 tiers assembled in parallel
  const [activeFacts, summaries, recentSessions, semanticMatches, recentMessages] =
    await Promise.all([

      // Tier 2: Active facts — Entity State Machine
      db.query(`
        SELECT DISTINCT ON (category) domain, category, fact
        FROM athlete_facts
        WHERE athlete_id = $1 AND status = 'active'
        ORDER BY category, created_at DESC
      `, [athleteId]),

      // Tier 3a: Last 4 weekly summaries
      db.query(`
        SELECT week_start, summary, total_km, acwr
        FROM training_block_summaries
        WHERE athlete_id = $1
        ORDER BY week_start DESC
        LIMIT 4
      `, [athleteId]),

      // Tier 3b: Last 5 sessions — pre-computed Tier C context per session
      db.query(`
        SELECT date, session_type, distance_m, avg_pace_s_km, avg_hr,
               avg_cadence, hr_zone, trimp, acwr_at_session,
               cardiac_drift_pct, cardiac_drift_status,
               aerobic_decoupling_pct, session_spike_flag, spike_risk_increase_pct
        FROM training_sessions
        WHERE athlete_id = $1
        ORDER BY date DESC
        LIMIT 5
      `, [athleteId]),

      // Tier 4a: Semantic search
      semanticSearch(athleteId, userMessage, 3),

      // Tier 1: Last 20 messages
      db.query(`
        SELECT role, content FROM messages
        WHERE athlete_id = $1 AND session_id = current_session
        ORDER BY created_at DESC LIMIT 20
      `, [athleteId]),
    ]);

  return buildSystemPrompt({ activeFacts, summaries, recentSessions, semanticMatches, recentMessages });
}
```

**Estimated total tokens per request:** ~2,800 tokens  
**Cost at Gemini 2.0 Flash ($0.075/1M tokens):** ~$0.0002/request → $0.002/day for 10 requests

---

## Data Flow: Strava Webhook → Storage

```
Athlete finishes run
        │
        ▼
Strava → POST /sync/strava
        │
        ▼
Fetch full activity from Strava API (summary endpoint)
        │
        ├──► Fetch Strava Streams API (separate call — per-second time-series)
        │    streams.service.fetchStreams(activityId, ['heartrate','velocity_smooth','cadence'])
        │    → Used for cardiac drift + aerobic decoupling (first-half vs second-half split)
        │    → Save raw streams → data/streams/strava_{activityId}.json  (never in DB)
        │
        ├──► Fetch OpenWeatherMap historical weather
        │    weather.service.getAtRunTime(lat, lng, startTimestampUnix)
        │    → weather_temp_celsius, weather_humidity_pct
        │    (Strava's device-reported temperature is unreliable — replaced by API data)
        │
        ├──► Load athlete's resting_hr and max_hr from athlete_facts
        │    (physiological.resting_hr, physiological.max_hr)
        │
        │    ⚠ NULL HANDLING — if resting_hr or max_hr not on file:
        │      trimp = null   (stored as null, not zero — to distinguish from missing)
        │      acwr_at_session = null
        │      Send Telegram: "Để tính tải luyện tập chính xác, anh cho biết
        │        nhịp tim lúc nghỉ (resting HR) của anh là bao nhiêu?"
        │      When user replies → INSERT athlete_facts physiological.resting_hr
        │                        → retroactively recompute TRIMP for recent sessions
        │
        ├──► Sports Science Module computes (Tier A — pure JS, zero LLM):
        │
        │    Basic metrics:
        │      pacePerKm(distanceM, durationS)
        │      strideLength(cadenceSpm, paceSecPerKm)
        │      dominantHrZone(avgHR, athlete.maxHR)
        │
        │    Training load (requires resting_hr + max_hr — may be null):
        │      trimp(durationMin, avgHR, restingHR, maxHR, gender)
        │      acwr(trimp7Days, trimp28Days)          ← TRIMP-based, not km
        │      acwrStatus(ratio)                       → 'optimal' | 'caution' | 'danger'
        │
        │    Aerobic quality (uses Streams data + OpenWeatherMap temp):
        │      cardiacDrift(firstHalfHR, secondHalfHR)       ← from Streams split
        │      cardiacDriftStatus(drift, weather_temp_celsius) → temp-adjusted threshold
        │      aerobicDecoupling(hr1, pace1, hr2, pace2)      ← from Streams split
        │      aerobicDecouplingStatus(decoupling, temp)
        │
        │    Injury risk:
        │      recentMaxLongRun(last6WeeksSessions)
        │      singleSessionSpike(distanceM, recentMax)  → flag if > 110% of recent max
        │
        ├──► INSERT all computed columns → training_sessions
        │      (weather_temp_celsius, weather_humidity_pct,
        │       cardiac_drift_pct, cardiac_drift_status,
        │       aerobic_decoupling_pct, trimp, acwr_at_session,
        │       session_spike_flag, spike_risk_increase_pct)
        │
        ├──► formatSessionContext(metrics) → Tier C string
        │
        ├──► Generate text summary of session (one Gemini call using Tier C context)
        │    "Easy run 12km @ 5:52/km. HR Zone 2 ✓ (drift 4.1% normal at 27°C).
        │     TRIMP 52, ACWR 0.91 (optimal). No spike flag."
        │
        └──► Embed summary → memories_semantic (for future Tier 4 search)
```

### Onboarding: Collecting resting_hr and max_hr

These values are not available from Strava. Collected via two paths:

1. **Web onboarding form** — asked during initial setup alongside race goal
2. **Telegram prompt** — triggered on first Strava sync if values missing (see NULL HANDLING above)

Once provided, stored as:
```
physiological.resting_hr   "52 bpm"    source: 'chat'
physiological.max_hr       "185 bpm"   source: 'chat'
```

**Retroactive TRIMP recompute:** When resting_hr or max_hr is first provided, a background job
recomputes `trimp` and `acwr_at_session` for all sessions in the last 28 days where these were null.
This ensures ACWR history is accurate from the start.

---

## Data Flow: User Sends Chat Message

```
User: "My left knee is sore after today's run. Should I skip Thursday's tempo?"
        │
        ▼
POST /chat { message, athleteId, sessionId }
        │
        ▼
assembleContext() — parallel fetch of all 4 tiers
        │
        ├── Tier 2 active facts:
        │     sports.race_goal: "Sub-3:30 HCMC Marathon 2026"
        │     health.injury: "None active"      ← agent sees this is NEW info
        │     physiological.threshold_pace: "4:35/km"
        │
        ├── Tier 3 summaries + sessions: last 4 weeks + last 5 runs
        │
        ├── Tier 4 semantic: finds similar "knee soreness → tempo decision" cases from past
        │
        └── Tier 1: last 20 messages
        │
        ▼
Call Gemini 2.0 Flash with assembled prompt + Tools available:
  - search_historical_facts(topic)  ← for past archived facts
  - log_training_note(note)         ← for agent to flag something
        │
        ▼
Gemini responds: "With a sub-3:30 goal and 72km base, losing one tempo won't
hurt you. But a sore knee 2 days before a quality session is a yellow flag.
Replace Thursday's tempo with an easy 8km. If it persists past Sunday, we
reassess the Build Phase entry..."
        │
        ▼
Stream response to user
        │
        ▼
Store messages → messages table
Embed assistant response → memories_semantic
        │
        ▼ (next Sunday cron)
Memory Extraction sees "left knee sore" conversation →
Differential prompt finds it's NEW (health.injury was "None active") →
INSERT: domain=health, category=knee_soreness,
        fact="Mild soreness reported post-run 2026-05-01, monitoring",
        status=active
```

---

## Data Flow: User Sets a New Goal

Two entry points — structured form (web UI) or natural language (chat). Both converge at
the same Goal Processing Service after input is captured.

```
┌─────────────────────────────────┐     ┌──────────────────────────────────────┐
│  PATH A: Web UI Form            │     │  PATH B: Telegram / Chat             │
│                                 │     │                                      │
│  User fills form:               │     │  User: "I want to run sub-3:30 at    │
│  ├─ Race name: HCMC Marathon    │     │   HCMC Marathon on Dec 7th 2026"     │
│  ├─ Race date: 2026-12-07       │     │                                      │
│  ├─ Goal time: 3:30:00          │     │  POST /chat { message, athleteId }   │
│  └─ Current weekly km: 55km     │     │          │                           │
│                                 │     │          ▼                           │
│  POST /api/goals {              │     │  Gemini detects goal-setting intent  │
│    raceName, raceDate,          │     │  Extracts structured data:           │
│    goalTime, currentWeeklyKm    │     │    race: "HCMC Marathon"             │
│  }                              │     │    date: "2026-12-07"                │
│                                 │     │    goalTime: "3:30:00"               │
│                                 │     │          │                           │
│                                 │     │  Missing info? → ask clarifying Qs: │
│                                 │     │  "What's your current weekly km?"   │
│                                 │     │  User replies → structured complete  │
└────────────────┬────────────────┘     └──────────────────┬───────────────────┘
                 │                                         │
                 └─────────────────┬───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │  Goal Processing Service      │
                    │  src/services/goal.service.js │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
          ┌────────────────────────────────────────────────────┐
          │  STEP 1: Sports Science Module — pure JS, zero LLM  │
          │                                                      │
          │  parseGoalTime("3:30:00")                            │
          │    → 12600 seconds                                   │
          │                                                      │
          │  targetPaceFromGoalTime(12600, 42.195)               │
          │    → 298 sec/km  →  formatPace() → "4:58/km"        │
          │                                                      │
          │  weeksUntilRace("2026-12-07")                        │
          │    → 32 weeks                                        │
          │                                                      │
          │  requiredLtPace(298)                                 │
          │    → 277 sec/km → "4:37/km"  (LT ~7% faster)        │
          │                                                      │
          │  goalFeasibility(                                    │
          │    weeksAvailable=32,                                │
          │    currentLtPace=athlete_facts.lt_pace || null,      │
          │    targetPace=298                                    │
          │  ) → { feasible: true, reason: "..." }               │
          │                                                      │
          │  trainingPhases(32) →                                │
          │    Base  (w1–11):  Aerobic base, long run to 25km    │
          │    Build (w12–21): Tempo + threshold, LR to 30km     │
          │    Peak  (w22–27): Race-specific, peak LR 32–35km    │
          │    Taper (w28–32): Volume –30%/wk, race sharpening   │
          └────────────────────────┬───────────────────────────┘
                                   │
                                   ▼
          ┌────────────────────────────────────────────────────┐
          │  STEP 2: Archive old goal (Entity State Machine)    │
          │                                                      │
          │  SELECT existing sports.race_goal from athlete_facts │
          │  If found → INSERT new row:                          │
          │    category: "race_goal"                             │
          │    fact: "Abandoned: Sub-3:45 Da Lat Ultra 2026"     │
          │    status: "inactive"    ← old goal archived        │
          │  (never deleted — available via Tier 4 tool use)     │
          └────────────────────────┬───────────────────────────┘
                                   │
                                   ▼
          ┌────────────────────────────────────────────────────┐
          │  STEP 3: Write new goal to athlete_facts (Tier 2)   │
          │                                                      │
          │  INSERT (status: active):                            │
          │    sports.race_goal    "Sub-3:30 HCMC Marathon       │
          │                         2026-12-07"                  │
          │    sports.race_date    "2026-12-07"                  │
          │    sports.target_pace  "4:58/km"                     │
          │    sports.weeks_to_race "32"                         │
          │    sports.training_phase "Base Phase — Week 0"       │
          │    sports.required_lt_pace "4:37/km"                 │
          │    physiological.lt_pace_gap                         │
          │      "Need 8 sec/km LT improvement over 32 weeks"    │
          │        (if current LT pace is known)                 │
          └────────────────────────┬───────────────────────────┘
                                   │
                                   ▼
          ┌────────────────────────────────────────────────────┐
          │  STEP 4: INSERT into training_goals table           │
          │                                                      │
          │  Stores structured goal data + phase breakdown:      │
          │    race_name, race_date, goal_time_s: 12600          │
          │    target_pace_s_km: 298                             │
          │    weeks_available: 32                               │
          │    phases: [{ phase, weeks, focus }, ...]  (JSONB)   │
          │    feasibility: "feasible"                           │
          │    status: "active"                                  │
          └────────────────────────┬───────────────────────────┘
                                   │
                                   ▼
          ┌────────────────────────────────────────────────────┐
          │  STEP 5: Gemini generates goal assessment           │
          │  (one call — coaching narrative only)               │
          │                                                      │
          │  Context injected:                                   │
          │    [Tier 2 active facts — including new goal]        │
          │    [Phase breakdown from Sports Science Module]      │
          │    [Feasibility result + LT gap if known]            │
          │    [Last 4 weekly summaries if athlete has history]  │
          │                                                      │
          │  Gemini writes:                                      │
          │    - Feasibility assessment ("This is ambitious      │
          │       but achievable with 32 weeks...")              │
          │    - Phase overview ("Weeks 1–11 focus on base...")  │
          │    - First week recommendation                       │
          │    - One flag if any risk detected                   │
          └────────────────────────┬───────────────────────────┘
                                   │
                                   ▼
          ┌────────────────────────────────────────────────────┐
          │  STEP 6: Store + embed                              │
          │                                                      │
          │  Store Gemini assessment → training_goals.gemini_assessment │
          │  Store as message → messages table                   │
          │  Embed assessment → memories_semantic (Tier 4)      │
          └────────────────────────┬───────────────────────────┘
                                   │
                  ┌────────────────┴───────────────┐
                  ▼                                ▼
     Web UI response:                     Chat response:
     ┌───────────────────┐               Gemini streams
     │ Goal Summary Card │               assessment back
     │ ─────────────────│               to Telegram/Web
     │ Sub-3:30 Marathon │               chat interface
     │ Dec 7 · 32 weeks  │
     │ Target: 4:58/km   │
     │ Required LT: 4:37 │
     │ ─────────────────│
     │ Base  w1–11       │
     │ Build w12–21      │
     │ Peak  w22–27      │
     │ Taper w28–32      │
     │ ─────────────────│
     │ [Gemini assessment│
     │  narrative...]    │
     └───────────────────┘
```

### Goal-Setting Functions (Sports Science Module)

Added to `src/science/sports-science.js` — pure JS, no LLM:

```javascript
// Parse "3:30:00" or "3:30" → total seconds
export const parseGoalTime = (timeStr) => {
  const parts = timeStr.split(':').map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 3600 + parts[1] * 60;
  return parts[0] * 60;
};

// Target pace from goal time — always marathon distance (42.195km)
export const targetPaceFromGoalTime = (goalTimeSeconds, distanceKm = 42.195) =>
  Math.round(goalTimeSeconds / distanceKm);

// Weeks from today to race date
export const weeksUntilRace = (raceDateStr) => {
  const diff = new Date(raceDateStr) - new Date();
  return Math.floor(diff / (1000 * 60 * 60 * 24 * 7));
};

// Required LT pace for a marathon goal
// Research: LT pace is ~7% faster than marathon race pace (TrainingPeaks)
export const requiredLtPace = (targetPaceSecPerKm) =>
  Math.round(targetPaceSecPerKm * 0.93);

// Feasibility check — uses current LT pace from athlete_facts if available
// LT improvement rate: > 3 sec/km per week = unrealistic; < 1.5 = achievable
export const goalFeasibility = (weeksAvailable, currentLtPaceSecPerKm, targetPaceSecPerKm) => {
  if (weeksAvailable < 12)
    return { feasible: false, reason: 'Less than 12 weeks — insufficient preparation time' };

  if (!currentLtPaceSecPerKm)
    return {
      feasible: weeksAvailable >= 16 ? 'unknown' : 'risky',
      reason: 'No LT pace on file — set a baseline with a 30-min time trial',
    };

  const neededLt   = requiredLtPace(targetPaceSecPerKm);
  const ltGapSec   = currentLtPaceSecPerKm - neededLt;  // positive = need to improve
  const weeklyRate = ltGapSec / weeksAvailable;

  if (weeklyRate > 3)
    return { feasible: false,     reason: `Requires ${ltGapSec}s/km LT gain — too aggressive for ${weeksAvailable} weeks` };
  if (weeklyRate > 1.5)
    return { feasible: 'stretch', reason: `Requires ${ltGapSec}s/km LT gain — challenging but possible` };
  return   { feasible: true,      reason: `Goal is achievable — needs ~${ltGapSec > 0 ? ltGapSec : 0}s/km LT improvement` };
};

// Phase breakdown based on weeks available
// Research: Taper = 15-20% of total; Peak only when > 20 weeks available
export const trainingPhases = (weeksUntilRace) => {
  if (weeksUntilRace < 12) return [
    { phase: 'Prep',  weeks: Math.round(weeksUntilRace * 0.75), focus: 'Build base mileage, all easy runs' },
    { phase: 'Taper', weeks: Math.round(weeksUntilRace * 0.25), focus: 'Reduce volume, maintain pace' },
  ];

  if (weeksUntilRace <= 20) return [
    { phase: 'Base',  weeks: Math.round(weeksUntilRace * 0.45), focus: 'Aerobic base, 80% easy, long run to 25km' },
    { phase: 'Build', weeks: Math.round(weeksUntilRace * 0.35), focus: 'Add tempo + intervals, long run to 30km' },
    { phase: 'Taper', weeks: Math.round(weeksUntilRace * 0.20), focus: 'Volume –30%/week, race sharpening' },
  ];

  return [  // > 20 weeks
    { phase: 'Base',  weeks: Math.round(weeksUntilRace * 0.35), focus: 'Aerobic base, 80% easy, long run to 25km' },
    { phase: 'Build', weeks: Math.round(weeksUntilRace * 0.30), focus: 'Tempo + threshold, long run to 30km' },
    { phase: 'Peak',  weeks: Math.round(weeksUntilRace * 0.20), focus: 'Race-specific workouts, peak LR 32–35km' },
    { phase: 'Taper', weeks: Math.round(weeksUntilRace * 0.15), focus: 'Volume –30%/week, race sharpening' },
  ];
};
```

### New DB Table: `training_goals`

```sql
-- Stores one row per goal. athlete_facts mirrors the active goal for context injection.
-- Keeps full structured data (phases, feasibility) that is too large for athlete_facts.
CREATE TABLE training_goals (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_id          UUID REFERENCES athletes(id) ON DELETE CASCADE,
  race_name           TEXT NOT NULL,
  race_date           DATE NOT NULL,
  goal_time_s         INTEGER NOT NULL,        -- total seconds e.g. 12600 for 3:30:00
  target_pace_s_km    INTEGER NOT NULL,        -- seconds/km e.g. 298 for 4:58/km
  required_lt_pace_s_km INTEGER,              -- LT pace needed (7% faster than target)
  weeks_available     INTEGER NOT NULL,
  phases              JSONB NOT NULL,          -- [{ phase, weeks, focus }]
  feasibility         TEXT NOT NULL,           -- 'true' | 'stretch' | 'risky' | 'false' | 'unknown'
  feasibility_reason  TEXT,
  gemini_assessment   TEXT,                    -- initial coaching narrative from Gemini
  status              TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'completed' | 'abandoned'
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_training_goals_athlete ON training_goals (athlete_id, status, created_at DESC);
```

### What athlete_facts Receives (Tier 2 injection)

After goal is set, these facts are active and injected into every prompt:

```
sports.race_goal:       "Sub-3:30 HCMC Marathon 2026-12-07"
sports.race_date:       "2026-12-07"
sports.target_pace:     "4:58/km"
sports.weeks_to_race:   "32"                   ← updated weekly by cron
sports.training_phase:  "Base Phase — Week 0"  ← updated weekly by cron
sports.required_lt_pace "4:37/km"
```

### Weekly Phase Tracker (Sunday cron addition)

The Sunday weekly-summary cron also updates `sports.weeks_to_race` and `sports.training_phase` so Gemini always knows where in the plan the athlete is:

```javascript
// Added to weekly-summary.js (runs Sunday 23:00)
const activeGoal = await db.query(
  `SELECT * FROM training_goals WHERE athlete_id = $1 AND status = 'active'`,
  [athleteId]
);
if (activeGoal.rows[0]) {
  const weeksLeft = weeksUntilRace(activeGoal.rows[0].race_date);
  const totalWeeks = activeGoal.rows[0].weeks_available;
  const weeksDone  = totalWeeks - weeksLeft;
  const phases     = activeGoal.rows[0].phases;

  // Determine current phase
  let accumulated = 0;
  let currentPhase = phases[0];
  for (const p of phases) {
    accumulated += p.weeks;
    if (weeksDone < accumulated) { currentPhase = p; break; }
  }

  // Update athlete_facts
  await insertFact(athleteId, 'sports', 'weeks_to_race', `${weeksLeft} weeks`);
  await insertFact(athleteId, 'sports', 'training_phase',
    `${currentPhase.phase} Phase — Week ${weeksDone} of ${totalWeeks}`);
}
```

---

## Four Cron Jobs

```
┌──────────────────────────────────────────────────────────────────────┐
│  Sunday 23:00 — Weekly Summary (Tier 3 + Tier B update)              │
│                                                                      │
│  Sports Science Module (Tier B — pure JS):                           │
│  1. Fetch all sessions from past 7 days + past 28 days               │
│  2. weeklyZoneDistribution(sessions, athlete.maxHR)                  │
│       → low_intensity_pct, high_intensity_pct, is_polarized          │
│  3. acwr(weekTrimp, last28DaysTrimp)   ← TRIMP-based                 │
│  4. recentMaxLongRun(sessions, 6)      ← rolling 6-week window       │
│  5. total_km, weekly_trimp totals                                    │
│                                                                      │
│  Gemini (coaching narrative only):                                   │
│  6. Gemini receives Tier B output + last 5 sessions                  │
│  7. Writes coaching narrative (~300 words)                           │
│  8. INSERT into training_block_summaries                             │
│     (with zone_distribution, weekly_trimp, acwr, is_polarized)      │
│  9. Embed summary → memories_semantic                                │
│  10. Update athlete_facts: sports.recent_max_long_run                │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  Sunday 23:30 — Memory Extraction (Tier 2 update)                    │
│                                                                      │
│  1. Load current active facts (existing knowledge)                   │
│  2. Load this week's messages + new weekly summary                   │
│  3. Differential prompt → Gemini extracts ONLY new/changed facts     │
│  4. INSERT new/changed rows into athlete_facts                       │
│  5. Embed new facts → memories_semantic                              │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  1st of Month 02:00 — Memory Decay                                   │
│                                                                      │
│  1. UPDATE athlete_facts SET status='archived'                       │
│     WHERE status='inactive' AND created_at < NOW() - '6 months'     │
│  2. Log how many facts were archived                                 │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  Monday 07:00 — Resting HR Check                                     │
│                                                                      │
│  1. For each athlete with no physiological.resting_hr or             │
│     physiological.max_hr in athlete_facts:                           │
│  2. Send Telegram message:                                           │
│     "Chào buổi sáng! Để tính tải luyện tập chính xác, anh cho biết  │
│      nhịp tim lúc nghỉ (resting HR) của anh là bao nhiêu nhé?       │
│      (Đo sáng sớm trước khi ra giường)"                              │
│  3. When athlete replies with a number:                              │
│     → INSERT physiological.resting_hr into athlete_facts            │
│     → Trigger retroactive TRIMP recompute for last 28 days          │
│  4. Skip athletes who have already provided both values              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
running-coach/
├── src/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.js
│   │   │   ├── sync.js
│   │   │   └── athlete.js
│   │   └── middleware/
│   │       └── auth.js
│   ├── services/
│   │   ├── memory.service.js       ← assembleContext(), writeFact(), archiveFact()
│   │   ├── gemini.service.js       ← buildPrompt(), callGemini(), streamReply()
│   │   ├── embedding.service.js    ← text → vector via text-embedding-004
│   │   ├── goal.service.js         ← processGoal(), archiveGoal(), updatePhase()
│   │   ├── strava.service.js       ← OAuth, webhook, activity fetch
│   │   ├── streams.service.js      ← Strava Streams API (per-second HR/pace for drift calc)
│   │   ├── weather.service.js      ← OpenWeatherMap historical API (temp + humidity)
│   │   └── datalake.service.js     ← save/read raw JSON time-series files
│   ├── science/
│   │   └── sports-science.js       ← pure JS math: ACWR, HR zones, drift, TRIMP
│   ├── bot/
│   │   └── telegram.bot.js
│   ├── cron/
│   │   ├── weekly-summary.js       ← Sun 23:00
│   │   ├── memory-extraction.js    ← Sun 23:30 (differential prompting)
│   │   ├── memory-decay.js         ← 1st of month 02:00
│   │   └── resting-hr-ask.js       ← Mon 07:00 (prompt for resting HR if missing)
│   ├── db/
│   │   ├── schema.sql
│   │   └── index.js
│   └── app.js
├── data/
│   └── streams/                    ← Data Lake: raw GPS/HR JSON files
│       └── strava_12345678.json    ← per-second HR, pace, cadence from Streams API
├── web/                            ← Next.js frontend
│   ├── app/
│   │   ├── chat/page.tsx
│   │   ├── dashboard/page.tsx
│   │   └── api/
│   └── components/
├── .env.example
└── package.json
```

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Node.js + Express | Your experience |
| AI Model | Gemini 2.0 Flash | Fast, cheap, long context |
| Embeddings | `text-embedding-004` (Gemini) | Same API key |
| Database | PostgreSQL + pgvector | Single DB, no separate vector store |
| Sports Science | Pure Node.js | Deterministic, testable, no LLM hallucination |
| Data Lake | Local JSON files (`data/streams/`) | Keeps DB lean, raw data preserved |
| Strava | OAuth2 + Webhook + Streams API | Real-time push + per-second HR/pace data |
| OpenWeatherMap | Historical weather API | Temperature + humidity at run location (device-reported temp unreliable) |
| Web | Next.js (App Router) | Full-stack in one repo |
| Telegram | Telegraf.js | Lightweight |
| Cron | node-cron | 4 jobs: summary, extraction, decay, resting-hr-ask |
| Auth | NextAuth.js | Web + API |
| Deploy | Railway or Render | Simple solo ops |

---

## Key Packages

```json
{
  "@google/generative-ai": "^0.21.0",
  "pg": "^8.13.0",
  "pgvector": "^0.2.0",
  "telegraf": "^4.16.0",
  "strava-v3": "^2.1.0",
  "axios": "^1.8.0",
  "node-cron": "^3.0.0",
  "express": "^4.21.0"
}
```

---

## Environment Variables

```bash
# .env.example

# AI
GEMINI_API_KEY=

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/running_coach

# Telegram
TELEGRAM_BOT_TOKEN=

# Strava (OAuth2 + Webhooks + Streams API — same credentials)
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_VERIFY_TOKEN=        # for webhook subscription verification

# OpenWeatherMap (historical weather at run location + time)
OPENWEATHER_API_KEY=

# App
APP_URL=https://your-domain.com
NODE_ENV=production
```

---

## Phased Build Plan

### Phase 1 — Memory Foundation (Week 1-2)
- [ ] PostgreSQL schema with `athlete_facts` + `training_goals` tables
- [ ] Goal-setting flow: web form + chat path both working
- [ ] Sports Science goal functions: `parseGoalTime`, `targetPaceFromGoalTime`, `weeksUntilRace`, `trainingPhases`, `goalFeasibility`
- [ ] Active facts context injection working (goal facts visible in every prompt)
- [ ] Basic Gemini chat: Tier 1 (working memory) + Tier 2 (active facts)
- [ ] Telegram bot: `/goal`, `/log`, `/ask`, `/facts`

### Phase 2 — Sports Science + Integrations (Week 3-4)
- [ ] Sports Science Module (acwr, hrZones, cardiacDrift, trimp)
- [ ] Strava OAuth + webhook sync → computed metrics stored
- [ ] Strava Streams API: fetch per-second HR/pace → split first/second half for drift + decoupling
- [ ] OpenWeatherMap integration: historical weather at run location + start time
- [ ] Onboarding flow: collect resting_hr + max_hr (web form + Telegram prompt fallback)
- [ ] TRIMP null handling + retroactive recompute on first HR values provided
- [ ] Monday 07:00 cron: check if resting_hr missing → send Telegram reminder
- [ ] Data Lake: raw JSON time-series to `data/streams/`
- [ ] pgvector semantic search working (Tier 4a)

### Phase 3 — Memory Intelligence (Week 5-6)
- [ ] Weekly summary cron (Tier 3 mid-term)
- [ ] Memory Extraction cron (Differential Prompting → Tier 2 auto-update)
- [ ] Memory Decay cron (monthly archived)
- [ ] Tool Use: `search_historical_facts` for Tier 4b

### Phase 4 — Web App (Week 7-8)
- [ ] Next.js dashboard: training calendar, active facts panel
- [ ] Chat interface with streaming
- [ ] Activity charts: pace, HR, cadence, ACWR trend
- [ ] Training plan generation (JSON output for calendar rendering)

---

## What Changed from v1

| v1 | v2 | Why |
|---|---|---|
| `memories_long` JSONB blob | `athlete_facts` Entity State Machine | Healed injuries stayed in context forever |
| No memory lifecycle | `active → inactive → archived` | Stale facts polluted advice |
| No deduplication | `DISTINCT ON (category)` + Differential Prompting | Memory grew without new information |
| LLM computes metrics | Sports Science Module (pure JS, Tier A/B/C) | Math errors → bad training advice |
| ACWR from km | ACWR from TRIMP (Banister 1991) | 15km easy ≠ 15km tempo in physiological stress |
| No cardiac drift context | Temperature-adjusted drift threshold | 18% drift at 30°C is normal, not a fitness failure |
| No spike detection | `singleSessionSpike()` — +10% = +64% injury risk | Weekly ACWR can look fine while one run causes injury |
| No zone distribution tracking | `weeklyZoneDistribution()` — checks 80/20 compliance | Polarized training requires explicit monitoring |
| No LT pace | `ltPaceFromTimeTrial()` stored in `athlete_facts` | LT pace is strongest single marathon predictor |
| No VO2max estimate | `vo2maxFromRacePace()` (Daniels & Gilbert 1979) | Tracks fitness improvement across training blocks |
| Raw data in `training_sessions.raw_data` JSONB | Data Lake (JSON files) | DB stayed lean; raw data preserved |
| One cron job | Four cron jobs | Summary, extraction, decay, resting-hr-ask |
| No memory extraction | Sunday extraction cron | Tier 2 was manual-only in v1 |
| Garmin Connect integration | Removed — no public API for individual developers | Garmin requires formal business partnership; unofficial libraries violate ToS |
| Device-reported temperature from Strava | OpenWeatherMap historical API | Strava's avg_temp is unreliable (device-reported, often missing) |
| No per-second HR data | Strava Streams API | Required for cardiac drift + aerobic decoupling (first/second half split) |
| No resting_hr / max_hr collection | Onboarding form + Monday Telegram cron | Required for TRIMP formula; retroactive recompute when first provided |
