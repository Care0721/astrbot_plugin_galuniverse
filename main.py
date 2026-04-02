import random
import os
import logging
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

@register("gal_universe_pro", "Developer", "Galgame 沉浸式助手增强版", "1.4.0")
class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.base_path = os.path.dirname(__file__)
        self.logger = logging.getLogger("astrbot")
        
        # 默认配置初始化
        self._ensure_files_exist()
        self.reload_data()

    def _ensure_files_exist(self):
        """检查并初始化数据文件"""
        files = {
            "wives.txt": "古河渚 (CLANNAD)\n冬马和纱 (白色相簿2)\n小木曾雪菜 (白色相簿2)",
            "spots.txt": "CLANNAD|东京都瑞穗町长冈(古河面包店)|https://zh.moegirl.org.cn/CLANNAD/圣地巡礼"
        }
        for name, content in files.items():
            path = os.path.join(self.base_path, name)
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

    def reload_data(self):
        """从网页配置或本地文件加载数据"""
        conf = self.context.get_config()
        self.wives_file = conf.get("wives_file", "wives.txt")
        self.spots_file = conf.get("spots_file", "spots.txt")
        
        # 加载女主列表
        w_path = os.path.join(self.base_path, self.wives_file)
        with open(w_path, "r", encoding="utf-8") as f:
            self.heroines = [line.strip() for line in f if line.strip()]
            
        # 加载圣地数据
        s_path = os.path.join(self.base_path, self.spots_file)
        self.spots_db = {}
        with open(s_path, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    parts = line.strip().split("|")
                    if len(parts) >= 3:
                        self.spots_db[parts[0].upper()] = {"desc": parts[1], "link": parts[2]}

    @filter.command("今日老婆")
    async def daily_wife(self, event: AstrMessageEvent):
        """获取每日专属 Galgame 运势"""
        uid = event.get_sender_id()
        today = datetime.now().strftime("%Y%m%d")
        
        # 使用 UID 和日期锁定每日结果
        random.seed(f"{uid}_{today}")
        
        wife = random.choice(self.heroines)
        fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶"]
        colors = ["樱花粉", "纯净白", "薄荷绿", "深海蓝", "夕阳橘", "星空紫"]
        tips = [
            "今天推个人线会有意想不到的展开！",
            "适合去圣地巡礼，呼吸二次元的空气。",
            "小心坏档，记得多存几个存档位。",
            "今日宜表白，成功率提升 50%！"
        ]

        res = (
            f"✨ --- 今日 Gal 运势 --- ✨\n"
            f"👤 羁绊角色：{wife}\n"
            f"🧧 签运等级：【{random.choice(fortunes)}】\n"
            f"🎨 幸运色彩：{random.choice(colors)}\n"
            f"📝 寄语：{random.choice(tips)}"
        )
        yield event.plain_result(res)

    @filter.command("圣地巡礼")
    async def pilgrimage(self, event: AstrMessageEvent, game: str = None):
        """查询圣地坐标"""
        if not game:
            yield event.plain_result("💡 请输入游戏名。示例：/圣地巡礼 CLANNAD")
            return

        query = game.upper()
        # 模糊匹配
        match = next((k for k in self.spots_db if query in k), None)
        
        if match:
            data = self.spots_db[match]
            yield event.plain_result(f"🗺️ 《{match}》圣地情报：\n📍 地点：{data['desc']}\n🔗 链接：{data['link']}")
        else:
            yield event.plain_result(f"🔍 没找到《{game}》的记录。你可以尝试更短的关键词。")

    @filter.command("添加老婆")
    async def add_wife(self, event: AstrMessageEvent, name: str):
        """(管理员) 动态添加女主"""
        if not event.is_from_admin(): return # 权限检查
        
        path = os.path.join(self.base_path, self.wives_file)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n{name}")
        
        self.reload_data()
        yield event.plain_result(f"✅ 已成功将【{name}】加入后宫名单！")

    @filter.command("添加圣地")
    async def add_spot(self, event: AstrMessageEvent, content: str):
        """(管理员) 格式：游戏名|描述|链接"""
        if not event.is_from_admin(): return
        
        if "|" not in content:
            yield event.plain_result("❌ 格式错误！请使用：游戏名|描述|链接")
            return

        path = os.path.join(self.base_path, self.spots_file)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n{content}")
        
        self.reload_data()
        yield event.plain_result("✅ 圣地坐标已收录！")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        """强制同步网页配置与本地文件"""
        self.reload_data()
        yield event.plain_result("🔄 数据已完成热重载！")
