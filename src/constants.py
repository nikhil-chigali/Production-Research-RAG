import os
from pathlib import Path
from ml_collections import ConfigDict

paths = ConfigDict()
env = os.getenv("ENV", "dev")

paths = ConfigDict()
paths.root_dir = Path(__file__).parent.parent
paths.data_dir = paths.root_dir / "data" / env
paths.artifacts_dir = paths.root_dir / "artifacts"
