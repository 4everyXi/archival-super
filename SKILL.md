---
name: archival-super
description: "[Pipeline] 档案化超级管线——逆向思维：只删不增，确定才动。统一入口：processor（三删+安全表）→ inherit_prefix（日期继承）。集成 detox 安全表、rename-clean 重名处理、bulk-rename-py 管线架构。 触发：档案化、批量重命名、文件名规范化、文件整理、去平台ID、日期格式化。 Near-misses: 需要翻译（路由到 archival-translator）、单文件手动改名。"
---

# Archival Super — 档案化超级管线

> **逆向思维：只删不增，确定才动。**
> 一个文件经过管线，只可能变短（被删除噪音），不可能变长（被增加内容）。

## 设计原则

| 原则 | 核心 | 实现 |
|------|------|------|
| **风险不对称** | 假阳性比假阴性严重 | safe table 只含 55 个噪音字符 |
| **机械优先** | 能用脚本就不用AI | 两步全机械，零语义猜测 |
| **幂等性** | 重复运行不变 | 已处理的文件名不会被二次处理 |
| **可回滚** | 操作可逆 | 统一 backup + rollback |

## 9 仓库正确用法

| 仓库 | 用了什么 | 为什么符合逆向思维 |
|------|---------|-------------------|
| **detox** | safe table 55 条目 | ✅ 只替换确定噪音，不在表里不动 |
| **detox** | wipeup 去重算法 | ✅ 连续分隔符折叠为单个，确定冗余 |
| **rename-clean** | ensure_unique | ✅ 纯机械重名处理，不涉及语义 |
| **filebatch-prefixer** | 已有日期前缀检测 | ✅ 只读不写，提取已有信息 |
| **filebatch-prefixer** | mtime 日期回退 | ⚠️ 正向操作，默认关闭，需显式启用 |
| **bulk-rename-py** | Pipeline 三阶段架构 | ✅ 工作流模式，不涉及字符处理 |
| **sanitize** | validate 后置验证 | ✅ 确定性检查，不做修改 |
| **Nomina** | 规则引擎模式 | ❌ Phase 2 参考，未集成 |
| **detox/sanitize 其他** | filter pipeline 理念 | ✅ 借鉴了管道设计 |

## 快速参考

| 命令 | 说明 |
|------|------|
| `python -m archival_pipeline.cli <目录> --preview preview.json` | 逆向模式预览 |
| `python -m archival_pipeline.cli <目录> --execute --backup backup` | 执行+备份 |
| `python -m archival_pipeline.cli <目录> --flatten all` | 纯平铺（全部文件） |
| `python -m archival_pipeline.cli <目录> --flatten archived` | 纯平铺（仅档案化过的） |
| `python -m archival_pipeline.cli <目录> --execute --backup backup --flatten all` | 档案化 + 平铺全部 |
| `python -m archival_pipeline.cli <目录> --execute --backup backup --flatten archived` | 档案化 + 平铺已变更的 |
| `python -m archival_pipeline.cli --rollback backup_processor.json backup_inherit.json` | 统一回滚 |

