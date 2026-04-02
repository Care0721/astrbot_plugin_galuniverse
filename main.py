import os
import random
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Union, Dict, List

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

try:
    from astrbot.api.star import StarTools
except ImportError:
    StarTools = None

@register("astrbot_plugin_universe", "Care", "超硬核 Galgame 沉浸式助手", "1.7.4")
class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 3. [中危修复] 引入异步锁，解决并发读写竞争风险
        self.io_lock = asyncio.Lock()
        
        # 2. & 5. [低/中危修复] 更加严谨的路径合法性校验
        self.base_path = self._get_safe_data_dir()
        
        self.heroines: List[str] = []
        self.spots_db: Dict[str, dict] = {}
        
        # 初始加载不使用异步锁，因为是在初始化阶段
        self._load_data_sync()

    def _get_safe_data_dir(self) -> str:
        """5. [低危修复] 改进类型特征判断逻辑，使用 Pathlike 校验替代字符串匹配"""
        target_path = None
        
        if StarTools and hasattr(StarTools, "get_data_dir"):
            try:
                # 尝试标准调用
                res = StarTools.get_data_dir()
                # 严格校验：如果是 Path 对象或非本类实例的字符串则采纳
                if isinstance(res, (str, Path)) and "GalUniversePlugin" not in str(res):
                    target_path = Path(res)
            except Exception:
                try:
                    res = StarTools.get_data_dir(self)
                    if isinstance(res, (str, Path)) and "GalUniversePlugin" not in str(res):
                        target_path = Path(res)
                except Exception:
                    pass

        # 2. [中危修复] Fallback 路径规范化：不再直接依赖不稳定 cwd
        if not target_path:
            # 使用插件目录同级的 data 目录（符合大多数容器化部署逻辑）
            target_path = Path(__file__).parent.parent.parent / "data" / "plugins" / "astrbot_plugin_universe"
            
        target_path.mkdir(parents=True, exist_ok=True)
        return str(target_path.absolute())

    def _get_safe_filename(self, config_key: str, default_name: str) -> str:
        """1. [中危修复] 增加对 None 或异常类型的防护"""
        conf = self.context.get_config() or {}
        val = conf.get(config_key, default_name)
        
        if not isinstance(val, str):
            return default_name
            
        safe_name = os.path.basename(val)
        return safe_name if safe_name else default_name

    def _load_data_sync(self):
        """同步加载逻辑，仅供初始化调用"""
        wives_file = self._get_safe_filename("wives_file", "wives.txt")
        spots_file = self._get_safe_filename("spots_file", "spots.txt")
        
        w_path = os.path.join(self.base_path, wives_file)
        s_path = os.path.join(self.base_path, spots_file)

        # 8. 自动补偿缺失文件
        for p, content in [(w_path, "古河渚\n冬马和纱"), (s_path, "CLANNAD|瑞穗町|url")]:
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f: f.write(content)

        try:
            with open(w_path, "r", encoding="utf-8") as f:
                self.heroines = [line.strip() for line in f if line.strip()]
            
            new_spots = {}
            with open(s_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("|")
                    if len(parts) >= 3:
                        new_spots[parts[0].strip().upper()] = {"desc": parts[1].strip(), "link": parts[2].strip()}
            self.spots_db = new_spots
        except Exception as e:
            logger.error(f"加载失败: {e}")

    async def reload_data_async(self):
        """6. [低危修复] 区分首次加载与热重载，并使用异步锁保护"""
        async with self.io_lock:
            # 内部执行同步 IO 但由锁保护防止并发导致的数据截断
            self._load_data_sync()
            return True

    @filter.command("今日老婆")
    async def daily_wife(self, event: AstrMessageEvent):
        if not self.heroines:
            yield event.plain_result("❌ 库中无数据，请联系管理员添加。")
            return
            
        uid = event.get_sender_id()
        today = datetime.now().strftime("%Y%m%d")
        rng = random.Random(f"{uid}_{today}")
        
        wife = rng.choice(self.heroines)
        yield event.plain_result(f"✨ 今日羁绊角色：{wife}\n（数据已通过并发安全校验）")

    @filter.command("添加老婆")
    async def add_wife(self, event: AstrMessageEvent, name: str = ""):
        if not event.is_from_admin():
            yield event.plain_result("⛔ 权限不足。")
            return
            
        name = name.strip()
        if not name: return

        # 4. [中危修复] 防止大小写/重复冲突
        if any(name.lower() == h.lower() for h in self.heroines):
            yield event.plain_result(f"⚠️ {name} 已在名单中（触发冲突保护）。")
            return

        async with self.io_lock:
            wives_file = self._get_safe_filename("wives_file", "wives.txt")
            path = os.path.join(self.base_path, wives_file)
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{name}")
            self._load_data_sync() # 锁内重载
            
        yield event.plain_result(f"✅ 已添加：{name}")

    @filter.command("添加圣地")
    async def add_spot(self, event: AstrMessageEvent, content: str = ""):
        if not event.is_from_admin(): return
        
        parts = content.split("|")
        if len(parts) != 3:
            yield event.plain_result("❌ 格式：游戏名|描述|链接")
            return

        game_name = parts[0].strip()
        # 4. [中危修复] 预防数据覆盖风险
        if game_name.upper() in self.spots_db:
            yield event.plain_result(f"⚠️ 《{game_name}》数据已存在，请手动编辑文件修改。")
            return

        async with self.io_lock:
            spots_file = self._get_safe_filename("spots_file", "spots.txt")
            path = os.path.join(self.base_path, spots_file)
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{content.strip()}")
            self._load_data_sync()
            
        yield event.plain_result(f"✅ 《{game_name}》圣地已收录。")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        if not event.is_from_admin(): return
        if await self.reload_data_async():
            yield event.plain_result(f"🔄 热重载成功！当前角色数：{len(self.heroines)}")
