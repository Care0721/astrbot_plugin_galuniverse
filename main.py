import os
import random
from datetime import datetime
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 尝试安全导入 StarTools
try:
    from astrbot.api.star import StarTools
except ImportError:
    StarTools = None

@register("astrbot_plugin_universe", "Care", "超硬核 Galgame 沉浸式助手", "1.7.3")
class GalUniversePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 1. [高危修复] 数据持久化目录：使用动态防御与安全回退机制
        self.base_path = self._get_safe_data_dir()
        
        self.heroines = []
        self.spots_db = {}
        
        self.reload_data()

    def _get_safe_data_dir(self):
        """安全获取数据目录，完美兼容不同版本框架并防止返回对象本身"""
        dir_path = ""
        try:
            if StarTools and hasattr(StarTools, "get_data_dir"):
                try:
                    dir_path = str(StarTools.get_data_dir())
                except TypeError:
                    dir_path = str(StarTools.get_data_dir(self))
        except Exception as e:
            logger.warning(f"[GalUniverse] StarTools获取目录失败: {e}")
        
        # 终极兜底：如果获取失败或获取到了插件实例对象，则强制使用标准外置挂载目录
        if not dir_path or "GalUniversePlugin" in str(dir_path):
            dir_path = os.path.abspath(os.path.join(os.getcwd(), "data", "plugins", "astrbot_plugin_universe"))
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            
        return dir_path

    def _get_safe_filename(self, config_key, default_name):
        """2. [中危修复] 配置文件路径约束：切断所有可能导致越界读写的相对路径符号"""
        conf = self.context.get_config() or {}
        raw_name = conf.get(config_key, default_name)
        # 强制只提取文件名，丢弃诸如 ../../ 等攻击性前缀
        safe_name = os.path.basename(raw_name) 
        if not safe_name:
            safe_name = default_name
        return safe_name

    def reload_data(self):
        """3. & 8. [高/中危修复] 增加异常处理与基于动态配置的文件初始化"""
        wives_file = self._get_safe_filename("wives_file", "wives.txt")
        spots_file = self._get_safe_filename("spots_file", "spots.txt")
        
        w_path = os.path.join(self.base_path, wives_file)
        s_path = os.path.join(self.base_path, spots_file)
        
        # 8. [中危修复] 动态初始化配置指定的文件，而不是死板的默认名
        if not os.path.exists(w_path):
            try:
                with open(w_path, "w", encoding="utf-8") as f:
                    f.write("古河渚 (CLANNAD)\n冬马和纱 (白色相簿2)\n小木曾雪菜 (白色相簿2)")
            except Exception as e:
                logger.error(f"[GalUniverse] 创建女主列表文件失败: {e}")
                
        if not os.path.exists(s_path):
            try:
                with open(s_path, "w", encoding="utf-8") as f:
                    f.write("CLANNAD|东京都瑞穗町长冈(古河面包店)|https://zh.moegirl.org.cn/CLANNAD/圣地巡礼")
            except Exception as e:
                logger.error(f"[GalUniverse] 创建圣地文件失败: {e}")

        # 3. [高危修复] 读取操作完整套用异常捕获，避免插件崩溃导致系统启动失败
        try:
            with open(w_path, "r", encoding="utf-8") as f:
                self.heroines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"[GalUniverse] 读取 {wives_file} 失败，使用内存残留数据: {e}")
            if not hasattr(self, 'heroines'): self.heroines = []
            
        try:
            temp_db = {}
            with open(s_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "|" in line:
                        parts = line.strip().split("|")
                        if len(parts) >= 3:
                            temp_db[parts[0].strip().upper()] = {"desc": parts[1].strip(), "link": parts[2].strip()}
            self.spots_db = temp_db
        except Exception as e:
            logger.error(f"[GalUniverse] 读取 {spots_file} 失败: {e}")
            if not hasattr(self, 'spots_db'): self.spots_db = {}
                
        logger.info(f"GalUniverse 数据加载完毕：{len(self.heroines)} 位女主，{len(self.spots_db)} 个圣地。")

    @filter.command("今日老婆")
    async def daily_wife(self, event: AstrMessageEvent):
        if not self.heroines:
            yield event.plain_result("❌ 后宫名单为空，请先添加数据！")
            return
            
        uid = event.get_sender_id()
        today = datetime.now().strftime("%Y%m%d")
        
        rng = random.Random(f"{uid}_{today}")
        wife = rng.choice(self.heroines)
        fortunes = ["超大吉", "大吉", "中吉", "小吉", "末吉", "平", "凶"]
        
        yield event.plain_result(
            f"✨ --- 今日 Gal 运势 --- ✨\n"
            f"👤 羁绊角色：{wife}\n"
            f"🧧 签运等级：【{rng.choice(fortunes)}】\n"
            f"📝 建议：今天推个人线会有意想不到的展开！"
        )

    @filter.command("圣地巡礼")
    async def pilgrimage(self, event: AstrMessageEvent, game: str = ""):
        if not game or not game.strip():
            yield event.plain_result("💡 请输入游戏名。示例：/圣地巡礼 CLANNAD")
            return

        query = game.strip().upper()
        
        # 6. [中危修复] 消除首个命中歧义，优先【精确匹配】，再降级为【模糊匹配】
        match = None
        if query in self.spots_db:
            match = query
        else:
            match = next((k for k in self.spots_db if query in k), None)
        
        if match:
            data = self.spots_db[match]
            yield event.plain_result(f"🗺️ 《{match}》圣地情报：\n📍 地点：{data['desc']}\n🔗 链接：{data['link']}")
        else:
            yield event.plain_result(f"🔍 没找到关于《{game.strip()}》的记录。")

    @filter.command("添加老婆")
    async def add_wife(self, event: AstrMessageEvent, name: str = ""):
        # 4. [中危修复] 拒绝“静默退回”，明确反馈权限问题
        if not event.is_from_admin():
            yield event.plain_result("⛔ 权限拒绝：仅限管理员可执行此操作。")
            return
        
        # 7. [低危修复] 输入校验不足：防空与防重
        name = name.strip()
        if not name:
            yield event.plain_result("❌ 名字不能为空。")
            return
            
        if name in self.heroines:
            yield event.plain_result(f"⚠️ {name} 已经在后宫名单里了！")
            return
            
        wives_file = self._get_safe_filename("wives_file", "wives.txt")
        path = os.path.join(self.base_path, wives_file)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{name}")
            self.reload_data()
            yield event.plain_result(f"✅ 已加入后宫名单：{name}")
        except Exception as e:
            logger.error(f"[GalUniverse] 写入老婆数据失败: {e}")
            yield event.plain_result("❌ 写入文件失败，请查看后台日志。")

    @filter.command("添加圣地")
    async def add_spot(self, event: AstrMessageEvent, content: str = ""):
        if not event.is_from_admin():
            yield event.plain_result("⛔ 权限拒绝：仅限管理员可执行此操作。")
            return
        
        content = content.strip()
        if not content:
            yield event.plain_result("❌ 内容不能为空。")
            return
            
        parts = content.split("|")
        if len(parts) != 3 or not parts[0].strip() or not parts[1].strip() or not parts[2].strip():
            yield event.plain_result("❌ 格式错误！请使用：游戏名|描述|链接 (且各项均不能为空)")
            return

        spots_file = self._get_safe_filename("spots_file", "spots.txt")
        path = os.path.join(self.base_path, spots_file)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n{content}")
            self.reload_data()
            yield event.plain_result("✅ 圣地数据收录成功！")
        except Exception as e:
            logger.error(f"[GalUniverse] 写入圣地数据失败: {e}")
            yield event.plain_result("❌ 写入文件失败，请查看后台日志。")

    @filter.command("重载Gal数据")
    async def reload_cmd(self, event: AstrMessageEvent):
        # 5. [中危修复] 重载鉴权缺失，防止恶意调用压垮 I/O
        if not event.is_from_admin():
            yield event.plain_result("⛔ 权限拒绝：仅限管理员可重载数据。")
            return
            
        self.reload_data()
        yield event.plain_result("🔄 数据已完成热重载！")
