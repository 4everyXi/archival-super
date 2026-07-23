"""Step 0: 翻译——日/韩/英→中文文件名翻译

三种引擎，按优先级：
  1. 映射表（默认）：预定义词汇替换，不猜未知词
  2. Google（免费）：通过 deep-translator，无需 API Key
  3. AI（任意 OpenAI 兼容 API）：需要 API Key + endpoint

集成来源:
  deep-translator (MIT): https://github.com/nidhaloff/deep-translator
  Smart-File-Translator: clean_text() 文件名清理
  LinguaGacha: 术语表(glossary)系统概念
"""
import json
import re
from pathlib import Path
from archival_pipeline.steps.base import PipelineStep
from archival_pipeline.models import (
    PipelineContext, StepPreview, StepResult, BackupData,
)
from archival_pipeline.translator.engine import TranslationEngine, DEFAULT_TRANSLATIONS
from archival_pipeline.translator.config import BuiltinConfig
from archival_pipeline.translator.sequence import create_full_sanitize_sequence


# ── 文件名清理（移植自 Smart-File-Translator） ─────────────────
def clean_filename(name: str) -> str:
    """清理翻译后的文件名
    
    规则（移植自 Smart-File-Translator clean_text()）:
    - 小写
    - 空格 → 下划线
    - 去掉非法字符 /\\:*?"<>|'’
    - 去掉首尾下划线
    """
    s = name.lower().replace(" ", "_")
    for c in '/\\:*?"<>|\'': s = s.replace(c, "")
    s = re.sub(r'_+', '_', s)  # 去重连续下划线
    return s.strip("_")


# ── 术语表系统（概念借鉴自 LinguaGacha） ──────────────────────
# 格式: { "日文/英文原文": "中文译文" }
DEFAULT_GLOSSARY: dict[str, str] = {}


# ── Google 翻译引擎 ──────────────────────────────────────────
def _translate_google(text: str, target: str = "zh-CN") -> str | None:
    """通过 deep-translator 调用 Google 翻译（免费，无需 Key）
    
    集成自 deep-translator GoogleTranslator (MIT)
    """
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception:
        return None


# ── AI 翻译引擎（OpenAI 兼容 API） ──────────────────────────
def _translate_ai(text: str, api_key: str, endpoint: str = "https://api.deepseek.com",
                  model: str = "deepseek-chat") -> str | None:
    """通过任意 OpenAI 兼容 API 翻译
    
    集成自 Smart-File-Translator 的 AI 翻译模式
    提示词设计借鉴 LinguaGacha 的 {source}→{target} 格式
    """
    import urllib.request
    import urllib.error

    prompt = (
        "You are a professional filename translator. "
        f"Translate the following text to Chinese (zh-CN). "
        "Return ONLY the translated text. "
        "Do not add notes, explanations, quotes, or punctuation.\n\n"
        f"Text: {text}"
    )

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You translate filenames to Chinese."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 256,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"].strip()
                # 清理 AI 常见的多余字符
                content = content.replace('"', '').replace("'", "").replace("`", "")
                return content
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError,
                KeyError, IndexError) as e:
            if attempt < 2:
                import time
                time.sleep((attempt + 1) * 5)
            else:
                return None
    return None


# ── 主翻译函数 ─────────────────────────────────────────────
def translate_filename(name: str, engine: str = "table",
                       config: dict | None = None) -> str | None:
    """翻译文件名，支持三种引擎
    
    Args:
        name: 文件名
        engine: "table"|"google"|"ai"
        config: 引擎配置
            table: {mappings: list[tuple[str,str]], glossary: dict[str,str]}
            google: {target: str}
            ai: {api_key, endpoint, model}
    """
    config = config or {}
    stem = Path(name).stem
    ext = Path(name).suffix

    translated = None
    if engine == "google":
        translated = _translate_google(stem, config.get("target", "zh-CN"))
    elif engine == "ai":
        translated = _translate_ai(
            stem,
            api_key=config.get("api_key", ""),
            endpoint=config.get("endpoint", "https://api.deepseek.com"),
            model=config.get("model", "deepseek-chat"),
        )
    else:  # table mode (default)
        # 使用原始 archival translator 引擎
        mappings = config.get("mappings", DEFAULT_TRANSLATIONS)
        try:
            engine_inst = TranslationEngine(
                mappings=mappings,
                config=BuiltinConfig(),
                sequence=create_full_sanitize_sequence(),
            )
            result = engine_inst.translate(name)
            if result.translated:
                return result.translated
        except Exception:
            pass
        return None

    if translated and translated != stem:
        cleaned = clean_filename(translated)
        return cleaned + ext
    return None


class Step0Translator(PipelineStep):
    """翻译：日/韩/英→中文文件名翻译（可选步骤）
    
    三种模式:
      --translate              : 映射表模式（默认）
      --translate google       : Google 免费翻译
      --translate ai           : AI 翻译（需要 --step-config）
    
    术语表: 通过 step_config 传入自定义映射
    """
    name = "translator"
    description = "翻译：日/韩/英文件名→中文"

    def _get_engine(self, ctx: PipelineContext) -> tuple[str, dict]:
        step_cfg = ctx.step_configs.get(self.name, {})
        engine = step_cfg.get("engine", "table")
        return engine, step_cfg

    def preview(self, ctx: PipelineContext) -> StepPreview:
        engine, cfg = self._get_engine(ctx)
        ops = []
        changed = 0
        for rec in ctx.records:
            new_name = translate_filename(rec.current_path.name, engine, cfg)
            if new_name and new_name != rec.current_path.name:
                new_path = rec.current_path.with_name(new_name)
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
