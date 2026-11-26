"""持久化层：JSON 存储、原子写入、旧 TXT 迁移、检索与去重。

设计要点：
- 数据落在 ``data/plugin_data/<plugin>/``，插件升级/重装不丢；
- 写入使用临时文件 + ``os.replace``，避免进程中断导致 JSON 截断；
- 旧版 ``wives.txt`` / ``spots.txt`` 只做单向导入，导入后不再回写；
- 同一作品支持多个圣地（旧版用 dict 导致互相覆盖）。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .models import Heroine, Spot, split_name_work

SCHEMA_VERSION = 2
DATA_FILE = "gal.json"
STATE_FILE = "state.json"
LEGACY_FILES = ("wives.txt", "spots.txt")
MAX_SPOTS = 5000
MAX_HEROINES = 5000


@dataclass
class LoadReport:
    heroines: int = 0
    spots: int = 0
    migrated: bool = False
    created: bool = False
    legacy_sources: list[str] = field(default_factory=list)
    dropped: int = 0

    def summary(self) -> str:
        bits = [f"女主 {self.heroines}", f"圣地 {self.spots}"]
        if self.created:
            bits.append("新建数据文件")
        if self.migrated:
            bits.append(f"已从旧 TXT 导入（{', '.join(self.legacy_sources)}）")
        if self.dropped:
            bits.append(f"去重/丢弃 {self.dropped} 条")
        return "，".join(bits)


def _norm(text: str) -> str:
    return "".join(str(text).split()).upper()


class GalStore:
    """线程内使用的同步存储，调用方用 ``asyncio.to_thread`` 包一层即可。"""

    def __init__(self, data_dir: Path, assets_dir: Path, legacy_dirs: Iterable[Path] = ()) -> None:
        self.data_dir = Path(data_dir)
        self.assets_dir = Path(assets_dir)
        self.legacy_dirs = [Path(p) for p in legacy_dirs]
        self.path = self.data_dir / DATA_FILE
        self.heroines: list[Heroine] = []
        self.spots: list[Spot] = []
        self._heroine_keys: set[str] = set()
        self._spot_keys: set[str] = set()
        self._dirty = False

    # ---------------- 载入 ----------------

    def load(self, legacy_import: bool = True) -> LoadReport:
        report = LoadReport()
        # 支持热重载：先清空内存状态，避免重复累加
        self.heroines.clear()
        self.spots.clear()
        self._heroine_keys.clear()
        self._spot_keys.clear()
        self._dirty = False
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.path.exists():
            payload = self._read_json(self.path)
            if not payload.get("heroines") and not payload.get("spots"):
                # 文件损坏或为空：回退内置资产，保证插件仍可用
                payload = self._read_defaults()
                report.created = True
                self._dirty = True
            self._read_payload(payload, report)
        else:
            payload: dict = {}
            if legacy_import:
                payload = self._read_legacy(report)
            if not payload.get("heroines") and not payload.get("spots"):
                payload = self._read_defaults()
                report.created = True
            self._read_payload(payload, report)
            self._dirty = True

        self._rebuild_index()
        if self._dirty:
            self.save()
        report.heroines, report.spots = len(self.heroines), len(self.spots)
        return report

    def _read_json(self, path: Path) -> dict:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # 文件损坏：备份后回退到默认资产，避免整个插件起不来
            try:
                shutil.copy2(path, path.with_suffix(f".broken-{int(time.time())}.json"))
            except OSError:
                pass
            return {}

    def _read_payload(self, payload: dict, report: LoadReport) -> None:
        for raw in payload.get("heroines") or []:
            if not isinstance(raw, dict):
                continue
            try:
                heroine = Heroine.from_dict(raw)
            except (TypeError, ValueError):
                report.dropped += 1
                continue
            if not heroine.name:
                report.dropped += 1
                continue
            if heroine.key in self._heroine_keys:
                continue
            self._heroine_keys.add(heroine.key)
            self.heroines.append(heroine)

        for raw in payload.get("spots") or []:
            if not isinstance(raw, dict):
                continue
            try:
                spot = Spot.from_dict(raw)
            except (TypeError, ValueError):
                report.dropped += 1
                continue
            if not spot.work or not spot.name:
                report.dropped += 1
                continue
            if spot.key in self._spot_keys:
                continue
            self._spot_keys.add(spot.key)
            self.spots.append(spot)

    def _read_defaults(self) -> dict:
        heroines: list[dict] = []
        spots: list[dict] = []
        for name, bucket in (("wives.default.json", heroines), ("spots.default.json", spots)):
            path = self.assets_dir / name
            if not path.exists():
                continue
            data = self._read_json(path)
            bucket.extend(data.get("heroines") or [])
            bucket.extend(data.get("spots") or [])
        return {"version": SCHEMA_VERSION, "heroines": heroines, "spots": spots}

    def _read_legacy(self, report: LoadReport) -> dict:
        """读取旧版 txt。格式：女主每行一个；圣地 游戏|地点|链接。"""
        heroines: list[dict] = []
        spots: list[dict] = []
        found = False
        for directory in self.legacy_dirs:
            w_path, s_path = directory / "wives.txt", directory / "spots.txt"
            if w_path.exists():
                found = True
                report.legacy_sources.append(str(w_path))
                for line in self._iter_lines(w_path):
                    name, work = split_name_work(line)
                    if name:
                        heroines.append(Heroine(name=name, work=work).to_dict())
            if s_path.exists():
                found = True
                report.legacy_sources.append(str(s_path))
                for line in self._iter_lines(s_path):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 2 and parts[0] and parts[1]:
                        link = parts[2] if len(parts) > 2 else ""
                        spots.append(Spot(work=parts[0], name=parts[1], link=link).to_dict())
        report.migrated = found
        return {"version": SCHEMA_VERSION, "heroines": heroines, "spots": spots}

    @staticmethod
    def _iter_lines(path: Path) -> Iterable[str]:
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return []
        return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]

    # ---------------- 保存 ----------------

    def save(self) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "heroines": [h.to_dict() for h in self.heroines],
            "spots": [s.to_dict() for s in self.spots],
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.data_dir), prefix=".gal-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self._dirty = False

    def _rebuild_index(self) -> None:
        self._heroine_keys = {h.key for h in self.heroines}
        self._spot_keys = {s.key for s in self.spots}

    # ---------------- 写操作 ----------------

    def add_heroine(self, raw: str) -> tuple[bool, str]:
        name, work = split_name_work(raw)
        if not name:
            return False, "角色名不能为空"
        if len(self.heroines) >= MAX_HEROINES:
            return False, f"女主数量已达上限 {MAX_HEROINES}"
        heroine = Heroine(name=name, work=work)
        if heroine.key in self._heroine_keys:
            return False, f"「{heroine.display}」已在名单中"
        self.heroines.append(heroine)
        self._heroine_keys.add(heroine.key)
        self.save()
        return True, f"{heroine.display}（当前 {len(self.heroines)} 位）"

    def remove_heroine(self, keyword: str) -> tuple[int, list[str]]:
        q = keyword.strip().lower()
        if not q:
            return 0, []
        hits = [h for h in self.heroines if q in h.name.lower() or q in h.work.lower()]
        if not hits:
            return 0, []
        removed = [h.display for h in hits]
        ids = {h.id for h in hits}
        self.heroines = [h for h in self.heroines if h.id not in ids]
        self._rebuild_index()
        self.save()
        return len(removed), removed

    def add_spot(self, work: str, name: str, link: str = "", region: str = "") -> tuple[bool, str]:
        work, name = work.strip(), name.strip()
        if not work or not name:
            return False, "作品名和地点名都不能为空"
        if len(self.spots) >= MAX_SPOTS:
            return False, f"圣地数量已达上限 {MAX_SPOTS}"
        spot = Spot(work=work, name=name, link=link, region=region)
        if spot.key in self._spot_keys:
            return False, f"《{work}》的「{name}」已收录"
        self.spots.append(spot)
        self._spot_keys.add(spot.key)
        self.save()
        return True, f"《{work}》→ {name}（当前 {len(self.spots)} 条）"

    def remove_spot(self, keyword: str) -> tuple[int, list[str]]:
        q = keyword.strip().lower()
        if not q:
            return 0, []
        hits = [
            s
            for s in self.spots
            if q in s.work.lower() or q in s.name.lower() or q in s.region.lower()
        ]
        if not hits:
            return 0, []
        removed = [f"《{s.work}》{s.name}" for s in hits]
        ids = {s.id for s in hits}
        self.spots = [s for s in self.spots if s.id not in ids]
        self._rebuild_index()
        self.save()
        return len(removed), removed

    # ---------------- 查询 ----------------

    def find_spots(self, query: str, fuzzy: bool = True, limit: int = 5) -> list[Spot]:
        q = _norm(query)
        if not q:
            return []
        scored: list[tuple[int, Spot]] = []
        for spot in self.spots:
            work, name, region = _norm(spot.work), _norm(spot.name), _norm(spot.region)
            if work == q:
                score = 100
            elif fuzzy and work.startswith(q):
                score = 80
            elif fuzzy and q in work:
                score = 60
            elif fuzzy and q in name:
                score = 40
            elif fuzzy and region and q in region:
                score = 30
            else:
                continue
            scored.append((score, spot))
        scored.sort(key=lambda item: (-item[0], item[1].work, item[1].name))
        return [s for _, s in scored[: max(1, limit)]]

    def works(self) -> list[tuple[str, int]]:
        counter: dict[str, int] = {}
        for spot in self.spots:
            counter[spot.work] = counter.get(spot.work, 0) + 1
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    def merge_legacy(self) -> tuple[int, int]:
        """把旧 TXT 中尚不存在的条目补进来（幂等，可反复执行）。"""
        report = LoadReport()
        payload = self._read_legacy(report)
        added_h = added_s = 0
        for raw in payload.get("heroines") or []:
            heroine = Heroine.from_dict(raw)
            if heroine.name and heroine.key not in self._heroine_keys:
                self.heroines.append(heroine)
                self._heroine_keys.add(heroine.key)
                added_h += 1
        for raw in payload.get("spots") or []:
            spot = Spot.from_dict(raw)
            if spot.work and spot.name and spot.key not in self._spot_keys:
                self.spots.append(spot)
                self._spot_keys.add(spot.key)
                added_s += 1
        if added_h or added_s:
            self.save()
        return added_h, added_s

    def stats(self) -> dict[str, int]:
        return {
            "heroines": len(self.heroines),
            "spots": len(self.spots),
            "works": len({s.work for s in self.spots}),
        }


class StateStore:
    """每日抽签/重抽的轻量状态，单独存文件避免频繁重写主数据。"""

    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / STATE_FILE
        self.data: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("users"), dict):
                self.data = data["users"]
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            self.data = {}

    def save(self) -> None:
        today = time.strftime("%Y-%m-%d")
        # 只保留最近 2 天的记录，防止无限膨胀
        self.data = {k: v for k, v in self.data.items() if v.get("date") in (today,)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".state-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"users": self.data}, f, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def reroll_used(self, key: str, today: str) -> int:
        item = self.data.get(key) or {}
        return int(item.get("reroll", 0)) if item.get("date") == today else 0

    def mark_reroll(self, key: str, today: str) -> int:
        used = self.reroll_used(key, today) + 1
        self.data[key] = {"date": today, "reroll": used}
        self.save()
        return used
