from __future__ import annotations

import json
from pathlib import Path


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_awesome_forward_project(
    project_dir: str | Path,
    expected_by_page: dict[int, list[str]],
    *,
    page_count: int,
    max_per_page: int = 16,
) -> dict[str, object]:
    project = Path(project_dir)
    v6 = project / "02_v6"
    pagination = _load(v6 / "paginated_word_source.json")
    source_assets = _load(v6 / "source_assets.json")
    errors: list[str] = []

    if pagination.get("pagination_mode") != "explicit_text_markers":
        errors.append(f"wrong_pagination_mode:{pagination.get('pagination_mode')}")
    if int(pagination.get("page_count") or 0) != page_count:
        errors.append(f"wrong_page_count:{pagination.get('page_count')}:{page_count}")

    expected_hash_to_pages: dict[str, list[int]] = {}
    for page in range(1, page_count + 1):
        expected = expected_by_page.get(page, [])
        if len(expected) > max_per_page:
            errors.append(f"expected_page_over_limit:{page}:{len(expected)}")
        for digest in expected:
            expected_hash_to_pages.setdefault(digest, []).append(page)

    actual_hash_to_pages: dict[str, list[int]] = {}
    unresolved = 0
    for asset in source_assets.get("assets", []):
        digest = str(asset.get("sha256") or "")
        pages = [int(value) for value in asset.get("page_numbers", [])]
        actual_hash_to_pages[digest] = pages
        if asset.get("binding_status") != "bound":
            unresolved += 1
            errors.append(f"unresolved_binding:{digest}")

    for digest, expected_pages in expected_hash_to_pages.items():
        actual_pages = actual_hash_to_pages.get(digest)
        if actual_pages != expected_pages:
            errors.append(
                f"binding_mismatch:{digest}:expected={expected_pages}:actual={actual_pages}"
            )
    extra_hashes = sorted(set(actual_hash_to_pages).difference(expected_hash_to_pages))
    if extra_hashes:
        errors.append("unexpected_assets:" + ",".join(extra_hashes))

    pages_with_references = 0
    total_references = 0
    for page in range(1, page_count + 1):
        payload = _load(v6 / "page_sources" / f"page_{page:03d}.json")
        references = [
            reference
            for reference in payload.get("references", [])
            if reference.get("kind") == "word_image"
        ]
        actual_hashes = [str(reference.get("original_sha256") or "") for reference in references]
        expected_hashes = expected_by_page.get(page, [])
        if actual_hashes != expected_hashes:
            errors.append(
                f"page_reference_mismatch:{page}:expected={expected_hashes}:actual={actual_hashes}"
            )
        if len(actual_hashes) > max_per_page:
            errors.append(f"page_reference_over_limit:{page}:{len(actual_hashes)}")
        if actual_hashes:
            pages_with_references += 1
            total_references += len(actual_hashes)

    return {
        "valid": not errors,
        "errors": errors,
        "pagination_mode": pagination.get("pagination_mode"),
        "page_count": pagination.get("page_count"),
        "bound_assets": len(actual_hash_to_pages) - unresolved,
        "unresolved_assets": unresolved,
        "pages_with_references": pages_with_references,
        "total_references": total_references,
        "max_per_page": max_per_page,
    }
