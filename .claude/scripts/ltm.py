"""
ltm.py — Long Term Memory System

三层记忆结构：
- STM (Short-Term): Session 内存，TTL=1小时
- ITM (Intermediate): 7 天内任务相关，TTL=7天
- LTM (Long-Term): 永久沉淀的模式/规则

Usage:
    from ltm import LTM
    ltm = LTM()

    # 存储记忆
    ltm.store("pattern:api-error-handling", {...}, memory_type="pattern")

    # 检索相关记忆
    memories = ltm.retrieve("API 错误处理")

    # 注入到 context
    context = ltm.inject_to_context(max_memories=5)
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import fnmatch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import (
    LTM_DIR, LTM_STM_DIR, LTM_ITM_DIR, LTM_LTM_DIR,
    LTM_PATTERNS_DIR, LTM_RULES_DIR, LTM_ANTIPATTERNS_DIR, LTM_INDEX
)


class MemoryType(str, Enum):
    """记忆类型"""
    PATTERN = "pattern"           # 成功解决问题的模式
    RULE = "rule"                 # 经验证的规则
    ANTI_PATTERN = "anti-pattern" # 已知失败模式
    INSIGHT = "insight"           # 跨事件洞察
    CONTEXT = "context"           # 任务上下文


class MemoryTTL(int, Enum):
    """记忆 TTL 配置（秒）"""
    STM = 3600                    # 1 小时
    ITM = 7 * 24 * 3600          # 7 天
    LTM = 365 * 24 * 3600         # 1 年（触发 consolidate）


@dataclass
class Memory:
    """记忆条目"""
    id: str                      # 唯一 ID: MEM-{type}-{hash}
    type: MemoryType
    key: str                     # 语义 key（供检索）
    content: dict                # 记忆内容
    evidence: list[str] = field(default_factory=list)  # 证据文件
    confidence: float = 0.5      # 置信度 0-1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    accessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    access_count: int = 0        # 访问次数
    ttl: int = MemoryTTL.ITM     # TTL 秒数
    tags: list[str] = field(default_factory=list)     # 标签
    source: str = ""              # 来源: self-reflect, insight-extract, manual

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Memory":
        d["type"] = MemoryType(d["type"]) if isinstance(d["type"], str) else d["type"]
        return cls(**d)

    def is_expired(self) -> bool:
        """检查是否过期"""
        created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - created
        return age.total_seconds() > self.ttl

    def touch(self) -> None:
        """更新访问时间"""
        self.accessed_at = datetime.now(timezone.utc).isoformat()
        self.access_count += 1


class LTM:
    """
    长期记忆系统

    三层存储：
    - STM: .chatlabs/ltm/stm/ — Session 内存，重启丢失
    - ITM: .chatlabs/ltm/itm/ — 7 天内记忆
    - LTM: .chatlabs/ltm/ltm/ — 永久沉淀（patterns/rules/anti-patterns）
    """

    def __init__(self):
        self._ensure_dirs()
        self._stm_cache: dict[str, Memory] = {}  # 内存缓存

    def _ensure_dirs(self) -> None:
        """确保目录存在"""
        for d in [LTM_DIR, LTM_STM_DIR, LTM_ITM_DIR, LTM_LTM_DIR,
                  LTM_PATTERNS_DIR, LTM_RULES_DIR, LTM_ANTIPATTERNS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def _generate_id(self, memory_type: MemoryType, key: str) -> str:
        """生成唯一 ID"""
        hash_input = f"{memory_type.value}:{key}:{datetime.now(timezone.utc).isoformat()}"
        hash_val = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"MEM-{memory_type.value.upper()[:4]}-{hash_val}"

    def _get_storage_path(self, memory: Memory) -> Path:
        """获取存储路径"""
        if memory.type == MemoryType.PATTERN:
            return LTM_PATTERNS_DIR / f"{memory.id}.json"
        elif memory.type == MemoryType.RULE:
            return LTM_RULES_DIR / f"{memory.id}.json"
        elif memory.type == MemoryType.ANTI_PATTERN:
            return LTM_ANTIPATTERNS_DIR / f"{memory.id}.json"
        elif memory.type == MemoryType.INSIGHT:
            insights_dir = LTM_LTM_DIR / "insights"
            insights_dir.mkdir(parents=True, exist_ok=True)
            return insights_dir / f"{memory.id}.json"
        else:
            return LTM_ITM_DIR / f"{memory.id}.json"

    def _search_score(self, memory: Memory, query: str) -> float:
        """
        计算记忆与查询的相关性得分

        评分维度：
        - key 包含查询词: +0.5
        - tags 匹配: +0.3
        - 置信度高: +0.2
        """
        score = 0.0
        query_lower = query.lower()

        # Key 匹配
        if query_lower in memory.key.lower():
            score += 0.5

        # Tags 匹配
        for tag in memory.tags:
            if query_lower in tag.lower():
                score += 0.3
                break

        # 置信度加成
        score += memory.confidence * 0.2

        return score

    # ── 核心 API ─────────────────────────────────────────────────────

    def store(
        self,
        key: str,
        content: dict,
        memory_type: MemoryType,
        ttl: Optional[int] = None,
        tags: Optional[list[str]] = None,
        evidence: Optional[list[str]] = None,
        confidence: float = 0.5,
        source: str = "manual"
    ) -> Memory:
        """
        存储记忆

        Args:
            key: 语义 key（供检索）
            content: 记忆内容
            memory_type: 记忆类型
            ttl: TTL 秒数（默认根据类型）
            tags: 标签
            evidence: 证据文件列表
            confidence: 置信度 0-1
            source: 来源

        Returns:
            Memory 对象
        """
        # 设置 TTL
        if ttl is None:
            ttl_map = {
                MemoryType.PATTERN: MemoryTTL.LTM,
                MemoryType.RULE: MemoryTTL.LTM,
                MemoryType.ANTI_PATTERN: MemoryTTL.LTM,
                MemoryType.INSIGHT: MemoryTTL.LTM,
                MemoryType.CONTEXT: MemoryTTL.ITM,
            }
            ttl = ttl_map.get(memory_type, MemoryTTL.ITM)

        memory = Memory(
            id=self._generate_id(memory_type, key),
            type=memory_type,
            key=key,
            content=content,
            ttl=ttl,
            tags=tags or [],
            evidence=evidence or [],
            confidence=confidence,
            source=source,
        )

        # 存储到文件
        path = self._get_storage_path(memory)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(memory.to_dict(), ensure_ascii=False, indent=2))

        # 更新索引（针对 LTM 层）
        if memory.type in [MemoryType.PATTERN, MemoryType.RULE, MemoryType.ANTI_PATTERN, MemoryType.INSIGHT]:
            self._update_index(memory)

        # 缓存到 STM
        self._stm_cache[memory.id] = memory

        return memory

    def retrieve(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        limit: int = 10,
        min_score: float = 0.1
    ) -> list[Memory]:
        """
        语义检索记忆

        Args:
            query: 查询字符串
            memory_types: 筛选的记忆类型（None = 全部）
            limit: 返回数量上限
            min_score: 最低相关度阈值

        Returns:
            按相关性排序的记忆列表
        """
        candidates: list[tuple[float, Memory]] = []

        # 1. 先查 STM 缓存
        for memory in self._stm_cache.values():
            if not memory.is_expired():
                score = self._search_score(memory, query)
                if score >= min_score:
                    candidates.append((score, memory))

        # 2. 查 ITM 层
        for path in LTM_ITM_DIR.glob("*.json"):
            try:
                memory = Memory.from_dict(json.loads(path.read_text()))
                if memory.is_expired():
                    continue
                if memory_types and memory.type not in memory_types:
                    continue
                score = self._search_score(memory, query)
                if score >= min_score:
                    candidates.append((score, memory))
            except Exception:
                continue

        # 3. 查 LTM 层（patterns/rules/anti-patterns）
        for search_dir in [LTM_PATTERNS_DIR, LTM_RULES_DIR, LTM_ANTIPATTERNS_DIR]:
            for path in search_dir.glob("*.json"):
                try:
                    memory = Memory.from_dict(json.loads(path.read_text()))
                    if memory_types and memory.type not in memory_types:
                        continue
                    score = self._search_score(memory, query)
                    if score >= min_score:
                        candidates.append((score, memory))
                except Exception:
                    continue

        # 按得分排序，取 top N
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in candidates[:limit]]

    def inject_to_context(
        self,
        query: Optional[str] = None,
        max_memories: int = 5,
        memory_types: Optional[list[MemoryType]] = None
    ) -> list[dict]:
        """
        注入相关记忆到 context

        用于 session-start 时加载相关记忆

        Returns:
            格式化的记忆列表
        """
        if query:
            memories = self.retrieve(query, memory_types, limit=max_memories)
        else:
            # 默认取最近的 high-confidence 记忆
            memories = self._get_recent_high_confidence(limit=max_memories, memory_types=memory_types)

        result = []
        for m in memories:
            m.touch()
            result.append({
                "id": m.id,
                "type": m.type.value,
                "key": m.key,
                "summary": self._summarize_content(m.content),
                "confidence": m.confidence,
                "tags": m.tags,
                "evidence": m.evidence,
            })

        return result

    def _summarize_content(self, content: dict) -> str:
        """生成内容摘要"""
        if "pattern" in content:
            return content["pattern"][:200]
        if "description" in content:
            return content["description"][:200]
        if "rule" in content:
            return content["rule"][:200]
        return str(content)[:200]

    def _get_recent_high_confidence(
        self,
        limit: int = 5,
        memory_types: Optional[list[MemoryType]] = None
    ) -> list[Memory]:
        """获取最近的高置信度记忆"""
        all_memories: list[Memory] = []

        for search_dir in [LTM_PATTERNS_DIR, LTM_RULES_DIR, LTM_ANTIPATTERNS_DIR]:
            for path in search_dir.glob("*.json"):
                try:
                    m = Memory.from_dict(json.loads(path.read_text()))
                    if m.confidence >= 0.7:
                        all_memories.append(m)
                except Exception:
                    continue

        # 按访问时间降序
        all_memories.sort(key=lambda x: x.accessed_at, reverse=True)
        return all_memories[:limit]

    def _update_index(self, memory: Memory) -> None:
        """更新 LTM 索引"""
        index_entries = []
        if LTM_INDEX.exists():
            try:
                with LTM_INDEX.open("r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            index_entries.append(json.loads(line))
            except Exception:
                pass

        # 检查是否已存在
        existing = [i for i in index_entries if i.get("id") == memory.id]
        if existing:
            # 更新
            for i, entry in enumerate(index_entries):
                if entry.get("id") == memory.id:
                    index_entries[i] = {
                        "id": memory.id,
                        "type": memory.type.value,
                        "key": memory.key,
                        "confidence": memory.confidence,
                        "tags": memory.tags,
                    }
        else:
            index_entries.append({
                "id": memory.id,
                "type": memory.type.value,
                "key": memory.key,
                "confidence": memory.confidence,
                "tags": memory.tags,
            })

        LTM_INDEX.parent.mkdir(parents=True, exist_ok=True)
        LTM_INDEX.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in index_entries) + "\n"
        )

    # ── 记忆管理 ─────────────────────────────────────────────────────

    def consolidate(self, dry_run: bool = False) -> dict:
        """
        每日 consolidate: ITM → LTM

        - ITM 中高置信度（≥0.8）且访问≥3次 → 提升到 LTM
        - ITM 中过期记忆 → 删除
        - LTM 中久未访问（>30天）→ 降级或删除

        Returns:
            操作统计
        """
        stats = {
            "promoted": 0,
            "demoted": 0,
            "deleted": 0,
            "errors": []
        }

        # 1. 处理 ITM → LTM 提升
        for path in LTM_ITM_DIR.glob("*.json"):
            try:
                memory = Memory.from_dict(json.loads(path.read_text()))

                # 删除过期
                if memory.is_expired():
                    if not dry_run:
                        path.unlink()
                    stats["deleted"] += 1
                    continue

                # 检查是否可以提升到 LTM
                if memory.confidence >= 0.8 and memory.access_count >= 3:
                    # 创建 LTM 版本
                    ltm_memory = Memory(
                        id=memory.id,
                        type=memory.type,
                        key=memory.key,
                        content=memory.content,
                        ttl=MemoryTTL.LTM,
                        tags=memory.tags,
                        evidence=memory.evidence,
                        confidence=memory.confidence,
                        source=memory.source,
                    )
                    if not dry_run:
                        ltm_path = self._get_storage_path(ltm_memory)
                        ltm_path.parent.mkdir(parents=True, exist_ok=True)
                        ltm_path.write_text(json.dumps(ltm_memory.to_dict(), ensure_ascii=False, indent=2))
                        path.unlink()  # 删除 ITM 版本
                        self._update_index(ltm_memory)
                    stats["promoted"] += 1
            except Exception as e:
                stats["errors"].append(str(e))

        # 2. 处理 LTM 降级
        for search_dir in [LTM_PATTERNS_DIR, LTM_RULES_DIR, LTM_ANTIPATTERNS_DIR]:
            for path in search_dir.glob("*.json"):
                try:
                    memory = Memory.from_dict(json.loads(path.read_text()))

                    # 超过 30 天无访问 → 删除（认为已过时）
                    accessed = datetime.fromisoformat(memory.accessed_at.replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - accessed).days > 30:
                        if not dry_run:
                            path.unlink()
                            self._remove_from_index(memory.id)
                        stats["demoted"] += 1
                except Exception as e:
                    stats["errors"].append(str(e))

        return stats

    def _remove_from_index(self, memory_id: str) -> None:
        """从索引中移除"""
        if not LTM_INDEX.exists():
            return
        try:
            entries = []
            with LTM_INDEX.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("id") != memory_id:
                            entries.append(entry)
            LTM_INDEX.write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n"
            )
        except Exception:
            pass

    def get_health_status(self) -> dict:
        """
        获取 LTM 健康度状态

        Returns:
            健康度报告
        """
        counts = {
            "stm_cache": len(self._stm_cache),
            "patterns": len(list(LTM_PATTERNS_DIR.glob("*.json"))),
            "rules": len(list(LTM_RULES_DIR.glob("*.json"))),
            "anti_patterns": len(list(LTM_ANTIPATTERNS_DIR.glob("*.json"))),
            "itmemories": len(list(LTM_ITM_DIR.glob("*.json"))),
        }

        total = sum(v for k, v in counts.items() if k != "stm_cache")

        return {
            "total_memories": total,
            "in_cache": counts["stm_cache"],
            "by_type": counts,
            "health": "ok" if total > 0 else "empty",
            "recommendation": self._get_recommendation(counts)
        }

    def _get_recommendation(self, counts: dict) -> str:
        """根据状态给出建议"""
        total = sum(v for k, v in counts.items() if k != "stm_cache")
        if total == 0:
            return "LTM 为空，开始使用 self-reflect 积累经验"
        if counts["patterns"] == 0:
            return "暂无成功模式，考虑将成功的解决经验存入 LTM"
        if counts["anti_patterns"] > counts["patterns"] * 2:
            return "失败模式过多，建议加强成功经验的沉淀"
        return "LTM 健康，继续保持"

    def gc(self) -> dict:
        """
        垃圾回收：清理过期和孤立记忆

        Returns:
            清理统计
        """
        stats = {
            "orphaned_index_entries": 0,
            "orphaned_files": 0,
            "expired_itm": 0,
        }

        # 1. 清理孤立的索引条目
        if LTM_INDEX.exists():
            valid_ids = set()
            for search_dir in [LTM_PATTERNS_DIR, LTM_RULES_DIR, LTM_ANTIPATTERNS_DIR]:
                for path in search_dir.glob("*.json"):
                    try:
                        m = Memory.from_dict(json.loads(path.read_text()))
                        valid_ids.add(m.id)
                    except Exception:
                        continue

            entries = []
            with LTM_INDEX.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("id") in valid_ids:
                            entries.append(entry)
                        else:
                            stats["orphaned_index_entries"] += 1

            LTM_INDEX.parent.mkdir(parents=True, exist_ok=True)
            LTM_INDEX.write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n"
            )

        # 2. 清理过期 ITM
        for path in LTM_ITM_DIR.glob("*.json"):
            try:
                memory = Memory.from_dict(json.loads(path.read_text()))
                if memory.is_expired():
                    path.unlink()
                    stats["expired_itm"] += 1
            except Exception:
                continue

        return stats


# ── CLI 入口 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="LTM CLI")
    parser.add_argument("action", choices=["store", "retrieve", "consolidate", "gc", "health", "inject"])
    parser.add_argument("--key", help="记忆 key")
    parser.add_argument("--content", help="记忆内容（JSON 字符串）")
    parser.add_argument("--type", default="context", choices=["pattern", "rule", "anti-pattern", "insight", "context"])
    parser.add_argument("--query", help="检索 query")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ltm = LTM()

    if args.action == "store":
        content = json.loads(args.content) if args.content else {}
        memory = ltm.store(args.key, content, MemoryType(args.type))
        print(f"Stored: {memory.id}")

    elif args.action == "retrieve":
        results = ltm.retrieve(args.query or "", limit=args.limit)
        for m in results:
            print(f"[{m.id}] {m.key} (confidence: {m.confidence})")

    elif args.action == "consolidate":
        stats = ltm.consolidate(dry_run=args.dry_run)
        print(f"Consolidate: {stats}")

    elif args.action == "gc":
        stats = ltm.gc()
        print(f"GC: {stats}")

    elif args.action == "health":
        status = ltm.get_health_status()
        print(f"Health: {json.dumps(status, indent=2, ensure_ascii=False)}")

    elif args.action == "inject":
        results = ltm.inject_to_context(query=args.query, max_memories=args.limit)
        print(f"Injected {len(results)} memories:")
        for r in results:
            print(f"  [{r['type']}] {r['key']}: {r['summary'][:80]}...")
