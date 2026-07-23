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
    """通过任意 OpenAI 兼容 API 翻译（机械 AI 翻译）"""
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
                content = content.replace('"', '').replace("'", "").replace("`", "")
                return content
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError,
                KeyError, IndexError):
            if attempt < 2:
                import time
                time.sleep((attempt + 1) * 5)
            else:
                return None
    return None


# ── AI 精修引擎（原技能"正向精修"完整流程） ─────────────────
def _refine_ai(text: str, api_key: str,
               endpoint: str = "https://api.deepseek.com",
               model: str = "deepseek-chat",
               tone: str = "auto") -> str | None:
    """AI 精修——不是简单翻译，而是理解语义后精修

    原 archival 技能"正向精修"流程（六步）:
      ① 基调判断 → 成人/萌系/正经/技术
      ② 词汇提取+分类 → 角色名/描述/标记
      ③ 语义理解 → 语序反转/屏蔽词还原
      ④ 整句翻译 → 自然输出
      ⑤ 校准 → 技术规格不被翻译
      ⑥ 验证 → 结果自查

    Args:
        text: 文件名
        api_key: AI API Key
        endpoint: API 端点
        model: 模型名
        tone: 基调 (auto/adult/cute/formal/technical)
    """
    import urllib.request
    import urllib.error

    # 构建基调指示
    tone_map = {
        "adult": "成人内容，用词越粗俗淫荡越自然（肉棒/淫穴/巨根/颜射）",
        "cute": "萌系内容，用词越软萌越自然（小可爱/人家/软乎乎）",
        "formal": "正经/正式内容，用词越规范越自然",
        "technical": "技术/专业内容，术语越准确越自然（插帧/编码/渲染）",
        "auto": "根据内容自动判断基调，选择最合适的用词风格",
    }
    tone_instruction = tone_map.get(tone, tone_map["auto"])

    system_prompt = (
        "You are a professional filename refinement expert for Japanese media content. "
        "You understand Japanese language structure (SOV), Chinese structure (SVO), "
        "and the differences between them.\n\n"
        "Rules:\n"
        "1. Identify the tone first, then translate accordingly.\n"
        f"   Tone: {tone_instruction}\n"
        "2. Japanese name suffixes like ちゃん/くん/さん → 小/阿(neutral) or omit\n"
        "3. Japanese word order (SOV) → Chinese word order (SVO)\n"
        "4. Censored words (○×) → infer and restore the full word\n"
        "5. Technical specs (1080p, 4K, ver, fps) → NEVER translate, keep original\n"
        "6. Character names → search memory for known official translations\n"
        "7. Return ONLY the refined filename, no explanations.\n"
        "8. Maintain original file extension if present."
    )

    user_prompt = f"Refine this filename: {text}"

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 512,
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
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"].strip()
                content = content.replace('"', '').replace("'", "").replace("`", "")
                return content
        except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError,
                KeyError, IndexError):
            if attempt < 2:
                import time
                time.sleep((attempt + 1) * 10)
            else:
                return None
    return None


# ── 主翻译函数 ─────────────────────────────────────────────
def translate_filename(name: str, engine: str = "table",
                       config: dict | None = None) -> str | None:
    """翻译文件名，支持四种引擎

    Args:
        name: 文件名
        engine: "table"|"google"|"ai"|"refine"
        config: 引擎配置
    """

    def _call_ai(text, cfg):
        return _refine_ai(
            text,
            api_key=cfg.get("api_key", ""),
            endpoint=cfg.get("endpoint", "https://api.deepseek.com"),
            model=cfg.get("model", "deepseek-chat"),
            tone=cfg.get("tone", "auto"),
        )

    config = config or {}
    stem = Path(name).stem
    ext = Path(name).suffix

    if engine == "refine":
        translated = _call_ai(stem, config)
    elif engine == "ai":
        translated = _translate_ai(
            stem,
            api_key=config.get("api_key", ""),
            endpoint=config.get("endpoint", "https://api.deepseek.com"),
            model=config.get("model", "deepseek-chat"),
        )
    elif engine == "google":
        translated = _translate_google(stem, config.get("target", "zh-CN"))
    else:  # table mode
        mappings = config.get("mappings", DEFAULT_TRANSLATIONS)
        try:
            eng = TranslationEngine(
                mappings=mappings,
                config=BuiltinConfig(),
                sequence=create_full_sanitize_sequence(),
            )
            result = eng.translate(name)
            if result.translated:
                return result.translated
        except Exception:
            pass
        return None

    if translated and translated != stem:
        return clean_filename(translated) + ext
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
