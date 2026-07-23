"""Step 0: 翻译（可选）——日/韩/英→中文文件名翻译

逆向模式：映射表替换已知词汇，不做猜测。
正向精修：AI 语义翻译（需 web_search）。
"""
from pathlib import Path
from archival_pipeline.steps.base import PipelineStep
from archival_pipeline.models import (
    PipelineContext, StepPreview, StepResult, BackupData,
)
from archival_pipeline.translator.engine import TranslationEngine, DEFAULT_TRANSLATIONS
from archival_pipeline.translator.config import BuiltinConfig
from archival_pipeline.translator.sequence import create_full_sanitize_sequence


class Step0Translator(PipelineStep):
    """翻译：日/韩/英→中文文件名翻译（可选步骤）"""
    name = "translator"
    description = "翻译：日/韩/英文件名→中文"

    def preview(self, ctx: PipelineContext) -> StepPreview:
        step_cfg = ctx.step_configs.get(self.name, {})
        engine = TranslationEngine(
            mappings=DEFAULT_TRANSLATIONS,
            config=BuiltinConfig(**step_cfg),
            sequence=create_full_sanitize_sequence(),
        )
        ops = []
        changed = 0
        for rec in ctx.records:
            result = engine.translate(rec.current_path.name)
            if result.translated and result.translated != rec.current_path.name:
                new_path = rec.current_path.with_name(result.translated)
                from archival_pipeline.models import RenameOperation
                ops.append(RenameOperation(rec.current_path, new_path))
                changed += 1
        return StepPreview(
            step_name=self.name,
            operations=ops,
            statistics={"total": len(ctx.records), "changed": changed,
                        "skipped": len(ctx.records) - changed, "errors": 0},
        )

    def execute(self, ctx: PipelineContext) -> StepResult:
        preview = self.preview(ctx)
        backup = []
        errors = []
        for op in preview.operations:
            backup.append({"original": str(op.source), "new": str(op.destination)})
            if not ctx.dry_run:
                try:
                    op.source.rename(op.destination)
                except OSError as e:
                    errors.append(str(e))
            for rec in ctx.records:
                if rec.current_path == op.source:
                    rec.current_path = op.destination
                    break
        return StepResult(
            step_name=self.name,
            success=len(errors) == 0,
            backup_data=backup,
            errors=errors,
        )

    def rollback(self, backup_data: BackupData) -> bool:
        for item in reversed(backup_data.operations):
            src = Path(item["new"])
            dst = Path(item["original"])
            if src.exists():
                src.rename(dst)
        return True
