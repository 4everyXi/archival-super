"""Sequence — 移植自 detox 的 sequence_t

按顺序对文件名应用一系列过滤器。
"""
from archival_pipeline.translator.filters import Filter
from archival_pipeline.translator.table import TranslationTable


class Sequence:
    """过滤器链 — 等价于 detox 的 sequence_t

    新增:
    - sequence_review() — 等价 detox 的 sequence_review()，用于预加载验证
    - run() 沿用现有接口
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.filters: list[Filter] = []
        self.source_filename: str | None = None  # 移植自 sequence_t.source_filename

    def add(self, f: Filter) -> "Sequence":
        self.filters.append(f)
        return self

    def review(self) -> list[str]:
        """验证序列 — 移植自 detox 的 sequence_review()

        检查所有过滤器是否有效，返回 warnings 列表。
        在 C 里 this loads translation tables; 在 Python 里做参数验证。
        """
        warnings = []
        for f in self.filters:
            if not callable(getattr(f, "apply", None)):
                warnings.append(f"filter '{f.name}' has no apply() method")
        return warnings

    def run(self, text: str) -> str:
        for f in self.filters:
            text = f.apply(text)
        return text

    def run_with_stats(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        result = text
        changes = []
        for f in self.filters:
            before = result
            result = f.apply(result)
            if result != before:
                d = before[:40] + "..." if len(before) > 43 else before
                changes.append((f.name, f"{d} -> {result[:60]}"))
        return result, changes

    def __repr__(self) -> str:
        filter_names = [f.name for f in self.filters]
        return f"Sequence('{self.name}', {filter_names})"


def create_archival_sequence(table: TranslationTable) -> Sequence:
    """创建档案化翻译的标准过滤器链

    顺序（移植 detox 的默认序列思路）:
    1. translate — 日→中翻译（substring 匹配）
    2. wipeup    — 清理重复分隔符
    3. strip_extras — 清理多余空格
    """
    from modules.translation import filters as f
    seq = Sequence("archival-translate")
    seq.add(f.translate(table))
    seq.add(f.wipeup(remove_trailing=True))
    seq.add(f.strip_extras())
    return seq


def create_detox_style_sequence(table: TranslationTable) -> Sequence:
    """创建 detox 风格的过滤器链

    顺序:
    1. translate  — 翻译（日→中）
    2. safe       — 字符级安全替换（等价 detox clean_safe + safe.tbl）
    3. wipeup     — 清理重复分隔符（等价 detox clean_wipeup）
    4. strip_extras — 清理多余空格
    """
    from modules.translation import filters as f
    seq = Sequence("detox-style")
    seq.add(f.translate(table))
    seq.add(f.safe())
    seq.add(f.wipeup(remove_trailing=True))
    seq.add(f.strip_extras())
    return seq


def create_full_sanitize_sequence() -> Sequence:
    """创建完整安全清洗序列（不翻译，只做字符替换+清理）

    顺序:
    1. safe       — 字符级安全替换
    2. wipeup     — 清理重复分隔符
    3. lower      — 转小写

    等价 detox 的 "lower" 序列。
    """
    from modules.translation import filters as f
    seq = Sequence("sanitize")
    seq.add(f.safe())
    seq.add(f.wipeup(remove_trailing=True))
    seq.add(f.lower())
    return seq
