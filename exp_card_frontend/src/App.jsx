import { useEffect, useMemo, useState } from 'react'
import { confirmParsed, generateCard, getDownloadUrl, healthCheck, uploadFile } from './api'

const emptyCharter = {
  project_name: '',
  project_scope: '',
  stakeholders_now: [],
  stakeholders_future: [],
  objectives: [],
  key_results: [],
  milestones: [],
  value_points: [],
  cost_points: [],
  raw_text: '',
  parse_notes: '',
}

function arrayToText(value) {
  return Array.isArray(value) ? value.join('\n') : ''
}

function textToArray(value) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean)
}

export default function App() {
  const [health, setHealth] = useState(null)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', content: '请上传一页项目 charter（推荐 .pptx）。我会先解析内容，等你确认无误后再生成创新实验卡。' },
  ])
  const [sessionId, setSessionId] = useState('')
  const [parsed, setParsed] = useState(emptyCharter)
  const [warnings, setWarnings] = useState([])
  const [experimentCard, setExperimentCard] = useState(null)
  const [downloadUrl, setDownloadUrl] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    healthCheck().then(setHealth).catch(() => {})
  }, [])

  const editableFields = useMemo(() => [
    ['project_name', '项目名称', 'text'],
    ['project_scope', 'Project Scope', 'textarea'],
    ['stakeholders_now', '当前 Stakeholders', 'list'],
    ['stakeholders_future', '未来 Stakeholders', 'list'],
    ['objectives', 'Objectives', 'list'],
    ['key_results', 'Key Results', 'list'],
    ['milestones', 'Milestones', 'list'],
    ['value_points', 'Value Points', 'list'],
    ['cost_points', 'Cost Points', 'list'],
    ['parse_notes', '解析备注', 'textarea'],
  ], [])

  const pushChat = (role, content) => {
    setChatMessages((prev) => [...prev, { role, content }])
  }

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    setExperimentCard(null)
    setDownloadUrl('')
    pushChat('user', `上传文件：${file.name}`)
    try {
      const data = await uploadFile(file)
      setSessionId(data.session_id)
      setParsed(data.parsed_charter)
      setWarnings(data.warnings || [])
      pushChat(
        'assistant',
        `已完成解析。请检查右侧字段是否正确，确认后点击“确认解析内容”，再点击“开始分析生成实验卡”。`
      )
      if (data.warnings?.length) {
        pushChat('assistant', `解析提示：${data.warnings.join('；')}`)
      }
    } catch (e) {
      setError(e.message)
      pushChat('assistant', `解析失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleFieldChange = (key, type, value) => {
    setParsed((prev) => ({
      ...prev,
      [key]: type === 'list' ? textToArray(value) : value,
    }))
  }

  const handleConfirm = async () => {
    if (!sessionId) return
    setLoading(true)
    setError('')
    try {
      await confirmParsed(sessionId, parsed)
      pushChat('user', '我已确认解析内容无误。')
      pushChat('assistant', '已保存确认结果。现在可以点击“开始分析生成实验卡”。')
    } catch (e) {
      setError(e.message)
      pushChat('assistant', `确认失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!sessionId) return
    setLoading(true)
    setError('')
    try {
      pushChat('user', '开始分析并生成实验卡。')
      const data = await generateCard(sessionId, parsed)
      setExperimentCard(data.experiment_card)
      setDownloadUrl(getDownloadUrl(data.docx_download_url))
      pushChat('assistant', '实验卡已生成完成。你可以在下方查看结果，并下载 Word 文档。')
    } catch (e) {
      setError(e.message)
      pushChat('assistant', `生成失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="header">
        <div>
          <h1>创新实验卡生成器</h1>
          <p>上传一页项目企划书，确认解析结果后，一键生成 Word 实验卡。</p>
        </div>
        <div className="status-box">
          <div>后端状态：{health?.status || '未连接'}</div>
          <div>模型：{health?.model || '-'}</div>
          <div>图片直读：{health?.image_input_enabled ? '开启' : '关闭'}</div>
        </div>
      </div>

      <div className="main-grid">
        <section className="card">
          <h2>聊天与上传</h2>
          <div className="upload-row">
            <input type="file" accept=".pptx,.png,.jpg,.jpeg,.webp" onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <button onClick={handleUpload} disabled={!file || loading}>{loading ? '处理中...' : '上传并解析'}</button>
          </div>
          {error ? <div className="error">{error}</div> : null}
          {warnings.length ? <div className="warning">{warnings.join('；')}</div> : null}
          <div className="chat-box">
            {chatMessages.map((msg, idx) => (
              <div key={idx} className={`msg ${msg.role}`}>
                <div className="role">{msg.role === 'assistant' ? 'Assistant' : 'User'}</div>
                <div>{msg.content}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <h2>解析结果确认</h2>
          <div className="form-grid">
            {editableFields.map(([key, label, type]) => (
              <label key={key} className="field">
                <span>{label}</span>
                {type === 'text' ? (
                  <input value={parsed[key] || ''} onChange={(e) => handleFieldChange(key, type, e.target.value)} />
                ) : (
                  <textarea
                    rows={type === 'list' ? 4 : 6}
                    value={type === 'list' ? arrayToText(parsed[key]) : (parsed[key] || '')}
                    onChange={(e) => handleFieldChange(key, type, e.target.value)}
                  />
                )}
              </label>
            ))}
          </div>
          <div className="action-row">
            <button onClick={handleConfirm} disabled={!sessionId || loading}>确认解析内容</button>
            <button className="primary" onClick={handleGenerate} disabled={!sessionId || loading}>开始分析生成实验卡</button>
          </div>
        </section>
      </div>

      <section className="card result-card">
        <h2>实验卡结果</h2>
        {!experimentCard ? <p>还没有生成实验卡。</p> : (
          <div className="result-grid">
            <div>
              <h3>{experimentCard.project_name}</h3>
              <p><strong>核心假设：</strong>{experimentCard.core_hypothesis}</p>
              <p><strong>实验周期：</strong>{experimentCard.experiment_cycle}</p>
              <p><strong>实验方法：</strong>{experimentCard.experiment_method}</p>
              <h4>实验步骤</h4>
              <ul>{experimentCard.experiment_steps?.map((x, i) => <li key={i}>{x}</li>)}</ul>
              <h4>成功指标</h4>
              <ul>{experimentCard.success_metrics?.map((x, i) => <li key={i}>{x}</li>)}</ul>
              <h4>完成状态评估清单</h4>
              <ul>{experimentCard.completion_checklist?.map((x, i) => <li key={i}>{x}</li>)}</ul>
              
              {experimentCard.critical_acceptance_standard && (
                <div style={{ backgroundColor: '#fff3cd', padding: '15px', borderRadius: '8px', marginTop: '20px', border: '1px solid #ffeeba' }}>
                  <h4 style={{ color: '#856404', marginTop: 0 }}>🚨 关键验收标准 (Critical Acceptance Standard)</h4>
                  <p><strong>验收环境与前提：</strong>{experimentCard.critical_acceptance_standard.environment_and_prerequisites}</p>
                  <p><strong>核心通关指标 (Must-have)：</strong></p>
                  <ul style={{ color: '#155724' }}>
                    {experimentCard.critical_acceptance_standard.must_have_metrics?.map((x, i) => <li key={i}>{x}</li>)}
                  </ul>
                  <p><strong>一票否决项 (Red lines)：</strong></p>
                  <ul style={{ color: '#721c24' }}>
                    {experimentCard.critical_acceptance_standard.red_lines?.map((x, i) => <li key={i}>{x}</li>)}
                  </ul>
                </div>
              )}
            </div>
            <div>
              <h4>OKR/KR Mapping</h4>
              <div className="mapping-list">
                {(experimentCard.hypothesis_mapping || []).map((item, idx) => (
                  <div key={idx} className="mapping-item">
                    <div><strong>OKR/KR：</strong>{item.okr_or_kr}</div>
                    <div><strong>Hypothesis：</strong>{item.hypothesis}</div>
                    <div><strong>是否可行：</strong>{item.feasibility_check}</div>
                  </div>
                ))}
              </div>
              {downloadUrl ? (
                <a className="download-btn" href={downloadUrl}>下载 Word 文档</a>
              ) : null}
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
