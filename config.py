import os
import json

# 插件默认配置（完全兼容旧版Hoshino）
DEFAULT_CONFIG = {
    "use_proxy": False,
    "proxy_url": "",
    "model": "google/gemini-2.5-flash-image-preview:free",
    "max_tokens": 1000,
    "request_timeout_sec": 60.0,
    "keys_file_path": os.path.join(os.path.dirname(__file__), "resource", "openrouter_keys.json")
}

# 确保资源目录和密钥文件存在
def ensure_resource_dir():
    # 创建resource目录
    resource_dir = os.path.join(os.path.dirname(__file__), "resource")
    if not os.path.exists(resource_dir):
        os.makedirs(resource_dir, exist_ok=True)
    # 初始化密钥文件
    if not os.path.exists(DEFAULT_CONFIG["keys_file_path"]):
        init_keys = {"keys": [], "current": 0}
        with open(DEFAULT_CONFIG["keys_file_path"], "w", encoding="utf-8") as f:
            json.dump(init_keys, f, ensure_ascii=False, indent=2)

# 执行初始化
ensure_resource_dir()

# 对外导出配置
CONFIG = DEFAULT_CONFIG