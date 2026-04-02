import random
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.reload_data()   # 启动时立即加载

    def reload_data(self):
        """强制从最新 config 读取数据"""
        config = self.context.get_config()   # 每次都重新获取最新配置
        
        # 老婆列表
        self.heroines = config.get("heroines", ["古河渚 (CLANNAD)"])
        if not isinstance(self.heroines, list) or len(self.heroines) == 0:
            self.heroines = ["古河渚 (CLANNAD)"]

        # 圣地巡礼列表 - 加强解析容错
        spots_list = config.get("spots", [])
        self.spots = {}
        for item in spots_list:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                name = item["name"].strip()
                if name:
                    key = name.upper()
                    self.spots[key] = {
                        "desc": item.get("desc", "暂无描述"),
                        "link": item.get("link", "")
                    }

        self.fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶", "大凶"]

    @filter.command("今日老婆")
    async def daily_wife(self, event: AstrMessageEvent):
        if not self.context.get_config().get("enable_fortunes", True):
            yield event.plain_result("❌ 该功能已被管理员禁用。")
            return

        user_id = event.get_sender_id()
        today = datetime.now().strftime("%Y%m%d")
        random.seed(f"{user_id}_{today}")
        
        wife = random.choice(self.heroines)
        fortune = random.choice(self.fortunes)
        
        res = f"✨ --- 今日 Gal 运势 --- ✨\n👤 角色：{wife}\n🧧 签运：【{fortune}】\n📝 建议：今天和这位角色相处会有意想不到的惊喜哦！"
        yield event.plain_result(res)

    @filter.command("圣地巡礼")
    async def pilgrimage(self, event: AstrMessageEvent, game_name: str = None):
        if not game_name:
            yield event.plain_result("请输入游戏名，例如：/圣地巡礼 魔法使之夜")
            return

        query = game_name.strip().upper()
        # 更宽松的匹配
        matched = next((k for k in self.spots if query == k or query in k or k in query), None)

        if matched:
            info = self.spots[matched]
            res = f"🗺️ 《{matched}》圣地情报：\n📍 地点：{info['desc']}\n🔗 详情：{info.get('link', '暂无链接')}"
            yield event.plain_result(res)
        else:
            yield event.plain_result(f"暂未收录《{game_name}》。\n当前共收录 {len(self.spots)} 个圣地")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        self.reload_data()
        yield event.plain_result(
            f"✅ Galgame 数据已重新加载！\n"
            f"当前收录老婆：{len(self.heroines)} 个\n"
            f"当前收录圣地：{len(self.spots)} 个"
        )