from inspect import getsource

from app.knowledge import indexer


def test_knowledge_indexer_uses_original_media_library_adapter() -> None:
    source = getsource(indexer.rebuild_knowledge_index)

    assert "media_library_recovery" not in source
    assert "media_library._list_libraries" in source
    assert "media_library._list_items" in source
