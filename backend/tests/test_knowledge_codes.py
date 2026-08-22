from app.knowledge.codes import extract_video_code, extract_video_code_candidates


def test_video_code_candidates_normalize_common_tracker_formats():
    assert extract_video_code_candidates("SNOS-136") == ["SNOS-136"]
    assert "FC2-PPV-4883172" in extract_video_code_candidates("FC2PPV 4883172")
    assert "FC2-PPV-4886227" in extract_video_code_candidates("PPV4886227")
    assert "1PON-050126-001" in extract_video_code_candidates("050126_001-1PON")
    assert "CARIB-043026-001" in extract_video_code_candidates("043026-001-CARIB")


def test_video_code_candidates_keep_variant_and_canonical_code():
    assert extract_video_code_candidates("/downloads/MIDA-669-C.mp4") == ["MIDA-669-C", "MIDA-669"]
    assert extract_video_code("title MIDA669") == "MIDA-669"
