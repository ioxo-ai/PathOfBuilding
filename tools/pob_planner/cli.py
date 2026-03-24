#!/usr/bin/env python3
"""PoB Build Planner CLI - Main entry point.

Usage:
    python -m tools.pob_planner.cli defense <build.xml>
    python -m tools.pob_planner.cli transition <build_a.xml> <build_b.xml> [--type leveling|respec]
    python -m tools.pob_planner.cli gems [--active "Fireball"] [--max-supports 5] [--top 20]
    python -m tools.pob_planner.cli full <build.xml>
"""

import argparse
import sys
from pathlib import Path

from .build_parser import PoBBuild
from .defense_checker import run_defense_check, format_defense_report
from .build_transition import (
    diff_builds,
    plan_respec_transition,
    plan_leveling_transition,
    format_transition_report,
    TransitionType,
)
from .gem_explorer import (
    build_gem_database,
    find_best_combos,
    format_gem_explorer_report,
)


def find_pob_src() -> Path:
    """Find the PoB src directory relative to this script."""
    # Try relative to this file
    tool_dir = Path(__file__).resolve().parent
    pob_root = tool_dir.parent.parent
    src_dir = pob_root / "src"
    if src_dir.exists():
        return src_dir

    # Try current working directory
    cwd_src = Path.cwd() / "src"
    if cwd_src.exists():
        return cwd_src

    raise FileNotFoundError(
        "Cannot find PoB src directory. Run from the PoB root or set POB_SRC env var."
    )


def cmd_defense(args: argparse.Namespace) -> None:
    """Run defense assertion check on a build."""
    build = PoBBuild.from_xml_file(args.build)
    issues = run_defense_check(build)
    report = format_defense_report(build, issues)
    print(report)

    if args.json:
        import json
        result = {
            "build_name": build.name,
            "level": build.level,
            "class": build.ascend_class_name or build.class_name,
            "issues": [
                {
                    "category": i.category,
                    "name": i.name,
                    "severity": i.severity.name,
                    "current": i.current_value,
                    "target": i.target_value,
                    "description": i.description,
                    "suggestions": [
                        {"type": s.source_type, "description": s.description, "slot": s.slot_or_location}
                        for s in i.suggestions
                    ],
                }
                for i in issues
            ],
        }
        print("\n--- JSON Output ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_transition(args: argparse.Namespace) -> None:
    """Generate build transition plan."""
    build_a = PoBBuild.from_xml_file(args.build_a)
    build_b = PoBBuild.from_xml_file(args.build_b)

    diff = diff_builds(build_a, build_b)

    if args.type == "leveling":
        trans_type = TransitionType.LEVELING
        steps = plan_leveling_transition(build_b, current_level=build_a.level)
    else:
        trans_type = TransitionType.RESPEC
        steps = plan_respec_transition(build_a, build_b, diff)

    report = format_transition_report(build_a, build_b, diff, steps, trans_type)
    print(report)


def cmd_gems(args: argparse.Namespace) -> None:
    """Explore gem combinations."""
    src_dir = find_pob_src()
    print(f"Loading gem database from {src_dir}...")
    db = build_gem_database(src_dir)
    print(f"Loaded {len(db.active_gems)} active gems, {len(db.support_gems)} support gems")
    print()

    combos = find_best_combos(
        db,
        active_skill_name=args.active,
        max_supports=args.max_supports,
        top_n=args.top,
    )

    title = f"Gem Combos for: {args.active}" if args.active else "Top Gem Combos (All Active Skills)"
    report = format_gem_explorer_report(combos, title)
    print(report)


def cmd_full(args: argparse.Namespace) -> None:
    """Run full analysis: defense check + gem suggestions."""
    build = PoBBuild.from_xml_file(args.build)

    # Defense check
    issues = run_defense_check(build)
    report = format_defense_report(build, issues)
    print(report)

    # Active skills summary
    print("\n" + "=" * 70)
    print("  SKILL SETUP SUMMARY")
    print("=" * 70)
    for sg in build.skill_groups:
        if sg.enabled and sg.active_gems:
            actives = [g.name for g in sg.active_gems]
            supports = [g.name for g in sg.support_gems]
            print(f"\n  [{sg.slot or 'Unassigned'}]")
            print(f"    Active: {', '.join(actives)}")
            if supports:
                print(f"    Supports: {', '.join(supports)}")

    # Gear summary
    print("\n" + "=" * 70)
    print("  GEAR SUMMARY")
    print("=" * 70)
    for slot_name in ["Weapon 1", "Weapon 2", "Helmet", "Body Armour", "Gloves",
                      "Boots", "Amulet", "Ring 1", "Ring 2", "Belt"]:
        item = build.get_equipped_item(slot_name)
        if item:
            rarity_str = f" ({item.rarity})" if item.rarity else ""
            print(f"  {slot_name:15s}: {item.name}{rarity_str}")
        else:
            print(f"  {slot_name:15s}: (empty)")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pob-planner",
        description="PoB Build Planner - Analyze and plan Path of Exile builds",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Defense check
    p_defense = subparsers.add_parser("defense", help="Run defense assertion checks")
    p_defense.add_argument("build", type=Path, help="Path to PoB XML build file")
    p_defense.add_argument("--json", action="store_true", help="Also output JSON format")
    p_defense.set_defaults(func=cmd_defense)

    # Transition planner
    p_trans = subparsers.add_parser("transition", help="Plan build transition A → B")
    p_trans.add_argument("build_a", type=Path, help="Source build XML")
    p_trans.add_argument("build_b", type=Path, help="Target build XML")
    p_trans.add_argument("--type", choices=["leveling", "respec"], default="respec",
                         help="Transition type (default: respec)")
    p_trans.set_defaults(func=cmd_transition)

    # Gem explorer
    p_gems = subparsers.add_parser("gems", help="Explore gem combinations")
    p_gems.add_argument("--active", type=str, default=None,
                        help="Active skill name to optimize supports for")
    p_gems.add_argument("--max-supports", type=int, default=5,
                        help="Max support gems per link (default: 5)")
    p_gems.add_argument("--top", type=int, default=20,
                        help="Number of top results to show (default: 20)")
    p_gems.set_defaults(func=cmd_gems)

    # Full analysis
    p_full = subparsers.add_parser("full", help="Full build analysis")
    p_full.add_argument("build", type=Path, help="Path to PoB XML build file")
    p_full.set_defaults(func=cmd_full)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
