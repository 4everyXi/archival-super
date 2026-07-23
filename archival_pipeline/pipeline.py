"""Pipeline 编排器

借鉴自 bulk-rename-py (MIT):
  Source: https://github.com/codemorra/bulk-rename-py (commit 5f24922)
"""
from pathlib import Path
from archival_pipeline.models import (
    PipelineContext, FileRecord, PipelineResult, StepResult, BackupData,
)
from archival_pipeline.steps import discover_steps
from archival_pipeline.steps.base import PipelineStep


class Pipeline:
    """管线编排器——注册、排序、执行、回滚"""

    def __init__(self, target_dir: Path, config: dict | None = None,
                 step_configs: dict[str, dict] | None = None,
                 dry_run: bool = True):
        self.context = PipelineContext(
            target_dir=target_dir,
            config=config or {},
            step_configs=step_configs or {},
            dry_run=dry_run,
        )
        self.steps: list[PipelineStep] = []
        self._init_records()

    def _init_records(self):
        self.context.records = []
        for p in sorted(self.context.target_dir.rglob("*")):
            if p.is_file():
                self.context.records.append(
                    FileRecord(original_path=p, current_path=p)
                )

    def register(self, step: PipelineStep):
        self.steps.append(step)

    def register_all(self):
        for cls in discover_steps():
            self.steps.append(cls())

    def preview(self) -> PipelineResult:
        """链式预览：Step 1 的输出作为 Step 2 的输入

        每步预览时对 records 做临时修改（深拷贝），
        确保下一步看到的是上一步处理后的文件名。
        """
        import copy
        sim_records = copy.deepcopy(self.context.records)
        sim_ctx = copy.copy(self.context)
        sim_ctx.records = sim_records

        final_ops = []
        total_stats = {"total": 0, "changed": 0, "skipped": 0, "errors": 0}
        for step in self.steps:
            sp = step.preview(sim_ctx)
            self.context.step_results[step.name] = StepResult(step_name=step.name)
            final_ops.extend(sp.operations)
            for k in total_stats:
                total_stats[k] += sp.statistics.get(k, 0)
            # 将 preview 结果应用到 sim_records，让下一步看到链式结果
            for op in sp.operations:
                for rec in sim_records:
                    if rec.current_path == op.source:
                        rec.current_path = op.destination
                        break
        return PipelineResult(
            steps=list(self.context.step_results.values()),
            final_operations=final_ops, statistics=total_stats,
            target_dir=self.context.target_dir,
        )

    def run(self) -> PipelineResult:
        for step in self.steps:
            try:
                result = step.execute(self.context)
                self.context.step_results[step.name] = result
                if not result.success:
                    self._rollback_all()
                    return PipelineResult(
                        steps=[], final_operations=[],
                        statistics={"total": 0, "changed": 0, "skipped": 0, "errors": 1},
                    )
            except Exception as e:
                self.context.step_results[step.name] = StepResult(
                    step_name=step.name, success=False, errors=[str(e)])
                self._rollback_all()
                return PipelineResult(
                    steps=[], final_operations=[],
                    statistics={"total": 0, "changed": 0, "skipped": 0, "errors": 1},
                )
        total_stats = {"total": len(self.context.records), "changed": 0, "skipped": 0, "errors": 0}
        for r in self.context.step_results.values():
            total_stats["errors"] += len(r.errors)
        final_ops = []
        for rec in self.context.records:
            if rec.original_path != rec.current_path:
                from archival_pipeline.models import RenameOperation
                final_ops.append(RenameOperation(rec.original_path, rec.current_path))
        total_stats["changed"] = len(final_ops)
        total_stats["skipped"] = total_stats["total"] - total_stats["changed"]
        return PipelineResult(steps=list(self.context.step_results.values()), final_operations=final_ops, statistics=total_stats)

    def _rollback_all(self):
        for step in reversed(self.steps):
            result = self.context.step_results.get(step.name)
            if result and result.success and result.backup_data:
                step.rollback(BackupData(step_name=step.name, operations=result.backup_data))
