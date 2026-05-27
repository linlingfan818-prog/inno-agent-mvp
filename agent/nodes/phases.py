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
    """当用户确认了商业价值(Value)与具体量化金额，并且做出是否生成报告的选择后，调用此工具进入技术路线(How)探讨。"""
    market_value: str = Field(description="总结提炼出的核心商业价值与市场分析")
    value_amount: str = Field(description="具体量化的商业价值预估(例如'50万元')")
    generate_value_report: bool = Field(description="用户是否选择生成商业价值报告PDF (若用户选择跳过则为False)")

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
    pdf_instructions: str = Field(description="用户对生成技术报告的附加要求")
    generate_technical_report: bool = Field(description="用户是否选择生成详细技术路径报告PDF (若用户选择无需报告只提报画布，则为False)")

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
        args = response.tool_calls[0].get("args", {})
        market_value_text = args.get("market_value", "")
        value_amount_text = args.get("value_amount", "")
        generate_report = args.get("generate_value_report", False)
        
        # 如果需要生成商业价值报告，我们先在系统消息里打个招呼
        if generate_report:
            reply_text = "[系统回复] 已确认价值。用户选择了生成《商业价值报告》。请输出一条简短的消息告知用户正在为您奋笔疾书撰写报告...，流程图将自动流转去生成PDF并随后进入 EXPERT 阶段。"
            next_phase = "VALUE_REPORT"
        else:
            reply_text = "[系统回复] 已确认价值。用户跳过了报告生成。请向用户打招呼并开始探讨技术和成本 (How)。"
            next_phase = "EXPERT"
            
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToExpert",
            content=reply_text
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": next_phase,
            "market_value": market_value_text,
            "value_amount": value_amount_text,
            "generate_value_report": generate_report
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
        generate_report = args.get("generate_technical_report", False)
        
        if generate_report:
            reply_text = "[系统回复] 已成功确认技术方案。用户选择了生成报告。请简短回复正在生成中..."
        else:
            reply_text = "[系统回复] 已成功确认技术方案。用户选择了无需报告。流程结束。"
            
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToDone",
            content=reply_text
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "DONE",
            "generate_tech_report": generate_report,
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
import httpx

async def _generate_pdf_and_upload(state: AgentState, config: RunnableConfig, prompt: str, report_type_name: str) -> str:
    """Helper function to generate PDF from prompt and upload it."""
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    # 1. 运行大模型生成 Markdown
    sys_msg = SystemMessage(content=prompt)
    result = await llm.ainvoke([sys_msg] + state["messages"])
    md_text = result.content
    
    # 2. 转为 HTML
    html_content = markdown.markdown(md_text, extensions=['tables', 'fenced_code'])
    
    # 3. 构建带中文字体的 HTML 骨架
    font_path = os.path.join(os.getcwd(), "static", "fonts", "simhei.ttf").replace('\\', '/')
    html_template = f"""
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        @font-face {{
            font-family: 'SimHei';
            src: url('{font_path}');
        }}
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
    
    # 4. 生成 PDF
    report_id = str(uuid.uuid4())[:8]
    reports_dir = os.path.join(os.getcwd(), "static", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    file_name = f"{report_type_name}_{report_id}.pdf"
    file_path = os.path.join(reports_dir, file_name)
    
    with open(file_path, "w+b") as result_file:
        pisa_status = pisa.CreatePDF(html_template.encode('utf-8'), dest=result_file)
        
    if pisa_status.err:
        raise Exception(f"PDF Generation Error by xhtml2pdf for {report_type_name}")
        
    download_url = f"/static/reports/{file_name}"
    
    # 5. 上传到外部数据后台
    username = config.get("configurable", {}).get("username", "anonymous")
    session_id = config.get("configurable", {}).get("thread_id", "unknown_session")
    
    # 如果阶段不同，可能还没产生 project_name，可以 fallback 取 title 或默认名字
    project_name = state.get("how", {}).get("project_name", f"创新项目_{report_id}")
    
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

    return f"📄 **[点击此处下载《{report_type_name}》 PDF 版]({download_url})**\n\n{upload_status}"

async def value_report_node(state: AgentState, config: RunnableConfig):
    try:
        prompt = "请基于我们之前的探讨，撰写一份非常详尽的《商业价值报告》(PDF适用)。\n"
        prompt += f"其中必须明确提到用户刚刚确认的量化商业价值预估：{state.get('value_amount', '未知')}\n"
        prompt += "报告结构应包含：1. 业务背景与核心痛点 2. 创新产品形态 3. 市场规模与商业潜力分析 4. 竞品对标与竞争壁垒 5. 预期量化收益与ROI评估。请充分发散，将之前零散的对话梳理成极具专业性和感染力的万字商业报告级别长文。"
        
        result_msg = await _generate_pdf_and_upload(state, config, prompt, "商业价值报告")
        success_msg = f"🎉 商业价值报告已生成完成！\n\n{result_msg}\n\n接下来，我们将自动进入技术与成本评估环节 (EXPERT 阶段)。"
        return {
            "messages": [AIMessage(content=success_msg)],
            "current_phase": "EXPERT"
        }
    except Exception as e:
        err_msg = f"抱歉，商业报告生成过程中出现了错误: {str(e)}\n\n由于失败，我们将跳过此报告直接进入下一步 (EXPERT)。"
        return {
            "messages": [AIMessage(content=err_msg)],
            "current_phase": "EXPERT"
        }

async def report_node(state: AgentState, config: RunnableConfig):
    generate_tech_report = state.get("generate_tech_report", False)
    if not generate_tech_report:
        # 用户选择了不生成详细报告，流程结束，把最终的完整数据流推向画布即可
        return {
            "messages": [AIMessage(content="🎉 已确认技术方案。根据您的选择，已跳过生成长篇详细技术报告。\n\n目前所有结构化核心字段均已提取完成并同步至您的创新画布中，您可以随时在平台进行下一步的投递或导出。")],
            "current_phase": "FINISHED"
        }

    try:
        # 用户选择生成详细技术报告
        pdf_instructions = state.get("pdf_instructions", "")
        prompt = "请基于我们之前的完整探讨，为您撰写一份极其详尽的《详细技术路径报告》(PDF适用)。\n"
        prompt += "【极度重要】：此报告是为了作为“补充详情辅助材料”，请不要仅仅局限于画布的那 8 个干瘪的字段！你必须极度发散、扩写、深挖细节！写得越完整、详尽越好，必须是一份专业的“技术立项万字长文”。\n"
        if pdf_instructions:
            prompt += f"\n【用户特别嘱咐】：{pdf_instructions}\n"
        prompt += "\n报告结构应至少包含：1. 项目背景与痛点深度解析 2. 详细技术方案架构与系统设计 3. 核心算法或关键技术难点 4. 数据安全与合规性 5. 详细的实施路径、资源拆解与风控应对方案。"
        
        result_msg = await _generate_pdf_and_upload(state, config, prompt, "详细技术路径报告")
        success_msg = f"🎉 技术报告已生成完成！\n\n{result_msg}\n\n目前所有结构化核心字段均已提取完成并同步至您的创新画布中，您可以随时在平台进行下一步的投递或导出。"
        
        return {
            "messages": [AIMessage(content=success_msg)],
            "current_phase": "FINISHED"
        }
    except Exception as e:
        err_msg = f"抱歉，技术报告生成过程中出现了错误: {str(e)}\n\n您可以稍后尝试重试。"
        return {"messages": [AIMessage(content=err_msg)]}


