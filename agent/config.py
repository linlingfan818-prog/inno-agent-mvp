import os
import traceback
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import httpx

# 1. 显式加载环境变量
load_dotenv()

def initialize_llm() -> ChatOpenAI:
    """
    通过 default_headers 双保险焊死必填网关请求头的终极连接器
    """
    base_url = os.getenv("LLM_BASE_URL")      
    api_key = os.getenv("LLM_API_KEY")        
    model_name = os.getenv("LLM_MODEL_NAME")    

    if not all([base_url, api_key, model_name]):
        raise ValueError("❌ 错误: .env 文件中缺少大模型网关基础配置")

    # 🌟 核心硬性条件：缺一不可的全家桶防线
    custom_headers = {
        "Authorization": f"{api_key if 'Bearer' in api_key else 'Bearer ' + api_key}",
        "X-LLMI-API-URL": "https://api.llm-incubator.automotive.cloud/dev/v0",
        "X-Application-Name": "example-app",  # 生产内网审计必填项
        "Content-Type": "application/json"
    }

    # 2. 纯净代理挂载逻辑
    http_proxy_url = os.getenv("HTTP_PROXY", "http://127.0.0.1:3128")
    https_proxy_url = os.getenv("HTTPS_PROXY", "http://127.0.0.1:3128")

    mounts = {}
    mounts["http://api.llm-incubator.automotive.cloud"] = httpx.HTTPTransport(verify=False)
    mounts["https://api.llm-incubator.automotive.cloud"] = httpx.HTTPTransport(verify=False)
    
    if http_proxy_url:
        mounts["http://"] = httpx.HTTPTransport(proxy=http_proxy_url, verify=False)
    if https_proxy_url:
        mounts["https://"] = httpx.HTTPTransport(proxy=https_proxy_url, verify=False)

    # 3. 基础 HTTP 客户端（仅处理网络层穿透与 SSL 豁免）
    http_client = httpx.Client(
        mounts=mounts,
        timeout=httpx.Timeout(60.0, read=600.0)
    )

    print(f"🚀 [Core] 正在加载云端模型实例: {model_name}")

    # 4. 🌟【大双保险重构】
    # 我们不仅在 http_client 里带上 headers，
    # 还必须在 ChatOpenAI 级别显式传入 default_headers！
    # 这样 LangChain 在执行内部 bind_tools 深拷贝时，这些默认请求头也会被底层 OpenAI SDK 强制带上！
    return ChatOpenAI(
        model=model_name,
        openai_api_key=api_key.replace("Bearer ", ""), 
        openai_api_base=base_url,
        temperature=0.0,
        streaming=True,
        http_client=http_client,
        default_headers=custom_headers  # 👈 框架级护甲，杜绝 bind_tools 丢失 Headers
    )

# 全局唯一单例
try:
    llm = initialize_llm()
    if llm is None:
        raise ValueError("initialize_llm 返回了 None")
    print("✅ [Core] 独立 Agent 核心模型连接器：框架级多头护甲已完全焊死！")
except Exception as e:
    print(f"❌ [Core] 大模型初始化致命失败！")
    traceback.print_exc()
    llm = None