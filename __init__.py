from pkg.plugin.context import BasePlugin, register, handler
from pkg.plugin.events import GroupMessageReceived
from pkg.provider.tools import entities as tools_entities
import json
import random
import asyncio
from datetime import datetime

@register(
    name="群组BOSS战斗",
    description="让群友一起对战AI驱动的BOSS",
    version="1.0.0",
    author="AI Assistant"
)
class GroupBossBattle(BasePlugin):
    def __init__(self, host):
        super().__init__(host)
        self.bosses = {}  # 存储各个群的BOSS状态
        self.players = {}  # 存储玩家状态
        self.battle_cooldown = {}  # 战斗冷却时间
        
    async def initialize(self):
        """初始化插件"""
        self.ap.logger.info("群组BOSS战斗插件已启动")
    
    def create_boss(self, group_id):
        """创建一个新的BOSS"""
        boss_types = [
            {"name": "混沌巨龙", "hp": 1000, "attack": 50, "defense": 30},
            {"name": "深渊魔王", "hp": 800, "attack": 70, "defense": 20},
            {"name": "远古泰坦", "hp": 1200, "attack": 40, "defense": 40}
        ]
        boss = random.choice(boss_types)
        self.bosses[group_id] = {
            "name": boss["name"],
            "hp": boss["hp"],
            "max_hp": boss["hp"],
            "attack": boss["attack"],
            "defense": boss["defense"],
            "status": "alive",
            "last_words": "",
            "personality": self.generate_boss_personality()
        }
        return self.bosses[group_id]
    
    def generate_boss_personality(self):
        """生成BOSS的性格特征"""
        personalities = [
            "傲慢自大，看不起人类",
            "冷酷无情，沉默寡言",
            "狂暴嗜血，热衷战斗",
            "智慧深沉，喜欢玩弄对手",
            "古老神秘，充满智慧"
        ]
        return random.choice(personalities)
    
    def get_player_stats(self, user_id):
        """获取玩家状态"""
        if user_id not in self.players:
            self.players[user_id] = {
                "hp": 100,
                "attack": 20,
                "defense": 10,
                "exp": 0,
                "level": 1
            }
        return self.players[user_id]
    
    @handler(GroupMessageReceived)
    async def on_group_message(self, ctx):
        """处理群消息"""
        message = ctx.event.message.content
        group_id = ctx.event.message.group_id
        user_id = ctx.event.message.user_id
        
        if message == "!召唤boss":
            if group_id not in self.bosses:
                boss = self.create_boss(group_id)
                await ctx.event.message.reply(
                    f"一个{boss['name']}出现了！\n"
                    f"【等级】{boss['level'] if 'level' in boss else '???'}\n"
                    f"【生命】{boss['hp']}/{boss['max_hp']}\n"
                    f"【性格】{boss['personality']}\n"
                    f"使用 !攻击boss 来发起进攻！"
                )
            else:
                await ctx.event.message.reply(f"当前已有BOSS：{self.bosses[group_id]['name']}正在战斗中！")
        
        elif message == "!攻击boss":
            if group_id not in self.bosses:
                await ctx.event.message.reply("当前没有BOSS可以攻击，使用 !召唤boss 来召唤一个BOSS！")
                return
                
            # 检查冷却时间
            now = datetime.now()
            if user_id in self.battle_cooldown:
                if (now - self.battle_cooldown[user_id]).total_seconds() < 30:
                    await ctx.event.message.reply("你还需要休息一会儿才能继续战斗！")
                    return
            
            boss = self.bosses[group_id]
            player = self.get_player_stats(user_id)
            
            # 计算伤害
            damage = max(1, player["attack"] - boss["defense"] // 2)
            boss["hp"] -= damage
            
            # 记录冷却时间
            self.battle_cooldown[user_id] = now
            
            if boss["hp"] <= 0:
                boss["hp"] = 0
                boss["status"] = "defeated"
                # 获取BOSS的最后遗言
                last_words = await self.get_boss_last_words(boss)
                await ctx.event.message.reply(
                    f"你对{boss['name']}造成了{damage}点伤害！\n"
                    f"在最后一击下，{boss['name']}倒下了！\n"
                    f"BOSS的最后遗言：{last_words}\n"
                    f"所有参与战斗的勇士获得了丰厚的奖励！"
                )
                del self.bosses[group_id]
            else:
                # BOSS反击
                boss_damage = max(1, boss["attack"] - player["defense"])
                player["hp"] -= boss_damage
                
                # 获取BOSS的战斗台词
                battle_words = await self.get_boss_battle_words(boss, damage)
                
                await ctx.event.message.reply(
                    f"你对{boss['name']}造成了{damage}点伤害！\n"
                    f"BOSS还剩{boss['hp']}/{boss['max_hp']}点生命值\n"
                    f"{boss['name']}说：{battle_words}\n"
                    f"{boss['name']}对你造成了{boss_damage}点伤害！"
                )
    
    async def get_boss_battle_words(self, boss, damage):
        """使用大模型生成BOSS的战斗台词"""
        prompt = f"你现在是一个{boss['name']}，性格{boss['personality']}，刚刚受到了{damage}点伤害，血量还剩{boss['hp']}/{boss['max_hp']}。请用一句简短的话回应这次攻击，体现出你的性格特点。"
        
        try:
            response = await self.ap.llm.chat_with_function_call(
                prompt,
                tools_entities.LLMFunctionCall(
                    name="generate_boss_response",
                    description="生成BOSS的战斗台词",
                    parameters={"type": "object", "properties": {
                        "response": {"type": "string", "description": "BOSS的回应"}
                    }}
                )
            )
            return json.loads(response)["response"]
        except Exception as e:
            self.ap.logger.error(f"生成BOSS台词时出错：{e}")
            return "哼！"
    
    async def get_boss_last_words(self, boss):
        """使用大模型生成BOSS的最后遗言"""
        prompt = f"你现在是一个即将死去的{boss['name']}，性格{boss['personality']}。请用一句话作为你的最后遗言，体现出你的性格特点和对战斗的感悟。"
        
        try:
            response = await self.ap.llm.chat_with_function_call(
                prompt,
                tools_entities.LLMFunctionCall(
                    name="generate_boss_last_words",
                    description="生成BOSS的最后遗言",
                    parameters={"type": "object", "properties": {
                        "last_words": {"type": "string", "description": "BOSS的最后遗言"}
                    }}
                )
            )
            return json.loads(response)["last_words"]
        except Exception as e:
            self.ap.logger.error(f"生成BOSS最后遗言时出错：{e}")
            return "我...还会回来的..." 