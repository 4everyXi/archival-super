"""FileList — 移植自 detox 的 filelist.c

等价 struct filelist_t:
    char **files;   // 字符串数组
    int max;        // 当前容量
    int count;      // 已用数量
    int ptr;        // 当前遍历指针

迭代器模式（for name in filelist: ...）。
"""
from typing import Iterator


class FileList:
    """文件列表 — 移植自 detox 的 filelist_t

    支持:
    - put(name)  — 添加文件
    - get()      — 获取下一个（迭代器式）
    - reset()    — 重置指针
    - count      — 文件总数
    - __iter__   — Python 迭代器
    """

    def __init__(self, chunk: int = 16):
        self._files: list[str] = []
        self._ptr: int = 0
        self._chunk = chunk

    def put(self, name: str) -> None:
        """添加文件 — 移植自 detox 的 filelist_put()"""
        self._files.append(name)
        self._ptr = 0  # filelist_put 内部调用了 filelist_reset

    def get(self) -> str | None:
        """获取下一个文件 — 移植自 detox 的 filelist_get()

        detox 在读完一轮后 ptr 归零（环形）。
        Python 版在读完一轮后返回 None（更 Pythonic）。
        """
        if not self._files:
            return None
        if self._ptr >= len(self._files):
            self._ptr = 0
            return None
        name = self._files[self._ptr]
        self._ptr += 1
        return name

    def reset(self) -> None:
        """重置指针 — 移植自 detox 的 filelist_reset()"""
        self._ptr = 0

    @property
    def count(self) -> int:
        return len(self._files)

    def __iter__(self) -> Iterator[str]:
        return iter(self._files)

    def __len__(self) -> int:
        return len(self._files)

    def __bool__(self) -> bool:
        return len(self._files) > 0

    def __repr__(self) -> str:
        return f"FileList({len(self._files)} files, ptr={self._ptr})"
