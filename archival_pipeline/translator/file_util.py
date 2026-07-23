"""FileUtil — 移植自 detox 的 file.c 中的 ignore_file / is_protected 函数

安全机制（移植自 detox 的 check logic）：
1. is_protected()  — 检查是否为 "." / ".."
2. ignore_file()   — 检查是否应忽略该文件
3. check_rename_safety() — 重命名前检查目标是否存在且不同
"""
from pathlib import Path


def is_protected(name: str) -> bool:
    """检查是否为 "." 或 ".." — 移植自 detox 的 is_protected()

    detox 原文:
        return (filename[0] == '.' && (filename[1] == '\\0' ||
                (filename[1] == '.' && filename[2] == '\\0')));
    """
    if name == "." or name == "..":
        return True
    return False


def ignore_file(name: str, ignore_set: set[str] | None = None) -> bool:
    """检查文件是否应忽略 — 移植自 detox 的 ignore_file()

    detox 规则（组合）:
    1. 文件名以 "." 开头 → 忽略
    2. 文件名在 ignore_set 中 → 忽略

    参数:
        name: 文件名（不含路径）
        ignore_set: 忽略文件名集合
    """
    if name.startswith("."):
        return True
    if ignore_set and name in ignore_set:
        return True
    return False


def check_rename_safety(old_path: Path, new_path: Path) -> str | None:
    """重命名前安全检查 — 移植自 detox 的 parse_file() 中的冲突检测

    detox 逻辑:
        如果 new_path 已存在，检查：
        - 不同设备 → error
        - 不同 inode → error
        - 多个硬链接 → error

    Python 版:
        - 目标已存在且不是同文件 → error
        - 目标已存在且是同文件 → safe（无需重命名）
        - 目标不存在 → safe

    返回: None = 安全，str = 错误原因
    """
    if not new_path.exists():
        return None

    # Windows 上可以通过 resolve() 判断是否为同文件
    try:
        if old_path.resolve() == new_path.resolve():
            return None  # 同文件，无需重命名
        # 目标已存在 → 冲突
        return f"target already exists: {new_path.name}"
    except (FileNotFoundError, PermissionError, OSError) as e:
        return f"safety check failed: {e}"
