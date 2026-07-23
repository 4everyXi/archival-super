"""PipelineStep 抽象基类"""
from abc import ABC, abstractmethod
from archival_pipeline.models import (
    PipelineContext, StepPreview, StepResult, BackupData,
)


class PipelineStep(ABC):
    """每个管线步骤实现此抽象类"""
    name: str = ""
    description: str = ""

    @abstractmethod
    def preview(self, ctx: PipelineContext) -> StepPreview:
        """生成当前步骤的预览（只读）"""

    @abstractmethod
    def execute(self, ctx: PipelineContext) -> StepResult:
        """执行当前步骤，修改 ctx.records"""

    @abstractmethod
    def rollback(self, backup_data: BackupData) -> bool:
        """回滚当前步骤，接收备份数据"""
