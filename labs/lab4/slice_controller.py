#!/usr/bin/env python3
"""
Compatibility wrapper for the revised Lab 4 controller.

The current Lab 4 materials use `slice_controller_v2.py` as the canonical
implementation. This wrapper exists so older notes or commands that still call
`slice_controller.py` continue to work.
"""

from slice_controller_v2 import main


if __name__ == "__main__":
    main()
