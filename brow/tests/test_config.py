from brow.config import BROW_HOME, ensure_dirs

def test_ensure_dirs(tmp_brow_home):
    ensure_dirs()
    assert BROW_HOME.exists()
