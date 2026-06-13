# Sports Science Research
# Metrics for Sub-4 Hour Marathon Training

> **Purpose:** Evidence base for the Sports Science Module in ARCHITECTURE.md.
> Documents what each metric measures, what the safe thresholds are, what evidence
> supports them, and critically — what they miss.

**Target athlete profile:** Recreational runner, goal 3:30–3:59 finish (~5:00–5:41/km race pace), likely training in tropical climate (heat + high humidity).

---

## Verdict First

**Are ACWR + HR Zones + Cardiac Drift enough?**

**No.** They are a solid foundation but have documented blind spots:

| Metric | What it covers | What it misses |
|---|---|---|
| ACWR | Weekly load progression | Tissue-specific adaptation lag (tendons = 4–6 weeks, muscles = 48–72 hrs) |
| HR Zones | Training intensity distribution | Individual lactate threshold, heat-distorted readings |
| Cardiac Drift | Aerobic efficiency on long runs | Needs environmental context to interpret correctly |

The three metrics together don't tell you: lactate threshold pace, running economy, single-session spikes, or pacing strategy — all of which have stronger prediction power for marathon finish time than any of the three above.

**Recommended expanded set** (documented below with evidence):
1. ACWR (with TRIMP, not km) + single-session spike rule
2. HR Zones (80/20 distribution, verified HRmax)
3. Cardiac Drift + Aerobic Decoupling
4. Lactate Threshold Pace estimate
5. Single-Session Spike monitoring
6. Pacing strategy (negative split capability)

---

## 1. ACWR — Acute:Chronic Workload Ratio

### What it is
Ratio of acute load (last 7 days) to chronic load (rolling 28-day average).
A value of 1.0 means "training exactly as much as your recent average." Above 1.5 means a significant spike.

### Safe thresholds

| ACWR | Zone | Meaning |
|---|---|---|
| < 0.8 | Undertraining | Fitness declining |
| 0.8 – 1.3 | Optimal (green) | Safe progression |
| 1.3 – 1.5 | Caution (yellow) | Monitor closely |
| > 1.5 | Danger (red) | 2.15× higher injury hazard ratio |

### Evidence

**Gabbett (2016)** — the foundational paper.
Studied rugby league players and found ACWR > 1.5 correlated with significantly elevated injury risk. Also found: high *chronic* load is protective — a well-trained athlete can tolerate higher spikes than an undertrained one.
- Source: *British Journal of Sports Medicine*, 2016. PMID: 26758673
- PMC review: https://pmc.ncbi.nlm.nih.gov/articles/PMC8138569/

**Impellizzeri et al. (2020–2021)** — major critique. Read this.
Found that a *random* chronic workload ratio performs as well as the real ACWR in predicting injury — suggesting ACWR's predictive power may be a statistical artifact (rescaling the explanatory variable), not a true causal relationship.
- *Acute:Chronic Workload Ratio: Conceptual Issues and Fundamental Pitfalls* — PubMed: 32502973
- *Time to Dismiss ACWR* — PubMed: 33332011

**Practical implication:** Use ACWR as a monitoring guardrail, not a precise injury predictor. It's still useful for flagging sudden spikes, but don't over-rely on it.

### What workload unit to use: km vs. TRIMP

**Distance (km) alone is wrong.** A 15km easy run ≠ a 15km tempo run in physiological stress.

**TRIMP (Training Impulse)** — developed by Dr. Eric Banister (1991) — integrates duration × intensity via heart rate. One TRIMP unit = one minute of effort at Heart Rate Reserve midpoint.

Formula used in this system:
```
trimp = durationMin × hrRatio × (0.64 × e^(k × hrRatio))
where:
  hrRatio = (avgHR - restingHR) / (maxHR - restingHR)
  k = 0.64 (male) or 0.86 (female)
```

Use TRIMP for ACWR calculation. Distance can be stored separately for weekly volume tracking.

- Source: Banister 1991, *Modeling elite athletic performance*
- Applied guide: https://fellrnr.com/wiki/TRIMP

---

## 2. Heart Rate Zones

### Zone system

This system uses the standard 5-zone model based on % HRmax:

| Zone | % HRmax | Effort | Training purpose |
|---|---|---|---|
| Z1 | < 60% | Very easy | Recovery, warm-up |
| Z2 | 60–70% | Easy | Aerobic base building |
| Z3 | 70–80% | Moderate/tempo | Marathon race pace range |
| Z4 | 80–90% | Hard/threshold | Lactate threshold work |
| Z5 | 90–100% | Max | VO2max intervals |

**Marathon race pace zone:** For most recreational sub-4hr runners, race pace falls in **Z3–Z4** (roughly 78–85% HRmax). This matters for training because you should not do most of your runs at race pace.

### The 80/20 Polarized Model

**Seiler & Kjerland (2006)** — studied elite Norwegian cross-country skiers. Found their *natural* training distribution was ~80% low intensity (Z1–Z2), ~20% high intensity (Z4–Z5). Zone 3 ("tempo") was minimized — not avoided, just not dominant.

**Esteve-Lanao et al. (2007)** — sub-elite runners. Runners following 80/20 distribution improved 10K times more than groups doing more moderate-intensity training.
- Source: *Medicine & Science in Sports & Exercise*, 2007

**Systematic review (2024–2025)** — confirmed polarized training produces superior VO2max, VO2peak, and work economy gains over pyramidal or threshold-heavy approaches.
- Source: PMC https://pmc.ncbi.nlm.nih.gov/articles/PMC11679080/

**Practical target for sub-4hr training week (e.g., 60km/week):**
- ~48km in Z1–Z2 (easy/recovery runs)
- ~12km in Z4–Z5 (intervals, tempo)
- Z3 minimal — mostly transitions

### The 220-age formula problem

**Do not use 220 − age for HRmax.** Error range is ±10–20 bpm, which shifts all zone boundaries significantly. A 10 bpm error on HRmax moves every zone boundary by 6–18 bpm.

**Field test to get actual HRmax:**
1. Warm up 10 min easy
2. Run 1km hard, then immediately run 400m all-out
3. Record highest HR seen

Re-test every 6–12 months. Fitness gains can shift perceived max by 2–5 bpm.

- Source: https://marathonireland.com/blog/heart-rate-zones-marathon/

### Why HR zones alone are insufficient

HR is affected by: heat, humidity, dehydration, fatigue, caffeine, illness, sleep. On a hot day, your Z2 run may show Z3–Z4 HR. That doesn't mean you're training hard — it means cardiac drift is elevated.

Always combine HR zones with:
- Pace zones (based on lactate threshold or recent race times)
- RPE (Rate of Perceived Exertion) as a check

---

## 3. Cardiac Drift & Aerobic Decoupling

### Definitions

**Cardiac drift:** The progressive rise in HR during prolonged steady-state exercise even when pace stays constant. Caused by: plasma volume loss (sweat), reduced stroke volume, rising core temperature.

**Aerobic decoupling (Joe Friel):** The % change in HR/pace ratio from the first half to second half of a long run. If HR/pace tracks together (< 5% divergence), you're within your aerobic threshold for that pace.

Formula used in this system:
```javascript
aerobicDecoupling = ((hr2/pace2) - (hr1/pace1)) / (hr1/pace1) * 100
// hr1, pace1 = first half averages; hr2, pace2 = second half averages
```

### Thresholds (Friel)

| Decoupling % | Interpretation |
|---|---|
| ≤ 5% | Excellent — pace is sustainable, well within aerobic threshold |
| 5–10% | Acceptable — near aerobic threshold |
| > 10% | Too hard for this distance/pace, or aerobic base underdeveloped |

Source: Joe Friel, TrainingPeaks blog — https://www.trainingpeaks.com/blog/aerobic-endurance-and-decoupling/

### Normal cardiac drift ranges

| Condition | Expected HR drift |
|---|---|
| Cool conditions (< 20°C), well hydrated | 5–10% over 90 min |
| Warm conditions (25–30°C) | 10–15% |
| Hot + humid (30°C+, > 70% RH) | 15–25% |

Source: PMC systematic review on humidity effects — https://pmc.ncbi.nlm.nih.gov/articles/PMC5079215/
Cardiac drift study — PubMed 22410803

### Critical note for HCMC / tropical climate racing

At 30°C+ with 70–80% humidity (typical HCMC race day conditions), cardiac drift of 15–20% is physiologically normal, not a fitness failure. If the agent interprets this naively as "you're unfit" it gives wrong advice.

**The system must always factor in `avg_temp_celsius` when interpreting drift.** This is pre-computed by the Sports Science Module and passed to Gemini as context.

Correction factor (approximate, based on research):
- < 20°C: use Friel's 5% threshold as-is
- 20–25°C: allow up to 8%
- 25–30°C: allow up to 12%
- > 30°C: allow up to 18%

Source: Delineating impacts of air temperature and humidity — https://physoc.onlinelibrary.wiley.com/doi/10.1113/EP090969

---

## 4. What's Missing — Metrics to Add

### 4a. Lactate Threshold Pace (most important missing metric)

**Why it matters:** LT pace — the speed at which lactate begins accumulating faster than it's cleared — is the single strongest predictor of marathon performance. Combined with VO2max and running economy, these three explain ~90% of performance variance between trained runners.

For a sub-4hr marathoner:
- LT pace typically falls around **4:40–5:10/km**
- Marathon race pace (~5:00–5:41/km) should be **at or slightly below LT pace** for a well-trained runner

**How to estimate without lab testing (field test):**
- 30-min time trial at max sustainable effort → average pace ≈ LT pace
- Or: HR at the point where you can no longer hold a conversation

Once LT pace is known, store it as an `athlete_facts` entity (`physiological.lactate_threshold_pace`). The weekly summary cron can track whether it's improving.

Source: https://www.trainingpeaks.com/blog/all-you-need-to-know-about-lt-and-vo2-max/

### 4b. Single-Session Spike Rule (injury prevention)

**The "10% weekly volume rule" is weakly supported.** The stronger predictor is the single-session spike.

Evidence:
- Long run 10% longer than your recent maximum → **+64% injury risk**
- Long run 100% longer (doubling) → **+128% injury risk**

Source: Marathon Science analysis of injury data — https://marathonscience.beehiiv.com/p/the-single-session-spike-the-1-predictor-of-running-injuries-you-might-be-overlooking-75812c64b14131

**Implementation:** The Sports Science Module should flag sessions where `distance_m > recentMaxLongRun * 1.10`. Store `recent_max_long_run` as an `athlete_facts` entity updated after every long run.

### 4c. Pacing Strategy (race execution predictor)

**Pacing behavior in the first half of a marathon predicts finish time more reliably than any single training metric.**

Research finding: First 21.1km pace vs. second 21.1km pace ratio predicts finish time with R² = 0.72–0.88 (men), R² = 0.95 (women). Negative splitters consistently outperform positive splitters at equivalent fitness levels.

Source: *Predictive Performance Models in Marathon* — https://www.researchgate.net/publication/377337337

**What this means for training:** Some long runs should be done as negative-split practice (first half easy, second half at marathon pace). The agent should recommend this, especially in later training blocks.

### 4d. Tissue Adaptation Lag (injury prevention context)

ACWR and HR zones don't model this, but it's physiologically critical:

| Tissue | Adaptation time |
|---|---|
| Cardiovascular system | 1–2 weeks |
| Muscles | 48–72 hours |
| Tendons | 4–6 weeks |
| Bone stress response | 4–8 weeks |
| Aerobic mitochondria | 4–8 weeks |

**Practical rule:** Even if ACWR looks fine (0.9–1.1), sudden surface changes (road → trail), shoe changes, or stride length changes can load tendons in new ways before they've adapted. The agent should ask about surface/shoe changes when flagging potential injury risk.

---

## 5. Summary: Recommended Metrics for the Sports Science Module

### Tier A — Always computed (every session)

```
acwr(trimp)          → flag if > 1.3 (caution) or > 1.5 (danger)
cardiacDrift()       → adjusted by temperature (see thresholds above)
aerobicDecoupling()  → flag if > 5% (cool) or > 12% (hot)
hrZone()             → which zone dominated this session
trimp()              → training load unit for ACWR
pacePerKm()          → for trend tracking
strideLength()       → from cadence + pace
singleSessionSpike() → flag if distance > recentMaxLongRun * 1.10
```

### Tier B — Estimated periodically (every 4–6 weeks)

```
ltPaceEstimate()     → from 30-min time trial or recent race result
vo2maxEstimate()     → from Garmin/Strava if available, or Daniels table
weeklyDistribution() → % of km in each HR zone (check 80/20 compliance)
longRunProgression() → track longest run in rolling 6-week window
```

### Tier C — Passed to Gemini as context (never computed by LLM)

```
acwrStatus: "0.94 (optimal)"
sessionLoad: "68 TRIMP"
drift: "7.2% (normal for 28°C)"
decoupling: "4.8% (excellent, Z2 confirmed)"
sessionZone: "Zone 2 (87% of time)"
ltPace: "4:52/km"
spikeFlag: "none"
weeklyDistribution: "82% Z1-Z2, 18% Z4-Z5 (polarized ✓)"
```

---

## 6. Key References Summary

| Topic | Source | Year | Key number |
|---|---|---|---|
| ACWR thresholds | Gabbett, *BJSM* | 2016 | > 1.5 = 2.15× injury hazard ratio |
| ACWR critique | Impellizzeri et al., PubMed 32502973 | 2020 | Random ACWR = real ACWR in prediction |
| TRIMP formula | Banister, *Modeling athletic performance* | 1991 | Duration × HR reserve × exponential scaling |
| Polarized training (80/20) | Seiler & Kjerland, *SJMSS* | 2006 | 80% Z1-Z2, 20% Z4-Z5 |
| Polarized vs. threshold | Esteve-Lanao et al., *MSSE* | 2007 | 80/20 improves 10K more than threshold-heavy |
| Polarized systematic review | PMC 11679080 | 2024 | Superior VO2max + work economy |
| Aerobic decoupling | Joe Friel, TrainingPeaks | 2009 | < 5% = excellent aerobic base |
| Cardiac drift heat | PMC 5079215 | 2017 | Significant increase at > 61% RH |
| Heat + performance | PubMed 22410803 | 2012 | Drift mechanism: stroke volume + plasma volume |
| Tropical racing performance | Physiology (Wiley EP090969) | 2024 | Combined temp + humidity effect quantified |
| Single-session spike | Marathon Science / PMC 11986186 | 2025 | +10% long run = +64% injury risk |
| Pacing prediction | ResearchGate 377337337 | 2024 | First-half pace R² = 0.95 for finish time |
| Biomechanical fatigue | PMC 12575221 / Frontiers 2025 | 2025 | Step length + GCT predict pace decline |
| LT + VO2max + RE | TrainingPeaks / Runners Connect | — | Together explain ~90% of performance variance |
