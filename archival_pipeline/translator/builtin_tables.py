"""BuiltinTables — 移植自 detox 的 .tbl 文件和 builtin_table.c

按 detox 架构，每个映射表是 (key=字符码点, value=替换字符串) 的查找表。
Python 版直接保存为 dict[int, str]。
"""

# ============================================================
# safe.tbl — 替换 shell 不安全字符
# ============================================================
# 控制字符 → "_"
SAFE_CONTROL_CHARS: dict[int, str] = {
    0x01: "_",   # SOH
    0x02: "_",   # STX
    0x03: "_",   # ETX
    0x04: "_",   # EOT
    0x05: "_",   # ENQ
    0x06: "_",   # ACK
    0x07: "_",   # BEL
    0x08: "_",   # BS
    0x09: "_",   # HT
    0x0a: "_",   # LF
    0x0b: "_",   # VT
    0x0c: "_",   # FF
    0x0d: "_",   # CR
    0x0e: "_",   # SO
    0x0f: "_",   # SI
    0x10: "_",   # DLE
    0x11: "_",   # DC1
    0x12: "_",   # DC2
    0x13: "_",   # DC3
    0x14: "_",   # DC4
    0x15: "_",   # NAK
    0x16: "_",   # SYN
    0x17: "_",   # ETB
    0x18: "_",   # CAN
    0x19: "_",   # EM
    0x1a: "_",   # SUB
    0x1b: "_",   # ESC
    0x1c: "_",   # FS
    0x1d: "_",   # GS
    0x1e: "_",   # RS
    0x1f: "_",   # US
    0x7f: "_",   # DEL
}

# 特殊字符 → "_"
SAFE_SPECIAL_CHARS: dict[int, str] = {
    0x20: "_",   # 空格
    0x21: "_",   # !
    0x22: "_",   # "
    0x24: "_",   # $
    0x27: "_",   # '
    0x2a: "_",   # *
    0x2f: "_",   # /
    0x3a: "_",   # :
    0x3b: "_",   # ;
    0x3c: "_",   # <
    0x3e: "_",   # >
    0x3f: "_",   # ?
    0x40: "_",   # @
    0x5c: "_",   # \\
    0x60: "_",   # `
    0x7c: "_",   # |
}

# 括号类 → "-"（detox 设计：可配对字符用 -）
SAFE_BRACKET_CHARS: dict[int, str] = {
    0x28: "-",   # (
    0x29: "-",   # )
    0x5b: "-",   # [
    0x5d: "-",   # ]
    0x7b: "-",   # {
    0x7d: "-",   # }
}

# 特殊 → "_and_"
SAFE_AMPERSAND: dict[int, str] = {0x26: "_and_"}

# 完整 safe 表
SAFE_TABLE: dict[int, str] = {}
SAFE_TABLE.update(SAFE_CONTROL_CHARS)
SAFE_TABLE.update(SAFE_SPECIAL_CHARS)
SAFE_TABLE.update(SAFE_BRACKET_CHARS)
SAFE_TABLE.update(SAFE_AMPERSAND)

# 最大替换长度（用于分配输出 buffer）
SAFE_MAX_DATA_LENGTH = max(len(v) for v in SAFE_TABLE.values())


# ============================================================
# iso8859_1.tbl — 移植自 iso8859_1.tbl
# 拉丁 1 字符 → ASCII 转写
# ============================================================
ISO8859_1_TABLE: dict[int, str] = {
    # C1 控制字符 → _  (0x80-0x9f)
    0x80: "_", 0x81: "_", 0x82: "_", 0x83: "_",
    0x84: "_", 0x85: "_", 0x86: "_", 0x87: "_",
    0x88: "_", 0x89: "_", 0x8a: "_", 0x8b: "_",
    0x8c: "_", 0x8d: "_", 0x8e: "_", 0x8f: "_",
    0x90: "_", 0x91: "_", 0x92: "_", 0x93: "_",
    0x94: "_", 0x95: "_", 0x96: "_", 0x97: "_",
    0x98: "_", 0x99: "_", 0x9a: "_", 0x9b: "_",
    0x9c: "_", 0x9d: "_", 0x9e: "_", 0x9f: "_",

    # 可打印拉丁 1 转写
    0xa0: " ",    # NBSP → 空格
    0xa1: "!",    # ¡
    0xa2: "c",    # ¢ → c
    0xa3: "GBP",  # £ → GBP
    0xa4: "o",    # ¤ → o
    0xa5: "YEN",  # ¥ → YEN
    0xa7: "sec",  # § → sec
    0xa9: "(C)",  # ©
    0xaa: "a",    # ª → a
    0xab: "\"",   # « → "
    0xac: "-",    # ¬ → -
    0xae: "(R)",  # ®
    0xb0: "deg",  # ° → deg
    0xb1: "+-",   # ± → +-
    0xb2: "2",    # ² → 2
    0xb3: "3",    # ³ → 3
    0xb4: "'",    # ´ → '
    0xb5: "u",    # µ → u
    0xb6: "P",    # ¶ → P
    0xb7: ".",    # ·
    0xb8: ",",    # ¸ → ,
    0xb9: "1",    # ¹ → 1
    0xba: "o",    # º → o
    0xbb: "\"",   # » → "
    0xbf: "?",    # ¿
    0xc0: "A",    # À
    0xc1: "A",    # Á
    0xc2: "A",    # Â
    0xc3: "A",    # Ã
    0xc4: "Ae",   # Ä → Ae
    0xc5: "AA",   # Å → AA
    0xc6: "AE",   # Æ
    0xc7: "C",    # Ç
    0xc8: "E",    # È
    0xc9: "E",    # É
    0xca: "E",    # Ê
    0xcb: "E",    # Ë
    0xcc: "I",    # Ì
    0xcd: "I",    # Í
    0xce: "I",    # Î
    0xcf: "I",    # Ï
    0xd1: "N",    # Ñ
    0xd2: "O",    # Ò
    0xd3: "O",    # Ó
    0xd4: "O",    # Ô
    0xd5: "O",    # Õ
    0xd6: "Oe",   # Ö → Oe
    0xd7: "x",    # × → x
    0xd8: "O",    # Ø
    0xd9: "U",    # Ù
    0xda: "U",    # Ú
    0xdb: "U",    # Û
    0xdc: "Ue",   # Ü → Ue
    0xdd: "Y",    # Ý
    0xdf: "ss",   # ß → ss
    0xe0: "a",    # à
    0xe1: "a",    # á
    0xe2: "a",    # â
    0xe3: "a",    # ã
    0xe4: "ae",   # ä → ae
    0xe5: "aa",   # å → aa
    0xe6: "ae",   # æ
    0xe7: "c",    # ç
    0xe8: "e",    # è
    0xe9: "e",    # é
    0xea: "e",    # ê
    0xeb: "e",    # ë
    0xec: "i",    # ì
    0xed: "i",    # í
    0xee: "i",    # î
    0xef: "i",    # ï
    0xf1: "n",    # ñ
    0xf2: "o",    # ò
    0xf3: "o",    # ó
    0xf4: "o",    # ô
    0xf5: "o",    # õ
    0xf6: "oe",   # ö → oe
    0xf7: "/",    # ÷ → /
    0xf8: "o",    # ø
    0xf9: "u",    # ù
    0xfa: "u",    # ú
    0xfb: "u",    # û
    0xfc: "ue",   # ü → ue
    0xfd: "y",    # ý
    0xff: "y",    # ÿ
}

ISO8859_1_MAX_DATA_LENGTH = max(len(v) for v in ISO8859_1_TABLE.values())


# ============================================================
# unicode.tbl — 部分移植（常见 Unicode 转写）
# ============================================================
UNICODE_TABLE: dict[int, str] = {
    # 常见全角/特殊 Unicode 字符
    0x0130: "I",      # İ → I
    0x0152: "OE",     # Œ
    0x0153: "oe",     # œ
    0x0160: "S",      # Š
    0x0161: "s",      # š
    0x0178: "Y",      # Ÿ
    0x017d: "Z",      # Ž
    0x017e: "z",      # ž
    0x0192: "f",      # ƒ
    0x02c6: "^",      # ˆ
    0x02c7: "_",      # ˇ
    0x02d8: "_",      # ˘
    0x02d9: "_",      # ˙
    0x02da: "_",      # ˚
    0x02db: "_",      # ˛
    0x02dc: "~",      # ˜
    0x02dd: "'",      # ˝
    0x03b1: "alpha",  # α
    0x03b2: "beta",   # β
    0x03b3: "gamma",  # γ
    0x2013: "-",      # –
    0x2014: "--",     # —
    0x2018: "'",      # '
    0x2019: "'",      # '
    0x201a: ",",      # ‚
    0x201c: "\"",     # "
    0x201d: "\"",     # "
    0x201e: "\"",     # „
    0x2020: "_",      # †
    0x2021: "_",      # ‡
    0x2022: "*",      # •
    0x2026: "...",    # …
    0x2030: "ppm",    # ‰ → ppm
    0x2039: "<",      # ‹
    0x203a: ">",      # ›
    0x20ac: "EUR",    # € → EUR
    0x2122: "TM",     # ™
    0x2190: "<-",     # ←
    0x2192: "->",     # →
    0x2194: "<->",    # ↔
    0x2212: "-",      # −
    0x2260: "!=",     # ≠
    0x2264: "<=",     # ≤
    0x2265: ">=",     # ≥
    0x266a: "~",      # ♪
}

UNICODE_MAX_DATA_LENGTH = max(len(v) for v in UNICODE_TABLE.values()) if UNICODE_TABLE else 1
