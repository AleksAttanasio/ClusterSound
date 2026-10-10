"""CSV / JSON report export."""
import csv
import json

from .taxonomy import BY_ID

FIELDS = ["path", "rel", "class", "class_label", "group", "confidence", "user_label",
          "subcluster", "type", "duration", "alt_1", "alt_2", "alt_3"]


def rows(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        c = BY_ID[it["cls"]]
        alts = [a for a in it.get("alts", []) if a["cls"] != it["cls"]][:3]
        out.append({
            "path": it["path"], "rel": it["rel"], "class": c.id, "class_label": c.label,
            "group": c.group, "confidence": it["conf"], "user_label": it.get("user", False),
            "subcluster": it.get("sub", 1), "type": it["feats"].get("type", ""),
            "duration": round(float(it["info"].get("duration", 0.0)), 3),
            **{f"alt_{i + 1}": f"{a['cls']}:{a['p']}" for i, a in enumerate(alts)},
        })
    return out


def write(items: list[dict], path: str) -> None:
    data = rows(items)
    if path.lower().endswith(".json"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)
