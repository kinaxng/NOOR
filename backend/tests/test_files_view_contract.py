from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILES_VIEW = ROOT / "frontend" / "src" / "views" / "FilesView.vue"
ROUTER = ROOT / "frontend" / "src" / "router" / "index.ts"
SIDEBAR = ROOT / "frontend" / "src" / "components" / "noor" / "AppSidebar.vue"


def test_files_view_keeps_hardlink_actor_and_browser_tabs() -> None:
    text = FILES_VIEW.read_text(encoding="utf-8")

    assert "import HardlinkView from './HardlinkView.vue'" in text
    assert "import ActorManagementView from './ActorManagementView.vue'" in text
    assert "import FileBrowserView from './FileBrowserView.vue'" in text
    assert "files.tab.hardlinks" in text
    assert "files.tab.actors" in text
    assert "files.tab.browser" in text
    assert "import VisionTabs" in text
    assert "<VisionTabs" in text
    assert "files-title" not in text
    assert "router.push(`/files/${tab}`)" in text


def test_files_router_and_sidebar_use_files_section() -> None:
    router_text = ROUTER.read_text(encoding="utf-8")
    sidebar_text = SIDEBAR.read_text(encoding="utf-8")

    assert "{ path: '/files/:fileTab?', name: 'files', component: () => import('../views/FilesView.vue') }" in router_text
    assert "{ path: '/hardlinks', redirect: '/files/hardlinks' }" in router_text
    assert "path: '/files'" in sidebar_text
