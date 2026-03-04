#!/usr/bin/env python3
"""
DesignMe — AI kitchen planning and design aid for the KetaVision Solidity contract.

This module can be used as:
- A CLI wizard that walks a user through capturing room metrics and constraints.
- A library for building kitchen design sessions and generating layout ideas.
- An optional web3 client stub to submit summary plans to the on-chain KetaVision registry.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import random
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


APP_NAME = "DesignMe"
APP_VERSION = "1.0.0"


DEFAULT_STYLE_LABELS = [
    "minimalist",
    "warm-wood",
    "industrial",
    "scandi",
    "neo-classic",
    "maximalist",
    "galley-optimized",
    "island-centric",
    "chef-lab",
    "family-hub",
]

RISK_TIER_LABELS = [
    "chill",
    "low",
    "medium",
    "high",
    "degen",
    "max-degen",
    "experimental",
]


@dataclass
class RoomMetrics:
    width_m: float
    depth_m: float
    height_m: float
    windows: int
    doors: int
    gas_line: bool
    water_points: int
    notes: str = ""


@dataclass
class ApplianceSpec:
    name: str
    width_cm: int
    depth_cm: int
    height_cm: int
    must_keep: bool = True
    power_kw: float = 2.0


