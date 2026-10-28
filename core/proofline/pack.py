"""Trade packs: the price list, faults, safety rules and parts for one trade (packs/plumbing.yaml)."""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional

import yaml


class Pack:
    def __init__(self, data: dict):
        self.data = data
        self.name = data["pack"]
        self.currency = data.get("currency", "GBP")
        self.parts = {p["id"]: p for p in data.get("parts", [])}
        self.jobs = {j["id"]: j for j in data.get("jobs", [])}
        self.labour = data["labour"]
        self.excluded = data.get("excluded", [])
        self.trade = data.get("trade", {})
        self.safety = data.get("safety", [])
        self.faults = {f["id"]: f for f in data.get("faults", [])}

    @classmethod
    def load(cls, path: str) -> "Pack":
        return cls(yaml.safe_load(Path(path).read_text()))

    def part_price(self, part_id: Optional[str]) -> Optional[float]:
        part = self.parts.get(part_id or "")
        return float(part["price"]) if part else None

    def labour_hours(self, minutes: float) -> float:
        """Round worked minutes up to the billing increment, with a minimum charge."""
        step = float(self.labour.get("increment_hours", 0.25))
        hours = math.ceil((minutes / 60.0) / step - 1e-9) * step
        return max(hours, float(self.labour.get("minimum_hours", 0)))

    def excluded_match(self, text: str) -> Optional[dict]:
        """The excluded-work rule this text triggers (gas, electrical certificates), if any."""
        low = text.lower()
        for rule in self.excluded:
            if any(k in low for k in rule.get("keywords", [])):
                return rule
        return None

    def keywords(self, limit: int = 40) -> List[str]:
        """Words to bias Voice Transcribe towards: part names and aliases."""
        words: List[str] = []
        for part in self.parts.values():
            for w in [*part.get("aliases", [])]:
                if w not in words:
                    words.append(w)
        return words[:limit]

    def prompt_catalogue(self) -> str:
        """Price-list summary for the extraction prompt. Prices are left out on purpose:
        the model maps work to part ids, and pricing happens in code."""
        lines = ["Parts (id: name; also called):"]
        for p in self.parts.values():
            lines.append(f"- {p['id']}: {p['name']}; {', '.join(p.get('aliases', []))}")
        lines.append("Jobs this pack covers:")
        for j in self.jobs.values():
            lines.append(f"- {j['id']}: {j['name']} (usual steps: {', '.join(j.get('steps', []))})")
        return "\n".join(lines)

    def fault_catalogue(self) -> str:
        """Fault list for the triage prompt. Estimates are left out: pricing happens in code."""
        lines = ["Faults this trade handles (id: name; symptoms; what to film next):"]
        for f in self.faults.values():
            lines.append(f"- {f['id']}: {f['name']}; {', '.join(f.get('symptoms', []))}; "
                         f"ask: {' | '.join(f.get('follow_up_questions', []))}; "
                         f"needs a visit if: {', '.join(f.get('needs_visit_when', []))}")
        lines.append("Parts (id: name):")
        for p in self.parts.values():
            lines.append(f"- {p['id']}: {p['name']}")
        return "\n".join(lines)
