# GalUniverse Pro

> 给你的 AstrBot 装一位 Galgame 陪伴者：每天抽一位「今日老婆」，顺手查一查圣地巡礼。

支持 **OneBot v11（aiocqhttp / NapCat / Lagrange）**、**QQ 官方机器人**、Telegram、Discord、飞书等 AstrBot 已接入的平台。输出自动适配：纯文本平台走卡片，QQ 官方走 Markdown。

当前版本：**v2.1.2**

---

## 特性

| 功能 | 说明 |
|---|---|
| 今日老婆 | 每天固定抽一位角色 + 签运 + 建议，同一天结果稳定 |
| 换老婆 | 每日有限次重抽，次数可配 |
| 混合角色池 | 本地 310 位名单 + Bangumi 镜像角色池按比例抽取，能抽到名单外的角色 |
| 一条消息 | 立绘插在角色名字下面，图文合成一条发完 |
| 自动避重 | 记住最近抽过的人，连续几天不重复 |
| 没图就换人 | 立绘拉不到自动换下一位，绝不给卡片配错图 |
| Markdown | QQ 官方机器人自动排版（标题 / 加粗 / 引用 / 内嵌图片） |
| 圣地巡礼 | 按作品查取景地，同一作品支持多条，自动分页 |
| 圣地联动 | 抽到角色后，卡片内直接给出其作品的取景地与可点击链接 |
| 数据管理 | 聊天内增删角色 / 圣地，热重载不用重启 |
| 自检诊断 | `/gal 诊断` 一眼看清目录、名单量、接口与冲突 |

内置数据：**310 位角色 / 68 条圣地 / 52 部作品**（已去重清洗）。

---

## 安装

**推荐**：在 AstrBot WebUI 的插件市场搜索 `GalUniverse Pro` 一键安装，之后可在线更新。

手动安装：

1. 把插件目录放到 `data/plugins/` 下，**目录名必须是 `astrbot_plugin_universe`**
   （AstrBot 用 `metadata.yaml` 的 `name` 定位插件，目录名不一致会导致更新时提示「插件不存在」）；
2. 在 WebUI「插件」页点重载，或重启 AstrBot；
3. 进插件配置页按需调整。

依赖：`aiohttp` 由 AstrBot 自带；`Pillow` 可选，只用于把小图放大。

---

## 指令

### 所有人

| 指令 | 说明 |
|---|---|
| `/今日老婆` | 每日一抽，别名 `/今日运势`、`/抽老婆` |
| `/换老婆` | 重抽一次，别名 `/重抽` |
| `/圣地巡礼 <作品> [页码]` | 查询取景地，别名 `/巡礼`，支持模糊匹配 |
| `/圣地列表 [页码]` | 浏览已收录作品 |

```
/圣地巡礼 CLANNAD
/圣地巡礼 Summer Pockets 2
/圣地巡礼 cl            ← 模糊匹配到 CLANNAD
```

### 管理员

| 指令 | 说明 |
|---|---|
| `/gal 添加老婆 古河渚 (CLANNAD)` | 名字含空格也能正确解析 |
| `/gal 添加圣地 作品\|地点\|链接` | 链接可省略，第 4 段可选填地区 |
| `/gal 删除老婆 <关键词>` | 批量删除，返回删除清单 |
| `/gal 删除圣地 <关键词>` | 按作品 / 地点 / 地区匹配 |
| `/gal 重载` | 重载数据（兼容旧指令 `/重载Gal数据`） |
| `/gal 导入` | 从旧版 `wives.txt` / `spots.txt` 补录 |
| `/gal 统计` | 数据量与存储路径 |
| `/gal 诊断` | 自检：插件名 / 目录 / 名单量 / 接口 / 冲突 |
| `/gal 帮助` | 指令一览 |

---

## 输出样式

**一条消息发完**：文字卡片 + 立绘插在角色名字下面。

OneBot / Telegram / Discord 等走纯文本卡片：

```
🌙 今日老婆
━━━━━━━━━━━━
【古河渚 · CLANNAD】
[立绘图片]
✨ 大吉 ▰▰▰▰▰▰▱
记得存档。
📍 东京都瑞穗町长冈(古河面包店)
🔗 https://zh.moegirl.org.cn/CLANNAD/圣地巡礼
━━━━━━━━━━━━
2026-11-26 · 换一位发 /换老婆
```

QQ 官方机器人走 Markdown：

```markdown
## 🌙 今日老婆
# 古河渚 · CLANNAD
![古河渚 #240px #320px](https://你的域名/api/file/xxxx.jpg)
✨ **大吉** ▰▰▰▰▰▰▱
> 记得存档。
📍 东京都瑞穗町长冈(古河面包店)
<https://zh.moegirl.org.cn/CLANNAD/圣地巡礼>
***
2026-11-26 · 换一位发 /换老婆
```

圣地巡礼卡片：

```
🗺️ CLANNAD · 圣地巡礼
━━━━━━━━━━━━
① 东京都瑞穗町长冈(古河面包店)
   🔗 https://zh.moegirl.org.cn/CLANNAD/圣地巡礼
② 兵库县西宫市(光坂高校原型)
   🔗 https://zh.moegirl.org.cn/CLANNAD/圣地巡礼
━━━━━━━━━━━━
📍 共 2 处 · 第 1/1 页
```

签运分 7 档，各带 emoji 与进度条：🌈 超大吉 / ✨ 大吉 / 🍀 中吉 / 🌤️ 小吉 / 🌥️ 末吉 / ☁️ 平 / 🌧 凶。

---

## 配置项

在 WebUI 插件详情页可视化编辑，落盘于 `data/config/astrbot_plugin_universe_config.json`。

### 基础

| 配置 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enable_daily_wife` | bool | true | 今日老婆总开关 |
| `enable_pilgrimage` | bool | true | 圣地巡礼总开关 |
| `enable_spot_link` | bool | true | 今日老婆附带圣地信息 |
| `fortune_scope` | string | `per_user` | `per_user` / `per_group` / `global` |
| `fortune_pool` | list | 七档签运 | 自定义签运文案 |
| `advice_pool` | list | 12 条短句 | 今日建议文案，留空用内置 |
| `timezone` | string | `Asia/Shanghai` | 决定「每天」的分界点 |
| `reroll_per_day` | int | 1 | 每日重抽次数，0 关闭 |
| `fuzzy_match` | bool | true | 圣地模糊匹配 |
| `page_size` | int | 6 | 每页条数 |
| `link_style` | string | `full` | `full` 可点击 / `domain` / `hidden` |

### 角色池

| 配置 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `pool_source` | string | `hybrid` | `hybrid` 本地+镜像 / `bangumi` 仅镜像 / `local` 仅本地 |
| `bangumi_ratio` | int | 50 | 镜像抽取占比 %，仅 `hybrid` 生效，0 等于只用本地 |

### 立绘

| 配置 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `image_source` | string | `auto` | `auto` / `bangumi` / `local` / `off` |
| `image_cache_days` | int | 30 | 立绘缓存天数 |
| `image_upscale` | bool | true | 原图窄于 720px 时放大再发 |
| `image_api_bases` | list | 镜像 → 官方 | 接口地址，按顺序兜底 |
| `image_mirrors` | list | 3 个镜像 | 图床镜像，按顺序兜底，最后回源官方 |

### 消息

| 配置 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `render_mode` | string | `auto` | `auto` 图片走附件必定显示 / `markdown` / `text` |
| `single_message` | bool | true | 图文合成一条，立绘在名字下面 |
| `max_chars_per_message` | int | 1000 | 单条上限，超出自动分段 |
| `reply_with_at` | bool | false | OneBot 群聊 @ 发送者（QQ 官方自动忽略） |
| `extra_admin_ids` | list | [] | 额外管理员 ID |
| `legacy_import` | bool | true | 首次启动导入旧 TXT |

---

## 角色池与立绘

### 抽取来源

`pool_source` 决定池子：

1. `hybrid`（默认）：按 `bangumi_ratio` 的概率走镜像池，其余走本地名单；
2. `bangumi`：每次都在镜像池里抽；
3. `local`：只用本地名单，完全不联网。

镜像池取法：从 52 部作品里确定性挑一部 → 搜作品 ID → 取该作品角色（只保留有立绘的主角 / 配角，少于 6 人的作品弃用）→ 按 seed 选一位。抽到的角色天然带作品名，圣地链接能直接接上。

结果写入 `image_cache/bgm_pool.json`，同一天重复触发不变、断网也能复现。接口挂了或作品查不到时自动回落本地名单，不影响出卡。

### 自动避重

每个 scope 记住最近 20 次抽取（存在 `state.json`），候选序列会跳过前几天抽过的人。序列本身是确定性的，所以同一天多次触发结果不变 —— 想换发 `/换老婆`。

### 没图就换一位

立绘拉不到时自动换下一位候选（`seed#1`、`seed#2`…最多 6 位），直到拿到一张能用的图。全都失败只回一条「这次没拉到立绘」，不发没图的卡。

### 立绘来源优先级

1. **本地图片**：`data/plugin_data/astrbot_plugin_universe/images/`
   支持 `古河渚.jpg`、`古河渚 (CLANNAD).png`，扩展名 `.jpg/.jpeg/.png/.webp/.gif`
2. **Bangumi 镜像**：接口按 `image_api_bases` 顺序试，图片按 `image_mirrors` 顺序试，
   每个尺寸（large → medium → small → grid）都试一遍，全部失败才回源 `lain.bgm.tv`
3. 都拿不到：换一位角色重来

失败只封 30 分钟，网络抖一下不会让某个角色一整天没图。

### 只认同名，不凑数

内置名单是简体中译名，Bangumi 是日文原名。插件用 `name_key()` 做归一化（去空白、转大写、繁简与日文汉字折叠），所以这些能正确对上：

| 名单 | Bangumi |
|---|---|
| 小木曾雪菜 | 小木曽雪菜 |
| 远坂凛 | 遠坂凛 |
| 牧濑红莉栖 | 牧瀬紅莉栖 |

取图顺序：镜像池直给 → **作品内同名** → 全局同名。搜不到同名就不发图、换一位 —— 绝不拿搜索结果第一条凑数（那会把别人的脸贴上去）。

> 代价：约 4 成角色（阿尔托莉雅 / アルトリア 这类纯假名译名）拿不到图，会被跳过。宁可少一个人，也不配错图。

---

## 关于 Markdown 与图片

QQ 官方的「Markdown 消息（`msg_type=2`）」和「富媒体消息（`msg_type=7`）」互斥，同一条里不能既发 Markdown 又挂图片附件。但 Markdown **支持 `![](公网URL)` 内嵌图片**。

`render_mode=auto`（默认）的处理：

1. 先把立绘下载到本地缓存；
2. 若 AstrBot 配了 **`callback_api_base`（外部访问地址）**，把图注册成
   `https://你的域名/api/file/<token>`，再以 `![名字 #240px #320px](该地址)` 内嵌 ——
   这是你自己的域名，平台一定下得动，图正好落在名字下面；
3. 没配或注册失败，退回「图片附件 + 纯文本卡片」的同一条消息 —— 图片必定显示。

| `render_mode` | 行为 |
|---|---|
| `auto`（默认） | 能内嵌就内嵌（需 `callback_api_base`），否则图片附件 |
| `markdown` | 强制 Markdown 内嵌，可能加载失败 |
| `text` | 强制纯文本卡片 + 图片附件，兼容性最好 |

> 两个坑：QQ 的图片语法**必须带尺寸**（`![alt #宽px #高px](url)`），少写尺寸会被降级成链接文字；
> 直接内嵌 Bangumi 镜像地址也不行，QQ 服务器下不动境外图床，会显示「加载失败」。

---

## 数据存储

```
data/plugin_data/astrbot_plugin_universe/
├── gal.json        # 角色与圣地数据（原子写入）
├── state.json      # 重抽计数 + 最近抽取记录（按天清理）
├── images/         # 自定义立绘，优先级最高
└── image_cache/    # 立绘缓存 + bgm_pool.json + image_urls.json
```

**不写入插件目录**，升级 / 重装不丢数据。备份直接拷 `gal.json` 即可。

---

## 常见问题

**更新时提示「插件 xxx 不存在」**
v2.0.0 曾把插件名写成 `astrbot_plugin_galuniverse`，与市场名 `astrbot_plugin_universe` 不一致，AstrBot 按 `name` 精确匹配就找不到。v2.0.3 起已统一。若现在仍报错：卸载后从市场重装，或删掉 `data/plugins/astrbot_plugin_galuniverse` 目录再重载。数据不会丢。

**一条消息里卡片出现两遍**
`data/plugins/` 下同时存在新旧两个目录，两个实例各答一次。发 `/gal 诊断` 能直接看到冲突告警，删掉旧目录即可。

**抽来抽去就那几个人**
先发 `/gal 诊断` 看名单数量。少于 50 位说明数据没迁移完整，启动时会自动补录内置角色；也可以把 `bangumi_ratio` 调到 80~100 让镜像池承担更多。

**图片显示「加载失败」**
`render_mode` 被设成了 `markdown`。改回 `auto`，或在 AstrBot 设置里填 `callback_api_base`。

**图片和角色名对不上**
v2.1.1 已修。旧缓存里的错图会自动失效（缓存名带版本号）。

**OneBot 私聊用不了管理指令**
私聊事件 `role` 恒为 `member`，`is_admin()` 判不到。把 QQ 号填进 `extra_admin_ids`，或用 AstrBot 全局 `admins_id`。

**消息被截断**
QQ 单条约 4500 字节，中文 3 字节/字。默认按 1000 字分段，调小 `max_chars_per_message` 更保险。

**含空格参数被截断**
`Summer Pockets`、`古河渚 (CLANNAD)` 这类参数由插件自行解析，不受影响。指令前缀 `/`、`!`、`#`、`／` 都会自动剥离。

---

## 目录结构

```
main.py               # 指令注册与路由
__init__.py           # 包声明
metadata.yaml         # 插件元信息（name / version / repo）
_conf_schema.json     # WebUI 配置 Schema
requirements.txt      # 依赖声明
logo.png              # 插件图标
core/models.py        # 数据模型
core/store.py         # 持久化、迁移、检索
core/fortune.py       # 确定性抽签
core/bgm.py           # Bangumi 镜像角色池
core/images.py        # 立绘获取与多镜像兜底
core/parser.py        # 参数解析、长消息分段
core/render.py        # 卡片渲染（纯文本 / Markdown）
core/theme.py         # 视觉常量
assets/               # 内置初始数据
```

单测只留在本地开发目录，不进仓库：

```bash
python -m unittest discover -s tests -v
```

`core/` 只依赖标准库，可脱离 AstrBot 单测。

---

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 许可

AGPL-3.0，作者 Care。
