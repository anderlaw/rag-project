def test_build_search_text_uses_meaningful_document_name_and_structural_fields():
    from app.services.chunker import build_search_text

    search_text = build_search_text(
        document_name="AI获客数据权限相关.md",
        heading_path="一、项目概览 / 1.2 技术栈",
        section_title="1.2 技术栈",
        content="后端使用 FastAPI + PostgreSQL，前端使用 React + Vite。",
    )

    assert "[document_name] AI获客数据权限相关" in search_text
    assert "[heading_path] 一、项目概览 / 1.2 技术栈" in search_text
    assert "[section_title] 1.2 技术栈" in search_text
    assert "[content]\n后端使用 FastAPI + PostgreSQL" in search_text


def test_build_search_text_omits_meaningless_document_name():
    from app.services.chunker import build_search_text

    search_text = build_search_text(
        document_name="文档.md",
        heading_path="一、项目概览 / 1.2 技术栈",
        section_title="1.2 技术栈",
        content="后端使用 FastAPI。",
    )

    assert "[document_name]" not in search_text
    assert "[heading_path] 一、项目概览 / 1.2 技术栈" in search_text
