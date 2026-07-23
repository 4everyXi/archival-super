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


# ── 文本保护（翻译前保护标记，翻译后恢复） ──────────────────
# 概念借鉴自 LinguaGacha TextPreserveRule
# 保护文件名中的 [xxx] {xxx} 标记不被 AI 翻译

_RE_PROTECT = re.compile(r'(\[[^\]]+\]|\{[^}]+\})')


def protect_tags(name: str) -> tuple[str, list[str]]:
    """保护文件名中的标记，翻译后恢复"""
    tags = []
    def _replace(m):
        tags.append(m.group(1))
        return f"\x00TAG{len(tags)-1}\x00"
    protected = _RE_PROTECT.sub(_replace, name)
    return protected, tags


def restore_tags(name: str, tags: list[str]) -> str:
    """恢复被保护的标记"""
    result = name
    for i, tag in enumerate(tags):
        result = result.replace(f"\x00TAG{i}\x00", tag)
    return result


# ── 翻译函数 ─────────────────────────────────────────────
def _translate_google(text: str, target: str = "zh-CN") -> str | None:
    """通过 deep-translator 调用 Google 翻译（直接从 deep-translator repo 使用）"""
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception:
        return None


def _translate_ai(text: str, api_key: str, endpoint: str = "https://api.deepseek.com",
                  model: str = "deepseek-chat") -> str | None:
    """机械 AI 翻译（直接调用 OpenAI 兼容 API）"""
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
        "temperature": 0.3, "max_tokens": 256,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                c = json.loads(resp.read())["choices"][0]["message"]["content"].strip()
                return c.replace('"', '').replace("'", "").replace("`", "")
        except Exception:
            if attempt < 2:
                import time; time.sleep((attempt + 1) * 5)
    return None


def _refine_ai(text: str, api_key: str,
               endpoint: str = "https://api.deepseek.com",
               model: str = "deepseek-chat",
               tone: str = "auto") -> str | None:
    """AI 精修（原技能正向精修流程：基调+语序+角色名+屏蔽词）"""
    import urllib.request
    import urllib.error

    tone_map = {
        "adult": "成人内容，用词越粗俗淫荡越自然",
        "cute": "萌系内容，用词越软萌越自然",
        "formal": "正经/正式内容，用词越规范越自然",
        "technical": "技术/专业内容，术语越准确越自然",
        "auto": "根据内容自动判断基调",
    }
    sys_prompt = (
        "You are a professional filename refinement expert for Japanese media.\n"
        f"Tone: {tone_map.get(tone, tone_map['auto'])}\n"
        "Rules:\n"
        "1. Japanese SOV → Chinese SVO word order\n"
        "2. Censored words (○×) → restore full word\n"
        "3. Technical specs (1080p/4K/fps/ver) → NEVER translate\n"
        "4. Character names → use known official translations\n"
        "5. Return ONLY the refined filename, no explanations."
    )
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Refine: {text}"},
        ],
        "temperature": 0.5, "max_tokens": 512,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                c = json.loads(resp.read())["choices"][0]["message"]["content"].strip()
                return c.replace('"', '').replace("'", "").replace("`", "")
        except Exception:
            if attempt < 2:
                import time; time.sleep((attempt + 1) * 10)
    return None


def translate_filename(name: str, engine: str = "table",
                       config: dict | None = None) -> str | None:
    """翻译文件名，四种引擎"""
    config = config or {}
    stem = Path(name).stem
    ext = Path(name).suffix

    # 翻译前用文本保护
    protected_stem, tags = protect_tags(stem)

    if engine == "refine":
        translated = _refine_ai(protected_stem, **{k: config.get(k, "") for k in ["api_key", "endpoint", "model", "tone"]})
    elif engine == "ai":
        translated = _translate_ai(protected_stem, config.get("api_key", ""), config.get("endpoint", "https://api.deepseek.com"), config.get("model", "deepseek-chat"))
    elif engine == "google":
        translated = _translate_google(protected_stem, config.get("target", "zh-CN"))
    else:
        try:
            eng = TranslationEngine(mappings=config.get("mappings", DEFAULT_TRANSLATIONS), config=BuiltinConfig(), sequence=create_full_sanitize_sequence())
            r = eng.translate(name)
            return r.translated if r.translated else None
        except Exception:
            return None

    if translated and translated != protected_stem:
        restored = restore_tags(translated, tags)
        return clean_filename(restored) + ext
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
