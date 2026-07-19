"""Minimal .env loader: reads KEY=VALUE pairs into os.environ.

Used for e2e tests where the DeepSeek API key is stored in .env (gitignored).
NOT for production code paths.
"""
import os
from pathlib import Path


def load_env(env_path: Path = Path(".env")) -> dict[str, str]:
    """Parse .env file into a dict, also set os.environ for each key."""
    loaded: dict[str, str] = {}
    if not env_path.exists():
        return loaded
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        loaded[k] = v
        os.environ[k] = v
    return loaded


if __name__ == "__main__":
    env = load_env()
    for k in env:
        print(f"{k}: <set, {len(env[k])} chars>")