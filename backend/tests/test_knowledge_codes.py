from app.knowledge.codes import extract_video_code, extract_video_code_candidates


def test_video_code_candidates_normalize_common_tracker_formats():
    assert extract_video_code_candidates("TEST-025") == ["TEST-025"]
    assert "FC2-PPV-1000001" in extract_video_code_candidates("FC2PPV 1000001")
    assert "FC2-PPV-1000002" in extract_video_code_candidates("PPV1000002")
    assert "1PON-050126-001" in extract_video_code_candidates("050126_001-1PON")
    assert "CARIB-010101-001" in extract_video_code_candidates("010101-001-CARIB")


def test_video_code_candidates_keep_variant_and_canonical_code():
    assert extract_video_code_candidates("/downloads/TEST-001-C.mp4") == ["TEST-001-C", "TEST-001"]
    assert extract_video_code("title TEST001") == "TEST-001"
