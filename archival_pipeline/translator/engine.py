"""翻译引擎 — 扫描、翻译、重命名。"""
import re
import json
from pathlib import Path
from collections import Counter
from dataclasses import dataclass
from archival_pipeline.translator.table import TranslationTable
from archival_pipeline.translator.sequence import (
    create_archival_sequence,
    create_detox_style_sequence,
    create_full_sanitize_sequence,
)
from archival_pipeline.translator.config import ConfigFile, BuiltinConfig
from archival_pipeline.translator.file_util import is_protected, ignore_file, check_rename_safety
from archival_pipeline.translator.filelist import FileList
from typing import NamedTuple


class TranslationResult(NamedTuple):
    """单个翻译操作的结果。"""
    success: bool
    original_path: Path
    new_path: Path | None = None
    error_message: str | None = None
    changes: list[tuple[str, str]] | None = None  # (原文→译文) 记录


# ============================================================
# 内置翻译映射表
# 按长度降序排列，长词优先匹配防截断
# ============================================================
DEFAULT_TRANSLATIONS = [
    # ── 内容警告标签 ──
    ("※ロイコ蟲注意※", "※白化虫注意※"),
    ("※蟲閲覧注意※", "※虫浏览注意※"),
    ("※ロイコ 閲覧注意※", "※白化浏览注意※"),
    ("※閲覧注意※", "※浏览注意※"),
    ("※觸手※", "※触手※"),
    ("※蟲注意※", "※虫注意※"),
    ("※触手※", "※触手※"),
    ("蟲閲覧注意", "虫浏览注意"),
    ("ロイコ蟲注意", "白化虫注意"),
    ("ロイコ 閲覧注意", "白化浏览注意"),
    ("閲覧注意", "浏览注意"),
    ("蟲注意", "虫注意"),

    # ── 帖子长标题 ──
    ("スズハちゃんのぼうけん", "小铃羽的冒险"),
    ("スズハちゃんの変異", "小铃羽的变异"),
    ("帰宅中の桜ちゃん めがねなし", "回家途中的小樱无眼镜"),
    ("帰宅中の桜ちゃん めがね", "回家途中的小樱眼镜"),
    ("紗愛のおしごと", "纱爱的工作"),
    ("理亜ちゃんの楽園", "小理亚的乐园"),
    ("繁殖実験４", "繁殖实验4"),
    ("繁殖実験４ 変異", "繁殖实验4变异"),
    ("ななドラゴン", "娜娜龙"),
    ("踊り子モモカ、巣穴にて", "舞女桃香于巢穴中"),
    ("萌々香、つかまる", "萌萌香被抓住"),
    ("ポニテ。体操服。巣穴", "马尾体操服巢穴"),
    ("ななisメスゴキ", "娜娜是雌蟑螂"),
    ("ロゼモカちゃんのペット", "小蔷薇摩卡的宠物"),
    ("さくら 堕ちる", "樱堕落"),
    ("さくら　堕ちる", "樱堕落"),
    ("足コキ男の娘", "足交伪娘"),
    ("全体公開 ゆい巫女のナメクジ交尾", "全体公开唯巫女的蛞蝓交尾"),
    ("退勤後", "下班后"),
    ("優美のからだ", "优美的身体"),
    ("あいちゃん社長の屋外搾精", "小爱社长户外榨精"),
    ("さくら 捕まる", "樱被捕获"),
    ("志乃のハエ子壺", "志乃的蝇壶"),
    ("バッタペニスは優美のナカへ", "蚱蜢阴茎进入优美体内"),
    ("マキマリちゃんのクリスマ巣", "小卷茉莉的圣诞巢"),
    ("モカのクリスマ巣", "摩卡的圣诞巢"),
    ("うまｘ巫女", "马x巫女"),
    ("なな巫女蟲せっくす！！！", "娜娜巫女SEX！！！"),
    ("オバケコロギス", "鬼蟋螽"),
    ("繁殖教室", "繁殖教室"),
    ("変異化閲覧注意", "变异化浏览注意"),
    ("ロイコ教室", "白化教室"),
    ("フェラクレスオオスケベムシ", "赫拉克勒斯巨色虫"),
    ("志乃の水着交尾", "志乃的泳装交尾"),
    ("よもやまさんに托卵する", "对四方山小姐寄卵"),
    ("碧のハエ講義", "碧的蝇类讲座"),
    ("女王ロゼモカ", "女王蔷薇摩卡"),
    ("紗愛のハエ講義", "纱爱的蝇类讲座"),
    ("モカの巣　変異", "摩卡的巢变异"),
    ("モカの巣", "摩卡的巢"),
    ("なな巫女蟲", "娜娜巫女"),
    ("巣穴にて", "于巢穴中"),
    ("VS蛾", "VS蛾"),
    ("スズハちゃん", "小铃羽"),
    ("桜ちゃん", "小樱"),
    ("萌々香", "萌萌香"),
    ("ロゼモカちゃん", "小蔷薇摩卡"),

    # ── 文件修饰词（含平假名片假名双版本）──
    ("断面あり", "有剖面"),
    ("断面なし", "无剖面"),
    ("タイツスーツ", "连裤袜套装"),
    ("タイツシャツ", "连裤袜衬衫"),
    ("メイン通常", "主视频普通"),
    ("メガネOFF", "无眼镜"),
    ("メガネなし", "无眼镜"),
    ("めがねなし", "无眼镜"),   # 平假名版本（目录原始用字）
    ("めがね", "眼镜"),         # 平假名版本
    ("変異はだか", "变异裸体"),
    ("変異なし", "无变异"),
    ("スポブラ", "运动内衣"),
    ("セーターOFF", "无毛衣"),
    ("はんぶん", "一半"),
    ("セーター", "毛衣"),
    ("メイン", "主视频"),
    ("はだか", "裸体"),
    ("変異", "变异"),
    ("風呂", "浴室"),
    ("障子", "纸门"),
    ("メスゴキ", "雌蟑螂"),
    ("つかまる", "被抓住"),
    ("体操服", "体操服"),
    ("巣穴", "巢穴"),
    ("ポニテ", "马尾"),
    ("おFF", "OFF"),

    # ── 目录名残留词（档案化后空格→_导致全句不匹配，补独立词）──
    ("帰宅中", "回家途中"),       # 帰宅中の桜ちゃん→回家途中的小樱
    ("堕ちる", "堕落"),           # さくら堕ちる→樱堕落
    ("捕まる", "被捕获"),         # さくら捕まる→樱被捕获
    ("ナメクジ", "蛞蝓"),         # ナメクジ交尾→蛞蝓交尾
    ("ロイコ", "白化"),           # ロイコ蟲注意→白化虫注意
    ("全体公開", "全体公开"),
    # の→的（日文助词转中文，仅作为长句不匹配时的兜底）
    ("の", "的"),

    # ── 角色名（原创角色→音译）──
    # 注意：不要添加单字短映射，避免误伤日文词汇
    ("スズハ", "铃羽"),
    ("モモカ", "桃香"),
    ("ロゼモカ", "蔷薇摩卡"),
    ("モカ", "摩卡"),
    ("マキマリ", "卷茉莉"),
    ("よもやま", "四方山"),
    ("紗愛", "纱爱"),
    ("理亜", "理亚"),
    ("志乃", "志乃"),
    ("優美", "优美"),
    ("さくら", "樱"),
    ("ゆい", "唯"),
    ("なな", "娜娜"),
    ("碧", "碧"),
    # "あい" 太短会误伤"あいさつ"(问候)等词汇，需AI上下文判断
    ("触手", "触手"),

    # ── 等级标签 ──
    ("レベル３", "等级3"),
    ("レベル２", "等级2"),
    ("レベル", "等级"),

    # Eros directory characters
    ("アリス・ツーベルク", "爱丽丝·茨韦尔克"),
    ("Neuro-sama", "脑酱"),
    ("Laffey", "拉菲"),
    # ── nanasi108+ Fate 系列 ──
    ("敗北アルトリアの無様恥辱刑", "败北阿尔托莉雅的耻辱刑罚"),
    ("敗北アルトリア", "败北阿尔托莉雅"),
    ("無様恥辱刑", "耻辱刑罚"),
    ("アルトリア", "阿尔托莉雅"),
    ("精液ぶっかけver", "精液喷洒版"),
    ("精液ぶっかけ", "精液喷洒"),
    ("えちえち島風コス美遊ちゃんのShake_it", "涩涩岛风cos美游酱的Shake_it"),
    ("えちえち島風コス美遊ちゃん", "涩涩岛风cos美游酱"),
    ("えちえち", "涩涩"),
    ("島風", "岛风"),
    ("魅惑の少女淫魔サキュバス美遊ちゃんのSweet_Devil", "魅惑少女梦魔美游酱的Sweet_Devil"),
    ("魅惑の少女淫魔サキュバスイリヤちゃんのSweet_Devil", "魅惑少女梦魔伊莉雅酱的Sweet_Devil"),
    ("魅惑の少女淫魔サキュバス", "魅惑少女梦魔"),
    ("サキュバス美遊ちゃん", "梦魔美游酱"),
    ("サキュバスイリヤちゃん", "梦魔伊莉雅酱"),
    ("サキュバス", "梦魔"),
    ("美遊ちゃんのダイナミック腰振りダンス", "美游酱的动态扭腰舞"),
    ("美遊ちゃんモニタリング", "美游酱观察记录"),
    ("美遊ちゃん", "美游酱"),
    ("イリヤちゃん", "伊莉雅酱"),
    ("腰振りダンス", "扭腰舞"),
    ("セイバーレゼダンス", "Saber零式舞蹈"),
    ("セイバーお仕置き強制全裸露出オナニー", "Saber惩罚强制全裸露出自慰"),
    ("セイバー眠らせハメ撮りケツ穴", "Saber迷奸肛穴"),
    ("セイバー潮吹きディルド", "Saber潮吹假阳具"),
    ("セイバー", "Saber"),
    ("小悪魔びっち", "小恶魔碧池"),
    ("びっちver", "碧池版"),
    ("びっち", "碧池"),
    ("ビキニストリップ", "比基尼脱衣"),
    ("悦楽表情", "愉悦表情"),
    ("イヤイヤ表情", "不情愿表情"),
    ("鼻フック雌豚", "鼻钩母猪"),
    ("全裸スヤスヤ無覚醒", "全裸安眠无觉醒"),
    ("スヤスヤ無覚醒", "安眠无觉醒"),
    ("たて動画", "竖屏视频"),
    ("横動画", "横屏视频"),
    ("エロバニー", "涩涩兔女郎"),
    ("ドラゴンレディ", "龙女"),
    # --- English to Chinese mappings ---
    # Genshin Impact characters
    ("Yae Miko", "八重神子"),
    ("Sakura Miko", "樱巫女"),
    ("Nahida", "纳西妲"),
    ("Barbara", "芭芭拉"),
    ("Hu Tao", "胡桃"),
    ("Qiqi", "七七"),
    ("Diona", "迪奥娜"),
    ("Lumine", "荧"),
    ("Klee", "可莉"),
    ("Lisa", "丽莎"),
    ("Yae", "八重"),
    ("Dori", "多莉"),
    ("Bailu", "白露"),
    ("Yaoyao", "瑶瑶"),
    ("Paimon", "派蒙"),
    ("Rosaria", "罗莎莉亚"),
    ("Kanna", "康娜"),
    ("Ilulu", "伊露露"),
    # HSR characters
    ("Huohuo", "藿藿"),
    ("Clara", "克拉拉"),
    ("Qingque", "青雀"),
    ("Nobeta", "诺贝塔"),
    ("Hook", "虎克"),
    ("Encore", "安可"),
    # Description words
    ("Vertical", "竖屏"),
    ("Sound", "有声"),
    ("Anal", "肛交"),
    ("Fingering", "指交"),
    ("Dom", "攻"),
    ("Raiden Shogun", "雷电将军"),
    ("Sakura Miko", "樱巫女"),
    ("Fu Xuan", "符玄"),
    ("Fu_Xuan", "符玄"),
    ("Sparkle", "花火"),
    ("Intercourse", "性交"),
    ("Blowjob", "口交"),
    ("Cunnilingus", "舔阴"),
    # ZZZ / HSR characters (verified via web_search)
    ("Ju_Fufu", "橘福福"),
    ("Ju Fufu", "橘福福"),
    ("Cipher", "赛飞儿"),
      # verified-mappings.md sync (2026-07-11)
      # Character names from verified-mappings.md
      ("Panty", "潘迪"),
      ("Stocking", "斯托金"),
      ("Anya", "阿尼亚"),
      ("Tatsumaki", "战栗的龙卷"),
      ("Frieren", "芙莉莲"),
      ("Beatrice", "碧翠丝"),
      ("Ranni", "菈妮"),
      ("Nagatoro", "长瀞"),
      ("Gardevoir", "沙奈朵"),
      ("May", "小遥"),
      ("Gwen", "格温"),
      ("Ellie", "艾莉"),
      ("Pomni", "帕姆尼"),
      ("Rebecca", "丽贝卡"),
      ("Marnie", "玛俐"),
      ("Iono", "奇树"),
      ("Gawr Gura", "噶呜古拉"),
      # Technical terms from verified-mappings.md
      ("WIP", "进行中"),
      ("Colored", "着色版"),
      ("Lines", "线稿"),
      ("Loop", "循环"),


    ("Paizuri", "乳交"),
    ("Nude", "裸体"),
    ("Rear", "后入"),
    ("Clothed", "穿衣"),
    ("Vertical", "竖屏"),
    ("Naked", "裸体"),

    ("ぷちきっす", "小吻"),
    ("抱き枕カバーおまけ画像", "抱枕套特典图片"),
    ("抱き枕カバー", "抱枕套"),
    ("抱き枕", "抱枕"),
    ("カバーおまけ", "套特典"),
    ("イラスト", "插图"),
    ("アニメ", "动画"),
    ("おすすめ", "推荐"),
    ("おまけ画像", "特典图片"),
    ("おまけ", "特典"),
    ("SEなし", "无音效"),
    ("SE無し", "无音效"),
    ("ん゛", "嗯"),

    ("あり", "有"),
    ("なし", "无"),
    ("因為", "因为"),
    ("並", "并"),
    ("樂", "乐"),
    ("體", "体"),
    ("聖", "圣"),
    ("誕", "诞"),
    ("裝", "装"),
    ("奪", "夺"),
    ("處", "处"),
    ("純", "纯"),
    ("愛", "爱"),
    ("節", "节"),
    ("聲", "声"),
    ("麼", "么"),
    ("嗎", "吗"),
    ("與", "与"),
    ("為", "为"),
    ("０", "0"),
    ("１", "1"),
    ("２", "2"),
    ("３", "3"),
    ("４", "4"),
    ("５", "5"),
    ("６", "6"),
    ("７", "7"),
    ("８", "8"),
    ("９", "9"),
]



# ── 映射表 ──

@dataclass
class MappingEntry:
    """一条重命名映射记录。"""
    old_path: str
    new_path: str

    @classmethod
    def from_csv_row(cls, row: str, sep: str = ',') -> 'MappingEntry':
        parts = row.strip().split(sep)
        if len(parts) < 2:
            raise ValueError(f"Invalid row: {row}")
        return cls(old_path=parts[0].strip(), new_path=parts[1].strip())


class MappingTable:
    """重命名映射表 — 加载处理器 --export-map 导出的 CSV/TSV。

    用于桥接处理器（删除/格式化阶段）和翻译器（语义翻译阶段）：
    翻译器可以基于处理器已重命名的结果继续操作。
    """

    def __init__(self, entries: list[MappingEntry] | None = None):
        self.entries = entries or []

    @classmethod
    def load(cls, path: str | Path) -> 'MappingTable':
        """从 CSV 或 TSV 文件加载映射表。

        自动判断格式：.csv → 逗号分隔，其他 → 制表符分隔。
        支持 UTF-8 BOM。
        """
        p = Path(path)
        is_csv = p.suffix.lower() == '.csv'
        sep = ',' if is_csv else '\t'

        entries: list[MappingEntry] = []
        with open(p, encoding='utf-8-sig') as f:
            for i, line in enumerate(f):
                line = line.strip()
                if i == 0 and ('old_path' in line or 'new_path' in line):
                    continue  # 跳过表头
                if not line:
                    continue
                try:
                    entries.append(MappingEntry.from_csv_row(line, sep))
                except ValueError as e:
                    print(f"  跳过第 {i+1} 行: {e}")

        return cls(entries)

    def get_mapping_for(self, path: str | Path) -> str | None:
        """查找路径的映射目标。"""
        p_str = str(path).replace('\\', '/')
        for e in self.entries:
            if e.old_path == p_str or e.old_path in p_str:
                return e.new_path
        return None

    def invert(self) -> 'MappingTable':
        """反转映射（新→旧），用于回滚预览。"""
        return MappingTable([
            MappingEntry(old_path=e.new_path, new_path=e.old_path)
            for e in self.entries
        ])

    def to_dict(self) -> dict[str, str]:
        """转换为字典 {old: new}。"""
        return {e.old_path: e.new_path for e in self.entries}

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return f"MappingTable({len(self.entries)} entries)"


class TranslationEngine:
    """翻译引擎：扫描目录，翻译名称，重命名。"""

    def __init__(self, root_dir: Path, translations: list | None = None,
                 dry_run: bool = True, skip_extensions: frozenset | None = None,
                 external_mappings: dict[str, str] | None = None):
        self.root_dir = Path(root_dir)
        self.dry_run = dry_run
        self.skip_extensions = skip_extensions or frozenset()
        self.ignore_set = set()

        # 合并外部映射（外部覆盖内置）
        base = translations or list(DEFAULT_TRANSLATIONS)
        if external_mappings:
            seen = {k for k, v in base}
            for k, v in external_mappings.items():
                if k not in seen:
                    base.append((k, v))
                    seen.add(k)

        # 按长度降序排列
        self.translations = sorted(
            base,
            key=lambda x: -len(x[0])
        )

        # detox-style TranslationTable + Sequence
        self.table = TranslationTable.from_tuples(self.translations)
        self.sequence = create_archival_sequence(self.table)

        self._processed = 0
        self._errors = 0
        self._skipped = 0

    def apply_translation(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """对文本应用翻译映射，返回(翻译后, 变更记录)。"""
        result = self.table.translate(text)
        # 生成变更记录：只记录实际发生了替换的条目
        changes = []
        before = text
        for orig, trans in self.translations:
            if orig in before:
                before = before.replace(orig, trans)
                if before != result:
                    pass  # 已在 table.translate 中处理
        # 比较原文和结果生成 changes
        for orig, trans in self.translations:
            if orig in text and trans in result:
                changes.append((orig, trans))
        return result, changes

    def translate_name(self, name: str) -> tuple[str, list[tuple[str, str]]]:
        """翻译文件名/目录名，保留扩展名和日期前缀。"""
        # 分离扩展名（只切真正的文件扩展名，目录名含.的不切）
        stem, ext = name, ""
        if "." in name and name.count(".") <= 2:
            *stem_parts, ext = name.rsplit(".", 1)
            # 只有纯字母数字后缀才当扩展名（如 .mp3 .png .txt）
            # 目录名如 "1.SEあり" 的 "SEあり" 不是扩展名
            if ext and ext.isascii() and ext.replace(".","").isalnum():
                stem = ".".join(stem_parts)
                ext = f".{ext}"
            else:
                stem = name
                ext = ""

        # 提取日期前缀 (YYYY-MM-DD 或 YYYY-MM)
        date_prefix = ""
        m = re.match(r"^(\d{4}-\d{2}(?:-\d{2})?\s*)", stem)
        if m:
            date_prefix = m.group(1)
            stem = stem[len(date_prefix):]

        # 翻译
        translated_stem, changes = self.apply_translation(stem)
        return date_prefix + translated_stem + ext, changes

    def apply_sequence(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """Use detox-style filter chain to process text."""
        return self.sequence.run_with_stats(text)

    def apply_detox_safe(self, text: str) -> str:
        """Apply detox safe filter only (character-level replacement)."""
        from modules.translation import filters as f
        safe_filter = f.safe()
        return safe_filter.apply(text)

    def apply_full_detox_sequence(self, text: str) -> str:
        """Apply complete detox pipeline: safe -> wipeup -> lower."""
        seq = create_full_sanitize_sequence()
        return seq.run(text)

    def _should_skip(self, path: Path) -> bool:
        """检查文件是否应跳过。"""
        if is_protected(path.name):
            return True
        if ignore_file(path.name, self.ignore_set):
            return True
        return path.suffix.lower() in self.skip_extensions

    def process_directory(self, limit: int = 0, use_sequence: bool = False) -> dict:
        """处理目录：先目录(自底向上)后文件。返回处理计划。"""
        skip_ext = {".json", ".txt"} | self.skip_extensions

        # ── 扫描所有目录(自底向上) ──
        all_dirs = sorted(
            [d for d in self.root_dir.rglob("*") if d.is_dir() and d != self.root_dir],
            key=lambda p: -len(str(p))
        )

        dir_renames = []
        for d in all_dirs:
            if limit > 0 and len(dir_renames) >= limit:
                break
            new_name, changes = self.translate_name(d.name)
            if new_name != d.name:
                new_path = d.parent / new_name
                if not self.dry_run:
                    d.rename(new_path)
                dir_renames.append((d, new_path, changes))

        # ── 扫描所有文件 ──
        all_files = sorted(
            [f for f in self.root_dir.rglob("*") if f.is_file()],
            key=lambda p: -len(str(p))
        )

        file_results = []
        remaining_limit = limit - len(dir_renames) if limit > 0 else 0
        processed_files = 0

        for f in all_files:
            if self._should_skip(f):
                self._skipped += 1
                file_results.append(TranslationResult(True, f, new_path=f))
                continue

            if limit > 0 and processed_files >= remaining_limit and len(dir_renames) >= limit:
                file_results.append(TranslationResult(True, f, new_path=f, error_message="limit_reached"))
                continue

            new_name, changes = self.translate_name(f.name)
            if new_name != f.name:
                new_path = f.parent / new_name
                if not self.dry_run:
                    try:
                        f.rename(new_path)
                    except Exception as e:
                        self._errors += 1
                        file_results.append(TranslationResult(False, f, error_message=str(e)))
                        continue
                processed_files += 1
                self._processed += 1
                file_results.append(TranslationResult(True, f, new_path, changes=changes))
            else:
                self._skipped += 1
                file_results.append(TranslationResult(True, f, new_path=f))

        return {
            "dir_renames": dir_renames,      # list of (old_path, new_path, changes)
            "file_results": file_results,     # list of TranslationResult
            "stats": {
                "processed": self._processed,
                "errors": self._errors,
                "skipped": self._skipped,
            }
        }

    def get_statistics(self) -> dict:
        return {
            "processed": self._processed,
            "errors": self._errors,
            "skipped": self._skipped,
        }

    @staticmethod
    def extract_vocabulary(root_dir: Path, min_freq: int = 1) -> dict:
        """提取词汇并统计频率（用于建立翻译映射）。"""

        jp_words = Counter()
        en_words = Counter()

        for f in sorted(root_dir.rglob("*")):
            name = f.stem
            # 日文词汇
            jp = re.findall(r"[一-龠ぁ-んァ-ヶー]+", name)
            jp_words.update(jp)
            # 英文词汇
            en = re.findall(r"[a-zA-Z]{2,}", name)

            en_words.update([w.lower() for w in en])

        return {
            "japanese": {w: c for w, c in jp_words.most_common() if c >= min_freq},
            "english": {w: c for w, c in en_words.most_common() if c >= min_freq},
        }