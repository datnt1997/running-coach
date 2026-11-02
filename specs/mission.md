# Mission

## Purpose

Running Coach Agent is a personal AI coach that helps a single user set a running goal, build a structured training plan, and adapt that plan week by week based on real performance data — until the goal is achieved.

## Primary User

A runner training for one of two supported race distances, within a defined target range:

| Distance | Slowest supported | Fastest supported |
|---|---|---|
| Half Marathon (21.1 km) | No lower bound | **1:44:00** (~4:55/km) |
| Full Marathon (42.2 km) | No lower bound | **3:59:00** (~5:39/km) |

The user sets their own finish-time goal anywhere within this range — sub 2:15 HM, sub 1:55 HM, sub 4:30 FM, sub 4:00 FM, etc. Goals faster than the upper bounds (e.g. sub 1:40 HM, sub 3:45 FM) are out of scope — those athletes need elite-level coaching beyond what this agent is designed for.

## Problem Being Solved

Generic training plan apps give static schedules that ignore how the runner actually performed. A real coach adjusts — easier week after a tough race, harder week when the runner is responding well. This agent does that, continuously, using the runner's own data.

## Success Definition

- User states a goal and receives a personalized, science-based training plan within the first session.
- Plan automatically adapts each week based on Strava activity data (pace, heart rate, load).
- User crosses the finish line of their target event having trained consistently and injury-free.
- The app supports multiple languages. The MVP ships in Vietnamese (UI, coach chat, plan notes and summaries); English can be added later without redesigning the app.

## Out of Scope (v1)

- Distances other than HM and FM (5K, 10K, ultra-marathons, etc.).
- Goals faster than the supported ceiling: sub 1:40 HM or sub 3:45 FM.
- Multi-user or team features.
- Nutrition, sleep, or strength coaching.
- Real-time GPS tracking or in-run audio coaching.
- Selling or sharing plans with others.
