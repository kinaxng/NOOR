from __future__ import annotations

from app.api.endpoints.media_library_helpers import parse_item, parse_tags
from app.api.endpoints.media_library_listing import apply_filter_and_paginate, merge_group_metadata


def test_parse_tags_detects_facefusion_in_file_path():
    tags = parse_tags('DLDSS-498.mp4', [], '/media/DLDSS-498/facefusion.mp4')
    assert tags['has_facefusion'] is True


def test_parse_tags_does_not_match_partial_words_as_facefusion():
    tags = parse_tags('FFMPEG-498.mp4', [], '/media/FFMPEG-498/FFMPEG-498.mp4')
    assert tags['has_facefusion'] is False


def test_parse_tags_does_not_treat_title_uncensored_crack_as_uncensored_release():
    tags = parse_tags('DLDSS-498 無碼破解.mp4', [], '/media/DLDSS-498/DLDSS-498-u.mp4')

    assert tags['is_cracked'] is True
    assert tags['is_uncensored'] is False
    assert tags['release_type_key'] is None


def test_parse_tags_does_not_infer_uncensored_from_variant_filename():
    tags = parse_tags('DLDSS-498 無碼破解.mp4', [], '/media/DLDSS-498/DLDSS-498-uncensored.mp4')

    assert tags['is_cracked'] is True
    assert tags['is_uncensored'] is False
    assert tags['release_type_key'] is None


def test_parse_tags_treats_uc_as_cracked_and_chinese():
    tags = parse_tags('SNIS-063-UC.mp4', [], '/media/SNIS-063/SNIS-063-UC.mp4')
    assert tags['is_cracked'] is True
    assert tags['has_chinese'] is True


def test_parse_tags_detects_uncensored_release_from_path_or_studio():
    by_path = parse_tags('HEYZO-123.mp4', [], '/media/heyzo/HEYZO-123.mp4')
    by_studio = parse_tags('ABC-123.mp4', ['Tokyo-Hot'], '/media/ABC-123/ABC-123.mp4')

    assert by_path['is_uncensored'] is True
    assert by_path['release_type_key'] == 'uncensored'
    assert by_studio['is_uncensored'] is True
    assert by_studio['release_type_key'] == 'uncensored'


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


def test_variant_group_promotes_uncensored_tag_from_any_sibling():
    plain = {
        'id': 'plain',
        'name': 'DLDSS-498.mp4',
        'path': '/media/DLDSS-498/DLDSS-498.mp4',
        'tags': {'is_uncensored': False},
    }
    output = {
        'id': 'output',
        'name': 'DLDSS-498-heyzo.mp4',
        'path': '/media/DLDSS-498/DLDSS-498-heyzo.mp4',
        'tags': {'is_uncensored': True},
    }

    merged = merge_group_metadata(plain, [plain, output])

    assert merged['tags']['is_uncensored'] is True


def test_media_library_pagination_response_shape():
    items = [
        {'id': '1', 'name': 'AAA-001', 'tags': {'is_cracked': True}},
        {'id': '2', 'name': 'AAA-002', 'tags': {'is_cracked': False}},
        {'id': '3', 'name': 'AAA-003', 'tags': {'is_cracked': True}},
    ]

    payload = apply_filter_and_paginate(items, 'cracked', None, 1, 1)

    assert payload == {
        'items': [{'id': '3', 'name': 'AAA-003', 'tags': {'is_cracked': True}}],
        'total': 2,
        'offset': 1,
        'limit': 1,
    }


def test_parse_item_exposes_fanart_path():
    item = {
        "Id": "123",
        "Name": "ABC-123",
        "Type": "Movie",
        "MediaType": "Video",
        "ImageTags": {"Primary": "poster-tag"},
        "BackdropImageTags": ["backdrop-tag"],
        "MediaSources": [],
    }

    parsed = parse_item(item, {"server_url": "http://emby"})

    assert parsed["poster_path"] == "http://emby/emby/Items/123/Images/Primary?tag=poster-tag"
    assert parsed["fanart_path"] == "http://emby/emby/Items/123/Images/Backdrop?tag=backdrop-tag"
