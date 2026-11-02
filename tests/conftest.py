import sys
from pathlib import Path

# Make agent/ importable as top-level modules (config, client, deploy_agent)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))

# Make the chat app importable as `app` (spcs/app)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spcs"))
