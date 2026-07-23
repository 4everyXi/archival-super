"""archival_Super 统一 CLI 入口"""
import argparse
import json
import sys
from pathlib import Path
from archival_pipeline.pipeline import Pipeline
from archival_pipeline.preview import render
from archival_pipeline.backup import save_backup, rollback_all


def flatten(target: Path, mode: str = "all", changed_files: set | None = None):
    """平铺：将子目录中的文件移到根目录

    mode='all':      全部文件平铺，不限是否档案化
    mode='archived': 只平铺经过档案化变更的文件，未变更的保持原结构
    """
    moved = 0
    for p in sorted(target.rglob("*"), key=lambda x: len(str(x)), reverse=True):
        if p.is_file() and p.parent != target:
            if mode == "archived" and changed_files is not None:
                if p not in changed_files:
                    continue
            dest = target / p.name
            if dest.exists():
                stem = dest.stem
                ext = dest.suffix
                n = 2
                while (target / f"{stem}_{n}{ext}").exists():
                    n += 1
                dest = target / f"{stem}_{n}{ext}"
            p.rename(dest)
            moved += 1
            print(f"  {p.name}")

    for p in sorted(target.rglob("*"), key=lambda x: len(str(x)), reverse=True):
        if p.is_dir() and p != target:
            try:
                p.rmdir()
            except OSError:
                pass

    print(f"\n平铺完成: {moved} 个文件移到根目录")


def main():
    parser = argparse.ArgumentParser(description="archival_Super — 档案化管线统一入口")
    parser.add_argument("target", help="目标目录")
    parser.add_argument("--preview", metavar="FILE", help="生成预览文件")
    parser.add_argument("--format", choices=["json", "txt"], default="txt",
                        help="预览输出格式")
    parser.add_argument("--execute", action="store_true", help="执行重命名")
    parser.add_argument("--backup", metavar="PREFIX", help="备份文件前缀")
    parser.add_argument("--rollback", metavar="FILE", nargs="+", help="从备份回滚")
    parser.add_argument("--config", help="配置文件")
    parser.add_argument("--flatten", choices=["all", "archived"], nargs="?",
                        const="all", help="平铺：all=全部 | archived=仅档案化过的")
    args = parser.parse_args()

    target = Path(args.target).resolve()

    if args.rollback:
        success = rollback_all(args.rollback)
        sys.exit(0 if success else 1)

    config = {}
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    # 纯平铺模式（不执行档案化）
    if args.flatten and not args.execute:
        flatten(target, args.flatten)
        return

    p = Pipeline(target, config=config, dry_run=not args.execute)
    p.register_all()

    if not args.execute:
        result = p.preview()
        output = render(args.format, result)
        if args.preview:
            preview_path = Path(args.preview)
            if not preview_path.is_absolute():
                preview_path = target / preview_path
            preview_path.write_text(output, encoding="utf-8")
            print(f"预览已保存: {preview_path}")
        else:
            print(output)
        return

    result = p.run()
    if args.backup:
        for sr in result.steps:
            if sr.backup_data:
                backup_file = Path(f"{args.backup}_{sr.step_name}.json")
                if not backup_file.is_absolute():
                    backup_file = target / backup_file
                save_backup(sr.backup_data, backup_file, sr.step_name)
                print(f"备份已保存: {backup_file}")

    # 平铺（在档案化之后）
    if args.flatten:
        changed = set()
        if args.flatten == "archived":
            changed = {op.destination for op in result.final_operations}
        flatten(target, args.flatten, changed)

    if result.statistics.get("errors", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
