"""GalUniverse Pro v2 — AstrBot 插件入口。

适配说明：
- 平台无关：只依赖 AstrBot 抽象层（plain_result / chain_result），
  OneBot(aiocqhttp)、QQ 官方、Telegram、Discord 均可直接使用；
- OneBot 专属增强：群聊可选用 @发送者 回复、长消息自动分段、
  管理权限兼容 ``admins_id`` 全局配置与插件内 ``extra_admin_ids``；
- 指令参数自行解析（而非依赖装饰器注入），避免 OneBot 下
  "古河渚 (CLANNAD)"、"Summer Pockets" 这类含空格参数被截断。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Plain
from astrbot.api.star import Context, Star, StarTools, register

from .core import render
from .core.fortune import daily_seed, pick_advice, pick_fortune, pick_index, today_key
from .core.images import ImageFetcher
from .core.models import Heroine, Spot
from .core.parser import chunk_text, normalize, parse_int, split_fields, split_first, strip_command
from .core.store import GalStore, StateStore, norm

PLUGIN_NAME = "astrbot_plugin_universe"
VERSION = "2.0.1"

ADMIN_SUBS = {"添加老婆", "添加圣地", "删除老婆", "删除圣地", "重载", "统计", "导入", "备份"}


@register(PLUGIN_NAME, "Care", "如果在梦里能相遇的话，那大概就是现实", VERSION)
class GalUniversePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config: AstrBotConfig = config or {}
        self.plugin_dir = Path(__file__).resolve().parent

        try:
            self.data_dir = Path(StarTools.get_data_dir(PLUGIN_NAME))
        except Exception as exc:  # 极端情况下（旧内核无 StarTools）退回插件目录
            logger.warning(f"[GalUniverse] 获取数据目录失败，回退插件目录：{exc}")
            self.data_dir = self.plugin_dir / "data"
            self.data_dir.mkdir(parents=True, exist_ok=True)

        self.store = GalStore(
            data_dir=self.data_dir,
            assets_dir=self.plugin_dir / "assets",
            legacy_dirs=(self.plugin_dir, self.data_dir),
        )
        self.state = StateStore(self.data_dir)
        self.images = ImageFetcher(
            cache_dir=self.data_dir / "image_cache",
            local_dir=self.data_dir / "images",
            source=str(self._cfg("image_source", "auto") or "auto"),
            cache_days=parse_int(self._cfg("image_cache_days", 30), 30),
            api_base=str(self._cfg("image_api_base", "https://api.bgm.tv") or "https://api.bgm.tv"),
            mirrors=self._image_mirrors(),
        )
        self._lock = asyncio.Lock()
        self._loaded = False
        self._image_warned: set[str] = set()

    # ---------------- 生命周期 ----------------

    async def initialize(self) -> None:
        await self._load_data(legacy_import=bool(self._cfg("legacy_import", True)))

    async def terminate(self) -> None:
        try:
            self.state.save()
        except Exception as exc:
            logger.warning(f"[GalUniverse] 保存状态失败：{exc}")

    async def _load_data(self, legacy_import: bool = False) -> str:
        async with self._lock:
            report = await asyncio.to_thread(self.store.load, legacy_import)
            self._loaded = True
        logger.info(f"[GalUniverse] 数据加载完成：{report.summary()}")
        return report.summary()

    # ---------------- 配置与工具 ----------------

    def _cfg(self, key: str, default):
        try:
            value = self.config.get(key, default)
        except Exception:
            return default
        return default if value is None else value

    def _tz(self) -> str:
        return str(self._cfg("timezone", "Asia/Shanghai") or "Asia/Shanghai")

    def _sender_id(self, event: AstrMessageEvent) -> str:
        try:
            return str(event.get_sender_id() or "")
        except Exception:
            return ""

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """OneBot 私聊下 role 恒为 member，因此补充白名单兜底。"""
        try:
            if event.is_admin():
                return True
        except Exception:
            pass

        uid = self._sender_id(event)
        if not uid:
            return False

        extra = self._cfg("extra_admin_ids", []) or []
        if isinstance(extra, str):
            extra = [x for x in extra.replace("，", ",").split(",")]
        if uid in {str(x).strip() for x in extra if str(x).strip()}:
            return True

        try:
            global_conf = self.context.get_config() or {}
            admins = global_conf.get("admins_id") or []
            if isinstance(admins, str):
                admins = [admins]
            return uid in {str(x).strip() for x in admins}
        except Exception:
            return False

    async def _reply(self, event: AstrMessageEvent, text: str):
        """统一出口：长消息分段；OneBot 群聊可选 @ 发送者。"""
        limit = parse_int(self._cfg("max_chars_per_message", 1000), 1000)
        want_at = bool(self._cfg("reply_with_at", False))
        in_group = bool(event.get_group_id())
        is_onebot = False
        try:
            is_onebot = event.get_platform_name() == "aiocqhttp"
        except Exception:
            pass
        use_at = want_at and in_group and is_onebot

        for chunk in chunk_text(text, limit):
            if use_at:
                yield event.chain_result([At(qq=self._sender_id(event)), Plain(chunk)])
            else:
                yield event.plain_result(chunk)

    def _scope_key(self, event: AstrMessageEvent) -> str:
        scope = str(self._cfg("fortune_scope", "per_user") or "per_user")
        if scope == "global":
            return "global"
        if scope == "per_group":
            gid = event.get_group_id() or self._sender_id(event)
            return f"g:{event.get_platform_id()}:{gid}"
        return f"u:{event.get_platform_id()}:{self._sender_id(event)}"

    def _draw(self, scope_key: str, date_key: str, reroll: int = 0) -> tuple[Heroine | None, str, str]:
        heroines = self.store.heroines
        if not heroines:
            return None, "", ""
        seed = daily_seed(scope_key, date_key, reroll)
        heroine = heroines[pick_index(seed, len(heroines))]
        fortune = pick_fortune(seed, list(self._cfg("fortune_pool", []) or []))
        advice = pick_advice(seed, list(self._cfg("advice_pool", []) or []))
        return heroine, fortune, advice

    def _image_mirrors(self) -> list[str] | None:
        """镜像列表：优先读 image_mirrors，兼容旧的 image_mirror 字符串。"""
        raw = self._cfg("image_mirrors", None)
        if raw is None:
            raw = self._cfg("image_mirror", None)
        if raw is None:
            return None  # 交给 ImageFetcher 使用内置默认镜像
        if isinstance(raw, str):
            return [x.strip() for x in raw.replace("，", ",").split(",") if x.strip()]
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        return None

    def _link_style(self) -> str:
        style = str(self._cfg("link_style", "domain") or "domain").lower()
        return style if style in {"domain", "full", "hidden"} else "domain"

    def _spot_for(self, heroine: Heroine) -> tuple[Spot | None, int]:
        """按角色所属作品找圣地，精确匹配优先，其次模糊。"""
        if not bool(self._cfg("enable_spot_link", True)) or not heroine.work:
            return None, 0
        target = norm(heroine.work)
        group = [s for s in self.store.spots if norm(s.work) == target]
        if not group:
            matches = self.store.find_spots(heroine.work, fuzzy=True, limit=1)
            if not matches:
                return None, 0
            work = matches[0].work
            group = [s for s in self.store.spots if s.work == work]
        if not group:
            return None, 0
        return group[0], len(group)

    async def _emit_image(self, event: AstrMessageEvent, heroine: Heroine):
        """拉取角色立绘；任何失败都静默跳过，不影响文字卡片。"""
        if str(self._cfg("image_source", "auto")) == "off":
            return
        try:
            path = await self.images.fetch(heroine.name, heroine.work)
        except Exception as exc:
            logger.warning(f"[GalUniverse] 立绘获取失败：{exc}")
            return
        if not path:
            # 每个角色只提示一次，避免刷屏，同时方便排查网络问题
            if heroine.name not in self._image_warned and len(self._image_warned) < 200:
                self._image_warned.add(heroine.name)
                logger.info(
                    f"[GalUniverse] 未取到「{heroine.name}」的立绘"
                    f"（来源={self._cfg('image_source', 'auto')}，可检查 api.bgm.tv 连通性）"
                )
            return
        try:
            yield event.image_result(str(path))
        except Exception as exc:
            logger.warning(f"[GalUniverse] 立绘发送失败：{exc}")

    async def _emit_daily(
        self,
        event: AstrMessageEvent,
        heroine: Heroine,
        fortune: str,
        advice: str,
        date_key: str,
        reroll: int = 0,
    ):
        spot, total = self._spot_for(heroine)
        text = render.daily_card(
            heroine,
            fortune,
            advice,
            date_key,
            reroll=reroll,
            can_reroll=parse_int(self._cfg("reroll_per_day", 1), 1) > 0,
            spot=spot,
            spot_total=total,
            link_style=self._link_style(),
        )
        async for msg in self._reply(event, text):
            yield msg
        async for msg in self._emit_image(event, heroine):
            yield msg

    # ---------------- 抽老婆 ----------------

    @filter.command("今日老婆", alias={"今日运势", "抽老婆"})
    async def daily_wife(self, event: AstrMessageEvent):
        """抽取今日 Gal 运势（同一天结果固定）"""
        try:
            if not bool(self._cfg("enable_daily_wife", True)):
                async for msg in self._reply(
                    event, render.tip_card("🌙 今日老婆已关闭", "管理员可在插件配置中开启")
                ):
                    yield msg
                return
            if not self.store.heroines:
                async for msg in self._reply(event, render.empty_heroines()):
                    yield msg
                return

            date_key = today_key(self._tz())
            scope_key = self._scope_key(event)
            heroine, fortune, advice = self._draw(scope_key, date_key)
            if heroine is None:
                async for msg in self._reply(event, render.empty_heroines()):
                    yield msg
                return
            async for msg in self._emit_daily(
                event, heroine, fortune, advice, date_key
            ):
                yield msg
        except Exception as exc:
            logger.error(f"[GalUniverse] 今日老婆异常：{exc}")
            async for msg in self._reply(event, render.error_card()):
                yield msg

    @filter.command("换老婆", alias={"重抽"})
    async def reroll(self, event: AstrMessageEvent):
        """重新抽取今日角色（每日有限次）"""
        try:
            if not bool(self._cfg("enable_daily_wife", True)):
                async for msg in self._reply(
                    event, render.tip_card("🌙 今日老婆已关闭", "管理员可在插件配置中开启")
                ):
                    yield msg
                return
            if not self.store.heroines:
                async for msg in self._reply(event, render.empty_heroines()):
                    yield msg
                return

            date_key = today_key(self._tz())
            scope_key = self._scope_key(event)
            state_key = f"{scope_key}|{date_key}"
            limit = max(0, parse_int(self._cfg("reroll_per_day", 1), 1))
            used = self.state.reroll_used(state_key, date_key)
            if used >= limit:
                async for msg in self._reply(event, render.reroll_exhausted(limit)):
                    yield msg
                return

            used = self.state.mark_reroll(state_key, date_key)
            heroine, fortune, advice = self._draw(scope_key, date_key, used)
            if heroine is None:
                async for msg in self._reply(event, render.empty_heroines()):
                    yield msg
                return
            async for msg in self._emit_daily(
                event, heroine, fortune, advice, date_key, reroll=used
            ):
                yield msg
        except Exception as exc:
            logger.error(f"[GalUniverse] 换老婆异常：{exc}")
            async for msg in self._reply(event, render.error_card()):
                yield msg

    # ---------------- 圣地巡礼 ----------------

    @filter.command("圣地巡礼", alias={"巡礼"})
    async def pilgrimage(self, event: AstrMessageEvent):
        """查询某部作品的取景地，支持页码翻页"""
        try:
            if not bool(self._cfg("enable_pilgrimage", True)):
                async for msg in self._reply(
                    event, render.tip_card("🗺️ 圣地巡礼已关闭", "管理员可在插件配置中开启")
                ):
                    yield msg
                return

            body = strip_command(event.get_message_str(), "圣地巡礼", "巡礼")
            if not body:
                async for msg in self._reply(
                    event, render.usage("/圣地巡礼 CLANNAD")
                ):
                    yield msg
                return

            page = 1
            tokens = body.split(" ")
            if len(tokens) >= 2 and tokens[-1].isdigit():
                page = parse_int(tokens[-1], 1)
                work = " ".join(tokens[:-1])
            else:
                work = body

            fuzzy = bool(self._cfg("fuzzy_match", True))
            matches = self.store.find_spots(work, fuzzy=fuzzy, limit=len(self.store.spots) or 1)
            if not matches:
                q = normalize(work).upper()
                suggestions = [w for w, _ in self.store.works() if q and q in w.upper()][:3]
                async for msg in self._reply(event, render.not_found(work, suggestions)):
                    yield msg
                return

            best_work = matches[0].work
            group = [s for s in self.store.spots if s.work == best_work]
            group.sort(key=lambda s: (s.region, s.name))
            page_size = parse_int(self._cfg("page_size", 6), 6)
            items, page, total_pages = render.page_slice(group, page, page_size)
            async for msg in self._reply(
                event,
                render.spot_card(
                    best_work,
                    items,
                    page,
                    total_pages,
                    link_style=self._link_style(),
                    keyword=work,
                ),
            ):
                yield msg
        except Exception as exc:
            logger.error(f"[GalUniverse] 圣地巡礼异常：{exc}")
            async for msg in self._reply(event, render.error_card()):
                yield msg

    @filter.command("圣地列表", alias={"巡礼列表"})
    async def spot_list(self, event: AstrMessageEvent):
        """浏览已收录的作品清单"""
        try:
            works = self.store.works()
            if not works:
                async for msg in self._reply(
                    event,
                    render.usage("管理员可用 /gal 添加圣地 作品|地点|链接 添加"),
                ):
                    yield msg
                return
            page = parse_int(strip_command(event.get_message_str(), "圣地列表", "巡礼列表"), 1)
            page_size = parse_int(self._cfg("page_size", 6), 6) + 4
            items, page, total_pages = render.page_slice(works, page, page_size)
            async for msg in self._reply(
                event, render.works_card(items, page, total_pages, len(works))
            ):
                yield msg
        except Exception as exc:
            logger.error(f"[GalUniverse] 圣地列表异常：{exc}")
            async for msg in self._reply(event, render.error_card()):
                yield msg

    # ---------------- 管理入口 ----------------

    @filter.command("gal", alias={"GAL", "Gal", "gal帮助"})
    async def gal(self, event: AstrMessageEvent):
        """管理指令入口：/gal 帮助"""
        try:
            body = strip_command(event.get_message_str(), "gal", "GAL", "Gal", "gal帮助")
            sub, rest = split_first(body)

            if not sub or sub in {"帮助", "help", "?", "？"}:
                async for msg in self._reply(event, render.help_card(self.store.stats())):
                    yield msg
                return

            if sub not in ADMIN_SUBS:
                async for msg in self._reply(event, render.unknown_sub(sub)):
                    yield msg
                return

            if not self._is_admin(event):
                async for msg in self._reply(event, render.no_permission()):
                    yield msg
                return

            async for msg in self._dispatch_admin(event, sub, rest):
                yield msg
        except Exception as exc:
            logger.error(f"[GalUniverse] gal 指令异常：{exc}")
            async for msg in self._reply(event, render.error_card()):
                yield msg

    @filter.command("重载Gal数据")
    async def legacy_reload(self, event: AstrMessageEvent):
        """兼容旧版指令：重载数据"""
        if not self._is_admin(event):
            async for msg in self._reply(event, render.no_permission()):
                yield msg
            return
        summary = await self._load_data(legacy_import=False)
        async for msg in self._reply(event, render.info_card("🔄 数据已重载", summary)):
            yield msg

    async def _dispatch_admin(self, event: AstrMessageEvent, sub: str, rest: str):
        if sub == "添加老婆":
            if not rest:
                async for msg in self._reply(
                    event, render.usage("/gal 添加老婆 古河渚 (CLANNAD)")
                ):
                    yield msg
                return
            async with self._lock:
                ok, msg = await asyncio.to_thread(self.store.add_heroine, rest)
            async for item in self._reply(
                event, render.info_card("✅ 已加入" if ok else "❌ 未加入", msg)
            ):
                yield item
            return

        if sub == "添加圣地":
            fields = split_fields(rest)
            if len(fields) < 2:
                async for msg in self._reply(
                    event, render.usage("/gal 添加圣地 作品|地点|链接（链接可省略）")
                ):
                    yield msg
                return
            work, name = fields[0], fields[1]
            link = fields[2] if len(fields) > 2 else ""
            region = fields[3] if len(fields) > 3 else ""
            async with self._lock:
                ok, msg = await asyncio.to_thread(self.store.add_spot, work, name, link, region)
            async for item in self._reply(
                event, render.info_card("✅ 已收录" if ok else "❌ 未收录", msg)
            ):
                yield item
            return

        if sub == "删除老婆":
            if not rest:
                async for msg in self._reply(event, render.usage("/gal 删除老婆 关键词")):
                    yield msg
                return
            async with self._lock:
                count, removed = await asyncio.to_thread(self.store.remove_heroine, rest)
            if not count:
                async for msg in self._reply(
                    event, render.info_card("🔍 没有匹配项", f"未找到「{rest}」相关角色")
                ):
                    yield msg
                return
            preview = "、".join(removed[:8]) + ("…" if count > 8 else "")
            async for msg in self._reply(
                event, render.info_card(f"🗑️ 已删除 {count} 位", preview)
            ):
                yield msg
            return

        if sub == "删除圣地":
            if not rest:
                async for msg in self._reply(event, render.usage("/gal 删除圣地 关键词")):
                    yield msg
                return
            async with self._lock:
                count, removed = await asyncio.to_thread(self.store.remove_spot, rest)
            if not count:
                async for msg in self._reply(
                    event, render.info_card("🔍 没有匹配项", f"未找到「{rest}」相关圣地")
                ):
                    yield msg
                return
            preview = "、".join(removed[:6]) + ("…" if count > 6 else "")
            async for msg in self._reply(
                event, render.info_card(f"🗑️ 已删除 {count} 条", preview)
            ):
                yield msg
            return

        if sub == "重载":
            summary = await self._load_data(legacy_import=False)
            async for msg in self._reply(event, render.info_card("🔄 数据已重载", summary)):
                yield msg
            return

        if sub == "导入":
            async with self._lock:
                added_h, added_s = await asyncio.to_thread(self.store.merge_legacy)
            async for msg in self._reply(
                event,
                render.info_card(
                    "📥 旧数据导入完成", f"新增女主 {added_h} 位 · 新增圣地 {added_s} 条"
                ),
            ):
                yield msg
            return

        if sub == "统计":
            async for msg in self._reply(
                event, render.stats_card(self.store.stats(), str(self.store.path))
            ):
                yield msg
            return

        if sub == "备份":
            async with self._lock:
                await asyncio.to_thread(self.store.save)
            async for msg in self._reply(
                event, render.info_card("💾 已保存", f"数据文件：{self.store.path.name}")
            ):
                yield msg
            return
            return
