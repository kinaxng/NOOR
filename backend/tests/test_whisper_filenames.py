from app.pipeline.whisper.filenames import clean_media_stem


def test_clean_media_stem_preserves_normal_words_starting_with_ch() -> None:
    assert clean_media_stem("AAAAAA-chain-test.mp4") == "AAAAAA-chain-test"
    assert clean_media_stem("CHIKA-001.mp4") == "CHIKA-001"


def test_clean_media_stem_removes_only_trailing_version_and_subtitle_markers() -> None:
    assert clean_media_stem("SNIS-063-破解-C.mp4") == "SNIS-063"
    assert clean_media_stem("SNIS-063-UC.mkv") == "SNIS-063"
    assert clean_media_stem("SNIS-063.zh-CN.mp4") == "SNIS-063"
    assert clean_media_stem("SNIS-063_中文字幕.mp4") == "SNIS-063"
