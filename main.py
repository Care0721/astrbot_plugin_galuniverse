import random
import os
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger # 1. 使用官方 logger

@register("astrbot_plugin_universe", "Care", "如果在梦里能相遇的话，那大概就是现实", "1.8.0")
class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 2. 修复路径：使用 StarTools 获取持久化数据目录
        self.base_path = StarTools.get_data_dir(self)
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)

        # 3. 修复配置加载：增加空值保护
        self.conf = self.context.get_config() or {}

        self._ensure_files_exist()
        self.reload_data()

    def _ensure_files_exist(self):
        """初始化数据文件"""
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
        """重载数据"""
        self.conf = self.context.get_config() or {}
        wives_file = self.conf.get("wives_file", "wives.txt")
        spots_file = self.conf.get("spots_file", "spots.txt")

        w_path = os.path.join(self.base_path, wives_file)
        with open(w_path, "r", encoding="utf-8") as f:
            self.heroines = [line.strip() for line in f if line.strip()]

        s_path = os.path.join(self.base_path, spots_file)
        self.spots_db = {}
        with open(s_path, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    parts = line.strip().split("|")
                    if len(parts) >= 3:
                        self.spots_db[parts[0].strip().upper()] = {"desc": parts[1].strip(), "link": parts[2].strip()}
        logger.info(f"GalUniverse 数据加载完毕：{len(self.heroines)} 位女主，{len(self.spots_db)} 个圣地。")

    @filter.command("今日老婆")
    async def daily_wife(self, event: AstrMessageEvent):
        uid = event.get_sender_id()
        today = datetime.now().strftime("%Y%m%d")

        # 4. 修复随机污染：使用局部 Random 实例
        rng = random.Random(f"{uid}_{today}")

        wife = rng.choice(self.heroines)
        fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶"]

        # 新增：100条随机的 Gal 运势建议（每天根据 uid + 日期固定抽取一条）
        suggestions = [
            "今天推个人线会有意想不到的展开！",
            "多和女主互动，好感度直线上升！",
            "记得存档，关键时刻不后悔！",
            "今天约会运超强，浪漫满分！",
            "注意选项细节，解锁隐藏好感！",
            "推线时多读剧情，情感更深刻！",
            "今天运气大吉，CG 轻松入手！",
            "和老婆一起散步，羁绊加倍！",
            "别急着快进，对话藏惊喜！",
            "适合推支线，额外剧情丰富！",
            "今天主线大爆发，真爱结局近在眼前！",
            "频繁存档，避开悲剧 END！",
            "女主今天特别温柔，好感爆表！",
            "探索新场景，圣地巡礼开启！",
            "多送礼物，女主开心指数 +100！",
            "今天适合听 BGM，沉浸式推线！",
            "隐藏路线今天容易触发！",
            "推姐妹线会有甜蜜互动！",
            "注意女主生日，准备惊喜！",
            "今天 Gal 世界充满可能！",
            "存档后大胆选选项，勇敢无畏！",
            "和女主共进晚餐，氛围完美！",
            "今天推个人线，剧情反转精彩！",
            "收集全 CG，成就解锁！",
            "多聊天，了解女主内心！",
            "今天运势平平，但努力就有收获！",
            "推荐读原作小说，增强代入感！",
            "女主好感在小动作中体现！",
            "今天适合重温经典场景！",
            "推线别忘了喝水，保持精力！",
            "隐藏彩蛋今天高概率出现！",
            "和老婆一起玩游戏，乐趣加倍！",
            "注意时间管理，剧情推进顺畅！",
            "今天大吉，BAD END 远离！",
            "多关注对话选项的暗示！",
            "适合推后宫线，热闹非凡！",
            "女主今天想被宠爱！",
            "存档点选好，安全第一！",
            "今天推线会有温暖结局！",
            "探索世界观，故事更完整！",
            "好感度提升秘诀：真诚互动！",
            "今天推荐看 OP/ED，燃起热情！",
            "推线时记录关键选择！",
            "和女主约会地点选对！",
            "今天运气爆棚，一切顺利！",
            "别忽略支线剧情，丰富体验！",
            "女主内心独白是关键！",
            "今天适合刷成就！",
            "推个人线，感情线升温！",
            "多存多个档位，灵活切换！",
            "今天 Gal 运中吉，努力推线！",
            "注意声音演出，沉浸感强！",
            "和老婆分享日常，羁绊深！",
            "隐藏选项今天可见！",
            "推线别太快，享受过程！",
            "今天推荐多看立绘！",
            "好感事件触发概率高！",
            "适合去圣地巡礼现实中！",
            "女主今天超级可爱！",
            "剧情高潮即将到来！",
            "存档习惯养成，避免遗憾！",
            "今天推线会有感动时刻！",
            "多和 NPC 对话，世界丰富！",
            "注意季节变化，剧情随时间！",
            "今天大吉大利，结局完美！",
            "推荐推真爱路线！",
            "女主好感满值指日可待！",
            "今天适合重玩旧档！",
            "互动多多，CG 解锁快！",
            "推线时关灯，氛围感强！",
            "今天运势小吉，稳步前进！",
            "注意剧透避免，纯净体验！",
            "和女主一起旅行吧！",
            "隐藏 END 今天可解！",
            "多读系统提示，线索多！",
            "今天 Gal 世界在召唤你！",
            "推个人线，幸福满满！",
            "存档后勇敢尝试不同选择！",
            "女主今天有特殊事件！",
            "适合听 OST 推线！",
            "今天中吉，平衡发展！",
            "注意好感度条的变化！",
            "和老婆互诉心事！",
            "今天推荐探索地图！",
            "剧情推进有惊喜！",
            "多收集道具，提升属性！",
            "女主视线有深意！",
            "今天适合完成 side story！",
            "推线别忘记笑！",
            "运气平，靠努力取胜！",
            "今天有幸运抽奖感！",
            "注意选项颜色暗示！",
            "和女主共度节日！",
            "隐藏对话今天开放！",
            "推线过程开心最重要！",
            "今天 Gal 运末吉，小心谨慎！",
            "多备份存档！",
            "女主等待你的选择！",
            "今天推线会有永恒回忆！",
            "勇敢推线，梦想成真！"
        ]

        res = (
            f"✨ --- 今日 Gal 运势 --- ✨\n"
            f"👤 羁绊角色：{wife}\n"
            f"🧧 签运等级：【{rng.choice(fortunes)}】\n"
            f"📝 建议：{rng.choice(suggestions)}"
        )
        yield event.plain_result(res)

    @filter.command("圣地巡礼")
    async def pilgrimage(self, event: AstrMessageEvent, game: str = None):
        # 5. 修复输入校验：去掉空格
        if not game or not game.strip():
            yield event.plain_result("💡 请输入游戏名。示例：/圣地巡礼 CLANNAD")
            return

        query = game.strip().upper()
        match = next((k for k in self.spots_db if query in k), None)

        if match:
            data = self.spots_db[match]
            yield event.plain_result(f"🗺️ 《{match}》圣地情报：\n📍 地点：{data['desc']}\n🔗 链接：{data['link']}")
        else:
            yield event.plain_result(f"🔍 没找到关于《{game.strip()}》的记录。")

    @filter.command("添加老婆")
    async def add_wife(self, event: AstrMessageEvent, name: str):
        if not event.is_from_admin(): return

        name = name.strip()
        wives_file = self.conf.get("wives_file", "wives.txt")
        path = os.path.join(self.base_path, wives_file)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n{name}")

        self.reload_data()
        yield event.plain_result(f"✅ 已加入后宫名单：{name}")

    @filter.command("添加圣地")
    async def add_spot(self, event: AstrMessageEvent, content: str):
        if not event.is_from_admin(): return

        # 6. 修复逻辑漏洞：严格校验三段式格式
        parts = content.split("|")
        if len(parts) != 3:
            yield event.plain_result("❌ 格式错误！请使用：游戏名|描述|链接")
            return

        spots_file = self.conf.get("spots_file", "spots.txt")
        path = os.path.join(self.base_path, spots_file)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n{content.strip()}")

        self.reload_data()
        yield event.plain_result("✅ 圣地数据收录成功！")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        self.reload_data()
        yield event.plain_result("🔄 数据已完成热重载！")