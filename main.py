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
    if Web3 is None:
        raise RuntimeError("Install web3 to submit to chain (pip install web3).")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError("Not connected to RPC")

    acct = w3.eth.account.from_key(private_key)
    abi_fragment = [
        {
            "inputs": [
                {"internalType": "bytes32", "name": "planId", "type": "bytes32"},
                {"internalType": "uint8", "name": "layoutStyle", "type": "uint8"},
                {"internalType": "uint8", "name": "riskTier", "type": "uint8"},
                {"internalType": "uint32", "name": "ceilingHeightCm", "type": "uint32"},
                {"internalType": "uint32", "name": "areaCm2", "type": "uint32"},
                {"internalType": "uint16", "name": "applianceCount", "type": "uint16"},
            ],
            "name": "registerPlan",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        }
    ]
    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi_fragment)
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = contract.functions.registerPlan(
        plan_id,
        layout_style,
        risk_tier,
        ceiling_height_cm,
        area_cm2,
        appliance_count,
    ).build_transaction(
        {
            "from": acct.address,
            "nonce": nonce,
            "gas": 450_000,
            "maxFeePerGas": w3.to_wei("2", "gwei"),
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
        }
    )
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return tx_hash.hex()


def main(argv: List[str]) -> int:
    if "--version" in argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    print(f"{APP_NAME} v{APP_VERSION} — AI kitchen planning helper for KetaVision.")
    session = build_session_interactive()
    print("\n=== Suggested layouts ===")
    for idx, idea in enumerate(session.ideas, start=1):
        print(f"\n[{idx}] {idea.style_label} / tier={RISK_TIER_LABELS[idea.risk_tier]}")
        print(
            f"  ergonomics={idea.ergonomics_score:.1f} "
            f"storage={idea.storage_score:.1f} "
            f"vibe={idea.vibe_score:.1f}"
        )
        print(f"  plan hint: {idea.plan_id_hint}")
        print(f"  zones: {', '.join(idea.key_zones)}")
        print(f"  narrative: {idea.narrative}")

    path = os.path.abspath("designme_session.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(session.to_json())
    print(f"\nSession saved to {path}")
    return 0


# ---------------------------------------------------------------------------
# VALIDATION HELPERS
# ---------------------------------------------------------------------------


def validate_room(room: RoomMetrics) -> List[str]:
    """Return list of validation errors for room; empty if valid."""
    errs: List[str] = []
    if room.width_m <= 0 or room.depth_m <= 0:
        errs.append("Width and depth must be positive.")
    if room.height_m <= 0 or room.height_m > 6:
        errs.append("Ceiling height must be in (0, 6] m.")
    if room.windows < 0 or room.doors < 0:
        errs.append("Windows and doors must be non-negative.")
    if room.water_points < 0:
        errs.append("Water points must be non-negative.")
    return errs


def validate_constraints(c: ConstraintSet) -> List[str]:
    """Return list of validation errors for constraints; empty if valid."""
    errs: List[str] = []
    if c.budget_fiat < 0:
        errs.append("Budget must be non-negative.")
    if c.timeline_weeks <= 0 or c.timeline_weeks > 520:
        errs.append("Timeline weeks must be in (0, 520].")
    return errs


def validate_appliance(a: ApplianceSpec) -> List[str]:
    """Return list of validation errors for one appliance; empty if valid."""
    errs: List[str] = []
    if not a.name or not a.name.strip():
        errs.append("Appliance name required.")
    if a.width_cm <= 0 or a.depth_cm <= 0 or a.height_cm <= 0:
        errs.append("Dimensions must be positive.")
    if a.width_cm > 200 or a.depth_cm > 150 or a.height_cm > 250:
        errs.append("Dimensions out of typical range (w<=200, d<=150, h<=250 cm).")
    if a.power_kw < 0 or a.power_kw > 30:
        errs.append("Power should be in [0, 30] kW.")
    return errs


def validate_session(session: DesignSession) -> List[str]:
    """Aggregate validation for a full design session."""
    errs = validate_room(session.room) + validate_constraints(session.constraints)
    for i, a in enumerate(session.appliances):
        for e in validate_appliance(a):
            errs.append(f"Appliance[{i}] {a.name}: {e}")
    return errs


# ---------------------------------------------------------------------------
# REPORT BUILDERS
# ---------------------------------------------------------------------------


def build_room_report(room: RoomMetrics) -> str:
    """Single-line summary of room metrics."""
    area = room.width_m * room.depth_m
    return (
        f"Room {room.width_m:.1f}x{room.depth_m:.1f}m (h={room.height_m:.1f}m), "
        f"area={area:.1f}m², windows={room.windows}, doors={room.doors}, "
        f"gas={room.gas_line}, water_points={room.water_points}"
    )


def build_constraints_report(c: ConstraintSet) -> str:
    """Single-line summary of constraints."""
    return (
        f"Budget={c.budget_fiat:.0f}, timeline={c.timeline_weeks}w, "
        f"gas={c.prefer_gas}, induction={c.prefer_induction}, "
        f"noise_sensitive={c.noise_sensitive}, child_friendly={c.child_friendly}, "
        f"accessible={c.wheelchair_accessible}"
    )


def build_ideas_report(ideas: List[LayoutIdea]) -> List[str]:
    """List of short summaries for each layout idea."""
    lines: List[str] = []
    for i, idea in enumerate(ideas, 1):
        avg = (idea.ergonomics_score + idea.storage_score + idea.vibe_score) / 3.0
        lines.append(
            f"  [{i}] {idea.style_label} tier={RISK_TIER_LABELS[idea.risk_tier]} "
            f"ergo={idea.ergonomics_score:.1f} storage={idea.storage_score:.1f} "
            f"vibe={idea.vibe_score:.1f} avg={avg:.1f} hint={idea.plan_id_hint}"
        )
    return lines


def build_session_report(session: DesignSession) -> str:
    """Full text report for a design session."""
    parts = [
        "=== DesignMe Session Report ===",
        build_room_report(session.room),
        build_constraints_report(session.constraints),
        f"Appliances: {len(session.appliances)}",
    ]
    for a in session.appliances:
        parts.append(f"  - {a.name} {a.width_cm}x{a.depth_cm}x{a.height_cm}cm power={a.power_kw}kW")
    parts.append("Layout ideas:")
    parts.extend(build_ideas_report(session.ideas))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CONFIG / CONSTANTS REFERENCE
# ---------------------------------------------------------------------------

DEFAULT_MIN_WIDTH_M = 1.5
DEFAULT_MAX_WIDTH_M = 15.0
DEFAULT_MIN_DEPTH_M = 1.5
DEFAULT_MAX_DEPTH_M = 15.0
DEFAULT_MIN_HEIGHT_M = 2.0
DEFAULT_MAX_HEIGHT_M = 5.0
DEFAULT_MIN_BUDGET = 0.0
DEFAULT_MAX_BUDGET = 5_000_000.0
DEFAULT_MIN_TIMELINE_WEEKS = 1
DEFAULT_MAX_TIMELINE_WEEKS = 104
MAX_APPLIANCES_PER_SESSION = 64
MAX_IDEAS_PER_SESSION = 20
KV_MAX_STYLE_INDEX = 15
KV_MAX_TIER_INDEX = 6
KV_SCORE_MIN = 1
KV_SCORE_MAX = 10


def get_style_label(index: int) -> str:
    """Map style index to label; out of range returns 'unknown'."""
    if 0 <= index < len(DEFAULT_STYLE_LABELS):
        return DEFAULT_STYLE_LABELS[index]
    return "unknown"


def get_tier_label(index: int) -> str:
    """Map risk tier index to label; out of range returns 'unknown'."""
    if 0 <= index < len(RISK_TIER_LABELS):
        return RISK_TIER_LABELS[index]
    return "unknown"


# ---------------------------------------------------------------------------
# RUNBOOK / PROCEDURES
# ---------------------------------------------------------------------------

RUNBOOK_STEPS = [
    "1. Capture room metrics (width, depth, height, windows, doors, gas, water).",
    "2. Add appliances (name, dimensions, power, must-keep).",
    "3. Set constraints (budget, timeline, gas/induction, child-friendly, accessible).",
    "4. Generate layout ideas (heuristics: ergonomics, storage, vibe).",
    "5. Optionally export session JSON or submit plan to KetaVision contract.",
]


def get_runbook() -> List[str]:
    """Return runbook steps for DesignMe workflow."""
    return list(RUNBOOK_STEPS)


def print_runbook() -> None:
    """Print runbook to stdout."""
    for step in RUNBOOK_STEPS:
        print(step)


# ---------------------------------------------------------------------------
# STATE ENCODER / DECODER (for persistence)
# ---------------------------------------------------------------------------


def encode_session_to_dict(session: DesignSession) -> Dict[str, Any]:
    """Serialize session to a JSON-suitable dict."""
    return dataclasses.asdict(session)


def decode_session_from_dict(data: Dict[str, Any]) -> DesignSession:
    """Deserialize session from a dict (e.g. from JSON)."""
    room_data = data.get("room", {})
    room = RoomMetrics(
        width_m=float(room_data.get("width_m", 0)),
        depth_m=float(room_data.get("depth_m", 0)),
        height_m=float(room_data.get("height_m", 0)),
        windows=int(room_data.get("windows", 0)),
        doors=int(room_data.get("doors", 0)),
        gas_line=bool(room_data.get("gas_line", False)),
        water_points=int(room_data.get("water_points", 0)),
        notes=str(room_data.get("notes", "")),
    )
    appliances: List[ApplianceSpec] = []
    for a in data.get("appliances", []):
        appliances.append(
            ApplianceSpec(
                name=str(a.get("name", "")),
                width_cm=int(a.get("width_cm", 0)),
                depth_cm=int(a.get("depth_cm", 0)),
                height_cm=int(a.get("height_cm", 0)),
                must_keep=bool(a.get("must_keep", True)),
                power_kw=float(a.get("power_kw", 2.0)),
            )
        )
    c_data = data.get("constraints", {})
    constraints = ConstraintSet(
        budget_fiat=float(c_data.get("budget_fiat", 0)),
        timeline_weeks=int(c_data.get("timeline_weeks", 0)),
        prefer_gas=bool(c_data.get("prefer_gas", False)),
        prefer_induction=bool(c_data.get("prefer_induction", True)),
        noise_sensitive=bool(c_data.get("noise_sensitive", False)),
        child_friendly=bool(c_data.get("child_friendly", True)),
        wheelchair_accessible=bool(c_data.get("wheelchair_accessible", False)),
        notes=str(c_data.get("notes", "")),
    )
    ideas: List[LayoutIdea] = []
    for i in data.get("ideas", []):
        ideas.append(
            LayoutIdea(
                style_label=str(i.get("style_label", "")),
                risk_tier=int(i.get("risk_tier", 0)),
                ergonomics_score=float(i.get("ergonomics_score", 0)),
                storage_score=float(i.get("storage_score", 0)),
                vibe_score=float(i.get("vibe_score", 0)),
                narrative=str(i.get("narrative", "")),
                plan_id_hint=str(i.get("plan_id_hint", "")),
                key_zones=list(i.get("key_zones", [])),
            )
        )
    return DesignSession(room=room, appliances=appliances, constraints=constraints, ideas=ideas)


def load_session_from_file(path: str) -> DesignSession:
    """Load a design session from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return decode_session_from_dict(data)


def save_session_to_file(session: DesignSession, path: str) -> None:
    """Save a design session to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(session.to_json())


# ---------------------------------------------------------------------------
# GAS ESTIMATOR (off-chain, approximate)
# ---------------------------------------------------------------------------

GAS_REGISTER_PLAN = 250_000
GAS_RATE_PLAN = 120_000
GAS_PIN_PLAN = 80_000
GAS_SOFT_DELETE = 60_000
GAS_SET_ORACLE = 50_000
GAS_SET_FEE_BPS = 45_000


def estimate_register_plan_gas() -> int:
    return GAS_REGISTER_PLAN


def estimate_rate_plan_gas() -> int:
    return GAS_RATE_PLAN


def get_gas_estimates() -> Dict[str, int]:
    return {
        "registerPlan": GAS_REGISTER_PLAN,
        "ratePlan": GAS_RATE_PLAN,
        "pinPlan": GAS_PIN_PLAN,
        "softDeletePlan": GAS_SOFT_DELETE,
        "setOracle": GAS_SET_ORACLE,
        "setFeeBps": GAS_SET_FEE_BPS,
    }


# ---------------------------------------------------------------------------
# BATCH HELPERS
# ---------------------------------------------------------------------------


def generate_ideas_batch(
    room: RoomMetrics,
    appliances: List[ApplianceSpec],
    constraints: ConstraintSet,
    count: int = 5,
    style_labels: Optional[List[str]] = None,
) -> List[LayoutIdea]:
    """Generate multiple layout ideas; optionally fix style set."""
    ideas: List[LayoutIdea] = []
    styles = style_labels or DEFAULT_STYLE_LABELS
    for i in range(min(count, MAX_IDEAS_PER_SESSION)):
        style = styles[i % len(styles)] if styles else None
        ideas.append(LayoutHeuristics.synthesize_idea(room, appliances, constraints, style_label=style))
    return ideas


def build_session_from_dicts(
    room_dict: Dict[str, Any],
    appliances_list: List[Dict[str, Any]],
    constraints_dict: Dict[str, Any],
    num_ideas: int = 3,
) -> DesignSession:
    """Build a session from raw dicts (e.g. from API or web form)."""
    room = RoomMetrics(
        width_m=float(room_dict.get("width_m", 0)),
        depth_m=float(room_dict.get("depth_m", 0)),
        height_m=float(room_dict.get("height_m", 0)),
        windows=int(room_dict.get("windows", 0)),
        doors=int(room_dict.get("doors", 0)),
        gas_line=bool(room_dict.get("gas_line", False)),
        water_points=int(room_dict.get("water_points", 0)),
        notes=str(room_dict.get("notes", "")),
    )
    appliances: List[ApplianceSpec] = []
    for a in appliances_list:
        appliances.append(
            ApplianceSpec(
                name=str(a.get("name", "")),
                width_cm=int(a.get("width_cm", 60)),
                depth_cm=int(a.get("depth_cm", 60)),
                height_cm=int(a.get("height_cm", 90)),
                must_keep=bool(a.get("must_keep", True)),
                power_kw=float(a.get("power_kw", 2.0)),
            )
        )
    constraints = ConstraintSet(
        budget_fiat=float(constraints_dict.get("budget_fiat", 50000)),
        timeline_weeks=int(constraints_dict.get("timeline_weeks", 8)),
        prefer_gas=bool(constraints_dict.get("prefer_gas", False)),
        prefer_induction=bool(constraints_dict.get("prefer_induction", True)),
        noise_sensitive=bool(constraints_dict.get("noise_sensitive", False)),
        child_friendly=bool(constraints_dict.get("child_friendly", True)),
        wheelchair_accessible=bool(constraints_dict.get("wheelchair_accessible", False)),
        notes=str(constraints_dict.get("notes", "")),
    )
    session = DesignSession(room=room, appliances=appliances, constraints=constraints)
    session.ideas = generate_ideas_batch(room, appliances, constraints, count=num_ideas)
    return session


# ---------------------------------------------------------------------------
# DEMO / QUICK START
# ---------------------------------------------------------------------------


def create_demo_room() -> RoomMetrics:
    """Return a demo room for testing."""
    return RoomMetrics(
        width_m=3.6,
        depth_m=4.0,
        height_m=2.4,
        windows=1,
        doors=1,
        gas_line=False,
        water_points=1,
        notes="Demo room",
    )


def create_demo_appliances() -> List[ApplianceSpec]:
    """Return demo appliances list."""
    return [
        ApplianceSpec("Range cooker 90cm", 90, 60, 90, True, 8.0),
        ApplianceSpec("Fridge-freezer", 60, 65, 200, True, 0.5),
        ApplianceSpec("Dishwasher", 60, 60, 82, True, 2.0),
        ApplianceSpec("Sink unit", 100, 60, 90, True, 0),
    ]


def create_demo_constraints() -> ConstraintSet:
    """Return demo constraints."""
    return ConstraintSet(
        budget_fiat=75_000,
        timeline_weeks=12,
        prefer_gas=False,
        prefer_induction=True,
        noise_sensitive=False,
        child_friendly=True,
        wheelchair_accessible=False,
        notes="Demo constraints",
    )


def create_demo_session() -> DesignSession:
    """Build a full demo session with generated ideas."""
    room = create_demo_room()
    appliances = create_demo_appliances()
    constraints = create_demo_constraints()
    session = DesignSession(room=room, appliances=appliances, constraints=constraints)
    session.ideas = generate_ideas_batch(room, appliances, constraints, count=5)
    return session


def run_demo() -> None:
    """Run demo: create session, print report, save JSON."""
    session = create_demo_session()
    print(build_session_report(session))
    path = os.path.abspath("designme_demo_session.json")
    save_session_to_file(session, path)
    print(f"Demo session saved to {path}")


# ---------------------------------------------------------------------------
# REFERENCE / HELP
# ---------------------------------------------------------------------------


def print_usage() -> None:
    """Print usage and options."""
    print(f"{APP_NAME} v{APP_VERSION}")
    print("Usage: python DesignMe.py [--version] [--runbook] [--demo] [--help]")
    print("  No args: interactive wizard to capture room, appliances, constraints; then generate ideas.")
    print("  --version: print version")
    print("  --runbook: print runbook steps")
    print("  --demo: run demo and save designme_demo_session.json")
    print("  --help: this message")
    print_runbook()


# ---------------------------------------------------------------------------
# CSV EXPORT
# ---------------------------------------------------------------------------

import csv as _csv


def export_ideas_to_csv(ideas: List[LayoutIdea], path: str) -> None:
    """Write layout ideas to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["style_label", "risk_tier", "ergonomics_score", "storage_score", "vibe_score", "plan_id_hint", "narrative"])
        for i in ideas:
            w.writerow([
                i.style_label,
                i.risk_tier,
                f"{i.ergonomics_score:.2f}",
                f"{i.storage_score:.2f}",
                f"{i.vibe_score:.2f}",
                i.plan_id_hint,
                (i.narrative or "")[:200],
            ])


def export_appliances_to_csv(appliances: List[ApplianceSpec], path: str) -> None:
    """Write appliances to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["name", "width_cm", "depth_cm", "height_cm", "must_keep", "power_kw"])
        for a in appliances:
            w.writerow([a.name, a.width_cm, a.depth_cm, a.height_cm, a.must_keep, f"{a.power_kw:.2f}"])


# ---------------------------------------------------------------------------
# ERROR CODES REFERENCE (for KetaVision integration)
# ---------------------------------------------------------------------------

ERROR_CODES = {
    "KV_ORACLE_ONLY": "Only oracle can perform this action",
    "KV_AUDITOR_ONLY": "Only auditor can perform this action",
    "KV_OWNER_ONLY": "Only owner can perform this action",
    "KV_PLAN_EXISTS": "Plan already registered with this id",
    "KV_PLAN_NOT_FOUND": "Plan not found or soft-deleted",
    "KV_ALREADY_PINNED": "Plan already pinned",
    "KV_ALREADY_RATED": "Caller already rated this plan",
    "KV_FEE_TOO_HIGH": "Protocol fee exceeds maximum",
    "KV_PAUSED": "Namespace is paused",
    "KV_INVALID_SCORE": "Rating score out of range",
    "KV_ZERO_ADDRESS": "Zero address not allowed",
}


def get_error_description(code: str) -> str:
    """Return human-readable description for an error code."""
    return ERROR_CODES.get(code, "Unknown error")


def print_error_codes() -> None:
    """Print all known error codes and descriptions."""
    for code, desc in ERROR_CODES.items():
        print(f"  {code}: {desc}")


# ---------------------------------------------------------------------------
# ABI / ENCODING HELPERS (stub for contract calls)
# ---------------------------------------------------------------------------


def abi_encode_register_plan(
    plan_id: Union[bytes, str],
    layout_style: int,
    risk_tier: int,
    ceiling_height_cm: int,
    area_cm2: int,
    appliance_count: int,
) -> Dict[str, Any]:
    """Return dict suitable for encoding registerPlan calldata (stub)."""
    return {
        "method": "registerPlan",
        "params": {
            "planId": plan_id.hex() if hasattr(plan_id, "hex") else plan_id,
            "layoutStyle": layout_style,
            "riskTier": risk_tier,
            "ceilingHeightCm": ceiling_height_cm,
            "areaCm2": area_cm2,
            "applianceCount": appliance_count,
        },
    }


def abi_encode_rate_plan(
    plan_id: Union[bytes, str],
    ergonomics: int,
    storage_score: int,
    vibe: int,
    fee_wei: int = 0,
) -> Dict[str, Any]:
    """Return dict suitable for encoding ratePlan calldata (stub)."""
    return {
        "method": "ratePlan",
        "params": {
            "planId": plan_id.hex() if hasattr(plan_id, "hex") else plan_id,
            "ergonomics": ergonomics,
            "storageScore": storage_score,
            "vibe": vibe,
            "feeWei": fee_wei,
        },
    }


def session_to_ketavision_params(session: DesignSession, style_index: int, tier_index: int) -> Dict[str, Any]:
    """Map a design session and chosen idea to KetaVision register params."""
    room = session.room
    area_cm2 = int(room.width_m * 100 * room.depth_m * 100)
    ceiling_cm = int(room.height_m * 100)
    return {
        "layout_style": style_index,
        "risk_tier": tier_index,
        "ceiling_height_cm": ceiling_cm,
        "area_cm2": area_cm2,
        "appliance_count": len(session.appliances),
    }


# ---------------------------------------------------------------------------
# EXTRA DEMO FLOWS
# ---------------------------------------------------------------------------


def create_minimal_room() -> RoomMetrics:
    """Minimal room for unit-style kitchen."""
    return RoomMetrics(2.0, 1.8, 2.2, 0, 1, False, 1, "Minimal")


def create_large_room() -> RoomMetrics:
    """Large room for chef-lab style."""
    return RoomMetrics(6.0, 5.0, 3.0, 3, 2, True, 3, "Large chef lab")


def create_accessible_room() -> RoomMetrics:
    """Room with accessibility defaults."""
    return RoomMetrics(4.0, 3.5, 2.6, 2, 1, False, 2, "Wheelchair accessible")


def run_validation_demo() -> None:
    """Run validation on demo session and print any errors."""
    session = create_demo_session()
    errs = validate_session(session)
    if not errs:
        print("Validation passed.")
    else:
        for e in errs:
            print(f"  ERROR: {e}")


def run_gas_estimate_demo() -> None:
    """Print gas estimates for common KetaVision operations."""
    print("KetaVision gas estimates (approximate):")
    for name, gas in get_gas_estimates().items():
        print(f"  {name}: {gas}")


# ---------------------------------------------------------------------------
# KEYBOARD / CLI FLAGS
# ---------------------------------------------------------------------------

CLI_VERSION_FLAG = "--version"
CLI_RUNBOOK_FLAG = "--runbook"
CLI_DEMO_FLAG = "--demo"
CLI_HELP_FLAG = "--help"
CLI_LOAD_FLAG = "--load"
CLI_SAVE_FLAG = "--save"
CLI_REPORT_FLAG = "--report"
CLI_CSV_IDEAS_FLAG = "--csv-ideas"
CLI_CSV_APPLIANCES_FLAG = "--csv-appliances"
CLI_VALIDATE_FLAG = "--validate"
CLI_GAS_FLAG = "--gas"
CLI_ERRORS_FLAG = "--errors"


def handle_cli_load(path: str) -> DesignSession:
    """Load session from file and return it."""
    return load_session_from_file(path)


def handle_cli_save(session: DesignSession, path: str) -> None:
    """Save session to file."""
    save_session_to_file(session, path)


def handle_cli_report(session: DesignSession) -> None:
    """Print full session report."""
    print(build_session_report(session))


# ---------------------------------------------------------------------------
# STRING / DISPLAY HELPERS
# ---------------------------------------------------------------------------


def format_idea_one_line(idea: LayoutIdea) -> str:
    """Single line for one layout idea."""
    avg = (idea.ergonomics_score + idea.storage_score + idea.vibe_score) / 3.0
    return f"{idea.style_label} tier={idea.risk_tier} avg={avg:.1f} {idea.plan_id_hint}"


def format_room_one_line(room: RoomMetrics) -> str:
    """Single line for room."""
    return f"{room.width_m}x{room.depth_m}x{room.height_m}m w={room.windows} d={room.doors}"


def format_appliance_one_line(a: ApplianceSpec) -> str:
    """Single line for one appliance."""
    return f"{a.name} {a.width_cm}x{a.depth_cm}x{a.height_cm}cm {a.power_kw}kW"


def ideas_to_markdown(ideas: List[LayoutIdea]) -> str:
    """Convert ideas to a simple markdown list."""
    lines = ["## Layout ideas", ""]
    for i, idea in enumerate(ideas, 1):
        lines.append(f"{i}. **{idea.style_label}** (tier {idea.risk_tier})")
        lines.append(f"   - Ergonomics: {idea.ergonomics_score:.1f}, Storage: {idea.storage_score:.1f}, Vibe: {idea.vibe_score:.1f}")
        lines.append(f"   - {idea.narrative or idea.plan_id_hint}")
        lines.append("")
    return "\n".join(lines)


def session_to_markdown(session: DesignSession) -> str:
    """Convert full session to markdown."""
    parts = [
        "# DesignMe Session",
        "",
        "## Room",
        format_room_one_line(session.room),
        "",
        "## Appliances",
    ]
    for a in session.appliances:
        parts.append(f"- {format_appliance_one_line(a)}")
    parts.append("")
    parts.append(ideas_to_markdown(session.ideas))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# REFERENCE: KETAVISION CONTRACT BOUNDS
# ---------------------------------------------------------------------------
# layoutStyle: 0..15 (DEFAULT_STYLE_LABELS index or contract enum)
# riskTier: 0..6 (RISK_TIER_LABELS index)
# ceilingHeightCm: 200..600 (2m..6m in cm)
# areaCm2: positive, typically 40000..1000000 (4m²..100m²)
# applianceCount: 0..255
# rating scores: 1..10 (ergonomics, storage, vibe)
# feeBps: 0..500 (max 5%)
# ---------------------------------------------------------------------------


def clamp_style_index(idx: int) -> int:
    """Clamp style index to valid range for KetaVision."""
    return max(0, min(KV_MAX_STYLE_INDEX, idx))


def clamp_tier_index(idx: int) -> int:
    """Clamp risk tier index to valid range for KetaVision."""
    return max(0, min(KV_MAX_TIER_INDEX, idx))


def clamp_ceiling_height_cm(h_cm: int) -> int:
    """Clamp ceiling height to typical 200..600 cm."""
    return max(200, min(600, h_cm))


def clamp_rating_score(score: float) -> int:
    """Clamp and round rating to 1..10 for contract."""
    return max(KV_SCORE_MIN, min(KV_SCORE_MAX, int(round(score))))


def room_to_ceiling_cm(room: RoomMetrics) -> int:
    """Convert room height to ceiling height in cm for contract."""
    return clamp_ceiling_height_cm(int(room.height_m * 100))


def room_to_area_cm2(room: RoomMetrics) -> int:
    """Convert room dimensions to area in cm² for contract."""
    area_m2 = room.width_m * room.depth_m
    return max(1, int(area_m2 * 100 * 100))


def get_best_idea_by_ergonomics(session: DesignSession) -> Optional[LayoutIdea]:
    """Return the layout idea with highest ergonomics score, or None if no ideas."""
    if not session.ideas:
        return None
    return max(session.ideas, key=lambda i: i.ergonomics_score)


def get_best_idea_by_storage(session: DesignSession) -> Optional[LayoutIdea]:
    """Return the layout idea with highest storage score, or None if no ideas."""
    if not session.ideas:
        return None
    return max(session.ideas, key=lambda i: i.storage_score)


def get_best_idea_by_vibe(session: DesignSession) -> Optional[LayoutIdea]:
