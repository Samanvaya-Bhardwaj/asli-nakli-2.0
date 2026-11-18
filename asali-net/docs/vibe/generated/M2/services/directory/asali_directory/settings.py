from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Read from the environment: JOIN_TOKEN, ADMIN_TOKEN, DATA_DIR."""

    join_token: str
    admin_token: str
    data_dir: Path = Path("/data")
    online_window_s: int = 90
    max_clock_skew_s: int = 120
