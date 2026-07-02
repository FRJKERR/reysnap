"""Allow running ReySnap with ``python -m reysnap``."""

import sys
from .main import main

sys.exit(main())