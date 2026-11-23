from aios.store.store_version import StoreVersion


def test_versions_compare_number_by_number() -> None:
    assert StoreVersion.newer("1.10.0", "1.9.0")
    assert StoreVersion.newer("v2.0", "1.99.99")
    assert StoreVersion.newer("1.0.1", "1.0")
    assert not StoreVersion.newer("1.0.0", "1.0.0")
    assert not StoreVersion.newer("0.9", "1.0")


def test_a_missing_version_is_never_newer() -> None:
    assert not StoreVersion.newer(None, "1.0")
    assert not StoreVersion.newer("1.0", None)
