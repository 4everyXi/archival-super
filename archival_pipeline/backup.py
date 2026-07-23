"""统一备份/回滚"""
import json
import datetime
from pathlib import Path
from archival_pipeline.models import BackupData


def save_backup(backup_data: list[dict], filepath: str | Path,
                step_name: str = "") -> Path:
    data = {
        "step_name": step_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": backup_data,
    }
    fp = Path(filepath)
    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


def load_backup(filepath: str | Path) -> BackupData:
    data = json.loads(Path(filepath).read_text(encoding="utf-8"))
    return BackupData(
        step_name=data.get("step_name", ""),
        timestamp=data.get("timestamp", ""),
        operations=data.get("operations", []),
    )


def rollback_all(backup_files: list[str | Path]) -> bool:
    success = True
    for bf in reversed(backup_files):
        try:
            data = load_backup(bf)
            for item in reversed(data.operations):
                src = Path(item["new"])
                dst = Path(item["original"])
                if src.exists():
                    src.rename(dst)
        except Exception as e:
            print(f"回滚失败: {bf}: {e}")
            success = False
    return success
