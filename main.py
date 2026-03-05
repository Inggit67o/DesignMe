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

        score = 7.0 + triangle_bonus - density_penalty
        return max(1.0, min(score, 10.0))

    @staticmethod
    def compute_storage_score(room: RoomMetrics, appliances: List[ApplianceSpec]) -> float:
        height_factor = min(room.height_m / 2.4, 1.5)
        base = 6.0 * height_factor
        tall_items = sum(1 for a in appliances if a.height_cm >= 200)
        base += min(tall_items * 0.4, 2.0)
        return max(1.0, min(base, 10.0))

    @staticmethod
    def compute_vibe(room: RoomMetrics, constraints: ConstraintSet, style_label: str) -> float:
        vibe = 5.5
        if "industrial" in style_label:
            vibe += 1.0
        if "warm" in style_label or "wood" in style_label:
            vibe += 0.7
        if constraints.noise_sensitive:
            vibe -= 0.5
        if constraints.child_friendly:
            vibe += 0.4
        if "maximalist" in style_label:
            vibe += 1.3
        return max(1.0, min(vibe, 10.0))

    @staticmethod
    def synthesize_idea(
        room: RoomMetrics,
        appliances: List[ApplianceSpec],
        constraints: ConstraintSet,
        style_label: Optional[str] = None,
        risk_tier: Optional[int] = None,
    ) -> LayoutIdea:
        if style_label is None:
            style_label = random.choice(DEFAULT_STYLE_LABELS)
        if risk_tier is None:
            risk_tier = LayoutHeuristics.suggest_risk_tier(room, constraints)

        ergonomics = LayoutHeuristics.compute_ergonomics(room, appliances)
        storage = LayoutHeuristics.compute_storage_score(room, appliances)
        vibe = LayoutHeuristics.compute_vibe(room, constraints, style_label)

        narrative_parts = [
            f"Style: {style_label}, tier={RISK_TIER_LABELS[risk_tier]}",
            f"Room {room.width_m:.1f}m x {room.depth_m:.1f}m, height {room.height_m:.1f}m.",
            f"Approx {len(appliances)} major appliances.",
        ]
        if constraints.child_friendly:
            narrative_parts.append("Child-friendly clear run in front of hob.")
        if constraints.wheelchair_accessible:
            narrative_parts.append("Maintain turning circles near sink and cooktop.")
        if constraints.prefer_induction:
            narrative_parts.append("Prefer induction over gas for cooktop.")

        key_zones = [
            "prep_zone",
            "cooking_zone",
            "cleaning_zone",
            "pantry_zone",
            "coffee_corner",
        ]

        return LayoutIdea(
            style_label=style_label,
            risk_tier=risk_tier,
            ergonomics_score=ergonomics,
            storage_score=storage,
            vibe_score=vibe,
            narrative=" ".join(narrative_parts),
            plan_id_hint="plan-" + hex(random.getrandbits(64)),
            key_zones=key_zones,
        )


def _prompt_float(prompt: str, default: Optional[float] = None) -> float:
    while True:
        suffix = f" [{default}] " if default is not None else " "
        raw = input(prompt + suffix)
        if not raw and default is not None:
            return float(default)
        try:
            return float(raw)
        except ValueError:
            print("Enter a number.")


def _prompt_int(prompt: str, default: Optional[int] = None) -> int:
    while True:
        suffix = f" [{default}] " if default is not None else " "
        raw = input(prompt + suffix)
        if not raw and default is not None:
            return int(default)
        try:
            return int(raw)
        except ValueError:
            print("Enter an integer.")


def _prompt_bool(prompt: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{prompt} {suffix} ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Enter y or n.")


def capture_room_interactive() -> RoomMetrics:
    print("=== Room metrics ===")
    width = _prompt_float("Width (m)?", 3.6)
    depth = _prompt_float("Depth (m)?", 4.0)
    height = _prompt_float("Ceiling height (m)?", 2.4)
    windows = _prompt_int("Number of windows?", 1)
    doors = _prompt_int("Number of doors?", 1)
    gas_line = _prompt_bool("Gas line available?", False)
    water_points = _prompt_int("Water points (sinks etc.)?", 1)
    notes = input("Freeform notes for AI (optional): ")
    return RoomMetrics(
        width_m=width,
        depth_m=depth,
        height_m=height,
        windows=windows,
        doors=doors,
        gas_line=gas_line,
        water_points=water_points,
        notes=notes,
    )


def capture_appliances_interactive() -> List[ApplianceSpec]:
    print("=== Appliances ===")
    items: List[ApplianceSpec] = []
    while True:
        name = input("Appliance name (blank to finish): ").strip()
        if not name:
            break
        w = _prompt_int("Width (cm)?", 60)
        d = _prompt_int("Depth (cm)?", 60)
        h = _prompt_int("Height (cm)?", 200 if "fridge" in name.lower() else 90)
        must_keep = _prompt_bool("Must keep?", True)
        power = _prompt_float("Approx power (kW)?", 2.0)
        items.append(
            ApplianceSpec(
                name=name,
                width_cm=w,
                depth_cm=d,
                height_cm=h,
                must_keep=must_keep,
                power_kw=power,
            )
        )
    return items


def capture_constraints_interactive() -> ConstraintSet:
    print("=== Constraints ===")
    budget = _prompt_float("Budget (fiat)?", 50_000)
    weeks = _prompt_int("Timeline (weeks)?", 8)
    prefer_gas = _prompt_bool("Prefer gas?", False)
    prefer_induction = _prompt_bool("Prefer induction?", True)
    noise_sensitive = _prompt_bool("Noise sensitive?", False)
    child_friendly = _prompt_bool("Child friendly?", True)
    accessible = _prompt_bool("Wheelchair accessible?", False)
    notes = input("Freeform notes (optional): ")
    return ConstraintSet(
        budget_fiat=budget,
        timeline_weeks=weeks,
        prefer_gas=prefer_gas,
        prefer_induction=prefer_induction,
        noise_sensitive=noise_sensitive,
        child_friendly=child_friendly,
        wheelchair_accessible=accessible,
        notes=notes,
    )


def build_session_interactive() -> DesignSession:
    room = capture_room_interactive()
    appliances = capture_appliances_interactive()
    constraints = capture_constraints_interactive()
    session = DesignSession(room=room, appliances=appliances, constraints=constraints)
    for _ in range(3):
        idea = LayoutHeuristics.synthesize_idea(room, appliances, constraints)
        session.ideas.append(idea)
    return session


def _maybe_import_web3():
    try:
        from web3 import Web3  # type: ignore
    except ImportError:  # pragma: no cover - optional dependency
        return None
    return Web3


def submit_plan_to_ketavision(
    rpc_url: str,
    contract_address: str,
    plan_id: bytes,
    layout_style: int,
    risk_tier: int,
    ceiling_height_cm: int,
    area_cm2: int,
    appliance_count: int,
    private_key: str,
) -> str:
    """
    Minimal stub to call KetaVision.registerPlan; expects the full ABI externally.
    Returns transaction hash, or raises RuntimeError if web3 is not installed.
    """
    Web3 = _maybe_import_web3()
