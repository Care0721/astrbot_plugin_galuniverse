import random
import json
import os
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.base_path = os.path.dirname(__file__)
        
        # 新增：两个持久化备份文件（专门存放网页端配置的数据）
        self.data_dir = os.path.join("data", "plugins_data", "gal_universe_pro")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.web_heroines_file = os.path.join(self.data_dir, "web_heroines.json")
        self.web_spots_file = os.path.join(self.data_dir, "web_spots.json")
        
        self.reload_data()

    def reload_data(self):
        """优先从网页配置加载 + 自动备份到两个JSON文件"""
        config = self.context.get_config()
        
        # 1. 从网页端加载老婆列表
        self.heroines = config.get("heroines", ["古河渚 (CLANNAD)"])
        if not isinstance(self.heroines, list) or len(self.heroines) == 0:
            self.heroines = ["古河渚 (CLANNAD)"]
        
        # 2. 从网页端加载圣地巡礼（兼容 template_list）
        spots_list = config.get("spots", [])
        self.spots = {}
        for item in spots_list:
            if isinstance(item, dict) and "name" in item:
                name = str(item.get("name", "")).strip()
                if name:
                    key = name.upper()
                    self.spots[key] = {
                        "desc": item.get("desc", "暂无描述"),
                        "link": item.get("link", "")
                    }
        
        # 3. 自动把当前网页数据备份到两个JSON文件
        self._save_web_backup()
        
        self.fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶", "大凶"]

    def _save_web_backup(self):
        """把网页配置的数据保存到两个独立JSON文件"""
        # 保存老婆列表
        with open(self.web_heroines_file, "w", encoding="utf-8") as f:
            json.dump(self.heroines, f, ensure_ascii=False, indent=2)
        
        # 保存圣地巡礼（带 __template_key 结构，方便以后恢复）
        spots_list = []
        for key, info in self.spots.items():
            spots_list.append({
                "__template_key": "spot",
                "name": key,
                "desc": info["desc"],
                "link": info["link"]
            })
        with open(self.web_spots_file, "w", encoding="utf-8") as f:
            json.dump(spots_list, f, ensure_ascii=False, indent=2)

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
        matched_key = next((k for k in self.spots if query == k or query in k or k in query), None)

        if matched_key:
            info = self.spots[matched_key]
            res = f"🗺️ 《{matched_key}》圣地情报：\n📍 地点：{info['desc']}\n🔗 详情：{info.get('link', '暂无链接')}"
            yield event.plain_result(res)
        else:
            yield event.plain_result(f"暂未收录《{game_name}》。\n当前共收录圣地：{len(self.spots)} 个")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        self.reload_data()
        yield event.plain_result(
            f"✅ 数据已从网页配置重新加载并备份！\n"
            f"当前老婆：{len(self.heroines)} 个\n"
            f"当前圣地：{len(self.spots)} 个\n"
            f"备份文件已生成在：data/plugins_data/gal_universe_pro/"
        )