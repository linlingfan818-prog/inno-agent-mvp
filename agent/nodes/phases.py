import os
from langchain_core.messages import SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from langchain_core.runnables.config import RunnableConfig
from agent.state import AgentState
from agent.config import initialize_llm

# --- Phase Transition Tools ---
# These are the tools the LLM can call to trigger a state transition after user confirmation.

class TransitionToPM(BaseModel):
    """当用户确认了核心痛点(Why)，并且同意进入具体产品形态(What)讨论时调用此工具。"""
    why: str = Field(description="总结提炼出的核心痛点(Why)")

class TransitionToValue(BaseModel):
    """当用户确认了产品边界和需求(What)，并且同意进入商业价值与市场分析(Value)探讨时调用此工具。"""
    what: str = Field(description="总结提炼出的具体创新产品形态(What)")

class TransitionToExpert(BaseModel):
    """当用户确认了商业价值(Value)，并且同意进入技术路线和成本(How)探讨时调用此工具。"""
    market_value: str = Field(description="总结提炼出的核心商业价值与市场分析")

class TransitionToDone(BaseModel):
    """当用户确认了最终的技术路线和落地方案(How)，并且同意生成最终PDF报告时调用此工具。"""
    project_name: str = Field(description="项目名称")
    how_overview: str = Field(description="技术方案概览")
    scope: str = Field(description="项目范围")
    objective: str = Field(description="核心目标 (Objective)")
    key_results: str = Field(description="关键结果 (KRs) 组成的文本或列表")
    cost: str = Field(description="预算(数字或区间，例如 '130-155')")
    m1: str = Field(description="里程碑1的核心任务")
    m2: str = Field(description="里程碑2的核心任务")
    m3: str = Field(description="里程碑3的核心任务")
    m4: str = Field(description="里程碑4的核心任务")
    pdf_instructions: str = Field(description="用户对生成PDF技术报告的附加补充要求（若无则为空）")

# Helper to read prompts
def get_sys_prompt(filename: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return f"【缺少提示词文件: {filename}】"

# --- Phase Nodes ---

async def coach_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("coach.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToPM])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    # Check if the LLM decided to transition
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToPM":
        # Handle the transition
        tool_call_id = response.tool_calls[0]["id"]
        why_text = response.tool_calls[0].get("args", {}).get("why", "")
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToPM",
            content="[系统回复] 已成功切换至 PM 阶段。请向用户打招呼并开始探讨产品细节 (What)。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "PM",
            "why": why_text
        }
        
    return {"messages": [response]}

async def pm_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("pm.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToValue])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToValue":
        tool_call_id = response.tool_calls[0]["id"]
        what_text = response.tool_calls[0].get("args", {}).get("what", "")
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToValue",
            content="[系统回复] 已成功切换至 VALUE 阶段。请向用户打招呼并开始探讨市场价值与商业潜力。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "VALUE",
            "what": what_text
        }
        
    return {"messages": [response]}

async def value_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("value.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToExpert])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToExpert":
        tool_call_id = response.tool_calls[0]["id"]
        market_value_text = response.tool_calls[0].get("args", {}).get("market_value", "")
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToExpert",
            content="[系统回复] 已成功切换至 EXPERT 阶段。请向用户打招呼并开始探讨技术和成本 (How)。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "EXPERT",
            "market_value": market_value_text
        }
        
    return {"messages": [response]}

async def expert_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("expert.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToDone])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToDone":
        tool_call_id = response.tool_calls[0]["id"]
        args = response.tool_calls[0].get("args", {})
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToDone",
            content="[系统回复] 已成功确认。PDF报告生成节点将被触发。"
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "DONE",
            "pdf_instructions": args.get("pdf_instructions", ""),
            "how": {
                "project_name": args.get("project_name", ""),
                "how_overview": args.get("how_overview", ""),
                "scope": args.get("scope", ""),
                "objective": args.get("objective", ""),
                "key_results": args.get("key_results", ""),
                "cost": args.get("cost", ""),
                "milestones": {
                    "M1": args.get("m1", ""),
                    "M2": args.get("m2", ""),
                    "M3": args.get("m3", ""),
                    "M4": args.get("m4", "")
                }
            }
        }
        
    return {"messages": [response]}

from langchain_core.messages import AIMessage
import uuid
import markdown
from xhtml2pdf import pisa

async def report_node(state: AgentState, config: RunnableConfig):
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)

    try:
        # 直接使用大模型基于上下文和附加要求生成 Markdown 报告
        pdf_instructions = state.get("pdf_instructions", "")
        prompt = "请基于我们之前的完整探讨，撰写一份正式的、专业详尽的《技术立项白皮书》(PDF适用)。\n"
        if pdf_instructions:
            prompt += f"\n【用户特别嘱咐】：{pdf_instructions}\n"
        prompt += "\n报告结构应至少包含：1. 项目背景与痛点(Why) 2. 创新产品与商业价值(What/Value) 3. 技术方案架构(How) 4. OKRs与里程碑 5. 成本与资源。请确保排版精美，语言富有商业感染力与技术严谨性。"
        
        sys_msg = SystemMessage(content=prompt)
        result = await llm.ainvoke([sys_msg] + state["messages"])
        
        md_text = result.content
        
        # 注册中文字体以防止乱码
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        font_path = os.path.join(os.getcwd(), "static", "fonts", "simhei.ttf")
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('SimHei', font_path))
            
        # 将 Markdown 转换为 HTML
        html_content = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])
        
        # 为了兼容中文PDF，包装一层简单的 HTML 骨架和基础 CSS
        # xhtml2pdf 只有在明确指定被注册的字体名时才能正常渲染中文
        html_template = f"""
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: a4 portrait; margin: 2cm; }}
            body {{ font-family: "SimHei", sans-serif; font-size: 14px; line-height: 1.6; color: #333; }}
            h1 {{ color: #1e3a8a; text-align: center; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; font-family: "SimHei"; }}
            h2 {{ color: #2563eb; margin-top: 20px; font-family: "SimHei"; }}
            h3 {{ color: #3b82f6; font-family: "SimHei"; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 15px; font-family: "SimHei"; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f3f4f6; }}
            code {{ background-color: #f1f5f9; padding: 2px 4px; border-radius: 4px; font-family: monospace; }}
        </style>
        </head>
        <body>
        {html_content}
        </body>
        </html>
        """
        
        # 保存为 PDF
        report_id = str(uuid.uuid4())[:8]
        # 若是部署环境，建议映射到外部持久卷，这里放在当前目录的 static/reports 下
        reports_dir = os.path.join(os.getcwd(), "static", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        file_name = f"InnoReport_{report_id}.pdf"
        file_path = os.path.join(reports_dir, file_name)
        
        with open(file_path, "w+b") as result_file:
            pisa_status = pisa.CreatePDF(html_template.encode('utf-8'), dest=result_file)
            
        if pisa_status.err:
            raise Exception("PDF Generation Error by xhtml2pdf")
            
        download_url = f"/static/reports/{file_name}"
        
        # 尝试上传到外部数据后台
        import httpx
        username = config.get("configurable", {}).get("username")
        if not username:
            username = "anonymous"
            
        session_id = config.get("configurable", {}).get("thread_id", "unknown_session")
        project_name = state.get("how", {}).get("project_name", "未命名项目")
        
        api_base = os.environ.get("DATA_API_BASE_URL", "http://localhost:8080")
        external_api_key = os.environ.get("EXTERNAL_API_KEY", "")
        
        upload_status = ""
        if external_api_key:
            try:
                async with httpx.AsyncClient() as client:
                    with open(file_path, "rb") as f:
                        files = {'file': (file_name, f, 'application/pdf')}
                        data = {
                            'conversationId': session_id,
                            'title': project_name,
                            'username': username
                        }
                        headers = {"X-API-Key": external_api_key}
                        
                        resp = await client.post(
                            f"{api_base}/api/external/files",
                            data=data,
                            files=files,
                            headers=headers,
                            timeout=30.0
                        )
                        if str(resp.status_code).startswith("2"):
                            upload_status = "✅ 自动同步：报告已成功上传至数据后台归档！"
                        else:
                            upload_status = f"⚠️ 自动同步失败：HTTP {resp.status_code} - {resp.text}"
            except Exception as ex:
                upload_status = f"⚠️ 自动同步异常：网络请求失败或超时 ({str(ex)})"
        else:
            upload_status = "ℹ️ 未配置 EXTERNAL_API_KEY，跳过自动同步步骤。"

        success_msg = f"🎉 报告已生成！\n\n📄 **[点击此处下载《技术立项白皮书》 PDF 版]({download_url})**\n\n{upload_status}"
        
        # 由于我们取消了工具调用输出结构化数据，我们将直接返回现有 state 的 How 数据（通过之前 expert 的工具参数拿到）
        # 这里只需要追加生成的 PDF 下载链接
        return {
            "messages": [AIMessage(content=success_msg)],
            "current_phase": "FINISHED"
        }
    except Exception as e:
        err_msg = f"抱歉，PDF 报告生成过程中出现了错误: {str(e)}\n\n您可以稍后尝试重试。"
        return {"messages": [AIMessage(content=err_msg)]}


