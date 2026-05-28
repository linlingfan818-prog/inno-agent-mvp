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
    """当用户确认了商业价值(Value)与具体量化金额，并且同意进入技术路线(How)探讨时调用此工具。"""
    market_value: str = Field(description="总结提炼出的核心商业价值与市场分析")
    value_amount: str = Field(description="具体量化的商业价值预估(例如'50万元')")

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

class TransitionToPhase(BaseModel):
    """【时空穿梭工具】：当用户明确要求跳回或修改之前阶段的内容（例如：重新讨论痛点、重新定义产品）时，必须调用此工具跳转到指定阶段，不可在当前阶段强答。"""
    target_phase: str = Field(description="目标阶段，必须是以下之一: COACH (痛点), PM (产品), VALUE (商业价值), EXPERT (技术实现)")

class AnalyzeContextImpact(BaseModel):
    """【时空穿梭冲突检测工具】：当用户在当前阶段对核心信息做出了实质性的修改或补充，且这些修改可能影响后续阶段（若有）的上下文时调用此工具。"""
    changed_information: str = Field(description="用户补充或修改的具体信息内容")
    current_phase: str = Field(description="当前所在的阶段名称")

class GenerateValueReport(BaseModel):
    """【生成商业价值报告工具】：当用户选择生成商业价值报告时调用此工具。此工具【不会】导致阶段跳转，仅生成报告。"""
    additional_instructions: str = Field(description="用户补充的生成要求(如有)")

class GenerateTechReport(BaseModel):
    """【生成技术路径报告工具】：当用户选择生成技术路径报告时调用此工具。此工具【不会】导致阶段跳转，仅生成报告。"""
    additional_instructions: str = Field(description="用户补充的生成要求(如有)")

# Helper to read prompts
def get_sys_prompt(filename: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return f"【缺少提示词文件: {filename}】"

async def process_single_tool(tc, state: AgentState, config: RunnableConfig, current_phase: str):
    """处理单个工具调用，返回 (ToolMessage, state_updates)"""
    t_name = tc["name"]
    t_id = tc["id"]
    args = tc.get("args", {})
    
    if t_name == "TransitionToPhase":
        target = args.get("target_phase", "COACH").upper()
        if target not in ["COACH", "PM", "VALUE", "EXPERT"]: target = "COACH"
        return ToolMessage(tool_call_id=t_id, name=t_name, content=f"[系统回复] 时空穿梭成功。状态已退回至 {target} 阶段。请向用户打招呼并顺着他的话题重新探讨。原有数据已保留，无需重复收集用户未修改的部分。"), {"current_phase": target}
        
    elif t_name == "AnalyzeContextImpact":
        info = args.get("changed_information", "")
        return ToolMessage(tool_call_id=t_id, name=t_name, content=f"[系统回复] 已记录关于 '{info}' 的变更。请根据此变更调整后续探讨方向。"), {}

    elif t_name == "GenerateValueReport":
        if not state.get("value_amount"):
            return ToolMessage(tool_call_id=t_id, name=t_name, content="[系统回复] 拦截：无法生成商业报告。因为系统还没有收集到明确的商业价值预估(value_amount)。请先和用户探讨商业价值并引导用户确认金额。"), {}
        try:
            prompt = "请生成一份《商业价值报告》。"
            extra = args.get("additional_instructions", "")
            if extra: prompt += f"【用户的补充要求】：{extra}\n"
            prompt += "报告结构应包含：1. 业务背景与核心痛点 2. 创新产品形态 3. 市场规模与商业潜力分析 4. 竞品对标与竞争壁垒 5. 预期量化收益与ROI评估。"
            result_msg = await _generate_markdown_and_upload(state, config, prompt, "商业价值报告")
            return ToolMessage(tool_call_id=t_id, name=t_name, content=f"[系统回复] 商业价值报告生成成功：\n{result_msg}\n【系统强制指令】：报告已生成并保存。你在接下来的回复中【绝对不可以】输出报告正文。你必须向用户提供下载链接，并抛出选择题询问用户：‘报告已生成，请问您对报告内容是否有补充？如果确认无误，我们可以进入下一阶段。’ 选项必须为：\n[选项A] ✅ 报告没问题，确认进入下一阶段\n[选项B] ✏️ 我需要补充或调整一些内容..."), {}
        except Exception as e:
            return ToolMessage(tool_call_id=t_id, name=t_name, content=f"[系统回复] 生成失败：{str(e)}\n请委婉告知用户报错情况。"), {}

    elif t_name == "GenerateTechReport":
        if not state.get("how") or not state["how"].get("cost"):
            return ToolMessage(tool_call_id=t_id, name=t_name, content="[系统回复] 拦截：无法生成技术报告。因为系统还没有收集到技术里程碑(how)等核心信息。请向用户解释并引导其完成相关探讨。"), {}
        try:
            prompt = "请生成一份《详细技术路径报告》。"
            extra = args.get("additional_instructions", "")
            if extra: prompt += f"【用户的补充要求】：{extra}\n"
            prompt += "报告结构应至少包含：1. 项目背景与痛点深度解析 2. 详细技术方案架构与系统设计 3. 核心算法或关键技术难点 4. 数据安全与合规性 5. 详细的实施路径、资源拆解与风控应对方案。"
            result_msg = await _generate_markdown_and_upload(state, config, prompt, "技术路径报告")
            return ToolMessage(tool_call_id=t_id, name=t_name, content=f"[系统回复] 技术路径报告生成成功：\n{result_msg}\n【系统强制指令】：报告已生成并保存。你在接下来的回复中【绝对不可以】输出报告正文。你必须向用户提供下载链接，并抛出选择题询问用户：‘技术报告已生成，请问您对报告内容是否有补充？如果确认无误，我们可以结项。’ 选项必须为：\n[选项A] ✅ 报告没问题，确认结项\n[选项B] ✏️ 我需要补充或调整一些内容..."), {}
        except Exception as e:
            return ToolMessage(tool_call_id=t_id, name=t_name, content=f"[系统回复] 生成失败：{str(e)}\n请委婉告知用户报错情况。"), {}

    # Node specific handling
    if current_phase == "COACH" and t_name == "TransitionToPM":
        why_text = args.get("why", "")
        return ToolMessage(tool_call_id=t_id, name=t_name, content="[系统回复] 已成功切换至 PM 阶段。请向用户打招呼并开始探讨产品细节 (What)。"), {"current_phase": "PM", "why": why_text}
        
    elif current_phase == "PM" and t_name == "TransitionToValue":
        what_text = args.get("what", "")
        return ToolMessage(tool_call_id=t_id, name=t_name, content="[系统回复] 已成功切换至 VALUE 阶段。请向用户打招呼并开始探讨市场价值与商业潜力。"), {"current_phase": "VALUE", "what": what_text}
        
    elif current_phase == "VALUE" and t_name == "TransitionToExpert":
        market_value_text = args.get("market_value", "")
        value_amount_text = args.get("value_amount", "")
        
        reply_text = f"[系统回复] 已确认价值，已成功切换至 EXPERT 阶段。请向用户打招呼并开始探讨技术路线。"
        return ToolMessage(tool_call_id=t_id, name=t_name, content=reply_text), {
            "current_phase": "EXPERT", "market_value": market_value_text, "value_amount": value_amount_text
        }
        
    elif (current_phase == "EXPERT" or current_phase == "FINISHED") and t_name == "TransitionToDone":
        temp_how = {
            "project_name": args.get("project_name", ""),
            "how_overview": args.get("how_overview", ""),
            "scope": args.get("scope", ""),
            "objective": args.get("objective", ""),
            "key_results": args.get("key_results", ""),
            "cost": args.get("cost", ""),
            "milestones": {
                "M1": args.get("m1", ""), "M2": args.get("m2", ""), "M3": args.get("m3", ""), "M4": args.get("m4", "")
            }
        }
        
        reply_text = "[系统回复] 已成功确认技术方案，阶段变更为 FINISHED。请告知用户已顺利结项。"
        return ToolMessage(tool_call_id=t_id, name=t_name, content=reply_text), {
            "current_phase": "FINISHED", "how": temp_how
        }
        
    # Unhandled tool fallback
    return ToolMessage(tool_call_id=t_id, name=t_name, content=f"[系统回复] 错误：无法在当前阶段({current_phase})调用工具 {t_name}，或者参数错误。请勿再尝试调用此工具，直接回复用户。"), {}


async def coach_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("coach.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToPM, TransitionToPhase, GenerateValueReport, GenerateTechReport])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls:
        tool_messages = []
        state_updates = {}
        for tc in response.tool_calls:
            msg, updates = await process_single_tool(tc, state, config, "COACH")
            tool_messages.append(msg)
            state_updates.update(updates)
        return {"messages": [response] + tool_messages, **state_updates}
        
    return {"messages": [response]}

async def pm_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("pm.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToValue, TransitionToPhase, GenerateValueReport, GenerateTechReport])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls:
        tool_messages = []
        state_updates = {}
        for tc in response.tool_calls:
            msg, updates = await process_single_tool(tc, state, config, "PM")
            tool_messages.append(msg)
            state_updates.update(updates)
        return {"messages": [response] + tool_messages, **state_updates}
        
    return {"messages": [response]}

async def value_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("value.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToExpert, TransitionToPhase, GenerateValueReport, GenerateTechReport])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls:
        tool_messages = []
        state_updates = {}
        for tc in response.tool_calls:
            msg, updates = await process_single_tool(tc, state, config, "VALUE")
            tool_messages.append(msg)
            state_updates.update(updates)
        return {"messages": [response] + tool_messages, **state_updates}
        
    return {"messages": [response]}

async def expert_node(state: AgentState, config: RunnableConfig):
    sys_content = get_sys_prompt("expert.md")
    sys_msg = SystemMessage(content=sys_content)
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    llm_with_tools = llm.bind_tools([TransitionToDone, TransitionToPhase, GenerateValueReport, GenerateTechReport])
    response = await llm_with_tools.ainvoke([sys_msg] + state["messages"])
    
    if response.tool_calls:
        tool_messages = []
        state_updates = {}
        # Support FINISHED phase chatting directly with expert_node
        phase_name = state.get("current_phase", "EXPERT")
        for tc in response.tool_calls:
            msg, updates = await process_single_tool(tc, state, config, phase_name)
            tool_messages.append(msg)
            state_updates.update(updates)
        return {"messages": [response] + tool_messages, **state_updates}
        
    return {"messages": [response]}

import urllib.parse
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
import uuid
import re
import httpx

async def _generate_markdown_and_upload(state: AgentState, config: RunnableConfig, prompt: str, report_type_name: str) -> str:
    """Helper function to generate Markdown from prompt and upload it."""
    
    # 映射英文缩写，用于规避第三方后端乱码
    report_type_name_en = "Value" if "商业" in report_type_name else "Tech"
    
    api_key = config.get("configurable", {}).get("api_key")
    llm = initialize_llm(custom_api_key=api_key)
    
    # 1. 运行大模型生成 Markdown
    # ⚠️关键修复：为了彻底避免大模型在聊天上下文中产生“寒暄”或因为多轮对话格式要求导致 VertexAI 报错，
    # 我们将所有的历史记录提取为纯文本，放到一个全新的、无历史包袱的单轮 Prompt 中强制生成。
    conversation_text = ""
    for msg in state["messages"]:
        if isinstance(msg.content, str) and msg.content.strip():
            role = "AI" if msg.type == "ai" else "用户" if msg.type == "human" else "系统"
            conversation_text += f"[{role}]: {msg.content}\n"
            
    final_prompt = f"""
【任务目标】
请你作为一个专业的报告撰写专家，根据以下提供的全部项目讨论记录，撰写一份正式的《{report_type_name}》。

【强制格式要求】
1. 必须且只能输出 Markdown 正文，绝对不能包含任何聊天寒暄语（如“好的”、“没问题”、“这就为您生成”等）。
2. 直接以 `# ` 标题开始输出。
3. 结尾请以 `— 报告完 —` 结束，**绝对不要**在报告末尾包含任何对话选项、提问或类似“[选项A]”的内容。
4. {prompt}

【历史讨论记录】
{conversation_text}
"""
    
    sys_msg = SystemMessage(content="你是一个无情的专业报告生成机器，只输出报告正文，绝不说废话。")
    user_msg = HumanMessage(content=final_prompt)
    
    result = await llm.ainvoke([sys_msg, user_msg], config={"tags": ["hide_stream"]})
    md_text = result.content
    
    if not md_text or not md_text.strip() or "好的" in md_text[:20] or "稍候" in md_text or "稍等" in md_text:
        raise Exception("大模型生成了空内容，生成失败。")
        
    # 2. 提取项目名称并清理非法字符以用作文件名
    project_name_raw = state.get("how", {}).get("project_name", "")
    if not project_name_raw:
        # 兜底：如果 how 阶段还没走到，用 what，或者直接叫创新项目
        project_name_raw = state.get("what", "创新项目")
        # 如果太长，截断一下
        if len(project_name_raw) > 20:
            project_name_raw = project_name_raw[:20]
            
    # 清理 Windows 非法字符
    clean_project_name = re.sub(r'[\\/*?:"<>|]', "", project_name_raw).strip()
    if not clean_project_name:
        clean_project_name = "未命名项目"
        
    report_id = str(uuid.uuid4())[:8]
    reports_dir = os.path.join(os.getcwd(), "static", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    # 如果文件名冲突，加个随机 ID
    file_name = f"{clean_project_name}_{report_type_name}.md"
    file_path = os.path.join(reports_dir, file_name)
    if os.path.exists(file_path):
        file_name = f"{clean_project_name}_{report_type_name}_{report_id}.md"
        file_path = os.path.join(reports_dir, file_name)
    
    # 3. 写入 Markdown 文件
    with open(file_path, "w", encoding="utf-8") as result_file:
        result_file.write(md_text)
        
    # 修复中文文件名在浏览器下载时乱码的问题 (URL Encode + 强制 Content-Disposition)
    encoded_file_name = urllib.parse.quote(file_name)
    download_url = f"/api/download?file={encoded_file_name}"
    
    # 4. 上传到外部数据后台
    username = config.get("configurable", {}).get("username", "anonymous")
    session_id = config.get("configurable", {}).get("thread_id", "unknown_session")
    
    api_base = os.environ.get("DATA_API_BASE_URL", "http://localhost:8080")
    external_api_key = os.environ.get("EXTERNAL_API_KEY", "")
    
    upload_status = ""
    if external_api_key:
        try:
            async with httpx.AsyncClient() as client:
                with open(file_path, "rb") as f:
                    # ⚠️ 关键修复：老旧的外部 Java/Tomcat 后端在解析 Multipart/form-data 时默认使用 ISO-8859-1。
                    # 如果传中文 filename 会导致不可逆的乱码（如 ä¸ä¸ª...）。
                    # 因此物理上传的文件名采用纯英文+ID，而将真正的中文名放在 title 字段中传递！
                    safe_upload_name = f"Report_{report_type_name_en}_{report_id}.md"
                    files = {'file': (safe_upload_name, f, 'text/markdown')}
                    data = {
                        'conversationId': session_id,
                        'title': clean_project_name, # 后端通常能正确以 UTF-8 解析表单字段
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

    return f"📄 《{report_type_name}》已生成完毕。\n\n{upload_status}\n\n👉 请您前往您的专属数据后台系统查看或下载该报告。\n\n*(测试环境临时预览通道)：***[点击此处直接查看/下载报告]({download_url})**"
