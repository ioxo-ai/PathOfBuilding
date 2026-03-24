"""Feature 1: Defense Assertion Checker with priority scoring and fix suggestions."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from .build_parser import PoBBuild, ItemInfo


class Severity(IntEnum):
    """Defense gap severity levels."""
    CRITICAL = 3  # Will die frequently (e.g., no freeze immunity in endgame)
    WARNING = 2   # Significant weakness
    INFO = 1      # Nice to have, not critical


@dataclass
class FixSuggestion:
    """A suggested way to obtain a missing defense."""
    source_type: str  # "item_mod", "passive", "flask", "gem", "mastery", "pantheon"
    description: str
    slot_or_location: str = ""
    trade_search_hint: str = ""  # Keyword for trade site search


@dataclass
class DefenseIssue:
    """A detected defense gap."""
    category: str       # "immunity", "resistance", "ehp", "avoidance", "block"
    name: str           # Human-readable issue name
    severity: Severity
    current_value: float
    target_value: float
    description: str
    suggestions: list[FixSuggestion] = field(default_factory=list)

    @property
    def gap(self) -> float:
        return max(0, self.target_value - self.current_value)

    def __str__(self) -> str:
        icon = {Severity.CRITICAL: "[!!!]", Severity.WARNING: "[!!]", Severity.INFO: "[i]"}
        return (
            f"{icon[self.severity]} {self.name}: "
            f"{self.current_value:.0f}/{self.target_value:.0f} — {self.description}"
        )


# --- Knowledge Base: How to obtain defenses ---

FREEZE_IMMUNITY_SOURCES = [
    FixSuggestion("flask", "Immunity during Flask Effect (\"of Heat\" suffix)", "Flask", "flask freeze immune"),
    FixSuggestion("item_mod", "\"Cannot be Frozen\" mod on boots or body armour", "Boots", "cannot be frozen"),
    FixSuggestion("item_mod", "Brine King pantheon (50% reduced freeze duration, conditional immunity)", "", ""),
    FixSuggestion("passive", "Passive tree: Crystal Skin wheel or nearby avoidance nodes", "Passive Tree", ""),
    FixSuggestion("mastery", "Elemental Mastery: 100% chance to Avoid being Frozen", "Mastery", ""),
    FixSuggestion("gem", "Purity of Elements aura grants ailment immunity", "", ""),
]

CHILL_IMMUNITY_SOURCES = [
    FixSuggestion("flask", "Immunity during Flask Effect (\"of Heat\" suffix)", "Flask", "flask chill immune"),
    FixSuggestion("item_mod", "\"Cannot be Chilled\" mod", "Boots", "cannot be chilled"),
    FixSuggestion("gem", "Purity of Elements aura grants ailment immunity", "", ""),
    FixSuggestion("mastery", "Elemental Mastery: Chill avoidance", "Mastery", ""),
]

STUN_IMMUNITY_SOURCES = [
    FixSuggestion("item_mod", "\"Unwavering Stance\" keystone (cannot evade, cannot be stunned)", "Passive Tree", ""),
    FixSuggestion("passive", "Passive: Brine King pantheon for stun recovery", "Pantheon", ""),
    FixSuggestion("item_mod", "Stun avoidance mods on gear (helmet, boots)", "Helmet/Boots", "chance to avoid stun"),
    FixSuggestion("mastery", "Life Mastery: 50% increased Stun Threshold", "Mastery", ""),
    FixSuggestion("flask", "Flask suffix \"of Steadiness\" for stun avoidance", "Flask", ""),
    FixSuggestion("item_mod", "Presence of Chayula amulet (Chaos immunity + stun immunity)", "Amulet", "Presence of Chayula"),
]

CORRUPTED_BLOOD_SOURCES = [
    FixSuggestion("item_mod", "Corrupted Blood cannot be inflicted (jewel implicit)", "Jewel", "corrupted blood cannot be inflicted"),
    FixSuggestion("flask", "Bleed immunity flask (\"of Staunching\" suffix)", "Flask", "flask bleed immune"),
    FixSuggestion("passive", "Keystone or ascendancy that prevents corrupted blood", "Passive Tree", ""),
]

RESISTANCE_SOURCES = {
    "Fire": [
        FixSuggestion("item_mod", "Fire resistance mods on gear (rings, belt, boots)", "Ring/Belt", "+% fire resistance"),
        FixSuggestion("passive", "Passive tree resistance nodes", "Passive Tree", ""),
        FixSuggestion("gem", "Purity of Fire aura", "", ""),
        FixSuggestion("item_mod", "Crafted fire resistance via bench", "Any", ""),
    ],
    "Cold": [
        FixSuggestion("item_mod", "Cold resistance mods on gear (rings, belt, boots)", "Ring/Belt", "+% cold resistance"),
        FixSuggestion("passive", "Passive tree resistance nodes", "Passive Tree", ""),
        FixSuggestion("gem", "Purity of Ice aura", "", ""),
    ],
    "Lightning": [
        FixSuggestion("item_mod", "Lightning resistance mods on gear (rings, belt, boots)", "Ring/Belt", "+% lightning resistance"),
        FixSuggestion("passive", "Passive tree resistance nodes", "Passive Tree", ""),
        FixSuggestion("gem", "Purity of Lightning aura", "", ""),
    ],
    "Chaos": [
        FixSuggestion("item_mod", "Chaos resistance mods on gear (rings, amulet, belt)", "Ring/Amulet", "+% chaos resistance"),
        FixSuggestion("passive", "Passive tree chaos resistance nodes", "Passive Tree", ""),
        FixSuggestion("item_mod", "Amethyst Flask for temporary chaos resistance", "Flask", ""),
        FixSuggestion("mastery", "Chaos Mastery: +1% max chaos resistance", "Mastery", ""),
    ],
}

EHP_IMPROVEMENT_SOURCES = [
    FixSuggestion("item_mod", "Flat life on gear (belt, body armour, helmet)", "Belt/Body", "maximum life"),
    FixSuggestion("passive", "Life% nodes on passive tree", "Passive Tree", ""),
    FixSuggestion("item_mod", "Energy Shield on gear (for hybrid or CI builds)", "Body Armour", "energy shield"),
    FixSuggestion("item_mod", "Armour/Evasion base types for physical mitigation", "Body Armour", ""),
    FixSuggestion("gem", "Determination/Grace/Discipline auras", "", ""),
    FixSuggestion("mastery", "Life Mastery: +50 flat life", "Mastery", ""),
]


def _check_item_for_keyword(build: PoBBuild, keyword: str) -> bool:
    """Check if any equipped item has a specific keyword in its text."""
    for item in build.items.values():
        if item.has_mod(keyword):
            return True
    return False


def _check_config_flag(build: PoBBuild, flag: str) -> bool:
    """Check if a config boolean flag is set."""
    val = build.config.get(flag, "")
    return val.lower() == "true" if val else False


def check_ailment_immunity(
    build: PoBBuild,
    ailment: str,
    avoid_stat: str,
    immune_keywords: list[str],
    sources: list[FixSuggestion],
    severity: Severity = Severity.CRITICAL,
) -> Optional[DefenseIssue]:
    """Generic ailment immunity/avoidance checker."""
    # Check stat-based avoidance
    avoid_chance = build.stats.get(avoid_stat, 0)

    # Check item-based immunity keywords
    has_immunity = False
    for kw in immune_keywords:
        if _check_item_for_keyword(build, kw):
            has_immunity = True
            break

    if has_immunity or avoid_chance >= 100:
        return None

    return DefenseIssue(
        category="immunity",
        name=f"{ailment} Immunity",
        severity=severity,
        current_value=avoid_chance,
        target_value=100,
        description=f"{ailment} avoidance is {avoid_chance:.0f}% (need 100% for immunity)",
        suggestions=sources,
    )


def check_resistance_cap(
    build: PoBBuild,
    element: str,
    current: float,
    overcap: float,
    cap: float = 75,
    min_overcap: float = 0,
) -> Optional[DefenseIssue]:
    """Check if resistance is capped and has enough overcap for curse resistance."""
    if current < cap:
        missing = cap - current
        sev = Severity.CRITICAL if missing > 20 else Severity.WARNING
        return DefenseIssue(
            category="resistance",
            name=f"{element} Resistance",
            severity=sev,
            current_value=current,
            target_value=cap,
            description=f"{element} resistance is {current:.0f}% (cap: {cap}%, missing: {missing:.0f}%)",
            suggestions=RESISTANCE_SOURCES.get(element, []),
        )
    elif overcap < min_overcap:
        return DefenseIssue(
            category="resistance",
            name=f"{element} Resistance Overcap",
            severity=Severity.INFO,
            current_value=overcap,
            target_value=min_overcap,
            description=f"{element} overcap is only {overcap:.0f}% (recommend {min_overcap:.0f}%+ for Elemental Weakness)",
            suggestions=RESISTANCE_SOURCES.get(element, []),
        )
    return None


def run_defense_check(build: PoBBuild) -> list[DefenseIssue]:
    """Run all defense assertion checks on a build.

    Returns list of DefenseIssue sorted by severity (critical first).
    """
    issues: list[DefenseIssue] = []

    # === Elemental Resistances ===
    recommended_overcap = 15  # Buffer for ele weakness maps

    for element, resist_attr, overcap_attr in [
        ("Fire", "fire_resist", "fire_resist_overcap"),
        ("Cold", "cold_resist", "cold_resist_overcap"),
        ("Lightning", "lightning_resist", "lightning_resist_overcap"),
    ]:
        current = getattr(build.stats, resist_attr)
        overcap = getattr(build.stats, overcap_attr)
        issue = check_resistance_cap(build, element, current, overcap, 75, recommended_overcap)
        if issue:
            issues.append(issue)

    # Chaos resistance (softer requirement)
    chaos_res = build.stats.chaos_resist
    if chaos_res < 0:
        sev = Severity.CRITICAL if chaos_res < -30 else Severity.WARNING
        issues.append(DefenseIssue(
            category="resistance",
            name="Chaos Resistance",
            severity=sev,
            current_value=chaos_res,
            target_value=0,
            description=f"Chaos resistance is {chaos_res:.0f}% (recommend at least 0%+ for endgame)",
            suggestions=RESISTANCE_SOURCES["Chaos"],
        ))

    # === Ailment Immunities ===

    # Freeze immunity
    issue = check_ailment_immunity(
        build, "Freeze", "FreezeAvoidChance",
        ["cannot be frozen", "freeze immune"],
        FREEZE_IMMUNITY_SOURCES, Severity.CRITICAL,
    )
    if issue:
        issues.append(issue)

    # Chill immunity (less critical but important for speed)
    issue = check_ailment_immunity(
        build, "Chill", "ChillAvoidChance",
        ["cannot be chilled", "chill immune"],
        CHILL_IMMUNITY_SOURCES, Severity.WARNING,
    )
    if issue:
        issues.append(issue)

    # Corrupted Blood immunity
    cb_immune = _check_item_for_keyword(build, "corrupted blood cannot be inflicted")
    cb_avoid = build.stats.get("BleedAvoidChance", 0)
    if not cb_immune and cb_avoid < 100:
        issues.append(DefenseIssue(
            category="immunity",
            name="Corrupted Blood Immunity",
            severity=Severity.CRITICAL,
            current_value=1 if cb_immune else 0,
            target_value=1,
            description="No Corrupted Blood immunity (very dangerous in endgame)",
            suggestions=CORRUPTED_BLOOD_SOURCES,
        ))

    # Stun avoidance
    stun_avoid = build.stats.get("StunAvoidChance", 0)
    if stun_avoid < 100:
        # Check for Unwavering Stance or similar
        has_unwavering = _check_item_for_keyword(build, "unwavering stance")
        if not has_unwavering:
            sev = Severity.WARNING if stun_avoid >= 50 else Severity.CRITICAL
            issues.append(DefenseIssue(
                category="immunity",
                name="Stun Immunity/Avoidance",
                severity=sev,
                current_value=stun_avoid,
                target_value=100,
                description=f"Stun avoidance is {stun_avoid:.0f}% (stun-locking is dangerous)",
                suggestions=STUN_IMMUNITY_SOURCES,
            ))

    # === EHP Check ===
    total_ehp = build.stats.total_ehp
    life = build.stats.life
    es = build.stats.energy_shield

    # Basic life pool check
    if build.level >= 70:
        min_life = 4000 if build.level < 85 else 5000
        effective_pool = life + es
        if effective_pool < min_life:
            issues.append(DefenseIssue(
                category="ehp",
                name="Life + ES Pool",
                severity=Severity.CRITICAL if effective_pool < 3500 else Severity.WARNING,
                current_value=effective_pool,
                target_value=min_life,
                description=f"Life+ES pool is {effective_pool:.0f} (recommend {min_life}+ at level {build.level})",
                suggestions=EHP_IMPROVEMENT_SOURCES,
            ))

    # === Spell Suppression (for right-side builds) ===
    supp = build.stats.spell_suppression_chance
    if 0 < supp < 100:
        issues.append(DefenseIssue(
            category="avoidance",
            name="Spell Suppression Cap",
            severity=Severity.WARNING,
            current_value=supp,
            target_value=100,
            description=f"Spell Suppression is {supp:.0f}% (cap at 100% or don't invest)",
            suggestions=[
                FixSuggestion("item_mod", "Spell suppression on evasion gear (boots, gloves, helmet, body)", "Armour", "spell suppression"),
                FixSuggestion("passive", "Spell suppression nodes (right side of tree)", "Passive Tree", ""),
                FixSuggestion("mastery", "Evasion Mastery: spell suppression chance", "Mastery", ""),
            ],
        ))

    # === Block Check ===
    block = build.stats.block_chance
    spell_block = build.stats.spell_block_chance
    if block > 30 and block < 75:
        issues.append(DefenseIssue(
            category="block",
            name="Attack Block Cap",
            severity=Severity.INFO,
            current_value=block,
            target_value=75,
            description=f"Attack block is {block:.0f}% — consider capping or removing investment",
            suggestions=[
                FixSuggestion("item_mod", "Shield with high block chance", "Shield", "block chance"),
                FixSuggestion("passive", "Block nodes on passive tree", "Passive Tree", ""),
                FixSuggestion("item_mod", "Glancing Blows keystone (doubles block, halves effectiveness)", "Passive Tree", ""),
            ],
        ))

    # Sort by severity (critical first)
    issues.sort(key=lambda i: (-i.severity, i.category, i.name))
    return issues


def format_defense_report(build: PoBBuild, issues: list[DefenseIssue]) -> str:
    """Format a human-readable defense report."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"  DEFENSE REPORT: {build.name or 'Unknown Build'}")
    lines.append(f"  Level {build.level} {build.ascend_class_name or build.class_name}")
    lines.append("=" * 70)
    lines.append("")

    # Summary stats
    lines.append("--- Current Defense Summary ---")
    lines.append(f"  Life: {build.stats.life:.0f}  |  ES: {build.stats.energy_shield:.0f}  |  Armour: {build.stats.armour:.0f}  |  Evasion: {build.stats.evasion:.0f}")
    lines.append(f"  Fire: {build.stats.fire_resist:.0f}% (+{build.stats.fire_resist_overcap:.0f}%)  |  "
                 f"Cold: {build.stats.cold_resist:.0f}% (+{build.stats.cold_resist_overcap:.0f}%)  |  "
                 f"Lightning: {build.stats.lightning_resist:.0f}% (+{build.stats.lightning_resist_overcap:.0f}%)")
    lines.append(f"  Chaos: {build.stats.chaos_resist:.0f}% (+{build.stats.chaos_resist_overcap:.0f}%)")
    lines.append(f"  Block: {build.stats.block_chance:.0f}%  |  Spell Block: {build.stats.spell_block_chance:.0f}%")

    ehp = build.stats.total_ehp
    if ehp > 0:
        lines.append(f"  Total EHP: {ehp:,.0f}")
    lines.append("")

    if not issues:
        lines.append("  All defense checks PASSED! Build looks solid.")
        return "\n".join(lines)

    # Count by severity
    crits = sum(1 for i in issues if i.severity == Severity.CRITICAL)
    warns = sum(1 for i in issues if i.severity == Severity.WARNING)
    infos = sum(1 for i in issues if i.severity == Severity.INFO)
    lines.append(f"  Found {len(issues)} issues: {crits} critical, {warns} warning, {infos} info")
    lines.append("")

    # Group by category
    prev_cat = ""
    for issue in issues:
        if issue.category != prev_cat:
            lines.append(f"--- {issue.category.upper()} ---")
            prev_cat = issue.category

        lines.append(f"  {issue}")

        if issue.suggestions:
            lines.append("    How to fix:")
            for s in issue.suggestions[:4]:  # Limit to top 4 suggestions
                loc = f" [{s.slot_or_location}]" if s.slot_or_location else ""
                lines.append(f"      • ({s.source_type}){loc} {s.description}")
                if s.trade_search_hint:
                    lines.append(f"        Trade search: \"{s.trade_search_hint}\"")
        lines.append("")

    return "\n".join(lines)
