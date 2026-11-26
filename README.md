# GalUniverse Pro

> 给你的 AstrBot 装上一位 Galgame 陪伴者：每天抽一位「今日老婆」，顺手查一查圣地巡礼。

支持 **OneBot v11（aiocqhttp / NapCat / Lagrange）**、QQ 官方机器人、Telegram、Discord、飞书等 AstrBot 已接入的平台。指令输出为纯文本，不依赖 Markdown 渲染。

当前版本：**v2.0.0**

---

## 功能

| 功能 | 说明 |
|---|---|
| 今日老婆 | 每天固定抽一位角色 + 签运 + 建议，同一天结果稳定 |
| 换老婆 | 每日有限次重抽，次数可配置 |
| 圣地巡礼 | 按作品查询取景地，同一作品支持**多条**地点，自动分页 |
| 圣地列表 | 浏览已收录的全部作品与条目数 |
| 数据管理 | 聊天内增删角色/圣地，热重载无需重启 |
| 多平台 | 纯文本输出，OneBot 群聊可选 @ 回复、长消息自动分段 |

内置初始数据：**310 位角色 / 68 条圣地 / 52 部作品**（已去重清洗）。

---

## 安装

1. 将 `astrbot_plugin_galuniverse` 整个目录放入 AstrBot 的 `data/plugins/`；
2. 在 WebUI「插件」页点击重载，或重启 AstrBot；
3. 进入插件配置页按需调整（见下）。

无第三方依赖，`requirements.txt` 为空。

---

## 指令

### 所有人

| 指令 | 说明 |
|---|---|
| `/今日老婆` | 每日一抽，别名 `/今日运势`、`/抽老婆` |
| `/换老婆` | 重抽一次，别名 `/重抽` |
| `/圣地巡礼 <作品> [页码]` | 查询取景地，别名 `/巡礼`；支持模糊匹配 |
| `/圣地列表 [页码]` | 浏览已收录作品 |

示例：

```
/圣地巡礼 CLANNAD
/圣地巡礼 Summer Pockets 2
/圣地巡礼 cl          ← 模糊匹配到 CLANNAD
```

### 管理员

| 指令 | 说明 |
|---|---|
| `/gal 添加老婆 古河渚 (CLANNAD)` | 名字含空格也能正确解析 |
| `/gal 添加圣地 作品\|地点\|链接` | 链接可省略，第 4 段可选填地区 |
| `/gal 删除老婆 <关键词>` | 批量删除，返回删除清单 |
| `/gal 删除圣地 <关键词>` | 按作品/地点/地区匹配 |
| `/gal 重载` | 重载数据（兼容旧指令 `/重载Gal数据`） |
| `/gal 导入` | 从旧版 `wives.txt` / `spots.txt` 补录 |
| `/gal 统计` | 数据量与存储路径 |
| `/gal 帮助` | 指令一览 |

---

## 配置项

配置在 WebUI 插件详情页可视化编辑，落盘于 `data/config/astrbot_plugin_galuniverse_config.json`。

| 配置 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enable_daily_wife` | bool | true | 今日老婆总开关 |
| `enable_pilgrimage` | bool | true | 圣地巡礼总开关 |
| `fortune_scope` | string | `per_user` | `per_user` / `per_group` / `global` |
| `fortune_pool` | list | 七档签运 | 自定义签运文案 |
| `advice_pool` | list | 3 条 | 今日建议文案，留空用内置 |
| `timezone` | string | `Asia/Shanghai` | 决定「每天」的分界点 |
| `reroll_per_day` | int | 1 | 每日重抽次数，0 关闭 |
| `fuzzy_match` | bool | true | 圣地模糊匹配 |
| `page_size` | int | 6 | 每页条数 |
| `link_style` | string | `domain` | 链接展示：`domain` / `full` / `hidden` |
| `max_chars_per_message` | int | 1000 | 单条消息上限，超出自动分段 |
| `reply_with_at` | bool | false | OneBot 群聊 @ 发送者 |
| `extra_admin_ids` | list | [] | 额外管理员 ID（见下方 OneBot 说明） |
| `legacy_import` | bool | true | 首次启动导入旧 TXT |

---

## 消息样式

统一「标题 → 分隔线 → 主体 → 分隔线 → 页脚」结构，不用 Markdown、不用表格对齐，任何客户端都不会错行。

```
🌙 今日 Gal 运势
━━━━━━━━━━━━
👤 古河渚 · CLANNAD
✨ 大吉 ▰▰▰▰▰▰▱
📖 今天适合重温一段旧剧情，别忘了存档。
━━━━━━━━━━━━
🕒 2026-11-26 · 第 2 抽
💡 /换老婆 换一位
```

```
🗺️ CLANNAD · 圣地巡礼
━━━━━━━━━━━━
① 东京都瑞穗町长冈(古河面包店)
   🔗 zh.moegirl.org.cn/CLANNAD
② 兵库县西宫市(光坂高校原型)
   🔗 zh.moegirl.org.cn/CLANNAD
━━━━━━━━━━━━
📍 共 2 处 · 第 1/1 页
```

签运分 7 档，各带独立 emoji 与进度条：🌈 超大吉 / ✨ 大吉 / 🍀 中吉 / 🌤️ 小吉 / 🌥️ 末吉 / ☁️ 平 / 🌧 凶。

---

## OneBot 适配说明

1. **权限**：OneBot 私聊事件的 `role` 恒为 `member`，`is_admin()` 判定不到。
   把 QQ 号填进 `extra_admin_ids`，或使用 AstrBot 全局 `admins_id`，即可在私聊使用管理指令。
2. **消息长度**：QQ 单条约 4500 字节，中文 3 字节/字。默认按 1000 字分段，避免被服务端截断。
3. **@ 回复**：`reply_with_at` 仅在 `aiocqhttp` 平台的群聊生效，其他平台自动降级为普通消息。
4. **指令前缀**：`/`、`!`、`#`、`／` 等前缀都会被自动剥离，参数解析不受影响。
5. **含空格参数**：`Summer Pockets`、`古河渚 (CLANNAD)` 这类参数由插件自行解析，不会被空格截断。

---

## 数据存储

```
data/plugin_data/astrbot_plugin_galuniverse/
├── gal.json     # 角色与圣地数据（原子写入）
└── state.json   # 每日重抽计数（按天自动清理）
```

**不再写入插件目录**，插件升级/重装不会丢数据。备份直接拷 `gal.json` 即可。

### 从 v1.x 升级

首次启动会检测插件目录下的 `wives.txt` / `spots.txt` 并自动导入：

- 自动去重（旧版 376 行女主 → 310 条，66 条重复被合并）；
- 同一作品的多个地点全部保留（旧版用 dict 做索引，99 行只剩 52 条）；
- 支持 `古河渚 (CLANNAD)`、`古河渚（CLANNAD）`、`古河渚 - CLANNAD` 三种写法；
- 导入后不再回写 TXT，可在聊天里用 `/gal 导入` 再次补录。

---

## 开发

```bash
cd astrbot_plugin_galuniverse
python -m unittest discover -s tests -v
```

核心逻辑（`core/`）只依赖标准库，可脱离 AstrBot 单测。

```
main.py               # 指令注册与路由
_conf_schema.json     # WebUI 配置 Schema
core/models.py        # 数据模型
core/store.py         # 持久化、迁移、检索
core/fortune.py       # 确定性抽签
core/parser.py        # 参数解析、长消息分段
core/render.py        # 纯文本渲染
assets/               # 内置初始数据
tests/                # 单测
```

---

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 许可

AGPL-3.0，作者 Care。
