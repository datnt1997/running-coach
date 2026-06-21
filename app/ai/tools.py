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
                "enum": ["on_target", "above_prescribed", "below_prescribed"],
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
