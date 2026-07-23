"""统一预览生成 + 格式扩展"""
import json
import datetime
from pathlib import Path
from archival_pipeline.models import PipelineResult

_formatters: dict[str, type] = {}


def register_format(name: str, formatter_cls: type):
    _formatters[name] = formatter_cls


def render(name: str, result: PipelineResult) -> str:
    cls = _formatters.get(name)
    if not cls:
        raise ValueError(f"Unknown format: {name}")
    return cls().render(result)


class JsonFormatter:
    format_name = "json"

    def render(self, result: PipelineResult) -> str:
        data = {
            "file_renames": {
                "original_paths": [str(op.source) for op in result.final_operations],
                "new_paths": [str(op.destination) for op in result.final_operations],
            },
            "statistics": result.statistics,
            "steps": [s.step_name for s in result.steps],
            "timestamp": datetime.datetime.now().isoformat(),
        }
        return json.dumps(data, ensure_ascii=False, indent=2)


class TextFormatter:
    """人类可读预览——按父目录分组显示相对路径"""
    format_name = "txt"

    def _rel_path(self, path: Path, result: PipelineResult) -> str:
        """计算相对路径"""
        td = result.target_dir
        if td:
            try:
                return str(path.relative_to(td)).replace("\\", "/")
            except ValueError:
                pass
        return str(path).replace("\\", "/")

    def render(self, result: PipelineResult) -> str:
        lines = [f"共 {result.statistics.get('total', 0)} 个文件，{result.statistics.get('changed', 0)} 个变更\n"]

        if not result.final_operations:
            lines.append("\n（无变更）\n")
            return "".join(lines)

        current_parent = None
        for op in result.final_operations:
            if op.source.name == op.destination.name:
                continue
            parent = op.source.parent
            if parent != current_parent:
                current_parent = parent
                rel = self._rel_path(parent, result)
                lines.append(f"\n{rel}/\n")
            lines.append(f"    {op.source.name}  →  {op.destination.name}\n")

        return "".join(lines)


register_format("json", JsonFormatter)
register_format("txt", TextFormatter)
