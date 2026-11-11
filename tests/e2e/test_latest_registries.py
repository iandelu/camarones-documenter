"""Newer versions against the real public registries: one well-known library each still answers with a stable
version through lib/latest.py's own fetch and parser. Needs network. Run: uv run pytest -m e2e"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

KNOWN = [("Maven", "org.postgresql:postgresql"), ("npm", "react"), ("npm", "@angular/core"), ("PyPI", "requests"),
         ("Go", "golang.org/x/text"), ("NuGet", "Newtonsoft.Json"), ("Packagist", "symfony/console"),
         ("crates.io", "serde"), ("Pub", "http")]


@pytest.mark.parametrize("ecosystem, name", KNOWN)
def test_each_registry_answers_with_a_stable_version(kit, ecosystem, name):
    from lib import latest
    found = latest.parse(ecosystem, latest._fetch(latest.url(ecosystem, name)), name)
    assert found and latest.stable(found), (ecosystem, name, found)


def test_a_library_that_does_not_exist_is_not_found(kit):
    from lib import latest
    with pytest.raises(latest.NotFound):
        latest._fetch(latest.url("npm", "camaron-no-such-package-0d6c1f"))
