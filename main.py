import random
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 强制每次都从最新 config 读取
        self.config = self.context.get_config()
        self.reload_data()

    def reload_data(self):
        """重新加载所有数据 - 加强容错"""
        # 老婆列表
        self.heroines = self.config.get("heroines", ["古河渚 (CLANNAD)"])
        if not isinstance(self.heroines, list):
            self.heroines = ["古河渚 (CLANNAD)"]

        # 圣地巡礼 - 加强解析，兼容可能缺少 __template_key 的情况
        spots_list = self.config.get("spots", [])
        self.spots = {}
        valid_count = 0
        for item in spots_list:
            if isinstance(item, dict) and "name" in item:
                name = str(item.get("name", "")).strip()
                if name:
                    key = name.upper()
                    self.spots[key] = {
                        "desc": item.get("desc", "暂无描述"),
                        "link": item.get("link", "")
                    }
                    valid_count += 1

        self.fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶", "大凶"]

        # 调试信息（可选，后面可删）
        print(f"[GalPlugin] 加载完成 - 老婆: {len(self.heroines)} 个, 有效圣地: {valid_count} 个")

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
        
        res = f"✨ --- 今日 Gal 运势 --- ✨\n👤 角色：{wife}\n🧧 签运：【{fortune}】\n📝 建议：今天和这位角色相处会有意想不到的惊喜哦！"
        yield event.plain_result(res)

    @filter.command("圣地巡礼")
    async def pilgrimage(self, event: AstrMessageEvent, game_name: str = None):
        if not game_name:
            yield event.plain_result("请输入游戏名，例如：/圣地巡礼 魔法使之夜")
            return

        query = game_name.strip().upper()
        matched_key = next((k for k in self.spots if query == k or query in k or k in query), None)

        if matched_key:
            info = self.spots[matched_key]
            res = f"🗺️ 《{matched_key}》圣地情报：\n📍 地点：{info['desc']}\n🔗 详情：{info.get('link', '暂无')}"
            yield event.plain_result(res)
        else:
            yield event.plain_result(f"暂未收录《{game_name}》。\n当前共收录 {len(self.spots)} 个圣地")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        self.config = self.context.get_config()   # 强制刷新
        self.reload_data()
        yield event.plain_result(
            f"✅ Galgame 数据已重新加载！\n"
            f"当前收录老婆：{len(self.heroines)} 个\n"
            f"当前收录圣地：{len(self.spots)} 个"
        )