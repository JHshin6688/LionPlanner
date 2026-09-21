from src.pipeline.diff_engine import calculate_hash, has_content_changed


def test_hash_is_deterministic_and_content_sensitive():
    assert calculate_hash("abc") == calculate_hash("abc")
    assert calculate_hash("abc") != calculate_hash("abd")


def test_hash_treats_none_like_empty_string():
    assert calculate_hash(None) == calculate_hash("")


def test_unchanged_when_both_hashes_match():
    assert not has_content_changed("s", "r", "s", "r")


def test_changed_when_either_hash_differs():
    assert has_content_changed("s2", "r", "s", "r")
    assert has_content_changed("s", "r2", "s", "r")


def test_changed_when_no_previous_hashes():
    assert has_content_changed("s", "r", None, None)
