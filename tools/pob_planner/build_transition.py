"""Feature 2: Build Transition Planner - step-by-step plan from Build A to Build B."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from .build_parser import PoBBuild, GemInfo, SkillGroup, ItemInfo


class TransitionType(IntEnum):
    LEVELING = 1     # New character progressing through acts
    RESPEC = 2       # Existing character respeccing (orbs of regret)


class StepCategory(IntEnum):
    PASSIVE_TREE = 1
    GEMS = 2
    GEAR = 3
    ASCENDANCY = 4
    PANTHEON = 5
    CONFIG = 6


@dataclass
class TransitionStep:
    """A single step in the transition plan."""
    order: int
    category: StepCategory
    action: str          # "add", "remove", "swap", "respec"
    description: str
    details: str = ""
    cost_estimate: str = ""  # e.g., "2 Orbs of Regret", "~10c"
    priority: int = 0        # Higher = do first

    def __str__(self) -> str:
        cat_names = {
            StepCategory.PASSIVE_TREE: "TREE",
            StepCategory.GEMS: "GEMS",
            StepCategory.GEAR: "GEAR",
            StepCategory.ASCENDANCY: "ASCEND",
            StepCategory.PANTHEON: "PANTHEON",
            StepCategory.CONFIG: "CONFIG",
        }
        cost = f" (Cost: {self.cost_estimate})" if self.cost_estimate else ""
        return f"  Step {self.order}: [{cat_names[self.category]}] {self.description}{cost}"


@dataclass
class BuildDiff:
    """Differences between two builds."""
    # Passive tree
    nodes_to_add: set[int] = field(default_factory=set)
    nodes_to_remove: set[int] = field(default_factory=set)
    nodes_unchanged: set[int] = field(default_factory=set)

    # Gems
    gems_to_add: list[GemInfo] = field(default_factory=list)
    gems_to_remove: list[GemInfo] = field(default_factory=list)
    gems_unchanged: list[str] = field(default_factory=list)  # names

    # Gear
    slots_changed: dict[str, tuple[Optional[ItemInfo], Optional[ItemInfo]]] = field(default_factory=dict)
    slots_unchanged: list[str] = field(default_factory=list)

    # Class/Ascendancy
    class_changed: bool = False
    ascendancy_changed: bool = False
    old_class: str = ""
    new_class: str = ""
    old_ascendancy: str = ""
    new_ascendancy: str = ""

    # Other
    level_diff: int = 0
    bandit_changed: bool = False
    pantheon_changed: bool = False


def diff_builds(build_a: PoBBuild, build_b: PoBBuild) -> BuildDiff:
    """Compute the diff between two builds."""
    diff = BuildDiff()

    # Level
    diff.level_diff = build_b.level - build_a.level

    # Class / Ascendancy
    diff.old_class = build_a.class_name
    diff.new_class = build_b.class_name
    diff.class_changed = build_a.class_name != build_b.class_name
    diff.old_ascendancy = build_a.ascend_class_name
    diff.new_ascendancy = build_b.ascend_class_name
    diff.ascendancy_changed = build_a.ascend_class_name != build_b.ascend_class_name

    # Passive tree
    nodes_a = build_a.passive_spec.nodes if build_a.passive_spec else set()
    nodes_b = build_b.passive_spec.nodes if build_b.passive_spec else set()
    diff.nodes_to_add = nodes_b - nodes_a
    diff.nodes_to_remove = nodes_a - nodes_b
    diff.nodes_unchanged = nodes_a & nodes_b

    # Gems
    gems_a = {g.name for sg in build_a.skill_groups for g in sg.gems if g.enabled}
    gems_b = {g.name for sg in build_b.skill_groups for g in sg.gems if g.enabled}

    diff.gems_unchanged = list(gems_a & gems_b)
    for sg in build_b.skill_groups:
        for g in sg.gems:
            if g.enabled and g.name not in gems_a:
                diff.gems_to_add.append(g)
    for sg in build_a.skill_groups:
        for g in sg.gems:
            if g.enabled and g.name not in gems_b:
                diff.gems_to_remove.append(g)

    # Items
    all_slots = set(build_a.item_slots.keys()) | set(build_b.item_slots.keys())
    for slot_name in all_slots:
        item_a = build_a.get_equipped_item(slot_name)
        item_b = build_b.get_equipped_item(slot_name)

        if item_a is None and item_b is None:
            continue

        # Compare by name (simple heuristic)
        name_a = item_a.name if item_a else ""
        name_b = item_b.name if item_b else ""

        if name_a != name_b:
            diff.slots_changed[slot_name] = (item_a, item_b)
        else:
            diff.slots_unchanged.append(slot_name)

    # Bandit / Pantheon
    diff.bandit_changed = build_a.bandit != build_b.bandit
    diff.pantheon_changed = (
        build_a.pantheon_major != build_b.pantheon_major
        or build_a.pantheon_minor != build_b.pantheon_minor
    )

    return diff


def plan_respec_transition(
    build_a: PoBBuild,
    build_b: PoBBuild,
    diff: BuildDiff,
) -> list[TransitionStep]:
    """Generate ordered steps for respeccing from build A to build B."""
    steps: list[TransitionStep] = []
    step_num = 0

    # Phase 1: Immediate safety changes (resistances, defenses via gear)
    # Phase 2: Gem swaps (cheap, instant)
    # Phase 3: Passive respec (costs regrets)
    # Phase 4: Gear upgrades (most expensive)
    # Phase 5: Final tuning (pantheon, bandit)

    # --- Phase 0: Class change warning ---
    if diff.class_changed:
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.CONFIG,
            action="warning",
            description=f"Class change ({diff.old_class} → {diff.new_class}) requires a NEW CHARACTER",
            details="Cannot respec class on existing character. Create new character and level up.",
            priority=100,
        ))

    # --- Phase 1: Ascendancy ---
    if diff.ascendancy_changed and not diff.class_changed:
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.ASCENDANCY,
            action="respec",
            description=f"Respec ascendancy: {diff.old_ascendancy} → {diff.new_ascendancy}",
            details="Use the Altar of Ascendancy in Act 3 Library (requires all Izaro trials for Uber Lab)",
            cost_estimate="Requires running the Labyrinth again",
            priority=90,
        ))

    # --- Phase 2: Gem swaps (do first, free and instant) ---
    if diff.gems_to_remove:
        gem_names = [g.name for g in diff.gems_to_remove]
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.GEMS,
            action="remove",
            description=f"Remove old gems: {', '.join(gem_names)}",
            details="Unsocket or disable these gems",
            priority=80,
        ))

    if diff.gems_to_add:
        # Group by support vs active
        active_adds = [g for g in diff.gems_to_add if not g.is_support]
        support_adds = [g for g in diff.gems_to_add if g.is_support]

        if active_adds:
            names = [f"{g.name} (Lv{g.level})" for g in active_adds]
            step_num += 1
            steps.append(TransitionStep(
                order=step_num,
                category=StepCategory.GEMS,
                action="add",
                description=f"Socket new active gems: {', '.join(names)}",
                details="Purchase from gem vendor or trade",
                cost_estimate="Vendor cost or ~1-5c each",
                priority=75,
            ))

        if support_adds:
            names = [f"{g.name} (Lv{g.level})" for g in support_adds]
            step_num += 1
            steps.append(TransitionStep(
                order=step_num,
                category=StepCategory.GEMS,
                action="add",
                description=f"Socket new support gems: {', '.join(names)}",
                details="Purchase from gem vendor or trade. Level 20/20 gems may need trading.",
                cost_estimate="Varies (1c - 1div for 21/20)",
                priority=74,
            ))

    # --- Phase 3: Passive tree respec ---
    num_regrets = len(diff.nodes_to_remove)
    if num_regrets > 0:
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.PASSIVE_TREE,
            action="respec",
            description=f"Refund {num_regrets} passive points (unallocate old nodes)",
            details=f"Nodes to remove: {len(diff.nodes_to_remove)} points. Use Orbs of Regret.",
            cost_estimate=f"{num_regrets} Orbs of Regret",
            priority=60,
        ))

    num_allocate = len(diff.nodes_to_add)
    if num_allocate > 0:
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.PASSIVE_TREE,
            action="add",
            description=f"Allocate {num_allocate} new passive points",
            details=f"New nodes to allocate: {num_allocate}. Prioritize key nodes (keystones, notables) first.",
            priority=59,
        ))

    # --- Phase 4: Gear changes ---
    # Sort gear by importance: weapons first (biggest DPS impact), then body, then rest
    slot_priority = {
        "Weapon 1": 10, "Weapon 2": 9,
        "Body Armour": 8,
        "Helmet": 7, "Gloves": 6, "Boots": 6,
        "Amulet": 5, "Ring 1": 4, "Ring 2": 4,
        "Belt": 3,
        "Flask 1": 2, "Flask 2": 2, "Flask 3": 2, "Flask 4": 2, "Flask 5": 2,
    }

    sorted_slots = sorted(
        diff.slots_changed.items(),
        key=lambda x: slot_priority.get(x[0], 0),
        reverse=True,
    )

    for slot_name, (old_item, new_item) in sorted_slots:
        step_num += 1
        old_name = old_item.name if old_item else "(empty)"
        new_name = new_item.name if new_item else "(empty)"
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.GEAR,
            action="swap",
            description=f"[{slot_name}] {old_name} → {new_name}",
            details=f"Replace gear in {slot_name} slot",
            priority=50 + slot_priority.get(slot_name, 0),
        ))

    # --- Phase 5: Pantheon & Bandit ---
    if diff.pantheon_changed:
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.PANTHEON,
            action="swap",
            description=f"Change Pantheon: {build_a.pantheon_major}/{build_a.pantheon_minor} → {build_b.pantheon_major}/{build_b.pantheon_minor}",
            details="Visit the Pantheon panel to change god powers",
            priority=10,
        ))

    if diff.bandit_changed:
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.CONFIG,
            action="swap",
            description=f"Change Bandit: {build_a.bandit} → {build_b.bandit}",
            cost_estimate="Book of Reform (20 Orbs of Regret + Lapis Amulet)",
            priority=10,
        ))

    # Sort by priority (highest first) then re-number
    steps.sort(key=lambda s: -s.priority)
    for i, step in enumerate(steps):
        step.order = i + 1

    return steps


def plan_leveling_transition(
    build_target: PoBBuild,
    current_level: int = 1,
) -> list[TransitionStep]:
    """Generate leveling milestones for a fresh character reaching the target build."""
    steps: list[TransitionStep] = []
    step_num = 0

    # Act-based milestones
    act_milestones = [
        (1, 12, "Act 1-2: Use leveling uniques, link your main skill with basic supports"),
        (3, 28, "Act 3: First Labyrinth available, complete first 2 ascendancy points"),
        (4, 38, "Act 4: Siosa in Library sells all gems — acquire target gems here"),
        (6, 50, "Act 6: Resistance penalty (-30% all res). Fix resistances on gear!"),
        (8, 62, "Act 8: Cruel Lab for 4 ascendancy points"),
        (10, 68, "Act 10: Kitava penalty (-60% all res total). Cap resistances immediately!"),
    ]

    for act, lvl, desc in act_milestones:
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.CONFIG,
            action="milestone",
            description=f"Level ~{lvl}: {desc}",
            priority=100 - lvl,
        ))

    # Target build gems
    active_skills = build_target.all_active_skills()
    if active_skills:
        main_skill = active_skills[0]
        step_num += 1
        steps.append(TransitionStep(
            order=step_num,
            category=StepCategory.GEMS,
            action="add",
            description=f"Main skill: {main_skill.name} — start using as early as possible",
            details=f"Target level: {main_skill.level}, quality: {main_skill.quality}",
            priority=85,
        ))

    # Endgame prep
    step_num += 1
    steps.append(TransitionStep(
        order=step_num,
        category=StepCategory.CONFIG,
        action="milestone",
        description=f"Level 68-75: Start mapping. Switch to target gear progressively.",
        priority=30,
    ))

    step_num += 1
    steps.append(TransitionStep(
        order=step_num,
        category=StepCategory.CONFIG,
        action="milestone",
        description=f"Level 85+: Optimize passive tree, acquire final gear pieces",
        priority=20,
    ))

    step_num += 1
    steps.append(TransitionStep(
        order=step_num,
        category=StepCategory.CONFIG,
        action="milestone",
        description="Uber Lab for final 8 ascendancy points. Ensure all defense checks pass.",
        priority=15,
    ))

    # Sort and re-number
    steps.sort(key=lambda s: -s.priority)
    for i, step in enumerate(steps):
        step.order = i + 1

    return steps


def format_transition_report(
    build_a: PoBBuild,
    build_b: PoBBuild,
    diff: BuildDiff,
    steps: list[TransitionStep],
    transition_type: TransitionType,
) -> str:
    """Format a human-readable transition report."""
    lines: list[str] = []
    type_name = "RESPEC" if transition_type == TransitionType.RESPEC else "LEVELING"
    lines.append("=" * 70)
    lines.append(f"  BUILD TRANSITION PLAN ({type_name})")
    lines.append(f"  FROM: {build_a.name or 'Build A'} (Lv{build_a.level} {build_a.ascend_class_name})")
    lines.append(f"  TO:   {build_b.name or 'Build B'} (Lv{build_b.level} {build_b.ascend_class_name})")
    lines.append("=" * 70)
    lines.append("")

    # Summary
    lines.append("--- Change Summary ---")
    lines.append(f"  Passive nodes: +{len(diff.nodes_to_add)} / -{len(diff.nodes_to_remove)} / ={len(diff.nodes_unchanged)}")
    lines.append(f"  Gems: +{len(diff.gems_to_add)} / -{len(diff.gems_to_remove)} / ={len(diff.gems_unchanged)}")
    lines.append(f"  Gear slots changed: {len(diff.slots_changed)}")
    if diff.class_changed:
        lines.append(f"  *** CLASS CHANGE: {diff.old_class} → {diff.new_class} (NEW CHARACTER REQUIRED) ***")
    if diff.ascendancy_changed:
        lines.append(f"  Ascendancy change: {diff.old_ascendancy} → {diff.new_ascendancy}")
    lines.append("")

    # Cost estimate
    total_regrets = len(diff.nodes_to_remove)
    if total_regrets > 0:
        lines.append(f"  Estimated respec cost: {total_regrets} Orbs of Regret")
        lines.append("")

    # Steps
    lines.append("--- Step-by-Step Plan ---")
    for step in steps:
        lines.append(str(step))
        if step.details:
            lines.append(f"         {step.details}")

    lines.append("")
    return "\n".join(lines)
