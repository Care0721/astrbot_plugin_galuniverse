import random
import os
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.all import Config

@register("gal_universe_pro", "YourName", "Galgame 沉浸式助手网页配置版", "1.3.0")
class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.base_path = os.path.dirname(__file__)
        
        # --- 网页端配置项定义 ---
        # 这里的 key 对应网页上的输入框
        self.config_data = self.context.get_config()
        self.wives_file_name = self.config_data.get("wives_file", "wives.txt")
        self.spots_file_name = self.config_data.get("spots_file", "spots.txt")
        self.enable_fortunes = self.config_data.get("enable_fortunes", True)

        # 加载数据
        self.reload_data()

    def reload_data(self):
        """加载或重载 TXT 数据"""
        wives_path = os.path.join(self.base_path, self.wives_file_name)
        spots_path = os.path.join(self.base_path, self.spots_file_name)
        
        self.heroines = self._read_lines(wives_path, ["古河渚 (CLANNAD)"])
        self.spots = self._parse_spots(spots_path)
        self.fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶", "大凶"]

    def _read_lines(self, path, default):
        if not os.path.exists(path): return default
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f.readlines() if line.strip()]

    def _parse_spots(self, path):
        data = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if "|" in line:
                        parts = line.strip().split("|")
                        if len(parts) == 3:
                            name, desc, link = parts
                            data[name.upper()] = {"desc": desc, "link": link}
        return data

    @filter.command("今日老婆")
    async def daily_wife(self, event: AstrMessageEvent):
        """每日固定运势抽卡"""
        if not self.config_data.get("enable_fortunes", True):
            yield event.plain_result("❌ 该功能已被管理员禁用。")
            return

        user_id = event.get_sender_id()
        today = datetime.now().strftime("%Y%m%d")
        random.seed(f"{user_id}_{today}")
        
        wife = random.choice(self.heroines)
        fortune = random.choice(self.fortunes)
        
        res = (
            f"✨ --- 今日 Gal 运势 --- ✨\n"
            f"👤 角色：{wife}\n"
            f"🧧 签运：【{fortune}】\n"
            f"📝 建议：今天和这位角色相处会有意想不到的惊喜哦！"
        )
        yield event.plain_result(res)

    @filter.command("圣地巡礼")
    async def pilgrimage(self, event: AstrMessageEvent, game_name: str = None):
        """查询巡礼地点"""
        if not game_name:
            yield event.plain_result("请输入游戏名，如：/圣地巡礼 CLANNAD")
            return

        query = game_name.upper()
        matched_key = next((k for k in self.spots if query in k), None)
        
        if matched_key:
            info = self.spots[matched_key]
            res = (
                f"🗺️ 《{matched_key}》圣地情报：\n"
                f"📍 地点：{info['desc']}\n"
                f"🔗 详情：{info['link']}"
            )
            yield event.plain_result(res)
        else:
            yield event.plain_result(f"暂未收录《{game_name}》。")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        """如果你手动改了TXT，执行这个命令刷新内存"""
        self.reload_data()
        yield event.plain_result("✅ Galgame 数据库已重新加载！")
