from src.agents.recommend_course import _find_conflicts, _times_overlap


def test_overlapping_times():
    assert _times_overlap("10:00", "11:00", "10:30", "11:30")
    assert _times_overlap("10:00", "12:00", "10:30", "11:00")  # containment


def test_back_to_back_is_not_a_conflict():
    assert not _times_overlap("10:00", "11:00", "11:00", "12:00")


def test_disjoint_times():
    assert not _times_overlap("08:00", "09:00", "13:00", "14:00")


SCHEDULED = [
    {
        "course_id": "COMS W4111",
        "course_title": "Introduction to Databases",
        "schedule_time": [{"day": "Tue", "start": "08:40", "end": "09:55"}],
    }
]


def test_find_conflicts_reports_overlap_on_same_day():
    candidate = [{"day": "Tue", "start": "09:00", "end": "10:15"}]
    conflicts = _find_conflicts(candidate, SCHEDULED)
    assert len(conflicts) == 1
    assert conflicts[0]["conflicts_with_course_id"] == "COMS W4111"
    assert conflicts[0]["candidate_time"] == "09:00-10:15"


def test_find_conflicts_ignores_different_day():
    assert _find_conflicts([{"day": "Wed", "start": "08:40", "end": "09:55"}], SCHEDULED) == []


def test_find_conflicts_skips_incomplete_sessions_and_none():
    assert _find_conflicts([{"day": "Tue", "start": "09:00"}], SCHEDULED) == []
    assert _find_conflicts(None, SCHEDULED) == []
