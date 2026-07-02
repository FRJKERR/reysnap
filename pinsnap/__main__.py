"""Allow running PinSnap with ``python -m pinsnap``."""

import sys
from .main import main

sys.exit(main())