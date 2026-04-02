import random
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = self.context.get_config()
        self.reload_data()

    def reload_data(self):
        """重新加载配置数据"""
        self.heroines = self.config.get("heroines", ["古河渚 (CLANNAD)"])
        
        spots_list = self.config.get("spots", [])
        self.spots = {}
        for item in spots_list:
            if isinstance(item, dict) and "name" in item:
                name = str(item.get("name", "")).strip()
                if name:
                    key = name.upper()
                    self.spots[key] = {
                        "desc": item.get("desc", "暂无描述"),
                        "link": item.get("link", "暂无链接")
                    }
        
        self.fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶", "大凶"]

    @filter.command("今日老婆")
    async def daily_wife(self, event: AstrMessageEvent):
        if not self.config.get("enable_fortunes", True):
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
        if not game_name:
            yield event.plain_result("请输入游戏名，例如：/圣地巡礼 魔法使之夜")
            return

        query = game_name.strip().upper()
        
        # 加强匹配：完全匹配 或 包含匹配
        matched_key = None
        for k in self.spots:
            if query == k or query in k or k in query:
                matched_key = k
                break

        if matched_key:
            info = self.spots[matched_key]
            res = (
                f"🗺️ 《{matched_key}》圣地情报：\n"
                f"📍 地点：{info['desc']}\n"
                f"🔗 详情：{info.get('link', '暂无链接')}"
            )
            yield event.plain_result(res)
        else:
            yield event.plain_result(f"暂未收录《{game_name}》。\n提示：请检查网页配置中是否正确添加了该游戏名，并执行 /重载Gal数据")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        self.config = self.context.get_config()
        self.reload_data()
        count = len(self.spots)
        yield event.plain_result(f"✅ Galgame 数据已重新加载！\n当前收录老婆：{len(self.heroines)} 个\n当前收录圣地：{count} 个")