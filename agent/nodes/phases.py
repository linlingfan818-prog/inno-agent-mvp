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
    """当用户确认了最终的技术路线和落地方案(How)，并且同意结束讨论时调用此工具。"""
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
    pdf_instructions: str = Field(description="用户对生成技术报告的附加要求(如有)")
    generate_technical_report: bool = Field(description="用户是否选择一并生成详细技术路径报告PDF (若用户选择无需报告只提报画布，则为False)")

class TransitionToPhase(BaseModel):
    """【时空穿梭工具】：当用户明确要求跳回或修改之前阶段的内容（例如：重新讨论痛点、重新定义产品）时，必须调用此工具跳转到指定阶段，不可在当前阶段强答。"""
    target_phase: str = Field(description="目标阶段，必须是以下之一: COACH (痛点), PM (产品), VALUE (商业价值), EXPERT (技术实现)")

class GenerateValueReport(BaseModel):
    """【万能生成工具】：当用户在任何时候单独要求“重新生成”或“补充生成”【商业价值报告】时调用此工具。注意：必须满足前置条件(已有价值金额)才能成功。"""
    additional_instructions: str = Field(description="用户补充的生成要求(如有)")

class GenerateTechReport(BaseModel):
    """【万能生成工具】：当用户在任何时候单独要求“重新生成”或“补充生成”【技术路径报告】时调用此工具。注意：必须满足前置条件(已有技术方案)才能成功。"""
    additional_instructions: str = Field(description="用户补充的生成要求(如有)")

# Helper to read prompts
def get_sys_prompt(filename: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return f"【缺少提示词文件: {filename}】"

async def handle_universal_tools(response, state: AgentState, config: RunnableConfig):
    """处理全局通用的时空穿梭和文档生成工具"""
    if not response.tool_calls:
        return None
        
    tool_name = response.tool_calls[0]["name"]
    tool_call_id = response.tool_calls[0]["id"]
    args = response.tool_calls[0].get("args", {})
    
    if tool_name == "TransitionToPhase":
        target = args.get("target_phase", "COACH").upper()
        if target not in ["COACH", "PM", "VALUE", "EXPERT"]:
            target = "COACH"
        tool_msg = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=f"[系统回复] 时空穿梭成功。状态已退回至 {target} 阶段。请向用户打招呼并顺着他的话题重新探讨。原有数据已保留，无需重复收集用户未修改的部分。")
        return {"messages": [response, tool_msg], "current_phase": target}
        
    elif tool_name == "GenerateValueReport":
        if not state.get("value_amount"):
            tool_msg = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content="[系统回复] 拦截：无法生成商业报告。因为系统还没有收集到明确的商业价值预估(value_amount)。请先和用户探讨商业价值并引导用户确认金额。")
            return {"messages": [response, tool_msg]}
        try:
            extra = args.get("additional_instructions", "")
            prompt = "请基于我们之前的探讨，撰写一份非常详尽的《商业价值报告》(PDF适用)。\n"
            prompt += f"其中必须明确提到用户刚刚确认的量化商业价值预估：{state.get('value_amount', '未知')}\n"
            prompt += f"【用户的补充要求】：{extra}\n"
            prompt += "报告结构应包含：1. 业务背景与核心痛点 2. 创新产品形态 3. 市场规模与商业潜力分析 4. 竞品对标与竞争壁垒 5. 预期量化收益与ROI评估。"
            result_msg = await _generate_pdf_and_upload(state, config, prompt, "商业价值报告")
            tool_msg = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=f"[系统回复] 生成成功：\n{result_msg}\n请告知用户报告已生成。")
        except Exception as e:
            tool_msg = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=f"[系统回复] 生成失败：{str(e)}\n请委婉告知用户报错情况。")
        return {"messages": [response, tool_msg]}
        
    elif tool_name == "GenerateTechReport":
        if not state.get("how") or not state["how"].get("cost"):
            tool_msg = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content="[系统回复] 拦截：无法生成技术报告。因为系统还没有收集到技术里程碑(how)等核心信息。请向用户解释并引导其完成相关探讨。")
            return {"messages": [response, tool_msg]}
        try:
            extra = args.get("additional_instructions", "")
            prompt = "请基于我们之前的完整探讨，为您撰写一份极其详尽的《详细技术路径报告》(PDF适用)。\n"
            prompt += f"【用户的补充要求】：{extra}\n"
            prompt += "报告结构应至少包含：1. 项目背景与痛点深度解析 2. 详细技术方案架构与系统设计 3. 核心算法或关键技术难点 4. 数据安全与合规性 5. 详细的实施路径、资源拆解与风控应对方案。"
            result_msg = await _generate_pdf_and_upload(state, config, prompt, "详细技术路径报告")
            tool_msg = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=f"[系统回复] 生成成功：\n{result_msg}\n请告知用户报告已生成。")
        except Exception as e:
            tool_msg = ToolMessage(tool_call_id=tool_call_id, name=tool_name, content=f"[系统回复] 生成失败：{str(e)}\n请委婉告知用户报错情况。")
        return {"messages": [response, tool_msg]}
        
    return None

async def coach_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("coach.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToPM, TransitionToPhase, GenerateValueReport, GenerateTechReport])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    uni_result = await handle_universal_tools(response, state, config)
    if uni_result: return uni_result
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToPM":
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
    
    llm_with_tools = llm.bind_tools([TransitionToValue, TransitionToPhase, GenerateValueReport, GenerateTechReport])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    uni_result = await handle_universal_tools(response, state, config)
    if uni_result: return uni_result
    
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
    
    llm_with_tools = llm.bind_tools([TransitionToExpert, TransitionToPhase, GenerateValueReport, GenerateTechReport])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    uni_result = await handle_universal_tools(response, state, config)
    if uni_result: return uni_result
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToExpert":
        tool_call_id = response.tool_calls[0]["id"]
        args = response.tool_calls[0].get("args", {})
        market_value_text = args.get("market_value", "")
        value_amount_text = args.get("value_amount", "")
        generate_report = args.get("generate_value_report", False)
        
        reply_text = "[系统回复] 已确认价值。已成功切换至 EXPERT 阶段。请向用户打招呼并开始探讨技术和成本 (How)。"
        
        # 实时生成报告逻辑
        if generate_report:
            try:
                # Mock state update logic just for generating report instantly
                temp_state = dict(state)
                temp_state["value_amount"] = value_amount_text
                prompt = "请基于我们之前的探讨，撰写一份非常详尽的《商业价值报告》(PDF适用)。\n"
                prompt += f"其中必须明确提到用户刚刚确认的量化商业价值预估：{value_amount_text}\n"
                prompt += "报告结构应包含：1. 业务背景与核心痛点 2. 创新产品形态 3. 市场规模与商业潜力分析 4. 竞品对标与竞争壁垒 5. 预期量化收益与ROI评估。"
                result_msg = await _generate_pdf_and_upload(temp_state, config, prompt, "商业价值报告")
                reply_text = f"[系统回复] 已确认价值。已成功切换至 EXPERT 阶段。同时，商业报告生成成功：\n{result_msg}\n请一并告知用户并打招呼探讨技术。"
            except Exception as e:
                reply_text = f"[系统回复] 已确认价值。已成功切换至 EXPERT 阶段。但商业报告生成失败：{str(e)}\n请告知用户。"
            
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToExpert",
            content=reply_text
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "EXPERT",
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
    
    llm_with_tools = llm.bind_tools([TransitionToDone, TransitionToPhase, GenerateValueReport, GenerateTechReport])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    uni_result = await handle_universal_tools(response, state, config)
    if uni_result: return uni_result
    
    if response.tool_calls and response.tool_calls[0]["name"] == "TransitionToDone":
        tool_call_id = response.tool_calls[0]["id"]
        args = response.tool_calls[0].get("args", {})
        generate_report = args.get("generate_technical_report", False)
        
        reply_text = "[系统回复] 已成功确认技术方案，阶段变更为 FINISHED。用户选择了无需报告。流程结束。"
        
        temp_how = {
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
        
        if generate_report:
            try:
                temp_state = dict(state)
                temp_state["how"] = temp_how
                pdf_instructions = args.get("pdf_instructions", "")
                prompt = "请基于我们之前的完整探讨，为您撰写一份极其详尽的《详细技术路径报告》(PDF适用)。\n"
                if pdf_instructions: prompt += f"【用户特别嘱咐】：{pdf_instructions}\n"
                prompt += "报告结构应至少包含：1. 项目背景与痛点深度解析 2. 详细技术方案架构与系统设计 3. 核心算法或关键技术难点 4. 数据安全与合规性 5. 详细的实施路径、资源拆解与风控应对方案。"
                result_msg = await _generate_pdf_and_upload(temp_state, config, prompt, "详细技术路径报告")
                reply_text = f"[系统回复] 已成功确认技术方案，阶段变更为 FINISHED。技术报告生成成功：\n{result_msg}\n请告知用户。"
            except Exception as e:
                reply_text = f"[系统回复] 已成功确认技术方案，阶段变更为 FINISHED。但技术报告生成失败：{str(e)}\n请告知用户。"
            
        tool_msg = ToolMessage(
            tool_call_id=tool_call_id,
            name="TransitionToDone",
            content=reply_text
        )
        return {
            "messages": [response, tool_msg],
            "current_phase": "FINISHED",
            "generate_tech_report": generate_report,
            "pdf_instructions": args.get("pdf_instructions", ""),
            "how": temp_how
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
            font-family: SimHei;
            src: url('{font_path}');
        }}
        @page {{ size: a4 portrait; margin: 2cm; }}
        body {{ font-family: SimHei; font-size: 14px; line-height: 1.6; color: #333; }}
        h1 {{ color: #1e3a8a; text-align: center; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; font-family: SimHei; }}
        h2 {{ color: #2563eb; margin-top: 20px; font-family: SimHei; }}
        h3 {{ color: #3b82f6; font-family: SimHei; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 15px; font-family: SimHei; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f3f4f6; }}
        code {{ background-color: #f1f5f9; padding: 2px 4px; border-radius: 4px; font-family: SimHei; }}
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

    return f"📄 《{report_type_name}》已生成完毕。\n\n{upload_status}\n\n👉 请您前往您的专属数据后台系统查看或下载该报告。\n\n*(测试环境临时预览通道)：***[点击此处直接下载PDF进行乱码测试]({download_url})**"

# 删除了废弃的 value_report_node 和 report_node 节点


