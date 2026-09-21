import pytest

from src.agents.text_utils import find_course_id_mentions, normalize_course_id


@pytest.mark.parametrize(
    "raw",
    ["COMS W4118", "COMS-W4118", "coms w4118", "COMS  W4118", "COMSW4118"],
)
def test_normalize_course_id_collapses_formatting(raw):
    assert normalize_course_id(raw) == "COMSW4118"


def test_find_mentions_handles_space_and_hyphen_formats():
    text = "Take COMS W4118 and COMS-W3157 this term."
    assert find_course_id_mentions(text) == ["COMSW4118", "COMSW3157"]


def test_find_mentions_deduplicates_across_formats():
    assert find_course_id_mentions("COMS W4118, then COMS-W4118 again") == ["COMSW4118"]


def test_find_mentions_recognizes_grad_e_infix():
    assert find_course_id_mentions("COMS E6184 is a grad course") == ["COMSE6184"]


def test_find_mentions_matches_id_glued_to_korean_particle():
    # \b would fail here because Hangul counts as a word character.
    assert find_course_id_mentions("COMS-W4111에 대해 알려줘") == ["COMSW4111"]


def test_find_mentions_does_not_match_inside_longer_tokens():
    assert find_course_id_mentions("ABCDEFGH4118") == []
    assert find_course_id_mentions("COMS 44118") == []


def test_find_mentions_returns_empty_for_plain_text():
    assert find_course_id_mentions("no course ids in here") == []
