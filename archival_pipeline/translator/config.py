"""Config — 移植自 detox 的 config_file.c + spoof_config_file()

detox 的配置系统：
1. 搜索路径: SYSCONFDIR/detoxrc -> /etc/detoxrc -> ~/.detoxrc -> XDG_CONFIG_HOME/detox/detoxrc
2. 找不到任何配置文件时: spoof_config_file() 生成内置默认序列
3. 每个序列是一组过滤器的有序链表

本模块移植此设计，提供：
- BuiltinConfig.spoof() — 生成内置默认序列（等价 spoof_config_file）
- ConfigFile — 配置容器（等价 config_file_t）
"""
from archival_pipeline.translator.filters import Filter, safe, wipeup, lower, uncgi, safe_translate, utf8_translate
from archival_pipeline.translator.sequence import Sequence


class BuiltinConfig:
    """内置配置生成器 — 移植自 detox 的 spoof_config_file()"""

    @staticmethod
    def spoof() -> list[Sequence]:
        """生成内置默认序列列表 — 等价 detox spoof_config_file()"""

        # 安全+清理过滤器（被多个序列共享 — 注意: detox 在 C 里共享 filter_t 指针引用）
        safe_filter: Filter = safe()
        safe_wipeup: Filter = wipeup(remove_trailing=True)
        safe_and_wipe = Filter("safe+wipeup", lambda s: safe_wipeup.apply(safe_filter.apply(s)))

        sequences = []

        # -- default: safe → wipeup（detox 默认序列）
        seq = Sequence("default")
        seq.add(safe()).add(wipeup(remove_trailing=True))
        sequences.append(seq)

        # -- archival-safe: translate → safe → wipeup（档案化各 翻译+安全+清理）
        seq = Sequence("archival-safe")
        seq.add(safe()).add(wipeup(remove_trailing=True))
        sequences.append(seq)

        # -- iso8859_1: safe_translate → safe → wipeup
        seq = Sequence("iso8859_1")
        seq.add(safe_translate()).add(safe()).add(wipeup(remove_trailing=True))
        sequences.append(seq)

        # -- utf_8: utf8_translate → safe → wipeup
        seq = Sequence("utf_8")
        seq.add(utf8_translate()).add(safe()).add(wipeup(remove_trailing=True))
        sequences.append(seq)

        # -- uncgi: uncgi → safe → wipeup
        seq = Sequence("uncgi")
        seq.add(uncgi()).add(safe()).add(wipeup(remove_trailing=True))
        sequences.append(seq)

        # -- lower: safe → lower → wipeup
        seq = Sequence("lower")
        seq.add(safe()).add(lower()).add(wipeup(remove_trailing=True))
        sequences.append(seq)

        # -- 纯过滤器（无复合）: safe-only, wipeup-only, lower-only, uncgi-only
        seq = Sequence("safe-only")
        seq.add(safe())
        sequences.append(seq)

        seq = Sequence("wipeup-only")
        seq.add(wipeup(remove_trailing=True))
        sequences.append(seq)

        seq = Sequence("lower-only")
        seq.add(lower())
        sequences.append(seq)

        seq = Sequence("uncgi-only")
        seq.add(uncgi())
        sequences.append(seq)

        return sequences

    @staticmethod
    def get_default() -> Sequence:
        """获取默认序列 — 等价 detox 的 sequence_choose_default(sequences, NULL)"""
        seqs = BuiltinConfig.spoof()
        for s in seqs:
            if s.name == "default":
                return s
        return seqs[0]


class ConfigFile:
    """配置容器 — 移植自 detox 的 config_file_t

    包含:
    - sequences: list[Sequence]  （等价 sequence_t 链表）
    - files_to_ignore: set[str]   （等价 filelist_t files_to_ignore）
    """

    def __init__(self):
        self.sequences: list[Sequence] = []
        self.files_to_ignore: set[str] = set()

    def choose_sequence(self, name: str | None = None) -> Sequence | None:
        """选择序列 — 移植自 detox 的 sequence_choose_default()

        参数:
            name: 序列名。None 则使用名为 "default" 的序列，若无则用首个
        """
        target = name or "default"
        for s in self.sequences:
            if s.name == target:
                return s
        # 找不到且用户没指定 → 用第一个
        if name is None and self.sequences:
            return self.sequences[0]
        return None

    @classmethod
    def load_default(cls) -> "ConfigFile":
        """加载默认配置 — 等价 detox 的 config_file_load() 无配置文件时的兜底"""
        cfg = cls()
        cfg.sequences = BuiltinConfig.spoof()
        cfg.files_to_ignore = {".", "..", "{arch}"}  # detox 默认忽略
        return cfg
