from app.routers.interview.community import _status_from_quality


def test_quality_55_is_auto_approved():
    assert _status_from_quality(55) == "approved"


def test_quality_60_is_auto_approved():
    assert _status_from_quality(60) == "approved"


def test_quality_54_is_rejected():
    assert _status_from_quality(54) == "rejected"


def test_quality_40_is_rejected():
    assert _status_from_quality(40) == "rejected"


def test_quality_39_is_rejected():
    assert _status_from_quality(39) == "rejected"
