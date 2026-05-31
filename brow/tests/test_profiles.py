import pytest


@pytest.fixture
def pm(tmp_brow_home):
    from brow.profiles import ProfileManager

    return ProfileManager()


def test_get_or_create_profile(pm):
    path = pm.get_profile_dir("gmail")
    assert path.exists()
    assert path.name == "gmail"


def test_list_profiles(pm):
    pm.get_profile_dir("gmail")
    pm.get_profile_dir("work")
    profiles = pm.list()
    assert set(profiles) == {"gmail", "work"}


def test_delete_profile(pm):
    pm.get_profile_dir("gmail")
    pm.delete("gmail")
    assert "gmail" not in pm.list()


def test_delete_nonexistent(pm):
    with pytest.raises(KeyError):
        pm.delete("nope")


def test_save_state(pm):
    state = {"cookies": [{"name": "a", "value": "b"}], "origins": []}
    pm.save_state("gmail-auth", state)
    loaded = pm.load_state("gmail-auth")
    assert loaded == state


def test_load_nonexistent_state(pm):
    with pytest.raises(FileNotFoundError):
        pm.load_state("nope")


def test_list_states(pm):
    pm.save_state("s1", {"cookies": []})
    pm.save_state("s2", {"cookies": []})
    assert set(pm.list_states()) == {"s1", "s2"}
