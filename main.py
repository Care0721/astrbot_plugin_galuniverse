import random
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List

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
        self.io_lock: asyncio.Lock = asyncio.Lock()
        
        # 安全路径（动态计算）
        self.base_path: Path = self._get_safe_data_dir()
        
        self.heroines: List[str] = []
        self.spots_db: Dict[str, dict] = {}
        
        # 初始化加载
        self._load_data_sync()

    def _sanitize_text(self, text: str) -> str:
        """[安全修复] 清洗用户输入，防止 Data Injection"""
        if not isinstance(text, str):
            return ""
        # 移除所有换行符和控制字符
        return text.replace('\n', ' ').replace('\r', ' ').strip()

    def _get_safe_data_dir(self) -> Path:
        """[现代化修复] 动态获取数据目录 + 完整 pathlib 使用"""
        target_path: Path | None = None
        
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

        # 动态 fallback：使用插件实际文件夹名称（不再硬编码）
        if not target_path:
            plugin_folder_name = Path(__file__).resolve().parent.name
            target_path = (
                Path(__file__).resolve().parent.parent.parent
                / "data"
                / "plugins"
                / plugin_folder_name
            )
            
        target_path.mkdir(parents=True, exist_ok=True)
        return target_path

    def _get_safe_filename(self, config_key: str, default_name: str) -> str:
        """[现代化修复] 使用 pathlib 安全获取文件名"""
        conf = self.context.get_config() or {}
        val = conf.get(config_key, default_name)
        
        if not isinstance(val, str):
            return default_name
            
        safe_name = Path(val).name
        return safe_name if safe_name else default_name

    def _load_data_sync(self) -> None:
        """同步加载逻辑（初始化与热重载使用）"""
        wives_file = self._get_safe_filename("wives_file", "wives.txt")
        spots_file = self._get_safe_filename("spots_file", "spots.txt")
        
        w_path = self.base_path / wives_file
        s_path = self.base_path / spots_file

        # 自动补偿缺失文件
        for p, content in [(w_path, "古河渚\n冬马和纱"), (s_path, "CLANNAD|瑞穗町|url")]:
            if not p.exists():
                p.write_text(content, encoding="utf-8")

        try:
            self.heroines = [
                line.strip()
                for line in w_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            
            new_spots: Dict[str, dict] = {}
            for line in s_path.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split("|")
                if len(parts) >= 3:
                    new_spots[parts[0].strip().upper()] = {
                        "desc": parts[1].strip(),
                        "link": parts[2].strip()
                    }
            self.spots_db = new_spots
        except Exception as e:
            logger.error(f"加载数据失败: {e}")

    async def reload_data_async(self) -> bool:
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
            
        name = self._sanitize_text(name)
        if not name:
            yield event.plain_result("❌ 请输入有效的名称。")
            return

        if any(name.lower() == h.lower() for h in self.heroines):
            yield event.plain_result(f"⚠️ {name} 已在名单中（触发冲突保护）。")
            return

        # 锁内写文件 + 仅更新内存
        async with self.io_lock:
            wives_file = self._get_safe_filename("wives_file", "wives.txt")
            path = self.base_path / wives_file
            with path.open("a", encoding="utf-8") as f:
                f.write(f"\n{name}")
            self.heroines.append(name)
            
        yield event.plain_result(f"✅ 已添加：{name}")

    @filter.command("添加圣地")
    async def add_spot(self, event: AstrMessageEvent, content: str = ""):
        if not event.is_from_admin():
            yield event.plain_result("⛔ 权限不足。")
            return
        
        content = self._sanitize_text(content)
        if not content:
            yield event.plain_result("❌ 请输入有效的圣地信息。")
            return

        # 【关键修复】先检查分隔符数量，彻底防止 IndexError
        if content.count('|') != 2:
            yield event.plain_result("❌ 格式：游戏名|描述|链接")
            return

        parts = [p.strip() for p in content.split('|')]
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
            path = self.base_path / spots_file
            with path.open("a", encoding="utf-8") as f:
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