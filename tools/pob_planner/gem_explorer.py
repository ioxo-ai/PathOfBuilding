"""Feature 3: Gem Combo Explorer - find strong active+support gem combinations.

This module works by:
1. Parsing PoB's Lua gem/skill data files to build a compatibility database
2. Generating candidate support gem combinations for a given active skill
3. Scoring combos using heuristics (damage multipliers, synergy tags)
4. Optionally running PoB headless to get actual DPS numbers

Since we're an external Python tool, we have two scoring modes:
- HEURISTIC: Fast, uses parsed gem data to estimate power (no PoB runtime needed)
- HEADLESS: Slow but accurate, uses PoB's Lua calculation engine via HeadlessWrapper
"""

import re
import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --- Gem Database (parsed from PoB Lua data) ---

@dataclass
class GemData:
    """Parsed gem data from PoB's Lua files."""
    name: str
    gem_id: str
    tags: set[str] = field(default_factory=set)
    is_support: bool = False
    req_str: int = 0
    req_dex: int = 0
    req_int: int = 0
    # Heuristic power metrics (extracted from support gem data)
    damage_multiplier: float = 1.0  # "more damage" multiplier at level 20
    speed_multiplier: float = 1.0   # "more attack/cast speed" at level 20
    added_damage: float = 0.0       # Flat added damage
    description_hints: list[str] = field(default_factory=list)


@dataclass
class GemDatabase:
    """Database of all gems parsed from PoB data."""
    active_gems: dict[str, GemData] = field(default_factory=dict)
    support_gems: dict[str, GemData] = field(default_factory=dict)
    all_gems: dict[str, GemData] = field(default_factory=dict)


def parse_gems_from_lua(lua_text: str) -> list[dict]:
    """Parse gem entries from Gems.lua content.

    Handles multiline Lua table format like:
        ["Metadata/Items/Gems/SkillGemFireball"] = {
            name = "Fireball",
            tags = {
                intelligence = true,
                fire = true,
            },
            reqStr = 0,
            ...
        },
    """
    gems: list[dict] = []
    # Match each top-level gem entry (multiline)
    # Pattern: ["Metadata/..."] = { ... },
    entry_pattern = re.compile(
        r'\["(Metadata/Items/Gems/[^"]+)"\]\s*=\s*\{(.*?)\n\t\}',
        re.DOTALL,
    )

    for match in entry_pattern.finditer(lua_text):
        gem_id = match.group(1)
        body = match.group(2)

        gem_info: dict = {"gem_id": gem_id, "tags": set()}

        # Extract name
        name_match = re.search(r'name\s*=\s*"([^"]+)"', body)
        if name_match:
            gem_info["name"] = name_match.group(1)

        # Extract tags (multiline block)
        tags_match = re.search(r'tags\s*=\s*\{(.*?)\}', body, re.DOTALL)
        if tags_match:
            tag_str = tags_match.group(1)
            for tag_match in re.finditer(r'(\w+)\s*=\s*true', tag_str):
                gem_info["tags"].add(tag_match.group(1))

        # Extract requirements
        for req in ["reqStr", "reqDex", "reqInt"]:
            req_match = re.search(rf'{req}\s*=\s*(\d+)', body)
            if req_match:
                gem_info[req] = int(req_match.group(1))

        if "name" in gem_info:
            gems.append(gem_info)

    return gems


def parse_support_multipliers_from_lua(lua_text: str) -> dict[str, float]:
    """Parse 'more' damage multipliers from support gem skill data.

    Strategy:
    1. Find the stats list for each support gem
    2. Identify which stat index is the damage_+%_final stat
    3. Read that index from levels[20] data
    4. Also check constantStats for fixed multipliers
    """
    multipliers: dict[str, float] = {}

    # Parse each skills["..."] = { ... } block
    skill_pattern = re.compile(
        r'skills\["(\w+)"\]\s*=\s*\{(.*?)\n\}',
        re.DOTALL,
    )

    for match in skill_pattern.finditer(lua_text):
        body = match.group(2)

        # Get name
        name_match = re.search(r'name\s*=\s*"([^"]+)"', body)
        if not name_match:
            continue
        name = name_match.group(1)

        if 'support = true' not in body:
            continue

        # Method 1: constantStats with damage_+%_final
        # These are fixed multipliers (can be negative = "less damage")
        const_match = re.search(
            r'constantStats\s*=\s*\{(.*?)\n\t\}',
            body, re.DOTALL,
        )
        if const_match:
            const_body = const_match.group(1)
            for cm in re.finditer(r'"(support_\w*damage_\+%_final\w*)",\s*(-?\d+)', const_body):
                stat_name = cm.group(1)
                # Skip indirect stats
                if "as_though" in stat_name or "focus_fire" in stat_name:
                    continue
                val = int(cm.group(2))
                # Both positive (more) and negative (less) are valid multipliers
                const_mult = 1 + val / 100
                # Combine with existing (multiply constant and level-based)
                if name not in multipliers:
                    multipliers[name] = const_mult
                else:
                    multipliers[name] *= const_mult

        # Method 2: Find damage stat index in stats list, then read from levels[20]
        stats_match = re.search(r'\tstats\s*=\s*\{(.*?)\}', body, re.DOTALL)
        if not stats_match:
            continue

        stats_body = stats_match.group(1)
        stat_names = re.findall(r'"([^"]+)"', stats_body)

        # Find index of damage_+%_final stat (exclude indirect multipliers like shock_as_though)
        damage_stat_idx = None
        for idx, stat_name in enumerate(stat_names):
            if re.match(r'support_\w*damage_\+%_final', stat_name):
                # Exclude indirect stats like "shock_as_though_damage" or "minion_focus_fire"
                if "as_though" in stat_name or "focus_fire" in stat_name:
                    continue
                damage_stat_idx = idx
                break

        if damage_stat_idx is None:
            continue

        # Read levels[20] values
        level20_match = re.search(r'\[20\]\s*=\s*\{([^}]+)\}', body)
        if not level20_match:
            continue

        level_body = level20_match.group(1)
        # Extract numeric values before "levelRequirement"
        vals_part = level_body.split("levelRequirement")[0]
        vals = re.findall(r'(-?\d+(?:\.\d+)?)', vals_part)

        if damage_stat_idx < len(vals):
            val = float(vals[damage_stat_idx])
            if val > 0:
                new_mult = 1 + val / 100
                multipliers[name] = max(multipliers.get(name, 1.0), new_mult)

    return multipliers


def build_gem_database(pob_src_path: str | Path) -> GemDatabase:
    """Build gem database by parsing PoB's Lua data files."""
    pob_src = Path(pob_src_path)
    db = GemDatabase()

    # Parse Gems.lua for basic gem info
    gems_path = pob_src / "Data" / "Gems.lua"
    if gems_path.exists():
        gems_text = gems_path.read_text(encoding="utf-8", errors="replace")
        gem_entries = parse_gems_from_lua(gems_text)

        for entry in gem_entries:
            name = entry["name"]
            tags = entry["tags"]
            gem_id = entry["gem_id"]
            is_support = "support" in tags or "grants_active_skill" not in tags
            gem = GemData(
                name=name,
                gem_id=gem_id,
                tags=tags,
                is_support=is_support,
                req_str=entry.get("reqStr", 0),
                req_dex=entry.get("reqDex", 0),
                req_int=entry.get("reqInt", 0),
            )
            db.all_gems[name] = gem
            if is_support:
                db.support_gems[name] = gem
            else:
                db.active_gems[name] = gem

    # Parse support gem skill files for multipliers
    for sup_file in ["sup_str.lua", "sup_dex.lua", "sup_int.lua"]:
        sup_path = pob_src / "Data" / "Skills" / sup_file
        if sup_path.exists():
            sup_text = sup_path.read_text(encoding="utf-8", errors="replace")
            multipliers = parse_support_multipliers_from_lua(sup_text)
            for name, mult in multipliers.items():
                if name in db.support_gems:
                    db.support_gems[name].damage_multiplier = mult
                elif name in db.all_gems:
                    db.all_gems[name].damage_multiplier = mult

    return db


# --- Tag Compatibility ---

# Support gems require certain skill types to apply
SUPPORT_REQUIRES = {
    "attack": {"attack"},
    "spell": {"spell"},
    "projectile": {"projectile"},
    "area": {"area"},
    "duration": {"duration"},
    "minion": {"minion"},
    "melee": {"melee"},
}


def is_support_compatible(support: GemData, active: GemData) -> bool:
    """Check if a support gem can be linked to an active gem based on tags."""
    # Simple heuristic: if support has restrictive tags, active must match
    for tag_group_name, required_tags in SUPPORT_REQUIRES.items():
        if tag_group_name in support.tags:
            if not required_tags & active.tags:
                return False
    return True


# --- Combo Scoring ---

@dataclass
class GemCombo:
    """A candidate gem combination with its score."""
    active_gem: GemData
    support_gems: list[GemData]
    heuristic_score: float = 0.0
    actual_dps: Optional[float] = None  # Filled if headless calculation is used
    tag_synergy_score: float = 0.0

    @property
    def display_name(self) -> str:
        supports = ", ".join(g.name for g in self.support_gems)
        return f"{self.active_gem.name} + [{supports}]"


def score_combo_heuristic(active: GemData, supports: list[GemData]) -> float:
    """Score a gem combo using heuristic estimation.

    Scoring factors:
    1. Product of 'more damage' multipliers (biggest factor)
    2. Tag synergy bonus (supports matching active's tags)
    3. Penalty for too many supports with same function
    """
    # Base score from damage multipliers
    total_mult = 1.0
    for s in supports:
        total_mult *= s.damage_multiplier

    # Tag synergy: bonus for supports that share tags with active
    synergy = 0
    for s in supports:
        shared_tags = s.tags & active.tags
        synergy += len(shared_tags) * 0.05  # 5% bonus per shared tag

    # Diversity penalty: slight penalty for redundant supports
    tag_counts: dict[str, int] = {}
    for s in supports:
        for t in s.tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    diversity_penalty = sum(max(0, c - 2) * 0.02 for c in tag_counts.values())

    return total_mult * (1 + synergy) * (1 - diversity_penalty)


def find_best_combos(
    db: GemDatabase,
    active_skill_name: Optional[str] = None,
    max_supports: int = 5,
    top_n: int = 20,
    max_active_skills: int = 10,
) -> list[GemCombo]:
    """Find the best gem combinations.

    Args:
        db: Gem database
        active_skill_name: If set, only explore supports for this active skill.
                          If None, explore all active skills.
        max_supports: Max number of support gems in a link group
        top_n: Number of top combos to return
        max_active_skills: Max active skills to explore (when active_skill_name is None)
    """
    results: list[GemCombo] = []

    # Determine which active skills to explore
    if active_skill_name:
        actives_to_check = [db.active_gems[active_skill_name]] if active_skill_name in db.active_gems else []
    else:
        # Pick active skills with the most tag variety (more interesting combos)
        sorted_actives = sorted(
            db.active_gems.values(),
            key=lambda g: len(g.tags),
            reverse=True,
        )
        actives_to_check = sorted_actives[:max_active_skills]

    for active in actives_to_check:
        # Find compatible supports
        compatible_supports = [
            s for s in db.support_gems.values()
            if is_support_compatible(s, active)
        ]

        # If too many supports, pre-filter by damage multiplier
        if len(compatible_supports) > 15:
            compatible_supports.sort(key=lambda s: s.damage_multiplier, reverse=True)
            compatible_supports = compatible_supports[:15]

        # Generate combinations
        for r in range(min(max_supports, len(compatible_supports)), max(0, max_supports - 2), -1):
            for combo_supports in itertools.combinations(compatible_supports, r):
                score = score_combo_heuristic(active, list(combo_supports))
                combo = GemCombo(
                    active_gem=active,
                    support_gems=list(combo_supports),
                    heuristic_score=score,
                )
                results.append(combo)

            # Early stop if we have enough candidates
            if len(results) > top_n * 10:
                break

    # Sort by score and return top N
    results.sort(key=lambda c: c.heuristic_score, reverse=True)
    return results[:top_n]


def format_gem_explorer_report(combos: list[GemCombo], title: str = "Gem Combo Explorer") -> str:
    """Format gem exploration results as a readable report."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"  {title}")
    lines.append("=" * 70)
    lines.append("")

    if not combos:
        lines.append("  No compatible combinations found.")
        return "\n".join(lines)

    lines.append(f"  Top {len(combos)} combinations (ranked by heuristic score):")
    lines.append("")

    for i, combo in enumerate(combos, 1):
        dps_str = f" | Actual DPS: {combo.actual_dps:,.0f}" if combo.actual_dps else ""
        lines.append(f"  #{i:2d} [Score: {combo.heuristic_score:.3f}{dps_str}]")
        lines.append(f"      Active: {combo.active_gem.name}")
        lines.append(f"      Tags: {', '.join(sorted(combo.active_gem.tags))}")
        supports_str = " + ".join(
            f"{s.name} (x{s.damage_multiplier:.2f})"
            for s in combo.support_gems
        )
        lines.append(f"      Supports: {supports_str}")
        lines.append("")

    return "\n".join(lines)
