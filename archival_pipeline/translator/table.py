"""TranslationTable — 移植自 detox 的 table_t

- key: 原文（支持多字节 UTF-8）
- value: 译文
- 排序：key 长度降序（长匹配优先）
- 支持从 JSON/dict 加载
"""
import json
from pathlib import Path


class TranslationTable:
    """翻译映射表 — 等价于 detox 的 table_t + .tbl 文件"""

    def __init__(self, default_translation: str | None = None):
        self._entries: dict[str, str] = {}
        self._sorted_keys: list[str] = []
        self.default_translation = default_translation
        self.hits = 0
        self.misses = 0

    def put(self, key: str, value: str) -> None:
        self._entries[key] = value
        self._sorted_keys = sorted(self._entries.keys(), key=lambda k: -len(k))

    def get(self, key: str) -> str | None:
        val = self._entries.get(key)
        if val is not None:
            self.hits += 1
        else:
            self.misses += 1
        return val

    def has(self, key: str) -> bool:
        return key in self._entries

    def translate(self, text: str) -> str:
        """对文本应用所有映射（长优先匹配）"""
        for key in self._sorted_keys:
            if key in text:
                text = text.replace(key, self._entries[key])
        return text

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def keys(self) -> list[str]:
        return list(self._sorted_keys)

    def to_dict(self) -> dict[str, str]:
        return dict(self._entries)

    def to_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self._entries, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "TranslationTable":
        t = cls()
        for k, v in data.items():
            t.put(k, v)
        return t

    @classmethod
    def from_json(cls, path: str | Path) -> "TranslationTable":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_tuples(cls, tuples: list[tuple[str, str]]) -> "TranslationTable":
        t = cls()
        for k, v in tuples:
            t.put(k, v)
        return t

    def to_tuples(self) -> list[tuple[str, str]]:
        return [(k, self._entries[k]) for k in self._sorted_keys]

    @classmethod
    def merge(cls, *tables: "TranslationTable") -> "TranslationTable":
        """合并多个表，后者优先覆盖前者"""
        merged = cls()
        for t in tables:
            for k, v in t._entries.items():
                merged.put(k, v)
        return merged
