"""Parse PoB XML build files into structured Python objects."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GemInfo:
    name: str
    gem_id: str
    skill_id: str
    level: int
    quality: int
    quality_id: str = "Default"
    enabled: bool = True
    is_support: bool = False

    @classmethod
    def from_xml(cls, elem: ET.Element) -> "GemInfo":
        gem_id = elem.get("gemId", "")
        return cls(
            name=elem.get("nameSpec", ""),
            gem_id=gem_id,
            skill_id=elem.get("skillId", ""),
            level=int(elem.get("level", "1")),
            quality=int(elem.get("quality", "0")),
            quality_id=elem.get("qualityId", "Default"),
            enabled=elem.get("enabled", "true") == "true",
            is_support="Support" in gem_id,
        )


@dataclass
class SkillGroup:
    slot: str
    enabled: bool
    main_active_skill: int
    gems: list[GemInfo] = field(default_factory=list)

    @classmethod
    def from_xml(cls, elem: ET.Element) -> "SkillGroup":
        group = cls(
            slot=elem.get("slot", ""),
            enabled=elem.get("enabled", "true") == "true",
            main_active_skill=int(elem.get("mainActiveSkill", "1")),
        )
        for gem_elem in elem.findall("Gem"):
            group.gems.append(GemInfo.from_xml(gem_elem))
        return group

    @property
    def active_gems(self) -> list[GemInfo]:
        return [g for g in self.gems if not g.is_support and g.enabled]

    @property
    def support_gems(self) -> list[GemInfo]:
        return [g for g in self.gems if g.is_support and g.enabled]


@dataclass
class ItemInfo:
    id: int
    raw_text: str
    name: str = ""
    base_type: str = ""
    rarity: str = ""

    @classmethod
    def from_xml(cls, elem: ET.Element) -> "ItemInfo":
        raw = (elem.text or "").strip()
        lines = raw.split("\n")
        name = ""
        base_type = ""
        rarity = ""
        for line in lines:
            if line.startswith("Rarity: "):
                rarity = line[8:]
            elif rarity and not name:
                name = line.strip()
            elif name and not base_type:
                base_type = line.strip()
        return cls(
            id=int(elem.get("id", "0")),
            raw_text=raw,
            name=name,
            base_type=base_type,
            rarity=rarity,
        )

    def has_mod(self, keyword: str) -> bool:
        return keyword.lower() in self.raw_text.lower()


@dataclass
class ItemSlot:
    name: str
    item_id: int
    item: Optional[ItemInfo] = None

    @classmethod
    def from_xml(cls, elem: ET.Element) -> "ItemSlot":
        return cls(
            name=elem.get("name", ""),
            item_id=int(elem.get("itemId", "0")),
        )


@dataclass
class PassiveTreeSpec:
    class_id: int
    ascend_class_id: int
    tree_version: str
    nodes: set[int] = field(default_factory=set)
    mastery_effects: dict[int, int] = field(default_factory=dict)

    @classmethod
    def from_xml(cls, elem: ET.Element) -> "PassiveTreeSpec":
        nodes_str = elem.get("nodes", "")
        nodes = set()
        if nodes_str:
            nodes = {int(n) for n in nodes_str.split(",") if n.strip()}

        spec = cls(
            class_id=int(elem.get("classId", "0")),
            ascend_class_id=int(elem.get("ascendClassId", "0")),
            tree_version=elem.get("treeVersion", ""),
            nodes=nodes,
        )

        for mastery in elem.findall("MasteryEffects/Mastery"):
            node_id = int(mastery.get("nodeId", "0"))
            effect_id = int(mastery.get("effectId", "0"))
            if node_id and effect_id:
                spec.mastery_effects[node_id] = effect_id

        return spec


@dataclass
class BuildStats:
    """Parsed PlayerStat values from the build XML."""
    raw: dict[str, float] = field(default_factory=dict)

    # Convenience accessors for common stats
    @property
    def life(self) -> float:
        return self.raw.get("Life", 0)

    @property
    def energy_shield(self) -> float:
        return self.raw.get("EnergyShield", 0)

    @property
    def mana(self) -> float:
        return self.raw.get("Mana", 0)

    @property
    def evasion(self) -> float:
        return self.raw.get("Evasion", 0)

    @property
    def armour(self) -> float:
        return self.raw.get("Armour", 0)

    @property
    def fire_resist(self) -> float:
        return self.raw.get("FireResist", 0)

    @property
    def cold_resist(self) -> float:
        return self.raw.get("ColdResist", 0)

    @property
    def lightning_resist(self) -> float:
        return self.raw.get("LightningResist", 0)

    @property
    def chaos_resist(self) -> float:
        return self.raw.get("ChaosResist", 0)

    @property
    def fire_resist_overcap(self) -> float:
        return self.raw.get("FireResistOverCap", 0)

    @property
    def cold_resist_overcap(self) -> float:
        return self.raw.get("ColdResistOverCap", 0)

    @property
    def lightning_resist_overcap(self) -> float:
        return self.raw.get("LightningResistOverCap", 0)

    @property
    def chaos_resist_overcap(self) -> float:
        return self.raw.get("ChaosResistOverCap", 0)

    @property
    def block_chance(self) -> float:
        return self.raw.get("BlockChance", 0)

    @property
    def spell_block_chance(self) -> float:
        return self.raw.get("SpellBlockChance", 0)

    @property
    def spell_suppression_chance(self) -> float:
        return self.raw.get("SpellSuppressionChance", 0)

    @property
    def combined_dps(self) -> float:
        return self.raw.get("CombinedDPS", 0)

    @property
    def total_ehp(self) -> float:
        return self.raw.get("TotalEHP", 0)

    def get(self, key: str, default: float = 0) -> float:
        return self.raw.get(key, default)


@dataclass
class PoBBuild:
    """Full representation of a PoB build."""
    name: str = ""
    level: int = 1
    class_name: str = ""
    ascend_class_name: str = ""
    bandit: str = "None"
    pantheon_major: str = "None"
    pantheon_minor: str = "None"
    stats: BuildStats = field(default_factory=BuildStats)
    skill_groups: list[SkillGroup] = field(default_factory=list)
    items: dict[int, ItemInfo] = field(default_factory=dict)
    item_slots: dict[str, ItemSlot] = field(default_factory=dict)
    passive_spec: Optional[PassiveTreeSpec] = None
    config: dict[str, str] = field(default_factory=dict)
    raw_xml: str = ""

    @classmethod
    def from_xml_file(cls, path: str | Path) -> "PoBBuild":
        path = Path(path)
        xml_text = path.read_text(encoding="utf-8")
        return cls.from_xml_string(xml_text, name=path.stem)

    @classmethod
    def from_xml_string(cls, xml_text: str, name: str = "") -> "PoBBuild":
        root = ET.fromstring(xml_text)
        build = cls(raw_xml=xml_text, name=name)

        # Parse <Build> element
        build_elem = root.find("Build")
        if build_elem is not None:
            build.level = int(build_elem.get("level", "1"))
            build.class_name = build_elem.get("className", "")
            build.ascend_class_name = build_elem.get("ascendClassName", "")
            build.bandit = build_elem.get("bandit", "None")
            build.pantheon_major = build_elem.get("pantheonMajorGod", "None")
            build.pantheon_minor = build_elem.get("pantheonMinorGod", "None")

            # Parse PlayerStats
            for stat in build_elem.findall("PlayerStat"):
                stat_name = stat.get("stat", "")
                stat_value = float(stat.get("value", "0"))
                build.stats.raw[stat_name] = stat_value

        # Parse <Skills>
        skills_elem = root.find("Skills")
        if skills_elem is not None:
            for skill_elem in skills_elem.findall("Skill"):
                build.skill_groups.append(SkillGroup.from_xml(skill_elem))

        # Parse <Items>
        items_elem = root.find("Items")
        if items_elem is not None:
            for item_elem in items_elem.findall("Item"):
                item = ItemInfo.from_xml(item_elem)
                build.items[item.id] = item
            for slot_elem in items_elem.findall("Slot"):
                slot = ItemSlot.from_xml(slot_elem)
                build.item_slots[slot.name] = slot
                if slot.item_id in build.items:
                    slot.item = build.items[slot.item_id]

        # Parse <Tree>
        tree_elem = root.find("Tree")
        if tree_elem is not None:
            active_spec = int(tree_elem.get("activeSpec", "1"))
            specs = tree_elem.findall("Spec")
            if specs and active_spec <= len(specs):
                build.passive_spec = PassiveTreeSpec.from_xml(specs[active_spec - 1])

        # Parse <Config>
        config_elem = root.find("Config")
        if config_elem is not None:
            for input_elem in config_elem.findall("Input"):
                key = input_elem.get("name", "")
                val = (input_elem.get("boolean")
                       or input_elem.get("number")
                       or input_elem.get("string")
                       or "")
                build.config[key] = val

        return build

    def get_equipped_item(self, slot_name: str) -> Optional[ItemInfo]:
        slot = self.item_slots.get(slot_name)
        if slot and slot.item:
            return slot.item
        return None

    def all_gem_names(self) -> set[str]:
        names = set()
        for sg in self.skill_groups:
            for g in sg.gems:
                if g.enabled:
                    names.add(g.name)
        return names

    def all_active_skills(self) -> list[GemInfo]:
        result = []
        for sg in self.skill_groups:
            if sg.enabled:
                result.extend(sg.active_gems)
        return result

    def all_support_gems(self) -> list[GemInfo]:
        result = []
        for sg in self.skill_groups:
            if sg.enabled:
                result.extend(sg.support_gems)
        return result
