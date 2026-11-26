# GalUniverse Pro

> 给你的 AstrBot 装上一位 Galgame 陪伴者：每天抽一位「今日老婆」，顺手查一查圣地巡礼。

支持 **OneBot v11（aiocqhttp / NapCat / Lagrange）**、QQ 官方机器人、Telegram、Discord、飞书等 AstrBot 已接入的平台。指令输出为纯文本，不依赖 Markdown 渲染。

当前版本：**v2.1.0**

---

## 功能

| 功能 | 说明 |
|---|---|
| 今日老婆 | 每天固定抽一位角色 + 签运 + 建议，同一天结果稳定 |
| 换老婆 | 每日有限次重抽，次数可配置 |
| 角色池 | 本地名单与 Bangumi 镜像角色池按比例混合抽取，可抽到名单外角色 |
| 一条消息 | 立绘插在角色名字下面，图文合成一条消息发完 |
| Markdown | QQ 官方机器人自动用 Markdown 排版（标题/加粗/引用/内嵌图片） |
| 圣地巡礼 | 按作品查询取景地，同一作品支持**多条**地点，自动分页 |
| 圣地列表 | 浏览已收录的全部作品与条目数 |
| 圣地联动 | 抽到角色后，卡片内直接给出其作品的取景地与**可点击链接** |
| 数据管理 | 聊天内增删角色/圣地，热重载无需重启 |
| 自检诊断 | `/gal 诊断` 一眼看清目录、名单量、接口与遗留冲突 |
| 多平台 | 纯文本 / Markdown 双形态，OneBot 群聊可选 @ 回复、长消息自动分段 |

内置初始数据：**310 位角色 / 68 条圣地 / 52 部作品**（已去重清洗）。

> 抽到角色后若开启镜像角色池，会同时带上该作品的角色立绘与圣地链接 —— 名单只有 310 位，但 Bangumi 里的角色是几百上千位，重复感会明显下降。

---

## 安装

**推荐**：在 AstrBot WebUI 的插件市场搜索 `GalUniverse Pro` 一键安装，之后可直接在线更新。

手动安装：

1. 把插件目录放到 AstrBot 的 `data/plugins/` 下，**目录名必须是 `astrbot_plugin_universe`**
   （AstrBot 用 `metadata.yaml` 的 `name` 定位插件，目录名不一致会导致更新时提示「插件不存在」）；
2. 在 WebUI「插件」页点击重载，或重启 AstrBot；
3. 进入插件配置页按需调整（见下）。

无第三方依赖（`aiohttp` 由 AstrBot 自带），`requirements.txt` 为空。

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
| `/gal 诊断` | 自检：插件名/目录/名单量/接口/遗留冲突 |
| `/gal 帮助` | 指令一览 |

---

## 配置项

配置在 WebUI 插件详情页可视化编辑，落盘于 `data/config/astrbot_plugin_universe_config.json`。

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
| `enable_spot_link` | bool | true | 今日老婆附带圣地信息 |
| `image_source` | string | `auto` | 立绘来源：`auto` / `bangumi` / `local` / `off` |
| `image_cache_days` | int | 30 | 立绘缓存天数 |
| `image_upscale` | bool | true | 原图窄于 720px 时放大后再发，避免显示成缩略图 |
| `render_mode` | string | `auto` | 消息格式：`auto`（图片走附件，必定显示）/ `markdown` / `text` |
| `single_message` | bool | true | 图文合成一条消息，立绘插在名字下面 |
| `pool_source` | string | `hybrid` | 角色池：`hybrid`（本地+镜像）/ `bangumi`（仅镜像）/ `local`（仅本地） |
| `bangumi_ratio` | int | 50 | 镜像抽取占比 %，仅 `hybrid` 生效，0 等于只用本地 |
| `image_api_bases` | list | 镜像 → 官方 | 接口地址，按顺序兜底，官方恒定最后 |
| `image_mirrors` | list | bgmimg / waterbee / sakuraspark | 图片镜像站，按顺序兜底，全部失败回源官方 |
| `page_size` | int | 6 | 每页条数 |
| `link_style` | string | `full` | 链接展示：`full`（可点击）/ `domain` / `hidden` |
| `max_chars_per_message` | int | 1000 | 单条消息上限，超出自动分段 |
| `reply_with_at` | bool | false | OneBot 群聊 @ 发送者（QQ 官方已自动忽略） |
| `extra_admin_ids` | list | [] | 额外管理员 ID（见下方 OneBot 说明） |
| `legacy_import` | bool | true | 首次启动导入旧 TXT |

---

## 消息样式

**一条消息发完**：文字卡片 + 立绘插在角色名字下面。

OneBot / Telegram / Discord 等平台走纯文本卡片（图片按消息链顺序插在名字下方）：

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

QQ 官方机器人走 Markdown（`![](公网地址)` 内嵌图片，图片同样落在名字下面）：

```markdown
## 🌙 今日老婆
# 古河渚 · CLANNAD
![古河渚 #240px #320px](https://bgmimg.sakuraspark.fun/pic/crt/l/....jpg)
✨ **大吉** ▰▰▰▰▰▰▱
> 记得存档。
📍 东京都瑞穗町长冈(古河面包店)
<https://zh.moegirl.org.cn/CLANNAD/圣地巡礼>
***
2026-11-26 · 换一位发 /换老婆
```

> 注意 QQ 的图片语法**必须带尺寸**（`![alt #宽px #高px](url)`）。只写 `![alt](url)` 会被降级成链接文字，图不会出来 —— v2.0.5 就是踩了这个坑。

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

链接默认输出**带 `https://` 的完整 URL**，聊天客户端会自动识别为可点击链接；觉得太长可在配置里把 `link_style` 改成 `domain`。

签运分 7 档，各带独立 emoji 与进度条：🌈 超大吉 / ✨ 大吉 / 🍀 中吉 / 🌤️ 小吉 / 🌥️ 末吉 / ☁️ 平 / 🌧 凶。

## 关于 Markdown 与图片

QQ 官方机器人（`qq_official` / `qq_official_webhook`）已全量开放 Markdown，但它的
「Markdown 消息（`msg_type=2`）」与「富媒体消息（`msg_type=7`）」是互斥的两种消息类型，
不能在同一条里既发 Markdown 又挂图片附件。

本插件的处理方式（`render_mode=auto`，默认）：

1. 先把立绘下载到本地缓存；
2. 若 AstrBot 配了 **`callback_api_base`（外部访问地址）**，把本地图注册成
   `https://你的域名/api/file/<token>`，再以 `![名字 #240px #320px](该地址)` 内嵌进 Markdown ——
   这是**用户自己的域名**，平台一定下得动，图片正好落在名字下面；
3. 没配或注册失败，退回「图片附件 + 纯文本卡片」的**同一条消息** —— 图片必定显示。

> 为什么不能直接用 Bangumi 镜像的地址内嵌？QQ 的服务器在下载外链图，
> `bgmimg.sakuraspark.fun` 这类境外/Cloudflare 镜像它下不动，消息里就会显示「加载失败」。
> v2.0.5/2.0.6 踩的就是这个坑。

三种模式：

| `render_mode` | 行为 |
|---|---|
| `auto`（默认） | 能内嵌就内嵌（需 `callback_api_base`），否则图片附件 |
| `markdown` | 强制 Markdown，图片用文件服务或镜像外链内嵌，可能加载失败 |
| `text` | 强制纯文本卡片 + 图片附件，兼容性最好 |

## 关于「一条消息两个名字」

v2.0.5 已修：`今日老婆` 现在**只返回一次**结果。旧版是「文字一条 + 图片一条」分两次返回，
QQ 官方适配器会把同一事件内的返回合并进一个发送缓冲，看起来就像卡片被打印了两遍。

如果升级后仍然重复，说明 `data/plugins/` 下同时存在 `astrbot_plugin_universe` 与
`astrbot_plugin_galuniverse` 两份插件（v2.0.0 误建的副本），两个实例各答一次。
删掉旧目录后重载即可，发 `/gal 诊断` 能直接看到这个冲突。

---

## 角色池与立绘

**抽取来源**（`pool_source`）：

1. `hybrid`（默认）：按 `bangumi_ratio` 的概率走镜像角色池，其余走本地名单；
2. `bangumi`：每次都在镜像角色池里抽；
3. `local`：只用本地名单，不联网。

镜像角色池的取法：从已收录的 52 部作品里确定性挑一部 → 搜作品 ID → 取该作品角色（只保留有立绘的「主角 / 配角」）→ 按 seed 确定性地选一位。
所以抽到的角色天然带作品名，圣地巡礼链接能直接接上；接口挂了或作品查不到时**自动回落本地名单**，不影响出卡。

抽签结果会写进 `image_cache/bgm_pool.json`，同一天重复触发不会变、断网也能复现。

**没图就换一位**：抽到的角色如果立绘拉不下来，会自动换下一位候选（`seed#1`、`seed#2`，最多 3 位），
直到拿到一张能用的图；三位都不行就只发一条「这次没拉到立绘」的提示，不会发一张没图的卡。
候选序列本身也是确定性的，所以同一天多次触发仍然稳定。

**立绘优先级**：

1. **本地图片**：`data/plugin_data/astrbot_plugin_universe/images/`
   文件名支持 `古河渚.jpg`、`古河渚 (CLANNAD).png`，扩展名 `.jpg/.jpeg/.png/.webp/.gif`
2. **Bangumi 镜像**：接口按 `image_api_bases` 顺序尝试（默认 `bgmapi.sakuraspark.fun` → `api.bgm.tv`），
   图片按 `image_mirrors` 顺序尝试（默认 `bgmimg.sakuraspark.fun` → `bgmlain.waterbee.cc` → `bgm.sakuraspark.fun`），
   全部失败才回源 `lain.bgm.tv`
3. 都拿不到：只发文字卡片，不报错

`image_source` 可强制指定来源，或设 `off` 完全关闭。搜索失败会写 miss 标记，24 小时内不再重试，避免拖慢抽签。

Markdown 平台不会下载图片，而是用 `resolve_url()` 只取公网地址写进 `![]()`，地址缓存在 `image_cache/image_urls.json`。

## 关于「抽来抽去就那几个」

v2.0.3 修掉了两个会造成重复感的真实原因：

1. **数据目录残留**：旧版插件名 `astrbot_plugin_galuniverse` 与市场名 `astrbot_plugin_universe` 不一致，
   数据分别落在两个目录里，其中一份可能只有寥寥几条。启动时会自动从旧目录幂等补录。
2. **名单被截断**：`gal.json` 存在但条目极少时，旧逻辑不会补内置数据。现在名单少于 50 位会自动补入内置角色。

若仍觉得重复，用 `/gal 诊断` 看「名单」数量；也可以把 `bangumi_ratio` 调到 80~100，让镜像池承担更多抽取。

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
data/plugin_data/astrbot_plugin_universe/
├── gal.json        # 角色与圣地数据（原子写入）
├── state.json      # 每日重抽计数（按天自动清理）
├── images/         # 自定义立绘，优先级最高
└── image_cache/    # 立绘缓存 + bgm_pool.json + image_urls.json
```

**不再写入插件目录**，插件升级/重装不会丢数据。备份直接拷 `gal.json` 即可。

### 从 v1.x 升级

仓库不再附带旧的 `wives.txt` / `spots.txt`（内容已清洗进 `assets/`），
但首次启动仍会检测**你插件目录下**遗留的这两个文件并自动导入：

- 自动去重（旧版 376 行女主 → 310 条，66 条重复被合并）；
- 同一作品的多个地点全部保留（旧版用 dict 做索引，99 行只剩 52 条）；
- 支持 `古河渚 (CLANNAD)`、`古河渚（CLANNAD）`、`古河渚 - CLANNAD` 三种写法；
- 导入后不再回写 TXT，可在聊天里用 `/gal 导入` 再次补录。

### 从 v2.0.0 / v2.0.1 升级（重要）

v2.0.0 曾把插件名写成 `astrbot_plugin_galuniverse`，而插件市场条目是 `astrbot_plugin_universe`。
AstrBot 的「更新」是按 `metadata.yaml` 里的 `name` 精确匹配已安装插件的，名字对不上就会提示
**「插件 xxx 不存在 / 没有这个名称」**，于是更新失败。v2.0.3 起已统一回 `astrbot_plugin_universe` 并永久保持。

如果现在更新仍然报「没有这个名称」，按下面任一种方式做**一次**手动收尾，之后就能正常在线更新：

- **方式 A（推荐）**：WebUI 插件页卸载本插件 → 重新从插件市场安装 → 数据目录不变，`gal.json` 自动沿用；
- **方式 B**：进服务器 `data/plugins/`，若同时存在 `astrbot_plugin_universe` 与 `astrbot_plugin_galuniverse` 两个目录，
  删掉 `astrbot_plugin_galuniverse`（v2.0.0 误建的副本），保留 `astrbot_plugin_universe`，再重载插件。

两种情况都不会丢数据：启动时会自动把旧目录 `gal.json` 里的角色/圣地幂等补录进当前数据文件。
不确定现状时先发 `/gal 诊断`，它会直接告诉你有没有遗留目录冲突。

---

## 目录结构

仓库只放运行期真正会被加载的文件：

```
main.py               # 指令注册与路由
__init__.py           # 包声明，保证相对导入可用
metadata.yaml         # 插件元信息（name / version / repo）
_conf_schema.json     # WebUI 配置 Schema
requirements.txt      # 依赖声明（AstrBot 已内置）
core/models.py        # 数据模型
core/store.py         # 持久化、迁移、检索
core/fortune.py       # 确定性抽签
core/bgm.py           # Bangumi 镜像角色池
core/images.py        # 立绘获取与多镜像兜底
core/parser.py        # 参数解析、长消息分段
core/render.py        # 卡片渲染（纯文本 / Markdown）
core/theme.py         # 视觉常量（分隔线、签运、链接）
assets/               # 内置初始数据（角色 / 圣地）
```

单元测试只保留在本地开发目录，不进仓库（AstrBot 加载插件时用不到）：

```bash
python -m unittest discover -s tests -v
```

核心逻辑（`core/`）只依赖标准库，可脱离 AstrBot 单测。

---

## 更新日志

见 [CHANGELOG.md](CHANGELOG.md)。

## 许可

AGPL-3.0，作者 Care。
