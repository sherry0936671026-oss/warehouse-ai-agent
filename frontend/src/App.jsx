import { useEffect, useRef, useState } from "react"
import axios from "axios"

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"

const S = {
  app: { display: "flex", height: "100vh", fontFamily: "-apple-system, BlinkMacSystemFont, sans-serif", fontSize: 14, background: "#faf9f7" },
  sidebar: { width: 220, background: "#f1efe8", borderRight: "0.5px solid #ddd", display: "flex", flexDirection: "column", padding: "0 0 16px" },
  sidebarTitle: { padding: "20px 20px 4px", fontSize: 16, fontWeight: 600, color: "#2c2c2a" },
  navSection: { padding: "16px 20px 6px", fontSize: 11, color: "#888780", letterSpacing: "0.05em" },
  navItem: { padding: "8px 20px", fontSize: 13, color: "#5f5e5a", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, borderLeft: "2px solid transparent" },
  navItemActive: { padding: "8px 20px", fontSize: 13, color: "#2c2c2a", fontWeight: 500, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, borderLeft: "2px solid #378ADD", background: "#fff" },
  badge: { background: "#E24B4A", color: "#fff", fontSize: 10, fontWeight: 600, borderRadius: 99, padding: "1px 6px", marginLeft: 2 },
  badgeWarn: { background: "#BA7517", color: "#fff", fontSize: 10, fontWeight: 600, borderRadius: 99, padding: "1px 6px", marginLeft: 2 },
  badgeBlue: { background: "#378ADD", color: "#fff", fontSize: 10, fontWeight: 500, borderRadius: 4, padding: "1px 7px" },
  main: { flex: 1, overflowY: "auto" },
  topbar: { padding: "20px 28px 16px", borderBottom: "0.5px solid #e8e6e0", display: "flex", alignItems: "flex-start", justifyContent: "space-between", background: "#fff" },
  topbarTitle: { fontSize: 22, fontWeight: 500, color: "#2c2c2a" },
  topbarSub: { fontSize: 12, color: "#888780", marginTop: 3 },
  btnPrimary: { padding: "8px 18px", background: "#378ADD", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 500 },
  btnDanger: { padding: "8px 18px", background: "#E24B4A", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 500 },
  btnSuccess: { padding: "8px 18px", background: "#3B6D11", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: 500 },
  content: { padding: "24px 28px" },
  metrics: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 28 },
  metric: { background: "#f1efe8", borderRadius: 10, padding: "14px 16px" },
  metricLabel: { fontSize: 12, color: "#888780", marginBottom: 6 },
  metricValue: { fontSize: 26, fontWeight: 500 },
  sectionLabel: { fontSize: 14, fontWeight: 500, marginBottom: 12, color: "#2c2c2a" },
  tableWrap: { border: "0.5px solid #e8e6e0", borderRadius: 10, overflow: "hidden", marginBottom: 28, background: "#fff" },
  th: { background: "#f9f8f6", padding: "9px 14px", textAlign: "left", fontSize: 11, fontWeight: 500, color: "#888780", borderBottom: "0.5px solid #e8e6e0" },
  td: { padding: "10px 14px", borderBottom: "0.5px solid #f0ede8", fontSize: 13, color: "#2c2c2a" },
  prbTag: { display: "inline-block", background: "#faeeda", color: "#633806", fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 4 },
  detailCard: { border: "0.5px solid #e8e6e0", borderRadius: 10, padding: "18px 22px", marginBottom: 16, background: "#fff" },
  detailGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 24px" },
  detailRow: { padding: "8px 0", borderBottom: "0.5px solid #f0ede8" },
  detailKey: { fontSize: 12, color: "#888780", marginBottom: 3 },
  detailVal: { fontSize: 13, fontWeight: 500 },
  logItem: { display: "flex", gap: 12, paddingBottom: 12, borderBottom: "0.5px solid #f0ede8", marginBottom: 12 },
  logDot: { width: 8, height: 8, borderRadius: "50%", background: "#378ADD", marginTop: 4, flexShrink: 0 },
  actionBar: { display: "flex", gap: 8, paddingTop: 16, flexWrap: "wrap" },
  btn: { padding: "7px 18px", borderRadius: 6, border: "0.5px solid #ddd", cursor: "pointer", background: "#fff", fontSize: 13 },
  formGroup: { marginBottom: 16 },
  label: { fontSize: 12, color: "#888780", marginBottom: 6, display: "block" },
  input: { width: "100%", padding: "8px 12px", border: "0.5px solid #ddd", borderRadius: 6, fontSize: 13, background: "#fff", boxSizing: "border-box" },
  select: { width: "100%", padding: "8px 12px", border: "0.5px solid #ddd", borderRadius: 6, fontSize: 13, background: "#fff", boxSizing: "border-box" },
  warning: { background: "#FFF8E6", border: "0.5px solid #F0C040", borderRadius: 8, padding: "12px 16px", marginBottom: 16, fontSize: 13, color: "#633806" },
  modal: { position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.3)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 },
  modalBox: { background: "#fff", borderRadius: 12, padding: "24px 28px", width: 440, boxShadow: "0 8px 32px rgba(0,0,0,0.12)" },
}

const statusColor = { "待確認": "#BA7517", "異議": "#A32D2D", "已結案": "#5F5E5A" }
const statusBg = { "待確認": "#faeeda", "異議": "#fcebeb", "已結案": "#f1efe8" }
const RESPONSIBILITY = ["出發倉", "接收倉", "運輸途中", "待釐清"]

const SKU_LIST = [
  { value: "P001", label: "P001 包裝紙箱(大)" }, { value: "P002", label: "P002 包裝紙箱(小)" },
  { value: "P003", label: "P003 氣泡紙" }, { value: "P004", label: "P004 棧板" },
  { value: "P005", label: "P005 封箱膠帶" }, { value: "P006", label: "P006 防撞角條" },
  { value: "P007", label: "P007 標籤貼紙" }, { value: "P008", label: "P008 棉繩" },
  { value: "P009", label: "P009 防潮袋" }, { value: "P010", label: "P010 保麗龍內襯" },
]

const WH_LIST = [
  { value: "W1", label: "W1 北區倉" }, { value: "W2", label: "W2 中區倉" }, { value: "W3", label: "W3 南區倉" },
]

// ── 步驟顏色 ──────────────────────────────────────────────────────────────────
const stepDotColor = {
  start: "#888", router: "#378ADD", invoke: "#7C3AED",
  tool_call: "#D97706", tool_result: "#3B6D11",
  integrate: "#0891B2", done: "#3B6D11",
  fallback: "#E24B4A", error: "#E24B4A", validation_failed: "#E24B4A",
}

// ── 小元件 ────────────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  return (
    <span style={{ display: "inline-block", fontSize: 11, fontWeight: 500, padding: "2px 10px", borderRadius: 99, background: statusBg[status] || "#f1efe8", color: statusColor[status] || "#5F5E5A" }}>
      {status}
    </span>
  )
}
function PrbTag({ code }) { return <span style={S.prbTag}>{code}</span> }

// ── 庫存橫條圖（純 CSS）───────────────────────────────────────────────────────
function InventoryBar({ wh }) {
  const maxScale = wh.safety_stock * 5
  const pct = Math.min(wh.quantity / maxScale * 100, 100)
  const safetyPct = Math.min(wh.safety_stock / maxScale * 100, 100)
  const isLow = wh.quantity < wh.safety_stock

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 12 }}>
        <span style={{ fontWeight: 500 }}>{wh.warehouse_name}</span>
        <span style={{ color: isLow ? "#E24B4A" : "#3B6D11", fontWeight: 500 }}>
          {wh.quantity} {wh.unit}
          {isLow && <span style={{ marginLeft: 6, fontSize: 10, background: "#fcebeb", color: "#A32D2D", padding: "1px 6px", borderRadius: 4 }}>低庫存 ↓{wh.shortage}</span>}
        </span>
      </div>
      <div style={{ position: "relative", height: 14, background: "#f0ede8", borderRadius: 99, overflow: "visible" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: isLow ? "#E24B4A" : "#3B6D11", borderRadius: 99, transition: "width 0.4s" }} />
        {/* 安全庫存線 */}
        <div style={{ position: "absolute", left: `${safetyPct}%`, top: -3, bottom: -3, width: 2, background: "#BA7517", borderRadius: 1 }} />
      </div>
      <div style={{ fontSize: 11, color: "#aaa", marginTop: 3 }}>安全庫存：{wh.safety_stock} {wh.unit}</div>
    </div>
  )
}

// ── CloseModal ─────────────────────────────────────────────────────────────────
function CloseModal({ claim, onClose, onDone }) {
  const [closeType, setCloseType] = useState("補貨結案")
  const [note, setNote] = useState("")
  function submit() {
    axios.patch(`${API}/claims/${claim.event_id}/close?close_type=${closeType}&actor_wh=WH001&note=${encodeURIComponent(note)}`)
      .then(() => onDone()).catch(e => alert(e.response?.data?.detail || "結案失敗"))
  }
  return (
    <div style={S.modal} onClick={onClose}>
      <div style={S.modalBox} onClick={e => e.stopPropagation()}>
        <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 16 }}>結案</div>
        <div style={S.formGroup}>
          <label style={S.label}>結案方式</label>
          <div style={{ display: "flex", gap: 8 }}>
            {["補貨結案", "轉帳結案"].map(t => (
              <button key={t} onClick={() => setCloseType(t)}
                style={{ ...S.btn, background: closeType === t ? "#378ADD" : "#fff", color: closeType === t ? "#fff" : "#2c2c2a", borderColor: closeType === t ? "#378ADD" : "#ddd" }}>
                {t}
              </button>
            ))}
          </div>
        </div>
        <div style={S.formGroup}>
          <label style={S.label}>{closeType === "補貨結案" ? "車號（選填）" : "庫存ID / 轉帳紀錄編號"}</label>
          <input style={S.input} placeholder={closeType === "補貨結案" ? "例如 TRK-001" : "例如 INV-20250501-001"} value={note} onChange={e => setNote(e.target.value)} />
        </div>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button style={S.btn} onClick={onClose}>取消</button>
          <button style={S.btnSuccess} onClick={submit}>確認結案</button>
        </div>
      </div>
    </div>
  )
}

// ── DecisionLog 展開元件 ────────────────────────────────────────────────────────
function DecisionLog({ log }) {
  const [open, setOpen] = useState(false)
  if (!log || log.length === 0) return null
  return (
    <div style={{ marginTop: 8 }}>
      <button onClick={() => setOpen(o => !o)} style={{ ...S.btn, fontSize: 11, padding: "3px 10px", color: "#378ADD", borderColor: "#b5d4f4" }}>
        {open ? "▲" : "▼"} 決策推理（{log.length} 步）
      </button>
      {open && (
        <div style={{ marginTop: 8, borderLeft: "2px solid #e8e6e0", paddingLeft: 12 }}>
          {log.map((entry, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: stepDotColor[entry.step] || "#888", marginTop: 5, flexShrink: 0 }} />
              <div>
                <span style={{ fontSize: 10, fontWeight: 600, color: stepDotColor[entry.step] || "#888", textTransform: "uppercase", marginRight: 6 }}>{entry.step}</span>
                <span style={{ fontSize: 12, color: "#555" }}>{entry.reasoning}</span>
                <div style={{ fontSize: 10, color: "#bbb", marginTop: 1 }}>{entry.timestamp}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main App ───────────────────────────────────────────────────────────────────
export default function App() {
  const [page, setPage] = useState("dashboard")

  // ── Claim 相關 state ─────────────────────────────────────────────────────────
  const [claims, setClaims] = useState([])
  const [detail, setDetail] = useState(null)
  const [aiSummary, setAiSummary] = useState("")
  const [aiLoading, setAiLoading] = useState(false)
  const [warehouses, setWarehouses] = useState([])
  const [showCloseModal, setShowCloseModal] = useState(false)
  const [duplicateWarning, setDuplicateWarning] = useState([])
  const [form, setForm] = useState({
    item_id: "", prb_code: "1-2", qty_claimed: "",
    from_wh: "WH001", to_wh: "WH002", responsibility: "待釐清", note: ""
  })

  // ── AI 聊天 state ────────────────────────────────────────────────────────────
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState("")
  const [chatLoading, setChatLoading] = useState(false)
  const chatEndRef = useRef(null)

  // ── 庫存看板 state ────────────────────────────────────────────────────────────
  const [selectedSku, setSelectedSku] = useState("P001")
  const [inventoryData, setInventoryData] = useState(null)
  const [lowStock, setLowStock] = useState([])
  const [transferSku, setTransferSku] = useState("P001")
  const [transferTarget, setTransferTarget] = useState("W1")
  const [transferResult, setTransferResult] = useState(null)
  const [transferLoading, setTransferLoading] = useState(false)

  useEffect(() => {
    axios.get(`${API}/claims`).then(r => setClaims(r.data))
    axios.get(`${API}/warehouses`).then(r => setWarehouses(r.data))
    axios.get(`${API}/agent/safety-stock`).then(r => setLowStock(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (page === "inventory") loadInventory(selectedSku)
  }, [page])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatMessages])

  function loadInventory(sku) {
    setInventoryData(null)
    axios.get(`${API}/agent/inventory/${sku}`).then(r => setInventoryData(r.data)).catch(() => {})
  }

  // ── Claim 操作 ────────────────────────────────────────────────────────────────
  function openDetail(event_id) {
    setAiSummary(""); setAiLoading(true)
    axios.get(`${API}/claims/${event_id}`).then(r => { setDetail(r.data); setPage("detail") })
    axios.get(`${API}/claims/${event_id}/ai-summary`).then(r => { setAiSummary(r.data.summary); setAiLoading(false) })
  }
  function updateStatus(event_id, status) {
    axios.patch(`${API}/claims/${event_id}/status?status=${status}&actor_wh=WH001&note=${status}`)
      .then(() => {
        axios.get(`${API}/claims/${event_id}`).then(r => setDetail(r.data))
        axios.get(`${API}/claims`).then(r => setClaims(r.data))
      })
  }
  function checkDuplicate() {
    if (!form.item_id || !form.from_wh || !form.to_wh) return
    axios.get(`${API}/claims/check-duplicate?from_wh=${form.from_wh}&to_wh=${form.to_wh}&item_id=${form.item_id}`)
      .then(r => setDuplicateWarning(r.data.duplicates))
  }
  function submitClaim() {
    const now = new Date()
    const event_id = `EVT-${now.getFullYear()}${String(now.getMonth()+1).padStart(2,"0")}${String(now.getDate()).padStart(2,"0")}-${String(Math.floor(Math.random()*900)+100)}`
    axios.post(`${API}/claims`, {
      event_id, from_wh: form.from_wh, to_wh: form.to_wh,
      item_id: form.item_id, prb_code: form.prb_code,
      qty_claimed: parseInt(form.qty_claimed), status: "待確認",
      note: `[責任:${form.responsibility}] ${form.note}`
    }).then(() => {
      axios.get(`${API}/claims`).then(r => setClaims(r.data))
      setDuplicateWarning([]); setPage("list")
    })
  }
  function handleCloseDone() {
    setShowCloseModal(false)
    axios.get(`${API}/claims/${detail.claim.event_id}`).then(r => setDetail(r.data))
    axios.get(`${API}/claims`).then(r => setClaims(r.data))
  }

  // ── AI 聊天 ───────────────────────────────────────────────────────────────────
  function sendChat() {
    const msg = chatInput.trim()
    if (!msg || chatLoading) return
    setChatMessages(m => [...m, { role: "user", text: msg }])
    setChatInput(""); setChatLoading(true)
    axios.post(`${API}/agent/chat`, { message: msg })
      .then(r => {
        setChatMessages(m => [...m, {
          role: "ai", text: r.data.reply,
          categories: r.data.categories,
          decisionLog: r.data.decision_log,
        }])
      })
      .catch(() => setChatMessages(m => [...m, { role: "ai", text: "連線失敗，請確認後端是否啟動。", categories: [], decisionLog: [] }]))
      .finally(() => setChatLoading(false))
  }

  // ── 調撥建議 ──────────────────────────────────────────────────────────────────
  function runTransferSuggestion() {
    setTransferLoading(true); setTransferResult(null)
    const whLabel = WH_LIST.find(w => w.value === transferTarget)?.label || transferTarget
    const skuLabel = SKU_LIST.find(s => s.value === transferSku)?.label || transferSku
    axios.post(`${API}/agent/chat`, { message: `${skuLabel} 需要補貨到 ${whLabel}，請建議調撥方案` })
      .then(r => setTransferResult(r.data))
      .finally(() => setTransferLoading(false))
  }

  // ── 衍生資料 ─────────────────────────────────────────────────────────────────
  const myClaims = claims.filter(c => c.from_wh === "WH001")
  const incoming = claims.filter(c => c.to_wh === "WH001")
  const pending = claims.filter(c => c.status === "待確認").length
  const incomingPending = incoming.filter(c => c.status === "待確認").length
  const closed = claims.filter(c => c.status === "已結案").length
  const disputed = claims.filter(c => c.status === "異議").length
  const whName = (id) => warehouses.find(w => w.wh_id === id)?.wh_name || id
  const isClosed = detail?.claim?.status === "已結案"
  const whStats = warehouses.map(w => {
    const wc = claims.filter(c => c.from_wh === w.wh_id)
    const wClosed = wc.filter(c => c.status === "已結案").length
    const wDisp = wc.filter(c => c.status === "異議").length
    return { ...w, total: wc.length, closed: wClosed, disputed: wDisp, closeRate: wc.length ? Math.round(wClosed / wc.length * 100) : 0 }
  }).sort((a, b) => b.total - a.total)

  const navItem = (id, label, badge, bStyle) => (
    <div style={page === id ? S.navItemActive : S.navItem} onClick={() => setPage(id)}>
      {label}
      {badge > 0 && <span style={bStyle || S.badge}>{badge}</span>}
    </div>
  )

  const agentCategoryLabel = { inventory: "庫存", claim: "異議單", transfer: "調撥", report: "報表" }
  const agentCategoryColor = { inventory: "#0891B2", claim: "#D97706", transfer: "#7C3AED", report: "#3B6D11" }

  return (
    <div style={S.app}>
      {showCloseModal && detail && (
        <CloseModal claim={detail.claim} onClose={() => setShowCloseModal(false)} onDone={handleCloseDone} />
      )}

      {/* ── Sidebar ──────────────────────────────────────────────────────────── */}
      <div style={S.sidebar}>
        <div style={S.sidebarTitle}>倉庫管理系統</div>
        <div style={S.navSection}>Claim 管理</div>
        {navItem("dashboard", "Dashboard")}
        {navItem("list", "Claim 列表", pending)}
        {navItem("incoming", "收到的 Claim", incomingPending, S.badgeWarn)}
        {navItem("kpi", "主管 KPI")}
        <div style={S.navSection}>AI 助手</div>
        {navItem("ai-chat", "AI 倉庫對話")}
        {navItem("inventory", "庫存看板")}
        <div style={S.navSection}>工具</div>
        {navItem("new", "建立新 Claim")}
        <div style={S.navSection}>目前登入</div>
        <div style={{ padding: "0 20px", fontSize: 12, color: "#888780" }}>桃園一倉 WH001</div>
      </div>

      <div style={S.main}>

        {/* ── Dashboard ──────────────────────────────────────────────────────── */}
        {page === "dashboard" && (
          <>
            <div style={S.topbar}>
              <div>
                <div style={S.topbarTitle}>Dashboard</div>
                <div style={S.topbarSub}>桃園一倉 WH001 · {new Date().toISOString().slice(0,10)}</div>
              </div>
              <button style={S.btnPrimary} onClick={() => setPage("new")}>+ 建立 Claim</button>
            </div>
            <div style={S.content}>
              <div style={S.metrics}>
                <div style={S.metric}><div style={S.metricLabel}>待確認 Claim</div><div style={{ ...S.metricValue, color: "#BA7517" }}>{pending}</div></div>
                <div style={S.metric}><div style={S.metricLabel}>收到的（待處理）</div><div style={{ ...S.metricValue, color: "#A32D2D" }}>{incomingPending}</div></div>
                <div style={S.metric}><div style={S.metricLabel}>本月已結案</div><div style={{ ...S.metricValue, color: "#3B6D11" }}>{closed}</div></div>
                <div style={S.metric}><div style={S.metricLabel}>異議中</div><div style={{ ...S.metricValue, color: "#A32D2D" }}>{disputed}</div></div>
              </div>
              {lowStock.length > 0 && (
                <>
                  <div style={S.sectionLabel}>⚠️ 低庫存警示（{lowStock.length} 項）</div>
                  <div style={{ ...S.tableWrap, marginBottom: 28 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead><tr>{["倉庫","SKU","品名","現庫存","安全庫存","缺口"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                      <tbody>
                        {lowStock.slice(0, 5).map((item, i) => (
                          <tr key={i}>
                            <td style={S.td}>{item.warehouse_name}</td>
                            <td style={{ ...S.td, fontFamily: "monospace", color: "#888" }}>{item.sku}</td>
                            <td style={S.td}>{item.product_name}</td>
                            <td style={{ ...S.td, color: "#E24B4A", fontWeight: 500 }}>{item.quantity} {item.unit}</td>
                            <td style={{ ...S.td, color: "#888" }}>{item.safety_stock}</td>
                            <td style={{ ...S.td, color: "#A32D2D", fontWeight: 500 }}>↓{item.shortage}</td>
                          </tr>
                        ))}
                        {lowStock.length > 5 && (
                          <tr><td colSpan={6} style={{ ...S.td, textAlign: "center", color: "#888", cursor: "pointer" }} onClick={() => setPage("inventory")}>查看全部 {lowStock.length} 項 →</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              <div style={S.sectionLabel}>我發出的 Claim</div>
              <div style={S.tableWrap}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>{["事件 ID","商品","PRB","接收倉","數量","狀態"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {myClaims.length === 0 && <tr><td colSpan={6} style={{ ...S.td, color: "#aaa", textAlign: "center" }}>目前沒有 Claim</td></tr>}
                    {myClaims.map(c => (
                      <tr key={c.event_id} style={{ cursor: "pointer" }} onClick={() => openDetail(c.event_id)}>
                        <td style={{ ...S.td, fontFamily: "monospace", fontSize: 12, color: "#888" }}>{c.event_id}</td>
                        <td style={S.td}>{c.item_id}</td>
                        <td style={S.td}><PrbTag code={c.prb_code} /></td>
                        <td style={S.td}>{whName(c.to_wh)}</td>
                        <td style={S.td}>{c.qty_claimed}</td>
                        <td style={S.td}><StatusBadge status={c.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={S.sectionLabel}>收到的 Claim（需處理）</div>
              <div style={S.tableWrap}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>{["事件 ID","商品","PRB","出發倉","數量","狀態"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {incoming.length === 0 && <tr><td colSpan={6} style={{ ...S.td, color: "#aaa", textAlign: "center" }}>目前沒有待處理的 Claim 🎉</td></tr>}
                    {incoming.map(c => (
                      <tr key={c.event_id} style={{ cursor: "pointer" }} onClick={() => openDetail(c.event_id)}>
                        <td style={{ ...S.td, fontFamily: "monospace", fontSize: 12, color: "#888" }}>{c.event_id}</td>
                        <td style={S.td}>{c.item_id}</td>
                        <td style={S.td}><PrbTag code={c.prb_code} /></td>
                        <td style={S.td}>{whName(c.from_wh)}</td>
                        <td style={S.td}>{c.qty_claimed}</td>
                        <td style={S.td}><StatusBadge status={c.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ── Claim 列表 ──────────────────────────────────────────────────────── */}
        {page === "list" && (
          <>
            <div style={S.topbar}><div style={S.topbarTitle}>我發出的 Claim</div></div>
            <div style={S.content}>
              <div style={S.tableWrap}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>{["事件 ID","商品","PRB","接收倉","數量","狀態","建立日"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {myClaims.map(c => (
                      <tr key={c.event_id} style={{ cursor: "pointer" }} onClick={() => openDetail(c.event_id)}>
                        <td style={{ ...S.td, fontFamily: "monospace", fontSize: 12, color: "#888" }}>{c.event_id}</td>
                        <td style={S.td}>{c.item_id}</td>
                        <td style={S.td}><PrbTag code={c.prb_code} /></td>
                        <td style={S.td}>{whName(c.to_wh)}</td>
                        <td style={S.td}>{c.qty_claimed}</td>
                        <td style={S.td}><StatusBadge status={c.status} /></td>
                        <td style={{ ...S.td, color: "#888" }}>{c.created_at?.slice(0,10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ── 收到的 Claim ─────────────────────────────────────────────────────── */}
        {page === "incoming" && (
          <>
            <div style={S.topbar}><div style={S.topbarTitle}>收到的 Claim</div></div>
            <div style={S.content}>
              <div style={S.tableWrap}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>{["事件 ID","商品","PRB","出發倉","數量","狀態","建立日"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {incoming.length === 0 && <tr><td colSpan={7} style={{ ...S.td, color: "#aaa", textAlign: "center" }}>目前沒有待處理的 Claim 🎉</td></tr>}
                    {incoming.map(c => (
                      <tr key={c.event_id} style={{ cursor: "pointer" }} onClick={() => openDetail(c.event_id)}>
                        <td style={{ ...S.td, fontFamily: "monospace", fontSize: 12, color: "#888" }}>{c.event_id}</td>
                        <td style={S.td}>{c.item_id}</td>
                        <td style={S.td}><PrbTag code={c.prb_code} /></td>
                        <td style={S.td}>{whName(c.from_wh)}</td>
                        <td style={S.td}>{c.qty_claimed}</td>
                        <td style={S.td}><StatusBadge status={c.status} /></td>
                        <td style={{ ...S.td, color: "#888" }}>{c.created_at?.slice(0,10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ── 主管 KPI ─────────────────────────────────────────────────────────── */}
        {page === "kpi" && (
          <>
            <div style={S.topbar}><div style={S.topbarTitle}>主管 KPI 總覽</div></div>
            <div style={S.content}>
              <div style={S.metrics}>
                <div style={S.metric}><div style={S.metricLabel}>總 Claim 數</div><div style={S.metricValue}>{claims.length}</div></div>
                <div style={S.metric}><div style={S.metricLabel}>結案率</div><div style={{ ...S.metricValue, color: "#3B6D11" }}>{claims.length ? Math.round(closed/claims.length*100) : 0}%</div></div>
                <div style={S.metric}><div style={S.metricLabel}>異議率</div><div style={{ ...S.metricValue, color: "#A32D2D" }}>{claims.length ? Math.round(disputed/claims.length*100) : 0}%</div></div>
                <div style={S.metric}><div style={S.metricLabel}>待處理</div><div style={{ ...S.metricValue, color: "#BA7517" }}>{pending}</div></div>
              </div>
              <div style={S.sectionLabel}>各出發倉異常統計</div>
              <div style={S.tableWrap}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>{["倉庫","異常次數","已結案","異議","結案率"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {whStats.map(w => (
                      <tr key={w.wh_id}>
                        <td style={S.td}>{w.wh_id} {w.wh_name}</td>
                        <td style={S.td}>{w.total}</td>
                        <td style={{ ...S.td, color: "#3B6D11" }}>{w.closed}</td>
                        <td style={{ ...S.td, color: "#A32D2D" }}>{w.disputed}</td>
                        <td style={S.td}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <div style={{ flex: 1, height: 6, background: "#eee", borderRadius: 99 }}>
                              <div style={{ width: `${w.closeRate}%`, height: 6, background: "#3B6D11", borderRadius: 99 }} />
                            </div>
                            <span>{w.closeRate}%</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={S.sectionLabel}>異議中（需主管審核）</div>
              <div style={S.tableWrap}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>{["事件 ID","商品","出發倉","接收倉","數量","建立日"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                  <tbody>
                    {claims.filter(c => c.status === "異議").length === 0 && (
                      <tr><td colSpan={6} style={{ ...S.td, color: "#aaa", textAlign: "center" }}>目前沒有異議中的 Claim</td></tr>
                    )}
                    {claims.filter(c => c.status === "異議").map(c => (
                      <tr key={c.event_id} style={{ cursor: "pointer" }} onClick={() => openDetail(c.event_id)}>
                        <td style={{ ...S.td, fontFamily: "monospace", fontSize: 12, color: "#888" }}>{c.event_id}</td>
                        <td style={S.td}>{c.item_id}</td>
                        <td style={S.td}>{whName(c.from_wh)}</td>
                        <td style={S.td}>{whName(c.to_wh)}</td>
                        <td style={S.td}>{c.qty_claimed}</td>
                        <td style={{ ...S.td, color: "#888" }}>{c.created_at?.slice(0,10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ── Claim 詳細 ────────────────────────────────────────────────────────── */}
        {page === "detail" && detail && (
          <>
            <div style={S.topbar}>
              <div>
                <div style={{ fontFamily: "monospace", color: "#888", fontSize: 13 }}>{detail.claim.event_id}</div>
                <div style={S.topbarTitle}>{detail.claim.item_id}</div>
              </div>
              <StatusBadge status={detail.claim.status} />
            </div>
            <div style={S.content}>
              <div style={{ background: "#e6f1fb", border: "0.5px solid #b5d4f4", borderRadius: 10, padding: "14px 18px", marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 500, color: "#185FA5", marginBottom: 6 }}>AI 摘要</div>
                {aiLoading
                  ? <div style={{ fontSize: 13, color: "#378ADD" }}>分析中...</div>
                  : <div style={{ fontSize: 13, color: "#2c2c2a", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{aiSummary}</div>
                }
              </div>
              <div style={S.detailCard}>
                <div style={S.detailGrid}>
                  {[
                    ["PRB 代碼", <PrbTag key="prb" code={detail.claim.prb_code} />],
                    ["短少數量", `${detail.claim.qty_claimed} 件`],
                    ["出發倉", `${detail.claim.from_wh} ${whName(detail.claim.from_wh)}`],
                    ["接收倉", `${detail.claim.to_wh} ${whName(detail.claim.to_wh)}`],
                    ["建立時間", detail.claim.created_at?.slice(0,10)],
                    ["備註", detail.claim.note || "—"],
                  ].map(([k, v]) => (
                    <div key={k} style={S.detailRow}>
                      <div style={S.detailKey}>{k}</div>
                      <div style={S.detailVal}>{v}</div>
                    </div>
                  ))}
                </div>
              </div>
              {!isClosed && (
                <>
                  <div style={S.sectionLabel}>操作</div>
                  <div style={S.actionBar}>
                    <button style={{ ...S.btn, color: "#A32D2D", borderColor: "#A32D2D" }} onClick={() => updateStatus(detail.claim.event_id, "異議")}>異議</button>
                    <button style={S.btnSuccess} onClick={() => setShowCloseModal(true)}>補貨結案</button>
                    <button style={S.btnPrimary} onClick={() => setShowCloseModal(true)}>轉帳結案</button>
                    <button style={{ ...S.btn, marginLeft: "auto" }} onClick={() => setPage("dashboard")}>← 返回</button>
                  </div>
                </>
              )}
              {isClosed && (
                <div style={{ ...S.warning, background: "#eaf3de", border: "0.5px solid #b5d4a0", color: "#3B6D11", marginTop: 16 }}>
                  ✅ 此 Claim 已結案，無法再操作
                  <button style={{ ...S.btn, marginLeft: 16 }} onClick={() => setPage("dashboard")}>← 返回</button>
                </div>
              )}
              <div style={{ marginTop: 24, ...S.sectionLabel }}>事件 Log</div>
              <div style={S.detailCard}>
                {detail.logs.map((log, i) => (
                  <div key={i} style={S.logItem}>
                    <div style={{ ...S.logDot, background: log.action === "已結案" ? "#3B6D11" : log.action === "異議" ? "#A32D2D" : "#378ADD" }} />
                    <div>
                      <div style={{ fontSize: 13 }}>{log.action}　{log.note}</div>
                      <div style={{ color: "#aaa", fontSize: 12, marginTop: 2 }}>{log.actor_wh}　{log.timestamp?.slice(0,16)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* ── 建立 Claim ──────────────────────────────────────────────────────── */}
        {page === "new" && (
          <>
            <div style={S.topbar}>
              <div>
                <div style={S.topbarTitle}>建立新 Claim</div>
                <div style={S.topbarSub}>記錄一筆新的 PRB 異常事件</div>
              </div>
            </div>
            <div style={S.content}>
              <div style={{ maxWidth: 560 }}>
                {duplicateWarning.length > 0 && (
                  <div style={S.warning}>
                    ⚠️ 發現近期相似 Claim：{duplicateWarning.join("、")}<br />請確認是否為同一事件，或繼續建立新的。
                  </div>
                )}
                <div style={S.detailCard}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div style={S.formGroup}>
                      <label style={S.label}>出發倉</label>
                      <select style={S.select} value={form.from_wh} onChange={e => setForm({ ...form, from_wh: e.target.value })}>
                        {warehouses.map(w => <option key={w.wh_id} value={w.wh_id}>{w.wh_id} {w.wh_name}</option>)}
                      </select>
                    </div>
                    <div style={S.formGroup}>
                      <label style={S.label}>接收倉</label>
                      <select style={S.select} value={form.to_wh} onChange={e => setForm({ ...form, to_wh: e.target.value })}>
                        {warehouses.filter(w => w.wh_id !== form.from_wh).map(w => <option key={w.wh_id} value={w.wh_id}>{w.wh_id} {w.wh_name}</option>)}
                      </select>
                    </div>
                  </div>
                  <div style={S.formGroup}>
                    <label style={S.label}>商品 ID</label>
                    <input style={S.input} placeholder="例如 ITM-A001" value={form.item_id}
                      onChange={e => setForm({ ...form, item_id: e.target.value })} onBlur={checkDuplicate} />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div style={S.formGroup}>
                      <label style={S.label}>PRB 代碼</label>
                      <select style={S.select} value={form.prb_code} onChange={e => setForm({ ...form, prb_code: e.target.value })}>
                        <option value="1-2">1-2 進貨短少</option>
                        <option value="1-5">1-5 其他異常</option>
                        <option value="1-7">1-7 移除效期短少</option>
                      </select>
                    </div>
                    <div style={S.formGroup}>
                      <label style={S.label}>Claim 數量</label>
                      <input style={S.input} type="number" placeholder="0" value={form.qty_claimed} onChange={e => setForm({ ...form, qty_claimed: e.target.value })} />
                    </div>
                  </div>
                  <div style={S.formGroup}>
                    <label style={S.label}>責任歸屬</label>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {RESPONSIBILITY.map(r => (
                        <button key={r} onClick={() => setForm({ ...form, responsibility: r })}
                          style={{ ...S.btn, background: form.responsibility === r ? "#378ADD" : "#fff", color: form.responsibility === r ? "#fff" : "#2c2c2a", borderColor: form.responsibility === r ? "#378ADD" : "#ddd" }}>
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div style={S.formGroup}>
                    <label style={S.label}>備註說明</label>
                    <textarea style={{ ...S.input, height: 80, resize: "none" }} placeholder="說明異常情況..." value={form.note} onChange={e => setForm({ ...form, note: e.target.value })} />
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button style={S.btnPrimary} onClick={submitClaim}>送出建立</button>
                  <button style={S.btn} onClick={() => setPage("dashboard")}>取消</button>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── AI 倉庫對話 ──────────────────────────────────────────────────────── */}
        {page === "ai-chat" && (
          <>
            <div style={S.topbar}>
              <div>
                <div style={S.topbarTitle}>AI 倉庫助手</div>
                <div style={S.topbarSub}>多代理人系統 · 庫存 / 異議單 / 調撥 / 報表</div>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 73px)" }}>
              {/* 訊息區 */}
              <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>
                {chatMessages.length === 0 && (
                  <div style={{ textAlign: "center", color: "#aaa", marginTop: 60 }}>
                    <div style={{ fontSize: 32, marginBottom: 12 }}>🤖</div>
                    <div style={{ fontSize: 14, marginBottom: 20 }}>你好！我是倉庫 AI 助手，可以幫你查詢：</div>
                    <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
                      {[
                        "P001 現在哪個倉庫最多？",
                        "有哪些 claim 還在異議中？",
                        "P003 北區倉需要補貨，建議從哪裡調？",
                        "給我全倉的異常摘要",
                      ].map(q => (
                        <button key={q} onClick={() => { setChatInput(q) }}
                          style={{ ...S.btn, fontSize: 12, padding: "6px 12px", color: "#378ADD", borderColor: "#b5d4f4" }}>
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {chatMessages.map((msg, i) => (
                  <div key={i} style={{ marginBottom: 20, display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
                    {msg.role === "ai" && (
                      <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#378ADD", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "#fff", marginRight: 8, flexShrink: 0, marginTop: 2 }}>AI</div>
                    )}
                    <div style={{ maxWidth: "72%" }}>
                      <div style={{
                        background: msg.role === "user" ? "#378ADD" : "#fff",
                        color: msg.role === "user" ? "#fff" : "#2c2c2a",
                        padding: "12px 16px", borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
                        border: msg.role === "ai" ? "0.5px solid #e8e6e0" : "none",
                        fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap",
                      }}>
                        {msg.text}
                      </div>
                      {msg.role === "ai" && msg.categories?.length > 0 && (
                        <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
                          {msg.categories.map(cat => (
                            <span key={cat} style={{ fontSize: 10, fontWeight: 500, padding: "2px 8px", borderRadius: 4, background: agentCategoryColor[cat] + "18", color: agentCategoryColor[cat], border: `0.5px solid ${agentCategoryColor[cat]}44` }}>
                              {agentCategoryLabel[cat] || cat} Agent
                            </span>
                          ))}
                        </div>
                      )}
                      {msg.role === "ai" && <DecisionLog log={msg.decisionLog} />}
                    </div>
                  </div>
                ))}

                {chatLoading && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#888", fontSize: 13 }}>
                    <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#378ADD", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "#fff" }}>AI</div>
                    <div style={{ background: "#fff", border: "0.5px solid #e8e6e0", borderRadius: "16px 16px 16px 4px", padding: "12px 16px" }}>分析中...</div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* 輸入欄 */}
              <div style={{ padding: "12px 28px", borderTop: "0.5px solid #e8e6e0", background: "#fff", display: "flex", gap: 8 }}>
                <input
                  style={{ ...S.input, flex: 1 }}
                  placeholder="詢問庫存、異議單、調撥建議..."
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendChat()}
                  disabled={chatLoading}
                />
                <button style={{ ...S.btnPrimary, flexShrink: 0 }} onClick={sendChat} disabled={chatLoading}>
                  送出
                </button>
              </div>
            </div>
          </>
        )}

        {/* ── 庫存看板 ──────────────────────────────────────────────────────────── */}
        {page === "inventory" && (
          <>
            <div style={S.topbar}>
              <div>
                <div style={S.topbarTitle}>庫存看板</div>
                <div style={S.topbarSub}>三倉庫存比較 · 低庫存警示 · AI 調撥建議</div>
              </div>
            </div>
            <div style={S.content}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginBottom: 28 }}>

                {/* 三倉庫存比較 */}
                <div style={{ ...S.detailCard, marginBottom: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                    <div style={S.sectionLabel} >三倉庫存比較</div>
                    <select
                      style={{ ...S.select, width: "auto", fontSize: 12, padding: "5px 10px" }}
                      value={selectedSku}
                      onChange={e => { setSelectedSku(e.target.value); loadInventory(e.target.value) }}
                    >
                      {SKU_LIST.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                  </div>
                  {!inventoryData && <div style={{ color: "#aaa", fontSize: 13 }}>載入中...</div>}
                  {inventoryData && inventoryData.warehouses?.map(wh => (
                    <InventoryBar key={wh.warehouse_id} wh={wh} />
                  ))}
                  {inventoryData && (
                    <div style={{ marginTop: 12, fontSize: 12, color: "#888", display: "flex", gap: 16 }}>
                      <span>總庫存：<strong>{inventoryData.total_quantity} {inventoryData.unit}</strong></span>
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <div style={{ width: 12, height: 3, background: "#BA7517", borderRadius: 1 }} /> 安全庫存線
                      </span>
                    </div>
                  )}
                </div>

                {/* AI 調撥建議卡片 */}
                <div style={{ ...S.detailCard, marginBottom: 0 }}>
                  <div style={{ ...S.sectionLabel, marginBottom: 16 }}>AI 調撥建議</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
                    <div>
                      <label style={S.label}>目標品項</label>
                      <select style={S.select} value={transferSku} onChange={e => setTransferSku(e.target.value)}>
                        {SKU_LIST.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label style={S.label}>補貨目標倉</label>
                      <select style={S.select} value={transferTarget} onChange={e => setTransferTarget(e.target.value)}>
                        {WH_LIST.map(w => <option key={w.value} value={w.value}>{w.label}</option>)}
                      </select>
                    </div>
                  </div>
                  <button style={{ ...S.btnPrimary, width: "100%", marginBottom: 14 }} onClick={runTransferSuggestion} disabled={transferLoading}>
                    {transferLoading ? "AI 分析中..." : "分析調撥方案"}
                  </button>

                  {transferResult && (
                    <div style={{ background: "#f6f2ff", border: "0.5px solid #c4b5fd", borderRadius: 8, padding: "12px 14px" }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: "#7C3AED", marginBottom: 8 }}>建議方案</div>
                      <div style={{ fontSize: 13, lineHeight: 1.7, color: "#2c2c2a", whiteSpace: "pre-wrap", marginBottom: 10 }}>
                        {transferResult.reply}
                      </div>
                      <button
                        style={{ ...S.btnSuccess, fontSize: 12, padding: "6px 14px" }}
                        onClick={() => alert("調撥指令已送出（Mock）")}
                      >
                        ✓ 確認調撥（Mock）
                      </button>
                      <DecisionLog log={transferResult.decision_log} />
                    </div>
                  )}
                </div>
              </div>

              {/* 低庫存警示列表 */}
              <div style={S.sectionLabel}>低庫存警示（全倉）</div>
              <div style={S.tableWrap}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>{["倉庫","SKU","品名","現庫存","安全庫存","缺口","建議動作"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {lowStock.length === 0 && <tr><td colSpan={7} style={{ ...S.td, color: "#aaa", textAlign: "center" }}>載入中...</td></tr>}
                    {lowStock.map((item, i) => (
                      <tr key={i}>
                        <td style={S.td}>{item.warehouse_name}</td>
                        <td style={{ ...S.td, fontFamily: "monospace", color: "#888" }}>{item.sku}</td>
                        <td style={S.td}>{item.product_name}</td>
                        <td style={{ ...S.td, color: "#E24B4A", fontWeight: 500 }}>{item.quantity} {item.unit}</td>
                        <td style={{ ...S.td, color: "#888" }}>{item.safety_stock}</td>
                        <td style={{ ...S.td, color: "#A32D2D", fontWeight: 600 }}>↓{item.shortage}</td>
                        <td style={S.td}>
                          <button
                            style={{ ...S.btn, fontSize: 11, padding: "3px 10px", color: "#7C3AED", borderColor: "#c4b5fd" }}
                            onClick={() => { setTransferSku(item.sku); setTransferTarget(item.warehouse_id); document.querySelector("[data-page='inventory']") }}
                          >
                            建議調撥
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

      </div>
    </div>
  )
}
