from __future__ import annotations

from app.api.endpoints.media_library_helpers import parse_tags
from app.api.endpoints.media_library_listing import merge_group_metadata


def test_parse_tags_detects_facefusion_in_file_path():
    tags = parse_tags('DLDSS-498.mp4', [], '/media/DLDSS-498/facefusion.mp4')
    assert tags['has_facefusion'] is True


def test_parse_tags_does_not_match_partial_words_as_facefusion():
    tags = parse_tags('FFMPEG-498.mp4', [], '/media/FFMPEG-498/FFMPEG-498.mp4')
    assert tags['has_facefusion'] is False


def test_variant_group_promotes_facefusion_tag_from_any_sibling():
    plain = {
        'id': 'plain',
        'name': 'DLDSS-498.mp4',
        'path': '/media/DLDSS-498/DLDSS-498.mp4',
        'tags': {'has_facefusion': False},
    }
    output = {
        'id': 'output',
        'name': 'DLDSS-498-facefusion.mp4',
        'path': '/media/DLDSS-498/DLDSS-498-facefusion.mp4',
        'tags': {'has_facefusion': True},
    }

    merged = merge_group_metadata(plain, [plain, output])

    assert merged['tags']['has_facefusion'] is True
