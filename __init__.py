import os
import re
import json
import base64
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
import httpx
from hoshino import Service, priv, get_bot
from hoshino.typing import CQEvent, Message, MessageSegment

# 加载配置
from .config import CONFIG

# 全局常量
API_URL = "https://openrouter.ai/api/v1/chat/completions"
QLOGO_AVATAR = "https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640"
GENERATED_DIR = os.path.join(os.path.dirname(__file__), "resource", "generated")

# 提示词预设
DEFAULT_PROMPT = "Your task is to create a photorealistic, masterpiece-quality image of a 1/7 scale commercialized figurine based on the user's character. The final image must be in a realistic style and environment.\n\n**Crucial Instruction on Face & Likeness:** The figurine's face is the most critical element. It must be a perfect, high-fidelity 3D translation of the character from the source image. The sculpt must be sharp, clean, and intricately detailed, accurately capturing the original artwork's facial structure, eye style, expression, and hair. The final result must be immediately recognizable as the same character, elevated to a premium physical product standard. Do NOT generate a generic or abstract face.\n\n**Scene Composition (Strictly follow these details):**\n1. **Figurine & Base:** Place the figure on a computer desk. It must stand on a simple, circular, transparent acrylic base WITHOUT any text or markings.\n2. **Computer Monitor:** In the background, a computer monitor must display 3D modeling software (like ZBrush or Blender) with the digital sculpt of the very same figurine visible on the screen.\n3. **Artwork Display:** Next to the computer screen, include a transparent acrylic board with a wooden base. This board holds a print of the original 2D artwork that the figurine is based on.\n4. **Environment:** The overall setting is a desk, with elements like a keyboard to enhance realism. The lighting should be natural and well-lit, as if in a room."
DEFAULT_PROMPT2 = "Use the nano-banana model to create a 1/7 scale commercialized figure of thecharacter in the illustration, in a realistic styie and environment.Place the figure on a computer desk, using a circular transparent acrylic basewithout any text.On the computer screen, display the ZBrush modeling process of the figure.Next to the computer screen, place a BANDAl-style toy packaging box printedwith the original artwork."
DEFAULT_PROMPT3 = "Your primary mission is to accurately convert the subject from the user's photo into a photorealistic, masterpiece quality, 1/7 scale PVC figurine, presented in its commercial packaging.\n\n**Crucial First Step: Analyze the image to identify the subject's key attributes (e.g., human male, human female, animal, specific creature) and defining features (hair style, clothing, expression). The generated figurine must strictly adhere to these identified attributes.** This is a mandatory instruction to avoid generating a generic female figure.\n\n**Top Priority - Character Likeness:** The figurine's face MUST maintain a strong likeness to the original character. Your task is to translate the 2D facial features into a 3D sculpt, preserving the identity, expression, and core characteristics. If the source is blurry, interpret the features to create a sharp, well-defined version that is clearly recognizable as the same character.\n\n**Scene Details:**\n1. **Figurine:** The figure version of the photo I gave you, with a clear representation of PVC material, placed on a round plastic base.\n2. **Packaging:** Behind the figure, there should be a partially transparent plastic and paper box, with the character from the photo printed on it.\n3. **Environment:** The entire scene should be in an indoor setting with good lighting."
DEFAULT_PROMPT4 = "基于游戏截图人物的逼真 PVC 人偶，高度细致的纹理PVC 材质，光泽细腻，漆面光滑，放置在室内木质电脑桌上（桌上摆放着一些精致的桌面物品，例如人偶盒/鼠标），在柔和的室内灯光（台灯和自然光混合）的照射下，阴影和高光效果逼真，微距摄影风格，高分辨率，人物清晰对焦，景深浅（桌面背景略微模糊但清晰可见）。无风格化，色彩和设计忠实于参考，1:1 比例,返回图片给我！！！"
DEFAULT_PROMPT_Q = "((chibi style)), ((super-deformed)), ((head-to-body ratio 1:2)), ((huge head, tiny body)), ((smooth rounded limbs)), ((soft balloon-like hands and feet)), ((plump cheeks)), ((childlike big eyes)), ((simplified facial features)), ((smooth matte skin, no pores)), ((soft pastel color palette)), ((gentle ambient lighting, natural shadows)), ((same facial expression, same pose, same background scene)), ((seamless integration with original environment, correct perspective and scale)), ((no outline or thin soft outline)), ((high resolution, sharp focus, 8k, ultra-detailed)), avoid: realistic proportions, long limbs, sharp edges, harsh lighting, wrinkles, blemishes, thick black outlines, low resolution, blurry, extra limbs, distorted face"
DEFAULT_PROMPT5 = "一幅超写实、电影感的插画，描绘了图中人物动态地撞穿一张“考古探险”集换卡牌的边框。正处于跳跃中或用绳索摆荡，枪口的火焰帮助将卡牌古老的石雕边框震碎，在破口周围制造出可见的维度破裂效果，如能量裂纹和空间扭曲，使灰尘和碎片四散飞溅。充满活力地向前冲出，带有明显的运动深度，突破了卡牌的平面，卡牌内部（背景）描绘着茂密的丛林遗迹或布满陷阱的古墓内部。卡牌的碎屑与 crumbling 的石头、飞舞的藤蔓、古钱币碎片混合在一起。“考古探险”的标题和不知是谁的名字（带有一个风格化的文物图标）在卡牌剩余的、布满裂纹和风化痕迹的部分上可见。充满冒险感的、动态的灯光突出了运动能力和危险的环境。"
DEFAULT_PROMPT6 = "A 3D chibi-style version of the person in the photo is stepping through a glowing portal, reaching out and holding the viewer’s hand. As the character pulls the viewer forward, they turn back with a dynamic glance, inviting the viewer into their world.Behind the portal is the viewer’s real-life environment: a typical programmer’s study with a desk, monitor, and laptop, rendered in realistic detail. Inside the portal lies the character’s 3D chibi world, inspired by the photo, with a cool blue color scheme that sharply contrasts with the real-world surroundings.The portal itself is a perfectly elliptical frame glowing with mysterious blue and purple light, positioned at the center of the image as a gateway between the two worlds.The scene is captured from a third-person perspective, clearly showing the viewer’s hand being pulled into the character’s world. Use a 2:3 aspect ratio."
DEFAULT_PROMPT_DOUBLE = "Create a dynamic battle scene featuring the two characters from the provided images. The scene should show them in a cooperative fighting stance, with visible synergy between their movements. Maintain the original appearance and key features of both characters while rendering them in a consistent art style. Add dramatic lighting and motion effects to enhance the action-packed atmosphere. Ensure both characters are equally prominent and clearly recognizable from their source images."
PROMPT_MAP: Dict[str, str] = {
    "手办化1": DEFAULT_PROMPT,
    "手办化2": DEFAULT_PROMPT2,
    "手办化3": DEFAULT_PROMPT3,
    "手办化4": DEFAULT_PROMPT4,
    "Q版化": DEFAULT_PROMPT_Q,
    "破壁而出": DEFAULT_PROMPT5,  
    "次元壁": DEFAULT_PROMPT6,  
    "双打": DEFAULT_PROMPT_DOUBLE,    
}

COMMAND_PATTERNS = [
    re.compile(r"^(?:@(\d+) )?双打(?:@(\d+))?"), 
    re.compile(r"^(?:@(\d+) )?手办化4(?:@(\d+))?"),
    re.compile(r"^(?:@(\d+) )?手办化3(?:@(\d+))?"),
    re.compile(r"^(?:@(\d+) )?手办化2(?:@(\d+))?"),
    re.compile(r"^(?:@(\d+) )?手办化(?:@(\d+))?"),
    re.compile(r"^(?:@(\d+) )?Q版化(?:@(\d+))?"),
    re.compile(r"^(?:@(\d+) )?破壁而出(?:@(\d+))?"),
    re.compile(r"^(?:@(\d+) )?次元壁(?:@(\d+))?"),
]

# 初始化生成目录
os.makedirs(GENERATED_DIR, exist_ok=True)

# 服务注册（兼容旧版本方式）
sv = Service(
    name="手办",
    use_priv=priv.NORMAL,
    manage_priv=priv.ADMIN,
    visible=True,
    enable_on_default=False,
    help_="""
使用说明：
1. 发送命令+图片：发送"手办化1"并附带图片
2. 指定QQ：发送"手办化1@QQ号"使用该用户头像
3. 双打模式：发送"双打"并附带第一张图片，收到提示后发送第二张图片
""".strip()
)

# 自动添加的密钥配置（请替换为实际需要自动添加的密钥）
AUTO_ADD_KEYS = [
    "sk-or-v1-XXXXXX", 
]

# 全局变量用于标记定时任务是否已启动
auto_add_task_started = False

# ------------------------------ 工具函数 ------------------------------
def load_keys_config() -> dict:
    """加载API密钥配置"""
    try:
        with open(CONFIG["keys_file_path"], "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # 初始化配置文件
        init_cfg = {"keys": [], "current": 0}
        with open(CONFIG["keys_file_path"], "w", encoding="utf-8") as f:
            json.dump(init_cfg, f, ensure_ascii=False, indent=2)
        return init_cfg

def save_keys_config(cfg: dict) -> None:
    """保存API密钥配置"""
    with open(CONFIG["keys_file_path"], "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_next_api_key() -> str:
    """获取下一个可用API密钥（轮询）"""
    cfg = load_keys_config()
    keys = cfg.get("keys", [])
    if not keys:
        raise RuntimeError("看来次数用完（每日12点自动添加key），请使用【添加key】命令添加新key")
    idx = cfg.get("current", 0) % len(keys)
    cfg["current"] = (idx + 1) % len(keys)
    save_keys_config(cfg)
    return keys[idx]

def build_avatar_url(qq: str) -> str:
    """生成QQ头像URL"""
    return QLOGO_AVATAR.format(qq=qq)

def parse_command(message_text: str) -> Tuple[str, Optional[str]]:
    """解析命令，返回（预设标签，目标QQ）"""
    message_text = (message_text or "").strip()
    for pattern in COMMAND_PATTERNS:
        m = pattern.search(message_text)
        if m:
            # 提取@的QQ号（可能在指令前或后）
            qq1 = m.group(1)
            qq2 = m.group(2)
            target_qq = qq1 or qq2  # 优先取指令前的@
            
            cmd = m.group(0)
            if "双打" in cmd:
                preset = "双打"
            elif "手办化4" in cmd:
                preset = "手办化4"
            elif "手办化3" in cmd:
                preset = "手办化3"
            elif "手办化2" in cmd:
                preset = "手办化2"
            elif "Q版化" in cmd:
                preset = "Q版化"
            elif "破壁而出" in cmd:
                preset = "破壁而出"  
            elif "次元壁" in cmd:
                preset = "次元壁"    
            else:
                preset = "手办化1"
            return preset, target_qq
    return "", None

def select_prompt(preset_label: str) -> Tuple[str, str]:
    """根据预设标签选择提示词"""
    if preset_label in PROMPT_MAP:
        return PROMPT_MAP[preset_label], preset_label
    return PROMPT_MAP["手办化1"], "手办化1"

def build_payload(model: str, prompt: str, image_b64: str, max_tokens: int) -> dict:
    """构建单图API请求体"""
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }

def build_double_payload(model: str, prompt: str, image1_b64: str, image2_b64: str, max_tokens: int) -> dict:
    """构建双图API请求体"""
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image1_b64}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image2_b64}"}},
                ],
            }
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }

async def fetch_image_as_b64(url: str) -> str:
    """下载图片并转换为base64"""
    # 处理base64前缀
    if url.startswith("base64://"):
        return url.split("://", 1)[1]
    # 处理本地文件
    if url.startswith("file://"):
        local_path = url[len("file://"):]
        with open(local_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    if os.path.exists(url):
        with open(url, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
     # 处理网络URL（适配代理）
    proxy = None
    if CONFIG["use_proxy"] and CONFIG["proxy_url"]:
        proxy = CONFIG["proxy_url"]
    
    try:
        async with httpx.AsyncClient(timeout=30.0, proxy=proxy) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return base64.b64encode(resp.content).decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"图片下载失败: {str(e)}")

def extract_image_url_from_response(data: dict) -> Optional[str]:
    """从API响应中提取图片URL"""
    # 优先从images字段提取
    img = data.get("choices", [{}])[0].get("message", {}).get("images", [{}])[0]
    url = img.get("image_url", {}).get("url") or img.get("url")
    if url:
        return url
    # 从content字段提取链接
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    m = re.search(r'https?://[^\s<>"\)\]]+', content)
    if m:
        return m.group(0).rstrip(")]}>'\"")
    return None

def get_image_from_event(event: CQEvent) -> Optional[str]:
    """从事件中提取图片URL（兼容旧版本）"""
    # 1. 优先从回复消息中提取
    if hasattr(event, 'reply') and event.reply:
        for seg in event.reply.message:
            if seg.type == 'image':
                return seg.data.get('url')
    # 2. 从当前消息中提取
    for seg in event.message:
        if seg.type == 'image':
            return seg.data.get('url')
    return None

def get_at_qq_from_event(event: CQEvent) -> Optional[str]:
    """从事件中提取@的QQ号（兼容旧版本）"""
    for seg in event.message:
        if seg.type == "at" and seg.data.get("qq") != "all":
            return seg.data.get("qq")
    return None

# ------------------------------ 定时任务 - 每日12点自动添加密钥 ------------------------------
async def auto_add_keys_daily():
    """每天12点自动添加指定key的定时任务"""
    global auto_add_task_started
    auto_add_task_started = True
    sv.logger.info("每日自动添加密钥任务已启动")
    
    while True:
        # 计算距离下次12点的时间
        now = datetime.now()
        target = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if now > target:
            target += timedelta(days=1)
        delta = (target - now).total_seconds()
        sv.logger.info(f"距离下次自动添加密钥还有 {delta:.1f} 秒")
        await asyncio.sleep(delta)
        
        # 执行添加key操作
        try:
            existing_config = load_keys_config()
            existing_key_set = set(existing_config.get("keys", []))
            new_keys = []
            
            for key in AUTO_ADD_KEYS:
                if key and key not in existing_key_set and key.startswith("sk-or-v1-"):
                    existing_config.setdefault("keys", []).append(key)
                    new_keys.append(key[:12] + "***")
                    existing_key_set.add(key)
            
            if new_keys:
                save_keys_config(existing_config)
                sv.logger.info(f"每日自动添加密钥完成，新增{len(new_keys)}个密钥: {', '.join(new_keys)}")
            else:
                sv.logger.info("每日自动添加密钥检查：无新密钥需要添加")
        except Exception as e:
            sv.logger.error(f"每日自动添加密钥失败: {str(e)}", exc_info=True)

# 启动定时任务的兼容方法（Hoshino v1）
def start_auto_add_task():
    """启动每日自动添加密钥任务（兼容Hoshino v1）"""
    global auto_add_task_started
    if not auto_add_task_started:
        loop = asyncio.get_event_loop()
        loop.create_task(auto_add_keys_daily())

# 在插件加载时启动定时任务（Hoshino v1兼容方式）
start_auto_add_task()

# ------------------------------ 命令处理 ------------------------------
@sv.on_prefix(("添加key"))
async def cmd_add_key(bot, event: CQEvent):
    if not priv.check_priv(event, priv.ADMIN):
        await bot.send(event, "❌ 权限不足，仅管理员可执行此操作")
        return
    msg_content = str(event.message).strip()
    key_content = msg_content.replace("添加key", "", 1).strip()
    if not key_content:
        await bot.send(event, "❌ 请输入API密钥！示例：\n添加key sk-or-v1-xxxxxxxxxxxxxxxx")
        return
    # 分割多个密钥
    key_list = [k.strip() for k in re.split(r"[\s,;，；]", key_content) if k.strip()]
    valid_keys = [k for k in key_list if k.startswith("sk-or-v1-")]
    if not valid_keys:
        await bot.send(event, "❌ 未检测到有效密钥！密钥必须以「sk-or-v1-」开头")
        return
    # 保存密钥
    existing_config = load_keys_config()
    existing_key_set = set(existing_config.get("keys", []))
    new_keys = []
    duplicate_keys = []
    for key in valid_keys:
        if key in existing_key_set:
            duplicate_keys.append(key[:12] + "***")
        else:
            new_keys.append(key[:12] + "***")
            existing_config.setdefault("keys", []).append(key)
    save_keys_config(existing_config)
    # 反馈结果
    result_msg = ["✅ 密钥添加完成！"]
    if new_keys:
        result_msg.append(f"- 新增密钥：{', '.join(new_keys)}")
    if duplicate_keys:
        result_msg.append(f"- 跳过重复密钥：{', '.join(duplicate_keys)}")
    await bot.send(event, "\n".join(result_msg))

@sv.on_fullmatch(("key列表"))
async def cmd_show_keys(bot, event: CQEvent):
    if not priv.check_priv(event, priv.ADMIN):
        await bot.send(event, "❌ 权限不足，仅管理员可执行此操作")
        return
    cfg = load_keys_config()
    keys = cfg.get("keys", [])
    if not keys:
        await bot.send(event, "⚠️ 尚未配置任何API密钥")
        return
    masked_keys = [k[:12] + "***" for k in keys]
    await bot.send(event, f"已配置密钥（共{len(keys)}个）：\n" + "\n".join(masked_keys))

# 在全局添加缓存字典，记录等待图片的用户状态
waiting_for_image = {}  # key: user_id, value: preset
waiting_for_second_image = {}  # key: user_id, value: (preset, first_image_url)

# 全局状态变量拆分，分别管理普通指令和双打指令的等待状态
waiting_for_image = {}  # 普通指令: {user_id: preset}
waiting_for_double_image = {}  # 双打指令: {user_id: first_image_url}

# ------------------------------ 双打模式单独处理 ------------------------------
@sv.on_message()
async def handle_double_mode(bot, event: CQEvent):
    """单独处理双打模式的消息，支持@目标用户获取头像"""
    user_id = event.user_id
    msg_text = str(event.message).strip()
    preset, _ = parse_command(msg_text)
    
    # 只处理双打指令
    if preset != "双打":
        return
    
    # 情况1：用户已发送第一张图，现在处理第二张图
    if user_id in waiting_for_double_image:
        first_image_url = waiting_for_double_image.pop(user_id)
        
        # 优先从消息提取图片，其次提取@用户的头像
        second_image_url = get_image_from_event(event)
        target_qq = get_at_qq_from_event(event)  # 新增：提取@的目标QQ
        
        # 如果没有直接图片但有@用户，使用该用户头像
        if not second_image_url and target_qq:
            second_image_url = build_avatar_url(target_qq)
            await bot.send(event, f"已使用@用户{target_qq}的头像作为第二张图片")
        
        if not second_image_url:
            # 重新保存第一张图，等待第二张
            waiting_for_double_image[user_id] = first_image_url
            await bot.send(event, "未检测到第二张图片，请重新发送第二张图片（可直接附带图片或@目标用户使用其头像）")
            return
        
        # 两张图片都已获取，开始处理
        await bot.send(event, "⏳ 已收到两张图片，正在处理双打模式...")
        try:
            # 处理第一张图片
            first_image_b64 = await fetch_image_as_b64(first_image_url)
            # 处理第二张图片
            second_image_b64 = await fetch_image_as_b64(second_image_url)
            
            # 获取提示词并显示正确状态
            prompt, prompt_label = select_prompt("双打")
            await bot.send(event, f"🎨 正在生成{prompt_label}效果...")
            
            # 构建双图请求体
            payload = build_double_payload(
                model=CONFIG["model"],
                prompt=prompt,
                image1_b64=first_image_b64,
                image2_b64=second_image_b64,
                max_tokens=CONFIG["max_tokens"]
            )
            
            # 发送API请求
            headers = {
                "Authorization": f"Bearer {get_next_api_key()}",
                "Content-Type": "application/json"
            }
            
            proxy = CONFIG["proxy_url"] if CONFIG["use_proxy"] else None
            async with httpx.AsyncClient(proxy=proxy, timeout=60.0) as client:
                resp = await client.post(API_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            
            # 提取并发送结果
            result_url = extract_image_url_from_response(data)
            if result_url:
                await bot.send(event, Message(f"✨ {prompt_label}生成成功！\n{MessageSegment.image(result_url)}"))
            else:
                await bot.send(event, "❌ 未能从API响应中提取图片")
                
        except Exception as e:
            await bot.send(event, f"❌ 双打模式处理失败：{str(e)}")
            # 出错时恢复状态，允许重新发送
            waiting_for_double_image[user_id] = first_image_url
        return
    
    # 情况2：首次发送双打指令，处理第一张图
    # 优先从消息提取图片，其次提取@用户的头像
    first_image_url = get_image_from_event(event)
    target_qq = get_at_qq_from_event(event)  # 新增：提取@的目标QQ
    
    # 如果没有直接图片但有@用户，使用该用户头像
    if not first_image_url and target_qq:
        first_image_url = build_avatar_url(target_qq)
        await bot.send(event, f"已使用@用户{target_qq}的头像作为第一张图片")
    
    if not first_image_url:
        # 等待用户发送第一张图
        waiting_for_double_image[user_id] = None  # 用None标记等待第一张图
        await bot.send(event, "请发送第一张需要处理的图片（可直接附带图片或@目标用户使用其头像）")
        return
    else:
        # 已收到第一张图，等待第二张
        waiting_for_double_image[user_id] = first_image_url
        await bot.send(event, "已收到第一张图片，请发送第二张需要处理的图片（可直接附带图片或@目标用户使用其头像）")
        return

# ------------------------------ 其他指令处理 ------------------------------
@sv.on_message()
async def handle_other_commands(bot, event: CQEvent):
    """处理除双打之外的其他指令，支持@目标头像触发"""
    user_id = event.user_id
    msg_text = str(event.message).strip()
    # 解析命令，支持@在指令前后的格式
    preset, target_qq = parse_command(msg_text)
    
    # 调试日志：输出初始解析结果
    sv.logger.debug(f"初始解析 - preset: {preset}, target_qq: {target_qq}, 原始消息: {msg_text}")
    
    # 忽略双打指令
    if preset == "双打":
        return
    
    # 情况1：用户之前发送过指令，现在单独发送图片
    if user_id in waiting_for_image and not preset:
        preset = waiting_for_image.pop(user_id)
        image_url = get_image_from_event(event)
        if not image_url:
            await bot.send(event, "未检测到图片，请重新发送图片")
            waiting_for_image[user_id] = preset
            return
    # 情况2：用户发送了指令，但未附带图片且未识别到目标
    elif preset and not get_image_from_event(event) and not target_qq:
        # 再次尝试提取@目标（双重保障）
        target_qq = get_at_qq_from_event(event)
        if not target_qq:  # 确认确实没有目标才进入等待状态
            waiting_for_image[user_id] = preset
            await bot.send(event, "请发送需要处理的图片（可直接附带图片）或@目标用户使用其头像")
            return
    # 情况3：不匹配命令则忽略
    elif not preset:
        return

    # 单图处理逻辑
    try:
        # 1. 获取图片来源
        image_url = get_image_from_event(event)
        sv.logger.info(f"处理命令[{preset}]，初始图片URL: {image_url if image_url else '无'}")

        # 2. 处理目标QQ（多重提取保障）
        if not target_qq:
            target_qq = get_at_qq_from_event(event)
            sv.logger.info(f"从消息中提取到@的QQ: {target_qq if target_qq else '无'}")
        
        # 最终确认目标状态（增加调试日志）
        sv.logger.debug(f"最终目标确认 - target_qq: {target_qq}, image_url存在: {bool(image_url)}")
        
        # 3. 检查图片/目标是否存在
        if not image_url and not target_qq:
            await bot.send(event, "请发送需要处理的图片（可直接附带图片的消息）或@目标用户")
            return
        
        # 4. 使用头像作为图片源（当无直接图片时）
        if not image_url and target_qq:
            image_url = build_avatar_url(target_qq)
            sv.logger.info(f"使用目标QQ[{target_qq}]的头像作为图片源")
        if not image_url:
            image_url = build_avatar_url(str(event.user_id))
            sv.logger.info(f"使用发送者QQ[{event.user_id}]的头像作为图片源")
        
        # 验证图片URL有效性
        if not image_url.startswith(('http://', 'https://', 'base64://', 'file://')):
            raise RuntimeError(f"无效的图片URL格式: {image_url}")

        # 5. 处理图片
        await bot.send(event, "⏳ 正在处理图片，请稍候...")
        try:
            image_b64 = await fetch_image_as_b64(image_url)
            if len(image_b64) < 100:
                raise RuntimeError("图片转换失败，得到无效的base64数据")
        except Exception as e:
            await bot.send(event, f"❌ 图片处理失败：{str(e)}\n请重新发送图片或检查图片有效性")
            return
        
        # 6. 调用API生成图片
        prompt, prompt_label = select_prompt(preset)
        await bot.send(event, f"🎨 正在生成{prompt_label}效果...")
        payload = build_payload(
            model=CONFIG["model"],
            prompt=prompt,
            image_b64=image_b64,
            max_tokens=CONFIG["max_tokens"]
        )
        headers = {
            "Authorization": f"Bearer {get_next_api_key()}",
            "Content-Type": "application/json"
        }
        
        proxy = CONFIG["proxy_url"] if CONFIG["use_proxy"] else None
        async with httpx.AsyncClient(proxy=proxy, timeout=60.0) as client:
            resp = await client.post(API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        
        # 7. 提取并发送结果
        result_url = extract_image_url_from_response(data)
        if not result_url:
            await bot.send(event, "❌ 未能从API响应中提取图片")
            return
        
        await bot.send(event, Message(f"✨ {prompt_label}生成成功！\n{MessageSegment.image(result_url)}"))
    
    # 异常处理
    except httpx.HTTPError as e:
        status_code = e.response.status_code if e.response else None
        error_msg = f"❌ HTTP请求错误: {str(e)}"
        await bot.send(event, error_msg)
        
        if status_code in (401, 429):
            cfg = load_keys_config()
            keys = cfg.get("keys", [])
            if len(keys) > 0:
                removed_key = keys.pop(0)
                if cfg["current"] >= len(keys) and keys:
                    cfg["current"] = 0
                save_keys_config(cfg)
                
                error_type = "密钥无效或未授权" if status_code == 401 else "请求过于频繁"
                await bot.send(event, f"🔑 检测到{error_type}（{status_code}错误），已自动移除第一个密钥：{removed_key[:12]}***")
        
        sv.logger.error(f"处理HTTP错误: {str(e)}", exc_info=True)
        
    except Exception as e:
        error_msg = f"❌ 处理失败：{str(e)}"
        await bot.send(event, error_msg)
        sv.logger.error(f"处理失败: {str(e)}", exc_info=True)


# 同时确保get_at_qq_from_event函数能正确提取@的用户（如果之前实现有问题）
def get_at_qq_from_event(event: CQEvent) -> Optional[str]:
    """从事件中提取@的第一个用户QQ号"""
    for segment in event.message:
        if segment.type == "at" and segment.data.get("qq"):
            # 排除@全体成员的情况
            if segment.data["qq"] != "all":
                return segment.data["qq"]
    return None


@sv.on_prefix(("删除key"))
async def cmd_remove_key(bot, event: CQEvent):
    if not priv.check_priv(event, priv.ADMIN):
        await bot.send(event, "❌ 权限不足，仅管理员可执行此操作")
        return
    msg_content = str(event.message).strip()
    key_content = msg_content.replace("删除key", "", 1).strip()
    if not key_content:
        await bot.send(event, "❌ 请输入要删除的API密钥前缀或序号！示例：\n删除key 1\n删除key sk-or-v1-xxxx")
        return
    
    cfg = load_keys_config()
    keys = cfg.get("keys", [])
    if not keys:
        await bot.send(event, "⚠️ 尚未配置任何API密钥")
        return
    
    # 尝试按序号删除（1-based）
    removed = False
    if key_content.isdigit():
        idx = int(key_content) - 1
        if 0 <= idx < len(keys):
            removed_key = keys.pop(idx)
            removed = True
    else:
        # 尝试按前缀匹配删除
        to_remove = [k for k in keys if k.startswith(key_content)]
        if to_remove:
            for k in to_remove:
                keys.remove(k)
            removed = True
    
    if not removed:
        await bot.send(event, "❌ 未找到匹配的密钥，请检查输入")
        return
    
    # 保存配置并调整当前索引
    if cfg["current"] >= len(keys) and keys:
        cfg["current"] = 0
    save_keys_config(cfg)
    
    # 反馈结果
    masked_keys = [k[:12] + "***" for k in to_remove] if not key_content.isdigit() else [removed_key[:12] + "***"]
    await bot.send(event, f"✅ 成功删除密钥：\n" + "\n".join(masked_keys))
