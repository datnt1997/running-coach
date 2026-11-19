import pytest

from app.agent.plan_import import PlanImportError, parse_plan_csv

HEADER = "week,phase,day,type,distance_km,pace_zone,notes"


def test_parses_comma_separated_rows():
    rows = parse_plan_csv(f"{HEADER}\n1,base,Mon,easy,8,E,Relaxed\n1,base,Sat,long,16.5,E,\n")
    assert [(r.week_number, r.day, r.workout_type, r.distance_km) for r in rows] == [
        (1, "Mon", "easy", 8.0),
        (1, "Sat", "long", 16.5),
    ]
    assert rows[0].phase == "base" and rows[0].pace_zone == "E" and rows[0].notes == "Relaxed"
    assert rows[1].notes is None


def test_parses_tab_separated_paste_from_a_sheet():
    rows = parse_plan_csv("week\tphase\tday\ttype\tdistance_km\n2\tIII\ttue\ttempo\t10\n")
    assert rows[0].week_number == 2 and rows[0].day == "Tue" and rows[0].pace_zone is None


def test_blank_lines_are_skipped():
    rows = parse_plan_csv(f"\n{HEADER}\n\n1,base,Mon,easy,8,E,\n\n")
    assert len(rows) == 1


def test_bad_rows_are_all_reported_with_line_numbers_not_guessed():
    text = (
        f"{HEADER}\n"
        "1,base,Mon,easy,8,E,\n"      # line 2 fine
        "x,base,Tue,easy,8,E,\n"      # line 3 bad week
        "1,base,Funday,easy,8,E,\n"   # line 4 bad day
        "1,base,Wed,easy,far,E,\n"    # line 5 bad distance
        "1,base,Thu,easy,-3,E,\n"     # line 6 negative distance
        "1,,Fri,easy,5,E,\n"          # line 7 empty phase
        "1,base,Sat\n"                # line 8 too few cells
    )
    with pytest.raises(PlanImportError) as exc:
        parse_plan_csv(text)
    assert [e.line for e in exc.value.errors] == [3, 4, 5, 6, 7, 8]
    assert all(e.message for e in exc.value.errors)


def test_missing_required_column_is_reported_on_the_header():
    with pytest.raises(PlanImportError) as exc:
        parse_plan_csv("week,day,type,distance_km\n1,Mon,easy,8\n")
    assert exc.value.errors[0].line == 1
    assert "phase" in exc.value.errors[0].message


def test_empty_input_is_an_error():
    with pytest.raises(PlanImportError):
        parse_plan_csv("  \n")
    with pytest.raises(PlanImportError):
        parse_plan_csv(f"{HEADER}\n")
