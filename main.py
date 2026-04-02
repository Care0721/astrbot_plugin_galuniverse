import random
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 加载网页端配置（所有功能数据现在都可通过网页直接修改）
        self.config_data = self.context.get_config()
        
        # 加载数据
        self.reload_data()

    def reload_data(self):
        """从网页配置中重新加载所有功能数据"""
        # 老婆列表（数组，可在网页添加/删除/修改角色）
        self.heroines = self.config_data.get("heroines", ["古河渚 (CLANNAD)"])
        
        # 圣地巡礼数据（数组，每项为一个对象，可在网页添加/删除/修改）
        spots_list = self.config_data.get("spots", [])
        self.spots = {}
        for item in spots_list:
            if isinstance(item, dict) and "name" in item:
                name = str(item["name"]).upper().strip()
                if name:
                    self.spots[name] = {
                        "desc": item.get("desc", ""),
                        "link": item.get("link", "")
                    }
        
        # 签运列表（固定）
        self.fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶", "大凶"]

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
        """从网页配置重新加载所有数据（修改配置后执行此命令立即生效）"""
        self.config_data = self.context.get_config()
        self.reload_data()
        yield event.plain_result("✅ Galgame 所有功能数据已从网页配置重新加载！")


# ====================== 网页端配置文件 ======================
# 请在插件目录新建文件：_conf_schema.json
# 内容如下（复制粘贴即可）：