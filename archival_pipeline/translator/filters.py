"""Filters — 移植自 detox 的 clean_string.c + clean_utf_8.c

每个 Filter 做一件事，可组合到 Sequence 中。

新增（移植自 detox C 源码）:
- safe()         — 字符级替换（移植 clean_safe + safe.tbl）
- safe_translate() — 逐字符查表转写（移植 clean_iso8859_1）
- utf8_translate() — UTF-8 解码后逐码点查表（移植 clean_utf_8）
"""
import re
from typing import Callable


class Filter:
    """单个过滤器 — 等价于 detox sequence 中的一条规则"""

    def __init__(self, name: str, fn: Callable[[str], str]):
        self.name = name
        self.fn = fn

    def apply(self, text: str) -> str:
        return self.fn(text)


def translate(table: "TranslationTable") -> Filter:  # noqa: F821
    """翻译过滤器：映射表替换 — 等价于 clean_iso8859_1 / clean_safe

    本过滤器使用 substring 匹配（"长词优先"），适用于日→中翻译。
    """
    def _fn(text: str) -> str:
        return table.translate(text)
    return Filter("translate", _fn)


def safe(table: dict[int, str] | None = None) -> Filter:
    """安全字符替换过滤器 — 移植自 detox 的 clean_safe()

    逐字符检查，如果在映射表中则替换为对应值。
    不在映射表中的字符保留原样（detox: "Null translation == leave it alone"）。

    默认使用 safe.tbl 的全部映射：控制字符→_、特殊字符→_、括号→-、&→_and_。

    参数:
        table: 字符码点(int)→替换字符串(str) 映射。
               传 None 则使用内置 safe.tbl 内容。
    """
    from archival_pipeline.translator.builtin_tables import SAFE_TABLE, SAFE_MAX_DATA_LENGTH

    def _fn(text: str) -> str:
        tbl = SAFE_TABLE if table is None else table
        out = []
        for ch in text:
            code = ord(ch)
            replacement = tbl.get(code)
            if replacement is not None:
                out.append(replacement)
            else:
                out.append(ch)
        return "".join(out)
    return Filter("safe", _fn)


def safe_translate(table: dict[int, str] | None = None,
                   default_translation: str | None = None) -> Filter:
    """逐字符转写过滤器 — 移植自 detox 的 clean_iso8859_1()

    对字符码点 >= 0x80 的字符查表替换，ASCII 保留原样。
    default_translation=None 时不在表中的字符保留原样（detox 默认行为）。

    参数:
        table: 字符码点(int)→转写字符串(str) 映射。
        default_translation: 表中没有时的兜底替换。None=保留原样。
    """
    from archival_pipeline.translator.builtin_tables import ISO8859_1_TABLE

    def _fn(text: str) -> str:
        tbl = ISO8859_1_TABLE if table is None else table
        out = []
        for ch in text:
            code = ord(ch)
            if code < 0x80:
                out.append(ch)
                continue
            replacement = tbl.get(code)
            if replacement is not None:
                out.append(replacement)
            elif default_translation is not None:
                out.append(default_translation)
            else:
                out.append(ch)
        return "".join(out)
    return Filter("safe_translate", _fn)


def utf8_translate(table: dict[int, str] | None = None,
                   default_translation: str | None = None) -> Filter:
    """UTF-8 码点转写过滤器 — 移植自 detox 的 clean_utf_8()

    对多字节 UTF-8 解码为 Unicode 码点后查表替换。
    ASCII 字符（单字节 < 0x80）保留原样。

    参数:
        table: Unicode 码点(int)→转写字符串(str) 映射。
        default_translation: 表中没有时的兜底替换。None=保留原样。
    """
    from archival_pipeline.translator.builtin_tables import UNICODE_TABLE

    def _fn(text: str) -> str:
        tbl = UNICODE_TABLE if table is None else table
        table_max = max(len(v) for v in tbl.values()) if tbl else 1

        # 手动 UTF-8 解码（移植 detox 的 get_utf_8_width + clean_utf_8）
        def _utf8_width(b: int) -> int:
            if b & 0xC0 == 0xC0:   # UTF-8 编码起始
                if b & 0xFE == 0xFC:  return 6
                if b & 0xFC == 0xF8:  return 5
                if b & 0xF8 == 0xF0:  return 4
                if b & 0xF0 == 0xE0:  return 3
                if b & 0xE0 == 0xC0:  return 2
            if b & 0x80:  return -1   # 无效
            return 1

        data = text.encode("utf-8")
        i = 0
        out = []
        while i < len(data):
            b = data[i]
            width = _utf8_width(b)

            if width < 1:
                out.append("_")  # 无效编码
                i += 1
                continue

            if width == 1:
                out.append(chr(b))
                i += 1
                continue

            # 多字节 UTF-8: 解码码点
            code = 0
            if width == 2:
                code = b & 0x1F
            elif width == 3:
                code = b & 0x0F
            elif width == 4:
                code = b & 0x07
            elif width == 5:
                code = b & 0x03
            elif width == 6:
                code = b & 0x01

            valid = True
            for j in range(1, width):
                i += 1
                if i >= len(data):
                    valid = False
                    break
                cb = data[i]
                if cb & 0xC0 != 0x80:
                    valid = False
                    break
                code = (code << 6) | (cb & 0x3F)

            if not valid:
                out.append("_")
                continue

            replacement = tbl.get(code)
            if replacement is not None:
                out.append(replacement)
            elif default_translation is not None:
                out.append(default_translation)
            else:
                # 保留原始 UTF-8 字节（detox: null translation == leave it alone）
                start = i - width + 1
                out.append(data[start:i+1].decode("utf-8", errors="replace"))

            i += 1

        return "".join(out)
    return Filter("utf8_translate", _fn)


def wipeup(remove_trailing: bool = False) -> Filter:
    """清理重复分隔符 — 移植自 detox 的 clean_wipeup()

    detox 原文:
        Reduces any series of underscores or dashes to a single character.
        The dash takes precedence.
        If remove_trailing is set, then periods are added to the set.
        If a hash character, underscore, or dash are present at the start
        of the filename, they will be removed.
    """
    def _fn(text: str) -> str:
        s = text.lstrip("-_#")
        if not s:
            return text
        out = []
        sep = None
        srch = ".-_" if remove_trailing else "-_"
        for ch in s:
            idx = srch.find(ch)
            if idx >= 0:
                if sep is None or idx < srch.find(sep):
                    sep = ch
            else:
                if sep is not None:
                    out.append(sep)
                    sep = None
                out.append(ch)
        if sep is not None:
            out.append(sep)
        return "".join(out)
    return Filter("wipeup", _fn)


def max_length(max_len: int = 256) -> Filter:
    """截断文件名保留扩展名 — 移植自 detox 的 clean_max_length()

    detox 原文:
        Look back 5 characters for a second extension.
        If max_length <= extension_length, warn and return original.
    """
    def _fn(text: str) -> str:
        if len(text) <= max_len:
            return text

        ext = None
        # 找扩展名：最多回看 5 字符找第二个 . （detox 逻辑）
        dot = text.rfind(".")
        if dot >= 0 and dot < len(text) - 1:
            # 回看最多 5 字符
            back = max(dot - 5, 0)
            second = text.rfind(".", back, dot)
            if second >= 0:
                ext = text[second:]
            else:
                ext = text[dot:]

        if ext is None:
            return text[:max_len]

        if max_len <= len(ext):
            # detox: warning + give up
            return text

        body_len = max_len - len(ext)
        return text[:body_len] + ext
    return Filter("max_length", _fn)


def lower() -> Filter:
    """转小写 — 移植自 detox 的 clean_lower()"""
    def _fn(text: str) -> str:
        return text.lower()
    return Filter("lower", _fn)


def uncgi() -> Filter:
    """解码 CGI (%XX) — 移植自 detox 的 clean_uncgi()

    解码 %XX 为对应字符，+ → 空格。
    """
    def _fn(text: str) -> str:
        out = []
        i = 0
        while i < len(text):
            if text[i] == "%" and i + 2 < len(text):
                try:
                    out.append(chr(int(text[i+1:i+3], 16)))
                    i += 3
                    continue
                except (ValueError, IndexError):
                    pass
            elif text[i] == "+":
                out.append(" ")
                i += 1
                continue
            out.append(text[i])
            i += 1
        return "".join(out)
    return Filter("uncgi", _fn)


def strip_extras() -> Filter:
    """清理多余空格和标点（扩展过滤器 — 非 detox 原生）"""
    def _fn(text: str) -> str:
        s = re.sub(r"\s+", " ", text)
        s = s.rstrip(". ").lstrip()
        s = re.sub(r"_{2,}", "_", s)
        s = re.sub(r"-{2,}", "-", s)
        return s
    return Filter("strip_extras", _fn)
