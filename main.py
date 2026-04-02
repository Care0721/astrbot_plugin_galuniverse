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


@register("astrbot_plugin_universe", "Care", "如果在梦里能相遇的话，那大概就是现实", "1.8.0")
class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 并发安全：异步锁
        self.io_lock = asyncio.Lock()
        
        # 安全路径
        self.base_path = self._get_safe_data_dir()
        
        self.heroines: List[str] = []
        self.spots_db: Dict[str, dict] = {}
        
        # 初始化加载
        self._load_data_sync()

    def _sanitize_text(self, text: str) -> str:
        """[安全修复] 清洗用户输入，防止 Data Injection（评审重点）"""
        if not isinstance(text, str):
            return ""
        # 移除换行符，防止注入多行数据
        return text.replace('\n', ' ').replace('\r', ' ').strip()

    def _get_safe_data_dir(self) -> str:
        """[低危修复] 安全路径获取 + 异常日志记录（不再吞噬异常）"""
        target_path = None
        
        if StarTools and hasattr(StarTools, "get_data_dir"):
            try:
                res = StarTools.get_data_dir()
                if isinstance(res, (str, Path)) and "GalUniversePlugin" not in str(res):
                    target_path = Path(res)
            except Exception as e:
                logger.warning(f"StarTools.get_data_dir() 调用失败: {e}")
                try:
                    res = StarTools.get_data_dir(self)
                    if isinstance(res, (str, Path)) and "GalUniversePlugin" not in str(res):
                        target_path = Path(res)
                except Exception as e2:
                    logger.warning(f"StarTools.get_data_dir(self) 调用失败: {e2}")

        # Fallback：插件同级 data 目录
        if not target_path:
            target_path = Path(__file__).parent.parent.parent / "data" / "plugins" / "astrbot_plugin_universe"
            
        target_path.mkdir(parents=True, exist_ok=True)
        return str(target_path.absolute())

    def _get_safe_filename(self, config_key: str, default_name: str) -> str:
        """[中危修复] 配置文件名安全处理"""
        conf = self.context.get_config() or {}
        val = conf.get(config_key, default_name)
        
        if not isinstance(val, str):
            return default_name
            
        safe_name = os.path.basename(val)
        return safe_name if safe_name else default_name

    def _load_data_sync(self):
        """同步加载逻辑（仅初始化和热重载使用）"""
        wives_file = self._get_safe_filename("wives_file", "wives.txt")
        spots_file = self._get_safe_filename("spots_file", "spots.txt")
        
        w_path = os.path.join(self.base_path, wives_file)
        s_path = os.path.join(self.base_path, spots_file)

        # 自动补偿缺失文件
        for p, content in [(w_path, "古河渚\n冬马和纱"), (s_path, "CLANNAD|瑞穗町|url")]:
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(content)

        try:
            with open(w_path, "r", encoding="utf-8") as f:
                self.heroines = [line.strip() for line in f if line.strip()]
            
            new_spots = {}
            with open(s_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("|")
                    if len(parts) >= 3:
                        new_spots[parts[0].strip().upper()] = {
                            "desc": parts[1].strip(),
                            "link": parts[2].strip()
                        }
            self.spots_db = new_spots
        except Exception as e:
            logger.error(f"加载数据失败: {e}")

    async def reload_data_async(self):
        """[低危修复] 热重载使用锁保护"""
        async with self.io_lock:
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
        yield event.plain_result(f"✨ 今日羁绊角色：{wife}")

    @filter.command("添加老婆")
    async def add_wife(self, event: AstrMessageEvent, name: str = ""):
        if not event.is_from_admin():
            yield event.plain_result("⛔ 权限不足。")
            return
            
        # 【重要】清洗输入 + 立即响应空名称
        name = self._sanitize_text(name)
        if not name:
            yield event.plain_result("❌ 请输入有效的名称。")
            return

        # 重复检查（大小写不敏感）
        if any(name.lower() == h.lower() for h in self.heroines):
            yield event.plain_result(f"⚠️ {name} 已在名单中（触发冲突保护）。")
            return

        # 锁内写文件 + 仅更新内存（不再全量 reload）
        async with self.io_lock:
            wives_file = self._get_safe_filename("wives_file", "wives.txt")
            path = os.path.join(self.base_path, wives_file)
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{name}")
            self.heroines.append(name)   # 内存直接追加
            
        yield event.plain_result(f"✅ 已添加：{name}")

    @filter.command("添加圣地")
    async def add_spot(self, event: AstrMessageEvent, content: str = ""):
        if not event.is_from_admin():
            yield event.plain_result("⛔ 权限不足。")
            return
        
        # 【重要】清洗输入 + 立即响应
        content = self._sanitize_text(content)
        if not content:
            yield event.plain_result("❌ 请输入有效的圣地信息。")
            return

        parts = [p.strip() for p in content.split("|")]
        if len(parts) != 3:
            yield event.plain_result("❌ 格式：游戏名|描述|链接")
            return

        game_name, desc, link = parts
        if not game_name or not desc or not link:
            yield event.plain_result("❌ 格式不完整，请提供游戏名、描述和链接。")
            return

        if game_name.upper() in self.spots_db:
            yield event.plain_result(f"⚠️ 《{game_name}》数据已存在，请手动编辑文件修改。")
            return

        # 锁内写文件 + 仅更新内存
        async with self.io_lock:
            spots_file = self._get_safe_filename("spots_file", "spots.txt")
            path = os.path.join(self.base_path, spots_file)
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{game_name}|{desc}|{link}")
            self.spots_db[game_name.upper()] = {"desc": desc, "link": link}
            
        yield event.plain_result(f"✅ 《{game_name}》圣地已收录。")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        if not event.is_from_admin():
            yield event.plain_result("⛔ 权限不足。")
            return
        if await self.reload_data_async():
            yield event.plain_result(f"🔄 热重载成功！当前角色数：{len(self.heroines)}")