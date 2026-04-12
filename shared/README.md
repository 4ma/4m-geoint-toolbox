# Shared Utilities

Common code used across multiple tools. Import from here instead of copy-pasting.

## Available modules

| Module | What it provides |
|--------|-----------------|
| `db.py` | `get_engine()` — SQLAlchemy engine from `.env` credentials |

## Usage from a tool

```python
import sys
from pathlib import Path

# Add repo root to path so shared imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.db import get_engine

engine = get_engine(env_path=Path(__file__).parent / ".env")
```

## Adding new shared modules

If you find yourself writing the same code in 2+ tools, move it here. Keep modules small and focused — one responsibility per file.
