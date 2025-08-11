"""
Load environment variables from config.env file
"""

import os
from pathlib import Path

def load_env():
    """Load environment variables from config.env file"""
    env_file = Path("config.env")
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key] = value

# Load environment variables when this module is imported
load_env() 