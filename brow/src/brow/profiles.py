import json
import shutil
import brow.config as cfg

class ProfileManager:
    def __init__(self):
        cfg.ensure_dirs()

    def get_profile_dir(self, name):
        p = cfg.PROFILES_DIR / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def list(self):
        if not cfg.PROFILES_DIR.exists():
            return []
        return [d.name for d in cfg.PROFILES_DIR.iterdir() if d.is_dir()]

    def delete(self, name):
        p = cfg.PROFILES_DIR / name
        if not p.exists():
            raise KeyError(f"Profile '{name}' not found")
        shutil.rmtree(p)

    def save_state(self, name, state):
        cfg.ensure_dirs()
        (cfg.STATES_DIR / f"{name}.json").write_text(json.dumps(state, indent=2))

    def load_state(self, name):
        path = cfg.STATES_DIR / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"State '{name}' not found")
        return json.loads(path.read_text())

    def list_states(self):
        if not cfg.STATES_DIR.exists():
            return []
        return [p.stem for p in cfg.STATES_DIR.glob("*.json")]
