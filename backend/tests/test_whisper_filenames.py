from app.pipeline.whisper.filenames import clean_media_stem


def test_clean_media_stem_preserves_normal_words_starting_with_ch() -> None:
    assert clean_media_stem("AAAAAA-chain-test.mp4") == "AAAAAA-chain-test"
    assert clean_media_stem("TEST-026.mp4") == "TEST-026"


def test_clean_media_stem_removes_only_trailing_version_and_subtitle_markers() -> None:
    assert clean_media_stem("TEST-005-破解-C.mp4") == "TEST-005"
    assert clean_media_stem("TEST-005-UC.mkv") == "TEST-005"
    assert clean_media_stem("TEST-005.zh-CN.mp4") == "TEST-005"
    assert clean_media_stem("TEST-005_中文字幕.mp4") == "TEST-005"
