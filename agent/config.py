import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import httpx

# 1. 显式加载环境变量
load_dotenv()

# ==========================================
# 🌟 全局单例 HTTP 客户端池 (核心高并发优化)
# ==========================================
# 提取到模块级别，保证在多用户并发时全局复用底层的 TCP 连接池。
# 彻底消除不断创建客户端导致的连接无法释放和 Too many open files (文件描述符耗尽) 隐患。
http_proxy_url = os.getenv("HTTP_PROXY", "http://127.0.0.1:3128")
https_proxy_url = os.getenv("HTTPS_PROXY", "http://127.0.0.1:3128")

# 公司网关走直连并跳过 SSL 校验（内网中间人证书），其余流量走代理
_DIRECT_HOSTS = [
    "api.llm-incubator.automotive.cloud",
    "contivity.aws3116.ec1.aws.automotive.cloud:446",
]


def _build_mounts(transport_cls):
    mounts = {}
    for host in _DIRECT_HOSTS:
        mounts[f"http://{host}"] = transport_cls(verify=False)
        mounts[f"https://{host}"] = transport_cls(verify=False)
    if http_proxy_url:
        mounts["http://"] = transport_cls(proxy=http_proxy_url, verify=False)
    if https_proxy_url:
        mounts["https://"] = transport_cls(proxy=https_proxy_url, verify=False)
    return mounts


# 1. 同步 / 2. 异步请求用的 Mounts 规则
_mounts = _build_mounts(httpx.HTTPTransport)
_async_mounts = _build_mounts(httpx.AsyncHTTPTransport)

# 3. 创建全局单例客户端实例
GLOBAL_HTTP_CLIENT = httpx.Client(mounts=_mounts, timeout=httpx.Timeout(60.0, read=600.0))
GLOBAL_HTTP_ASYNC_CLIENT = httpx.AsyncClient(mounts=_async_mounts, timeout=httpx.Timeout(60.0, read=600.0))
# ==========================================

def initialize_llm(custom_api_key: str = None, model_source: str = "default") -> ChatOpenAI:
    """
    通过 default_headers 双保险焊死必填网关请求头的终极连接器
    """
    api_key = custom_api_key        
    
    if not api_key:
        raise ValueError("API Key 不能为空，请先在左侧配置！")

    # 根据模型来源决定配置
    if model_source.startswith("VIO:"):
        base_url = os.getenv("LLM_VIO_BASE_URL", "https://contivity.aws3116.ec1.aws.automotive.cloud:446")
        
        # 后端留存可用模型记录：
        # VIO:Claude 4.6 Sonnet, VIO:DeepSeek V4 Pro, VIO:Gemini 2.5 Pro, VIO:GPT-4o, 
        # VIO:GPT-5, VIO:Llama3 405B, VIO:Mistral Large 2, VIO:Qwen 3.5 235B 等
        model_name = model_source
        
        custom_headers = {
            "Authorization": f"{api_key if 'Bearer' in api_key else 'Bearer ' + api_key}",
            "Content-Type": "application/json"
        }
    else:
        # 默认使用原有的 LLM Incubator
        base_url = os.getenv("LLM_BASE_URL")      
        model_name = os.getenv("LLM_MODEL_NAME")    
        
        if not all([base_url, model_name]):
            raise ValueError("❌ 错误: .env 文件中缺少大模型网关基础配置")

        # 🌟 核心硬性条件：缺一不可的全家桶防线
        custom_headers = {
            "Authorization": f"{api_key if 'Bearer' in api_key else 'Bearer ' + api_key}",
            "X-LLMI-API-URL": "https://api.llm-incubator.automotive.cloud/dev/v0",
            "X-Application-Token": "gAAAAABq6sET5GbqX8isXnhIVqI6DCt0NX2qkV2YTevBUWQAZ55u8revPEVi9xOn3RoU-0huXbkmffRkck3FZSGwK5efiJ-1iNlV44D-n8Eg0WLxzyAU0Ww=",  # 生产内网审计必填项
            "Content-Type": "application/json"
        }

    print(f"🚀 [Core] 正在加载云端模型实例: {model_name} (Source: {model_source})")

    # 4. 🌟【大双保险重构】
    # 全局复用网络层 (GLOBAL_HTTP_CLIENT)，但通过 per-request 注入 specific headers (如 Token) 和特定工具能力。
    # 这样 LangChain 在执行内部 bind_tools 时依然能安全隔离，同时底层的网络性能得到极大释放。
    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key.replace("Bearer ", ""), 
        openai_api_base=base_url,
        temperature=0.0,
        streaming=True,
        http_client=GLOBAL_HTTP_CLIENT,
        http_async_client=GLOBAL_HTTP_ASYNC_CLIENT,
        default_headers=custom_headers  # 👈 框架级护甲，杜绝 bind_tools 丢失 Headers
    )

# 这里只负责每次实例化 ChatOpenAI 这个皮套，底层笨重的发车逻辑（TCP 连接池）已经被全局共享。