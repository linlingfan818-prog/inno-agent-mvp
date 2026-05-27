# Inno-Agent MVP 前端交接指南与 API 文档

这份文档旨在帮助前端工程师快速理解当前后端的架构、数据流向以及 API 接口规范，以便用专业的现代前端框架（如 React/Vue/Next.js）替代当前的 MVP 测试页面。

## 1. 核心架构与交互逻辑

### 1.1 会话管理 (Session Management)
- 后端**不负责**维护用户的登录体系，所有对话通过唯一的 `session_id` 进行沙盒隔离。
- 前端需要负责生成和持久化 `session_id`（目前 MVP 是随机生成并存入 LocalStorage）。
- API 请求时必须携带当前活跃的 `session_id` 和用户配置的 `api_key`。
- **关键提醒**：切换会话时，建议采用 SPA（单页应用）路由模式，不要强制刷新页面（`window.location.reload`），以免阻断后端尚未结束的长连接 SSE 推送。

### 1.2 SSE (Server-Sent Events) 双通道推送
对话接口 `/api/v1/chat` 采用流式输出，并且混合了两种不同类型的 Event：
- `event: message`：大模型吐出的打字机流式字符，前端需要将它们拼接显示。
- `event: state_update`：大模型在思考后改变了右侧画布的状态（比如产出了痛点分析或技术方案），前端需要捕获此事件并更新右侧的资料库 UI。

---

## 2. API 接口规范

所有的接口 Base URL 均为：`http://<后端服务器IP>:8002`

### 2.1 连通性测试接口
用于在进入核心交互前，测试用户配置的 API Key 是否有效。

- **Endpoint**: `POST /api/v1/check-key`
- **Content-Type**: `application/json`
- **Payload**:
  ```json
  {
    "api_key": "sk-xxxxx"
  }
  ```
- **Response**:
  ```json
  // 成功
  { "status": "success", "message": "API Key 验证通过！连接正常。" }
  
  // 失败
  { "status": "error", "message": "连接失败: 具体的报错信息" }
  ```

### 2.2 核心对话流接口 (SSE)
发送用户消息，并监听后端的流式返回。

- **Endpoint**: `POST /api/v1/chat`
- **Content-Type**: `application/json`
- **Payload**:
  ```json
  {
    "message": "用户输入的内容",
    "session_id": "前端生成的唯一ID",
    "api_key": "sk-xxxxx"
  }
  ```
- **SSE Response 示例**:
  前端需要使用 `fetch` 结合 `ReadableStream` 或者 `EventSource` 的方式监听返回的数据块。

  *文本流（打字机效果）：*
  ```text
  event: message
  data: {"chunk": "您"}
  
  event: message
  data: {"chunk": "好！"}
  ```

  *状态更新流（更新右侧画布）：*
  ```text
  event: state_update
  data: {"current_phase": "PM", "why": "跨部门沟通难...", "what": null, "how": null}
  ```
  > **注意**：`state_update` 事件可能在 `message` 事件之间穿插出现，前端需根据 `event` 名称分别处理。

### 2.3 获取历史记录接口
当用户重新进入页面或切换到其他 `session_id` 时，调用此接口拉取完整的对话记录和画布状态。

- **Endpoint**: `GET /api/v1/history/{session_id}`
- **Response**:
  ```json
  {
    "current_phase": "FINISHED",
    "why": "提取出的核心痛点文本",
    "what": "提取出的产品落地方案",
    "how": {
        "cost": "130-155",
        "milestones": {
            "M1": "基础设施搭建",
            "M2": "知识库构建",
            "M3": "插件开发",
            "M4": "灰度验证"
        }
    },
    "messages": [
      {
        "role": "user",
        "content": "我有个跨部门沟通难的问题"
      },
      {
        "role": "ai",
        "content": "好的，我们来挖掘一下..."
      }
    ]
  }
  ```

---

## 3. 给前端同事的建议

> [!TIP]
> 1. **大模型格式化渲染**：后端的 AI 返回的消息（`msg.content` 或 `chunk`）可能包含 Markdown 语法（加粗 `**`、换行 `\n` 等），甚至包含类似 `[选项A]直接购买现成系统` 这样的选项结构。建议前端直接引入类似 `react-markdown` 这样的库进行标准渲染。
> 2. **断线重连与防抖**：由于后端 LangGraph 生成最后结题报告时，没有文字流推送，大概会有 3~8 秒的静默处理期。前端在发送按钮上最好加上 `Loading` 状态，防止用户不耐烦疯狂连点导致脏数据。
> 3. **画布动画体验**：当收到 `event: state_update` 时，右侧的资料库数据会突然刷新。建议给右侧卡片加上类似骨架屏或内容替换时的渐变微动效（Fade-in），能让整体产品显得非常高级（WOW moment！）。

如果前端同学在联调时有遇到跨域（CORS）问题，后端目前的 `main.py` 已经开放了全域允许 (`allow_origins=["*"]`)，原则上可以直接跑通。如果有特定的 Headers 限制，可随时联系修改后端 CORS 配置。
