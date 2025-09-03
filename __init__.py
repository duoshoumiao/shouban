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

PROMPT_MAP: Dict[str, str] = {
    "手办化1": DEFAULT_PROMPT,
    "手办化2": DEFAULT_PROMPT2,
    "手办化3": DEFAULT_PROMPT3,
    "手办化4": DEFAULT_PROMPT4,
    "Q版化": DEFAULT_PROMPT_Q,
}

# 增强命令正则，确保能匹配带图片的消息
COMMAND_PATTERNS = [
    re.compile(r"^手办化4(?:@(\d+))?"),
    re.compile(r"^手办化3(?:@(\d+))?"),
    re.compile(r"^手办化2(?:@(\d+))?"),
    re.compile(r"^手办化(?:@(\d+))?"),
    re.compile(r"^Q版化(?:@(\d+))?"),
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
3. 回复图片：回复含图片的消息并发送"手办化1"
""".strip()
)

# 自动添加的密钥配置（请替换为实际需要自动添加的密钥）
AUTO_ADD_KEYS = [
    "sk-or-v1-XXXXXXX",  
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
            cmd = m.group(0)
            if "手办化4" in cmd:
                preset = "手办化4"
            elif "手办化3" in cmd:
                preset = "手办化3"
            elif "手办化2" in cmd:
                preset = "手办化2"
            elif "Q版化" in cmd:
                preset = "Q版化"
            else:
                preset = "手办化1"
            qq = m.group(1)
            return preset, qq
    return "", None

def select_prompt(preset_label: str) -> Tuple[str, str]:
    """根据预设标签选择提示词"""
    if preset_label in PROMPT_MAP:
        return PROMPT_MAP[preset_label], preset_label
    return PROMPT_MAP["手办化1"], "手办化1"

def build_payload(model: str, prompt: str, image_b64: str, max_tokens: int) -> dict:
    """构建API请求体"""
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

@sv.on_message()  # 不指定类型，兼容旧版本
async def handle_figure_conversion(bot, event: CQEvent):
    """处理手办化/Q版化命令的主函数，支持图片和@提及"""
    # 提取消息文本和图片
    msg_text = str(event.message).strip()
    preset, target_qq = parse_command(msg_text)
    
    # 不匹配命令则忽略
    if not preset:
        return
    
    try:
        # 1. 获取图片来源（优先级：消息中的图片 > 回复的图片 > 头像）
        image_url = get_image_from_event(event)
        
        # 2. 处理目标QQ（优先级：命令中的@ > 消息中的@ > 发送者）
        if not target_qq:
            target_qq = get_at_qq_from_event(event)
        if not image_url:
            # 如果没有图片，使用QQ头像
            if target_qq:
                image_url = build_avatar_url(target_qq)
            else:
                image_url = build_avatar_url(str(event.user_id))
        
        # 3. 处理图片
        await bot.send(event, "⏳ 正在处理图片，请稍候...")
        image_b64 = await fetch_image_as_b64(image_url)
        
        # 4. 调用API生成图片
        await bot.send(event, f"🎨 正在生成效果图...")
        prompt, prompt_label = select_prompt(preset)
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
        
        proxy = None
        if CONFIG["use_proxy"] and CONFIG["proxy_url"]:
            proxy = CONFIG["proxy_url"]
    
        async with httpx.AsyncClient(proxy=proxy, timeout=60.0) as client:
            resp = await client.post(API_URL, json=payload, headers=headers)
            resp.raise_for_status()  # 触发HTTP错误异常
            data = resp.json()
        
        # 5. 提取并发送结果
        result_url = extract_image_url_from_response(data)
        if not result_url:
            await bot.send(event, "❌ 未能从API响应中提取图片")
            return
        
        # 使用兼容的消息构建方式
        await bot.send(event, Message(f"✨生成成功！\n{MessageSegment.image(result_url)}"))
    
    except httpx.HTTPError as e:
        # 处理HTTP错误
        status_code = e.response.status_code if e.response else None
        error_msg = f"❌ HTTP请求错误: {str(e)}"
        await bot.send(event, error_msg)
        
        # 当错误为401（未授权）或429（请求过于频繁）时删除第一个key
        if status_code in (401, 429):
            cfg = load_keys_config()
            keys = cfg.get("keys", [])
            if len(keys) > 0:
                removed_key = keys.pop(0)  # 删除第一个key
                # 调整当前索引
                if cfg["current"] >= len(keys) and keys:
                    cfg["current"] = 0
                save_keys_config(cfg)
                
                # 根据错误类型显示不同消息
                error_type = "密钥无效或未授权" if status_code == 401 else "请求过于频繁"
                await bot.send(event, f"🔑 检测到{error_type}（{status_code}错误），已自动移除第一个密钥：{removed_key[:12]}***")
        
        sv.logger.error(f"手办化处理HTTP错误: {str(e)}", exc_info=True)
        
    except Exception as e:
        # 处理其他非HTTP错误
        error_msg = f"❌ 处理失败：{str(e)}"
        await bot.send(event, error_msg)
        sv.logger.error(f"手办化处理失败: {str(e)}", exc_info=True)

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
