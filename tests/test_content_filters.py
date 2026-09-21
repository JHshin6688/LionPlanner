from src.pipeline.content_filters import filter_review_noise, filter_syllabus_noise


def test_syllabus_drops_boilerplate_sections_and_images():
    raw = (
        "Intro text ![logo](http://x/y.png)\n"
        "# Grading\nExams 60%\n"
        "# Academic Honesty\nDo not cheat.\n"
        "# Office Hours\nMon 3pm\n"
        "# Projects\nTeam project\n"
    )
    out = filter_syllabus_noise(raw)
    assert "Exams 60%" in out
    assert "Team project" in out
    assert "Do not cheat" not in out
    assert "Mon 3pm" not in out
    assert "![" not in out


def test_syllabus_empty_passthrough():
    assert filter_syllabus_noise("") == ""


def test_review_keeps_only_summary_section():
    raw = (
        "nav junk\n"
        "## AI-Generated Summary\nHeavy workload.\n"
        "## Most Disagreed Review\nnot wanted\n"
        "## All Reviews\nalso not wanted\n"
    )
    out = filter_review_noise(raw)
    assert out.startswith("## AI-Generated Summary")
    assert "Heavy workload." in out
    assert "not wanted" not in out
    assert "nav junk" not in out


def test_review_without_marker_falls_back_to_image_stripping():
    out = filter_review_noise("some text ![img](a.png) more")
    assert "![" not in out
    assert "some text" in out


def test_review_empty_passthrough():
    assert filter_review_noise("") == ""
