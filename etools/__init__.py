# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""ETools -- ETL with first-class provenance, and financial data retrieval."""

from .core.run import current, run

__version__ = "0.1.0"
__all__ = ["run", "current", "__version__"]
