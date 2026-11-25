"""Provider-agnostic tool definitions (JSON Schema).

These dicts are translated into provider-specific tool/function-calling
formats by the concrete AI clients.
"""

_WORKOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "day": {
            "type": "string",
            "description": "Day of week abbreviation",
            "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        },
        "type": {
            "type": "string",
            "description": "Workout type, e.g. easy, tempo, interval, long, rest, cross",
        },
        "distance_km": {
            "type": "number",
            "description": "Distance of the session in kilometers (0 for rest days)",
        },
        "pace_zone": {
            "type": "string",
            "description": "Heart-rate / pace zone, e.g. Z1-Z5",
        },
        "notes": {
            "type": "string",
            "description": "Coaching notes for the session",
        },
    },
    "required": ["day", "type", "distance_km", "pace_zone"],
}

_WEEK_SCHEMA = {
    "type": "object",
    "properties": {
        "week_number": {"type": "integer"},
        "phase": {
            "type": "string",
            "enum": ["base", "build", "peak", "taper"],
        },
        "workouts": {
            "type": "array",
            "items": _WORKOUT_SCHEMA,
        },
    },
    "required": ["week_number", "phase", "workouts"],
}

ANALYZE_ACTIVITY_TOOL = {
    "name": "analyze_activity",
    "description": "Analyze a completed run against its planned workout across three adherence dimensions",
    "parameters": {
        "type": "object",
        "properties": {
            "pace_adherence": {
                "type": "string",
                "enum": ["on_target", "too_fast", "too_slow"],
                "description": "Was the actual pace within the prescribed zone?",
            },
            "hr_adherence": {
                "type": "string",
                "enum": ["on_target", "above_prescribed", "below_prescribed", "unavailable"],
                "description": "Was average HR consistent with the prescribed effort zone?",
            },
            "load_adherence": {
                "type": "string",
                "enum": ["on_target", "overreaching", "underloaded"],
                "description": "Was total load (volume × intensity) appropriate?",
            },
            "rationale": {
                "type": "string",
                "description": "Brief 1-2 sentence coaching rationale for the adherence assessment",
            },
        },
        "required": ["pace_adherence", "hr_adherence", "load_adherence", "rationale"],
    },
}

TOOLS = [
    {
        "name": "generate_training_plan",
        "description": "Generate a periodized running training plan",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "One-paragraph summary of the plan and its target",
                },
                "total_weeks": {"type": "integer"},
                "phase_breakdown": {
                    "type": "object",
                    "properties": {
                        "base": {"type": "integer"},
                        "build": {"type": "integer"},
                        "peak": {"type": "integer"},
                        "taper": {"type": "integer"},
                    },
                    "required": ["base", "build", "peak", "taper"],
                },
                "weeks": {
                    "type": "array",
                    "items": _WEEK_SCHEMA,
                },
            },
            "required": ["summary", "total_weeks", "phase_breakdown", "weeks"],
        },
    }
]

_DAY_ENUM = {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}

PROPOSE_PLAN_EDIT_TOOL = {
    "name": "propose_plan_edit",
    "description": (
        "Propose a change to the runner's Plan. For each week you change, give every workout of that "
        "week (unchanged days included); weeks you leave out stay as they are. The app checks the change "
        "against the runner's limits and shows it to the runner, who must confirm it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "One or two sentences in the runner's language: what changes and why",
            },
            "weeks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "week_number": {"type": "integer"},
                        "workouts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "day": _DAY_ENUM,
                                    "type": {
                                        "type": "string",
                                        "description": "easy, long, recovery, tempo, interval, repetition, marathon_pace or rest",
                                    },
                                    "distance_km": {"type": "number", "description": "Distance in km (0 for rest)"},
                                    "pace_zone": {"type": "string", "description": "Heart-rate zone, e.g. Z2"},
                                    "notes": {"type": "string"},
                                },
                                "required": ["day", "type", "distance_km"],
                            },
                        },
                    },
                    "required": ["week_number", "workouts"],
                },
            },
            "override": {
                "type": "object",
                "description": (
                    "Only when the runner explicitly asked to break a Weekly availability limit once: "
                    "the one day on which it is broken"
                ),
                "properties": {"week_number": {"type": "integer"}, "day": _DAY_ENUM},
                "required": ["week_number", "day"],
            },
            "goal_change": {
                "type": "object",
                "description": "Only when the request asks to change the Goal's race distance, target time or race date",
                "properties": {
                    "distance": {"type": "string", "enum": ["half_marathon", "full_marathon"]},
                    "target_time": {"type": "string", "description": "H:MM:SS"},
                    "race_date": {"type": "string", "description": "YYYY-MM-DD"},
                },
            },
        },
        "required": ["summary", "weeks"],
    },
}
