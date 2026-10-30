# Graph Report - .  (2026-07-04)

## Corpus Check
- 0 files · ~42,045 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 484 nodes · 1096 edges · 28 communities (27 shown, 1 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 98 edges (avg confidence: 0.62)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Product Specs & Design Decisions|Product Specs & Design Decisions]]
- [[_COMMUNITY_Strava Webhook & Repository Layer|Strava Webhook & Repository Layer]]
- [[_COMMUNITY_AI Provider Clients & Test Fakes|AI Provider Clients & Test Fakes]]
- [[_COMMUNITY_Architecture Vision & Project Docs|Architecture Vision & Project Docs]]
- [[_COMMUNITY_Goal & Plan API Core|Goal & Plan API Core]]
- [[_COMMUNITY_Activity Matching & Strava Client|Activity Matching & Strava Client]]
- [[_COMMUNITY_Goal Validation & Prompt Building|Goal Validation & Prompt Building]]
- [[_COMMUNITY_Sports Science Research|Sports Science Research]]
- [[_COMMUNITY_App Bootstrap & Strava OAuth Tests|App Bootstrap & Strava OAuth Tests]]
- [[_COMMUNITY_Frontend React Components|Frontend React Components]]
- [[_COMMUNITY_Strava Connections & Changelog Scripts|Strava Connections & Changelog Scripts]]
- [[_COMMUNITY_Frontend Package Config|Frontend Package Config]]
- [[_COMMUNITY_Goal Endpoint Tests|Goal Endpoint Tests]]
- [[_COMMUNITY_Changelog Skill & History|Changelog Skill & History]]
- [[_COMMUNITY_Feature Spec & Implementation Skills|Feature Spec & Implementation Skills]]
- [[_COMMUNITY_Python Package Metadata|Python Package Metadata]]

## God Nodes (most connected - your core abstractions)
1. `AIClient` - 29 edges
2. `GoalRequest` - 24 edges
3. `PlanRepository` - 22 edges
4. `ActivityDetail` - 21 edges
5. `validate_goal()` - 17 edges
6. `ActivityAnalysisRepository` - 17 edges
7. `PlannedWorkout` - 17 edges
8. `match_activity_to_workout()` - 16 edges
9. `AIResponse` - 16 edges
10. `StravaConnectionRepository` - 16 edges

## Surprising Connections (you probably didn't know these)
- `Project Structure (app/, tests/, docker/, scripts/)` --semantically_similar_to--> `CLAUDE.md (project guidance)`  [INFERRED] [semantically similar]
  ARCHITECTURE.md → CLAUDE.md
- `Tech Stack Table` --semantically_similar_to--> `CLAUDE.md (project guidance)`  [INFERRED] [semantically similar]
  ARCHITECTURE.md → CLAUDE.md
- `Running Coach Agent Concept` --semantically_similar_to--> `CLAUDE.md (project guidance)`  [INFERRED] [semantically similar]
  README.md → CLAUDE.md
- `Running Coach Agent Concept` --semantically_similar_to--> `ARCHITECTURE.md v2.0 (Hybrid: Time-Based Tiers + Entity State Machine)`  [INFERRED] [semantically similar]
  README.md → ARCHITECTURE.md
- `FakeStravaClient` --uses--> `ToolCall`  [INFERRED]
  tests/conftest.py → app/ai/client.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Pre-Merge Phase Documentation Lifecycle** — _claude_skills_feature_spec_skill_feature_spec_skill, _claude_skills_implementation_doc_skill_implementation_doc_skill, _claude_skills_changelog_skill_changelog_skill_manual [INFERRED 0.85]
- **Four-Tier Memory Architecture** — architecture_tier1_working_memory, architecture_tier2_active_facts_entity_state_machine, architecture_tier3_temporal_context, architecture_tier4_historical_memory [EXTRACTED 1.00]
- **Sports Science Module Zero-LLM Computation Functions** — architecture_trimp, architecture_acwr, architecture_cardiac_drift, architecture_aerobic_decoupling, architecture_hr_zones, architecture_single_session_spike [EXTRACTED 1.00]
- **Phase 1 goal lifecycle API (create/poll/list/delete)** — concept_post_goal_endpoint, concept_get_goal_plan_endpoint, concept_get_goals_endpoint, concept_delete_goal_endpoint [INFERRED 0.85]
- **Strava connect/status/disconnect lifecycle** — concept_strava_oauth_flow, concept_strava_connect_ui, concept_strava_connections_table [INFERRED 0.85]
- **Fitness Assessment Chat Widget spec-kit document bundle** — specs_2026_07_03_fitness_level_chat_widget_spec, specs_2026_07_03_fitness_level_chat_widget_plan, specs_2026_07_03_fitness_level_chat_widget_requirements, specs_2026_07_03_fitness_level_chat_widget_tasks, specs_2026_07_03_fitness_level_chat_widget_validation, specs_2026_07_03_fitness_level_chat_widget_implementation [EXTRACTED 1.00]

## Communities (28 total, 1 thin omitted)

### Community 0 - "Product Specs & Design Decisions"
Cohesion: 0.08
Nodes (61): activity_analyses table, AIClient abstraction, analyze_activity AI tool, Background task plan generation, build_weekly_summary function, Claude Sonnet 4.6 AI model, DELETE /goal/{goal_id} endpoint, FakeFitnessChatAIClient test double (+53 more)

### Community 1 - "Strava Webhook & Repository Layer"
Cohesion: 0.07
Nodes (31): AnalysisGenerationError, analyze_activity(), build_weekly_summary(), AsyncConnection, UUID, Analyze an activity against its planned workout via Claude.      Returns the ana, Generate a human-readable weekly summary by calling Claude once.      Fetches al, build_activity_analysis_messages() (+23 more)

### Community 2 - "AI Provider Clients & Test Fakes"
Cohesion: 0.08
Nodes (24): AnthropicClient, Async AI client backed by the Anthropic Messages API.      Uses tool use (functi, AIResponse, TokenUsage, ToolCall, GeminiClient, Async AI client backed by Google's Generative AI (Gemini).      The ``google-gen, get_pool() (+16 more)

### Community 3 - "Architecture Vision & Project Docs"
Cohesion: 0.07
Nodes (42): athlete_facts Table, Differential Prompting (Memory Extraction), ARCHITECTURE.md v2.0 (Hybrid: Time-Based Tiers + Entity State Machine), 4-Tier Memory Model, Goal-Setting Flow (Web Form + Chat), Rationale: JSONB Blob Staleness Problem (healed injuries never leave prompt), memories_semantic Table (pgvector), Monthly Memory Decay Cron (+34 more)

### Community 4 - "Goal & Plan API Core"
Cohesion: 0.13
Nodes (33): ABC, generate_plan(), _parse_plan_arguments(), PlanGenerationError, Raised when the AI client returns malformed or unusable plan output., Generate a training plan for a validated goal via the configured AI client., AIClient, get_ai_client() (+25 more)

### Community 5 - "Activity Matching & Strava Client"
Cohesion: 0.12
Nodes (22): match_activity_to_workout(), MatchResult, Match an activity to a planned workout by date + distance plausibility.      can, get_valid_access_token(), Load the stored connection, refresh if expired, return a valid access token., StravaClient, ActivityDetail, TokenSet (+14 more)

### Community 6 - "Goal Validation & Prompt Building"
Cohesion: 0.16
Nodes (26): build_messages(), build_user_prompt(), date, _weeks_until_race(), GoalOutOfScopeError, _parse_target_time(), date, Parse an HH:MM:SS (or H:MM:SS / MM:SS) string into a time. (+18 more)

### Community 7 - "Sports Science Research"
Cohesion: 0.11
Nodes (27): acwr() Function, acwrStatus() Function, aerobicDecoupling() Function, cardiacDrift() Function, formatSessionContext() (Tier C formatter), hrZones() Function, LT Pace & Goal Feasibility Functions (requiredLtPace, goalFeasibility, trainingPhases), singleSessionSpike() Function (+19 more)

### Community 8 - "App Bootstrap & Strava OAuth Tests"
Cohesion: 0.11
Nodes (13): get_strava_client(), connect_ui(), validate_config(), close_pool(), init_pool(), Create and open the global async connection pool., Close the global async connection pool., lifespan() (+5 more)

### Community 9 - "Frontend React Components"
Cohesion: 0.11
Nodes (19): App(), FitnessChat(), assessRace(), assessVdot(), levelFromVdot(), parseTimeToSeconds(), RACE_DISTANCES, vdotFromRace() (+11 more)

### Community 10 - "Strava Connections & Changelog Scripts"
Cohesion: 0.11
Nodes (15): AsyncConnection, strava_callback(), strava_connect(), strava_disconnect(), strava_status(), StravaConnectionRepository, git_log(), last_date_in_changelog() (+7 more)

### Community 11 - "Frontend Package Config"
Cohesion: 0.12
Nodes (15): dependencies, react, react-dom, react-router-dom, devDependencies, vite, @vitejs/plugin-react, name (+7 more)

### Community 12 - "Goal Endpoint Tests"
Cohesion: 0.27
Nodes (13): _assert_plan_quality(), _race_date(), POST /goal (202) then GET /goal/{goalId}/plan (200 ready). Returns (goalId, plan, _submit_and_fetch_plan(), test_ai_client_called_once(), test_delete_goal(), test_fm_too_fast_rejected(), test_hm_too_fast_rejected() (+5 more)

### Community 13 - "Changelog Skill & History"
Cohesion: 0.40
Nodes (4): Changelog Skill (Manual Git-Log Workflow), Goal Intake & AI Training Plan Generation Bootstrap, Initial Specs and Project Skeleton, Phase 2 Strava Sync & Real-Data Analysis Specs

### Community 14 - "Feature Spec & Implementation Skills"
Cohesion: 0.40
Nodes (5): Feature Spec Skill, specs/mission.md (referenced mission doc), specs/roadmap.md (referenced roadmap doc), specs/tech-stack.md (referenced tech-stack doc), Implementation Doc Skill

## Knowledge Gaps
- **47 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+42 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIClient` connect `Goal & Plan API Core` to `Strava Webhook & Repository Layer`, `AI Provider Clients & Test Fakes`, `Goal Validation & Prompt Building`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `PlanRepository` connect `Strava Webhook & Repository Layer` to `Goal & Plan API Core`, `Goal Validation & Prompt Building`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `ActivityDetail` connect `Activity Matching & Strava Client` to `Strava Webhook & Repository Layer`, `AI Provider Clients & Test Fakes`, `Goal & Plan API Core`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `AIClient` (e.g. with `AnalysisGenerationError` and `PlanGenerationError`) actually correct?**
  _`AIClient` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `GoalRequest` (e.g. with `PlanGenerationError` and `GoalOutOfScopeError`) actually correct?**
  _`GoalRequest` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `PlanRepository` (e.g. with `_WebhookEvent` and `GoalRequest`) actually correct?**
  _`PlanRepository` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `ActivityDetail` (e.g. with `AnalysisGenerationError` and `MatchResult`) actually correct?**
  _`ActivityDetail` has 7 INFERRED edges - model-reasoned connections that need verification._