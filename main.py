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


@dataclass
class ConstraintSet:
    budget_fiat: float
    timeline_weeks: int
    prefer_gas: bool
    prefer_induction: bool
    noise_sensitive: bool
    child_friendly: bool
    wheelchair_accessible: bool
    notes: str = ""


@dataclass
class LayoutIdea:
    style_label: str
    risk_tier: int
    ergonomics_score: float
    storage_score: float
    vibe_score: float
    narrative: str
    plan_id_hint: str = ""
    key_zones: List[str] = field(default_factory=list)


@dataclass
class DesignSession:
    room: RoomMetrics
    appliances: List[ApplianceSpec]
    constraints: ConstraintSet
    ideas: List[LayoutIdea] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2)


class LayoutHeuristics:
    @staticmethod
    def _area(room: RoomMetrics) -> float:
        return max(room.width_m * room.depth_m, 0.0)

    @staticmethod
    def suggest_risk_tier(room: RoomMetrics, constraints: ConstraintSet) -> int:
        base = 2
        if constraints.budget_fiat > 80_000:
            base += 1
        if constraints.budget_fiat > 150_000:
            base += 1
        if constraints.child_friendly:
            base -= 1
        if constraints.wheelchair_accessible:
            base -= 1
        if room.width_m * room.depth_m > 25:
            base += 1
        return min(max(base, 0), len(RISK_TIER_LABELS) - 1)

    @staticmethod
    def compute_ergonomics(room: RoomMetrics, appliances: List[ApplianceSpec]) -> float:
        triangle_bonus = 0.0
        if any("sink" in a.name.lower() for a in appliances):
            triangle_bonus += 1.5
        if any("hob" in a.name.lower() or "cooktop" in a.name.lower() for a in appliances):
            triangle_bonus += 1.5
        if any("fridge" in a.name.lower() for a in appliances):
            triangle_bonus += 1.5

        area = LayoutHeuristics._area(room)
        density_penalty = 0.0
        if area > 0:
            density = len(appliances) / area
            if density > 0.5:
                density_penalty = (density - 0.5) * 4.0

