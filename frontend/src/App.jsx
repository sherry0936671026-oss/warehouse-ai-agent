import { useEffect, useRef, useState, useCallback } from "react"
import axios from "axios"

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"

// ── Design tokens ─────────────────────────────────────────────────────────────
const S = {
  app: { display: "flex", height: "100vh", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", fontSize: 14, background: "#f7f6f4" },
  sidebar: { width: 216, background: "#1e1e1e", borderRight: "none", display: "flex", flexDirection: "column", padding: "0 0 16px", flexShrink: 0 },
  sidebarLogo: { padding: "20px 16px 12px", display: "flex", alignItems: "center", gap: 8 },
  sidebarLogoText: { fontSize: 14, fontWeight: 600, color: "#fff", letterSpacing: "0.01em" },
  sidebarLogoSub: { fontSize: 10, color: "#666", marginTop: 1 },
  navSection: { padding: "12px 16px 4px", fontSize: 10, color: "#555", letterSpacing: "0.08em", textTransform: "uppercase" },
  navItem: { padding: "7px 16px", fontSize: 13, color: "#999", cursor: "pointer", display: "flex", alignItems: "center", gap: 8, margin: "1px 6px", borderRadius: 6 },
  navItemActive: { padding: "7px 16px", fontSize: 13, color: "#fff", fontWeight: 500, cursor: "pointer", display: "flex", alignItems: "center", gap: 8, margin: "1px 6px", borderRadius: 6, background: "#2d2d2d" },
  badge: { background: "#e24b4a", color: "#fff", fontSize: 10, fontWeight: 600, borderRadius: 99, padding: "1px 6px", marginLeft: "auto" },
  badgeYellow: { background: "#BA7517", color: "#fff", fontSize: 10, fontWeight: 600, borderRadius: 99, padding: "1px 6px", marginLeft: "auto" },
  badgeGreen: { background: "#3B6D11", color: "#fff", fontSize: 10, fontWeight: 600, borderRadius: 99, padding: "1px 6px", marginLeft: "auto" },
  main: { flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" },
  topbar: { padding: "18px 28px 14px", borderBottom: "1px solid #ebebeb", display: "flex", alignItems: "flex-start", justifyContent: "space-between", background: "#fff", flexShrink: 0 },
  topbarTitle: { fontSize: 20, fontWeight: 600, color: "#1a1a1a" },
  topbarSub: { fontSize: 12, color: "#999", marginTop: 2 },
  content: { padding: "20px 28px", flex: 1 },
  metrics: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 },
  metric: { background: "#fff", border: "1px solid #ebebeb", borderRadius: 10, padding: "16px 18px" },
  metricLabel: { fontSize: 12, color: "#888", marginBottom: 8 },
  metricValue: { fontSize: 28, fontWeight: 600, color: "#1a1a1a" },
  metricSub: { fontSize: 11, color: "#bbb", marginTop: 4 },
  card: { background: "#fff", border: "1px solid #ebebeb", borderRadius: 10, padding: "16px 20px", marginBottom: 16 },
  sectionLabel: { fontSize: 13, fontWeight: 600, color: "#1a1a1a", marginBottom: 12 },
  tableWrap: { border: "1px solid #ebebeb", borderRadius: 10, overflow: "hidden", background: "#fff", marginBottom: 20 },
  th: { background: "#f9f8f6", padding: "9px 14px", textAlign: "left", fontSize: 11, fontWeight: 600, color: "#888", borderBottom: "1px solid #ebebeb", whiteSpace: "nowrap" },
  td: { padding: "10px 14px", borderBottom: "1px solid #f4f3f0", fontSize: 13, color: "#1a1a1a", verticalAlign: "middle" },
  tdMono: { padding: "10px 14px", borderBottom: "1px solid #f4f3f0", fontSize: 12, color: "#888", fontFamily: "monospace", verticalAlign: "middle" },
  btn: { padding: "7px 14px", borderRadius: 6, border: "1px solid #ddd", cursor: "pointer", background: "#fff", fontSize: 12, color: "#333", fontWeight: 500 },
  btnPrimary: { padding: "8px 16px", background: "#1a1a1a", color: "#fff", border: "none", borderRadius: 7, cursor: "pointer", fontSize: 13, fontWeight: 500 },
  btnDanger: { padding: "7px 14px", background: "#E24B4A", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 500 },
  btnSuccess: { padding: "7px 14px", background: "#16a34a", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 500 },
  btnBlue: { padding: "7px 14px", background: "#2563eb", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 500 },
  btnOutline: { padding: "7px 14px", borderRadius: 6, border: "1px solid #ddd", cursor: "pointer", background: "#fff", fontSize: 12, color: "#333" },
  formGroup: { marginBottom: 14 },
  label: { fontSize: 12, color: "#666", marginBottom: 5, display: "block", fontWeight: 500 },
  input: { width: "100%", padding: "8px 11px", border: "1px solid #ddd", borderRadius: 6, fontSize: 13, background: "#fff", boxSizing: "border-box" },
  select: { width: "100%", padding: "8px 11px", border: "1px solid #ddd", borderRadius: 6, fontSize: 13, background: "#fff", boxSizing: "border-box" },
  modal: { position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 },
  modalBox: { background: "#fff", borderRadius: 12, padding: "24px 28px", width: 560, maxHeight: "90vh", overflowY: "auto", boxShadow: "0 20px 60px rgba(0,0,0,0.2)" },
  alertYellow: { background: "#FFF8E6", border: "1px solid #F0C040", borderRadius: 8, padding: "10px 14px", marginBottom: 14, fontSize: 12, color: "#633806" },
  alertRed: { background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 8, padding: "10px 14px", marginBottom: 14, fontSize: 12, color: "#7f1d1d" },
  alertGreen: { background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 8, padding: "10px 14px", marginBottom: 14, fontSize: 12, color: "#14532d" },
}

// ── Status config ─────────────────────────────────────────────────────────────
const STATUS_CONFIG = {
  DRAFT:            { label: "草稿",    bg: "#f1efe8", color: "#5F5E5A" },
  IN_PROGRESS:      { label: "進行中",  bg: "#EFF6FF", color: "#1D4ED8" },
  IN_TRANSIT:       { label: "運輸中",  bg: "#FFF8E6", color: "#633806" },
  RECEIVING:        { label: "驗收中",  bg: "#EFF6FF", color: "#1D4ED8" },
  COMPLETED:        { label: "已完成",  bg: "#f0fdf4", color: "#14532d" },
  RECEIVED:         { label: "已收貨",  bg: "#f0fdf4", color: "#14532d" },
  CANCELLED:        { label: "已取消",  bg: "#f1efe8", color: "#888" },
  PENDING:          { label: "待處理",  bg: "#FFF8E6", color: "#633806" },
  INVESTIGATING:    { label: "調查中",  bg: "#EFF6FF", color: "#1D4ED8" },
  IN_COLLECT_BUFFER:{ label: "集貨中",  bg: "#faf5ff", color: "#6b21a8" },
  DISUSE_PENDING:   { label: "待除帳",  bg: "#fef9c3", color: "#713f12" },
  RESOLVED:         { label: "已結案",  bg: "#f0fdf4", color: "#14532d" },
  WRITTEN_OFF:      { label: "已除帳",  bg: "#f1efe8", color: "#888" },
  REJECTED:         { label: "已拒絕",  bg: "#fef2f2", color: "#7f1d1d" },
}

const CLAIM_TYPE_LABELS = {
  DAMAGE:           "損壞品",
  COUNT_DISCREPANCY:"盤點差異",
  INBOUND_SHORTAGE: "進貨短少",
  PICKING_SHORTAGE: "揀貨短少",
  TRANSFER_SHORTAGE:"調撥短少",
  TRANSFER_EXCESS:  "調撥溢出",
}

const CLAIM_TYPE_COLORS = {
  DAMAGE:           "#dc2626",
  COUNT_DISCREPANCY:"#d97706",
  INBOUND_SHORTAGE: "#7c3aed",
  PICKING_SHORTAGE: "#ea580c",
  TRANSFER_SHORTAGE:"#0284c7",
  TRANSFER_EXCESS:  "#16a34a",
}

function StatusTag({ status }) {
  const cfg = STATUS_CONFIG[status] || { label: status, bg: "#f1f5f9", color: "#475569" }
  return <span style={{ display:"inline-block", fontSize:11, fontWeight:600, padding:"2px 8px", borderRadius:99, background:cfg.bg, color:cfg.color }}>{cfg.label}</span>
}

function ClaimTypeTag({ type }) {
  const color = CLAIM_TYPE_COLORS[type] || "#888"
  return <span style={{ display:"inline-block", fontSize:11, fontWeight:600, padding:"2px 8px", borderRadius:4, background:color+"18", color, border:`1px solid ${color}33` }}>{CLAIM_TYPE_LABELS[type] || type}</span>
}

function DecisionLog({ log }) {
  const [open, setOpen] = useState(false)
  if (!log || log.length === 0) return null
  const stepColor = { start:"#888", router:"#2563eb", invoke:"#7C3AED", tool_call:"#D97706", tool_result:"#16a34a", integrate:"#0891B2", done:"#16a34a", error:"#E24B4A" }
  return (
    <div style={{ marginTop: 8 }}>
      <button onClick={() => setOpen(o => !o)} style={{ ...S.btn, fontSize: 11, padding:"3px 10px", color:"#2563eb", borderColor:"#bfdbfe" }}>
        {open ? "▲" : "▼"} 決策推理（{log.length} 步）
      </button>
      {open && (
        <div style={{ marginTop: 8, borderLeft: "2px solid #e8e6e0", paddingLeft: 12 }}>
          {log.map((entry, i) => (
            <div key={i} style={{ display:"flex", gap:8, marginBottom:8 }}>
              <div style={{ width:7, height:7, borderRadius:"50%", background:stepColor[entry.step]||"#888", marginTop:5, flexShrink:0 }} />
              <div>
                <span style={{ fontSize:10, fontWeight:600, color:stepColor[entry.step]||"#888", textTransform:"uppercase", marginRight:6 }}>{entry.step}</span>
                <span style={{ fontSize:12, color:"#555" }}>{entry.reasoning}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Generic table helpers ─────────────────────────────────────────────────────
function EmptyRow({ cols, text = "目前無資料" }) {
  return <tr><td colSpan={cols} style={{ ...S.td, textAlign:"center", color:"#bbb", padding:"24px" }}>{text}</td></tr>
}

// ── Dashboard Page ────────────────────────────────────────────────────────────
function DashboardPage({ onNavigate }) {
  const [data, setData] = useState(null)
  const [lowStock, setLowStock] = useState([])

  useEffect(() => {
    axios.get(`${API}/api/dashboard`).then(r => setData(r.data))
    axios.get(`${API}/api/inventory`).then(r => {
      const ls = r.data.filter(i => i.quantity < i.safety_stock)
      ls.sort((a, b) => (b.safety_stock - b.quantity) - (a.safety_stock - a.quantity))
      setLowStock(ls)
    })
  }, [])

  if (!data) return <div style={{ padding:40, color:"#aaa" }}>載入中...</div>

  const { warehouse_stats: whs, claim_summary, pending_operations: pops } = data
  const totalAvail  = whs.reduce((s, w) => s + w.available_qty, 0)
  const totalProblem = whs.reduce((s, w) => s + w.problem_qty, 0)
  const totalOpenClaims = whs.reduce((s, w) => s + w.open_internal_claims + w.open_cross_claims, 0) / 2
  const totalPending = Object.values(pops).reduce((s, v) => s + v, 0)

  return (
    <>
      <div style={S.topbar}>
        <div>
          <div style={S.topbarTitle}>倉庫總覽</div>
          <div style={S.topbarSub}>{new Date().toISOString().slice(0,10)} · 三倉即時狀態</div>
        </div>
      </div>
      <div style={S.content}>
        <div style={S.metrics}>
          <div style={S.metric}>
            <div style={S.metricLabel}>可用庫存總量</div>
            <div style={S.metricValue}>{totalAvail.toLocaleString()}</div>
            <div style={S.metricSub}>PICKING + BUFFER</div>
          </div>
          <div style={S.metric}>
            <div style={S.metricLabel}>問題品數量</div>
            <div style={{ ...S.metricValue, color: totalProblem > 0 ? "#e24b4a" : "#1a1a1a" }}>{totalProblem}</div>
            <div style={S.metricSub}>PROBLEM / CB / DISUSE</div>
          </div>
          <div style={S.metric}>
            <div style={S.metricLabel}>未結 Claim 數</div>
            <div style={{ ...S.metricValue, color: totalOpenClaims > 0 ? "#d97706" : "#1a1a1a" }}>{claim_summary.by_status ? Object.entries(claim_summary.by_status).filter(([k]) => !["RESOLVED","WRITTEN_OFF","REJECTED"].includes(k)).reduce((s,[,v]) => s+v, 0) : 0}</div>
            <div style={S.metricSub}>PENDING + INVESTIGATING + ...</div>
          </div>
          <div style={S.metric}>
            <div style={S.metricLabel}>待處理作業</div>
            <div style={{ ...S.metricValue, color: totalPending > 0 ? "#2563eb" : "#1a1a1a" }}>{totalPending}</div>
            <div style={S.metricSub}>入庫 {pops.inbound} / 轉倉 {pops.transfers} / 出貨 {pops.outbound} / 盤點 {pops.cycle_counts}</div>
          </div>
        </div>

        {/* Warehouse grid */}
        <div style={S.sectionLabel}>各倉狀態</div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12, marginBottom:24 }}>
          {whs.map(w => (
            <div key={w.warehouse_id} style={{ ...S.card, marginBottom:0 }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
                <div style={{ fontSize:14, fontWeight:600 }}>{w.warehouse_id}</div>
                <div style={{ fontSize:12, color:"#888" }}>{w.warehouse_name}</div>
              </div>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8 }}>
                <div style={{ background:"#f9f8f6", borderRadius:6, padding:"8px 10px" }}>
                  <div style={{ fontSize:10, color:"#888" }}>可用庫存</div>
                  <div style={{ fontSize:18, fontWeight:600, marginTop:2 }}>{w.available_qty.toLocaleString()}</div>
                </div>
                <div style={{ background: w.problem_qty > 0 ? "#fef2f2" : "#f9f8f6", borderRadius:6, padding:"8px 10px" }}>
                  <div style={{ fontSize:10, color:"#888" }}>問題品</div>
                  <div style={{ fontSize:18, fontWeight:600, color: w.problem_qty > 0 ? "#e24b4a" : "#1a1a1a", marginTop:2 }}>{w.problem_qty}</div>
                </div>
                <div style={{ background: w.open_internal_claims > 0 ? "#fffbeb" : "#f9f8f6", borderRadius:6, padding:"8px 10px" }}>
                  <div style={{ fontSize:10, color:"#888" }}>內部問題帳</div>
                  <div style={{ fontSize:16, fontWeight:600, color: w.open_internal_claims > 0 ? "#d97706" : "#1a1a1a", marginTop:2 }}>{w.open_internal_claims}</div>
                </div>
                <div style={{ background: w.open_cross_claims > 0 ? "#eff6ff" : "#f9f8f6", borderRadius:6, padding:"8px 10px" }}>
                  <div style={{ fontSize:10, color:"#888" }}>跨倉 Claim</div>
                  <div style={{ fontSize:16, fontWeight:600, color: w.open_cross_claims > 0 ? "#2563eb" : "#1a1a1a", marginTop:2 }}>{w.open_cross_claims}</div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Low stock alerts */}
        {lowStock.length > 0 && (
          <>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
              <div style={S.sectionLabel}>低庫存警示 ({lowStock.length} 項)</div>
            </div>
            <div style={S.tableWrap}>
              <table style={{ width:"100%", borderCollapse:"collapse" }}>
                <thead><tr>{["倉庫","SKU","品名","現庫存","安全庫存","缺口"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                <tbody>
                  {lowStock.slice(0,8).map((item, i) => (
                    <tr key={i}>
                      <td style={S.td}>{item.warehouse_id} {item.warehouse_name}</td>
                      <td style={S.tdMono}>{item.sku}</td>
                      <td style={S.td}>{item.product_name}</td>
                      <td style={{ ...S.td, color:"#e24b4a", fontWeight:600 }}>{item.quantity} {item.unit}</td>
                      <td style={{ ...S.td, color:"#888" }}>{item.safety_stock}</td>
                      <td style={{ ...S.td, color:"#c0392b", fontWeight:600 }}>↓{item.safety_stock - item.quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Pending operations */}
        <div style={S.sectionLabel}>待處理作業</div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10 }}>
          {[
            { label:"入庫驗收", count:pops.inbound, page:"inbound", color:"#7c3aed" },
            { label:"調撥進行中", count:pops.transfers, page:"transfer", color:"#2563eb" },
            { label:"出貨待揀", count:pops.outbound, page:"outbound", color:"#d97706" },
            { label:"盤點進行中", count:pops.cycle_counts, page:"cycle-count", color:"#16a34a" },
          ].map(op => (
            <div key={op.label} style={{ ...S.card, marginBottom:0, cursor:"pointer", transition:"box-shadow 0.15s" }} onClick={() => onNavigate(op.page)}>
              <div style={{ fontSize:12, color:"#888", marginBottom:6 }}>{op.label}</div>
              <div style={{ fontSize:24, fontWeight:600, color: op.count > 0 ? op.color : "#1a1a1a" }}>{op.count}</div>
              <div style={{ fontSize:11, color:"#bbb", marginTop:4 }}>點擊進入 →</div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

// ── Inventory Page ────────────────────────────────────────────────────────────
function InventoryPage() {
  const [items, setItems] = useState([])
  const [problemStock, setProblemStock] = useState([])
  const [filterWh, setFilterWh] = useState("")

  useEffect(() => {
    axios.get(`${API}/api/inventory`).then(r => setItems(r.data))
    axios.get(`${API}/api/inventory/problem-stock`).then(r => setProblemStock(r.data))
  }, [])

  const displayed = filterWh ? items.filter(i => i.warehouse_id === filterWh) : items
  const lowStockItems = displayed.filter(i => i.quantity < i.safety_stock)

  return (
    <>
      <div style={S.topbar}>
        <div>
          <div style={S.topbarTitle}>庫存看板</div>
          <div style={S.topbarSub}>可用庫存（PICKING + BUFFER）及問題品</div>
        </div>
        <select style={{ ...S.select, width:140 }} value={filterWh} onChange={e => setFilterWh(e.target.value)}>
          <option value="">全部倉庫</option>
          <option value="W1">W1 北區倉</option>
          <option value="W2">W2 中區倉</option>
          <option value="W3">W3 南區倉</option>
        </select>
      </div>
      <div style={S.content}>
        {lowStockItems.length > 0 && (
          <div style={S.alertYellow}>⚠️ 有 {lowStockItems.length} 項低於安全庫存</div>
        )}
        <div style={S.sectionLabel}>可用庫存</div>
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["倉庫","SKU","品名","可用數量","安全庫存","狀態"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {displayed.length === 0 && <EmptyRow cols={6} />}
              {displayed.map((item, i) => {
                const isLow = item.quantity < item.safety_stock
                return (
                  <tr key={i} style={{ background: isLow ? "#fffbeb" : "inherit" }}>
                    <td style={S.td}>{item.warehouse_id} <span style={{ color:"#888", fontSize:12 }}>{item.warehouse_name}</span></td>
                    <td style={S.tdMono}>{item.sku}</td>
                    <td style={S.td}>{item.product_name}</td>
                    <td style={{ ...S.td, fontWeight:600, color: isLow ? "#e24b4a" : "#16a34a" }}>{item.quantity} <span style={{ fontSize:11, color:"#888", fontWeight:400 }}>{item.unit}</span></td>
                    <td style={{ ...S.td, color:"#888" }}>{item.safety_stock}</td>
                    <td style={S.td}>
                      {isLow
                        ? <span style={{ fontSize:11, fontWeight:600, background:"#fef2f2", color:"#e24b4a", padding:"2px 8px", borderRadius:99 }}>低庫存 ↓{item.safety_stock - item.quantity}</span>
                        : <span style={{ fontSize:11, fontWeight:600, background:"#f0fdf4", color:"#16a34a", padding:"2px 8px", borderRadius:99 }}>正常</span>
                      }
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {problemStock.length > 0 && (
          <>
            <div style={S.sectionLabel}>問題品庫存（PROBLEM / COLLECT_BUFFER / DISUSE）</div>
            <div style={S.tableWrap}>
              <table style={{ width:"100%", borderCollapse:"collapse" }}>
                <thead><tr>{["倉庫","區域","分類","SKU","品名","數量","帳務狀態"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
                <tbody>
                  {problemStock.map((item, i) => (
                    <tr key={i}>
                      <td style={S.td}>{item.warehouse_id}</td>
                      <td style={S.td}><span style={{ fontSize:11, background:"#fef2f2", color:"#e24b4a", padding:"2px 7px", borderRadius:4, fontWeight:600 }}>{item.zone_type}</span></td>
                      <td style={S.td}>{item.cb_category || "—"}</td>
                      <td style={S.tdMono}>{item.sku}</td>
                      <td style={S.td}>{item.product_name}</td>
                      <td style={{ ...S.td, fontWeight:600 }}>{item.quantity}</td>
                      <td style={S.td}><span style={{ fontSize:11, color:"#888" }}>{item.acct_status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  )
}

// ── Inbound Page ──────────────────────────────────────────────────────────────
function InboundPage() {
  const [orders, setOrders] = useState([])
  const [detail, setDetail] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ warehouse_id:"W1", supplier:"", details:[{ sku:"P001", qty_expected:100 }] })
  const [receiveForm, setReceiveForm] = useState({})
  const [products, setProducts] = useState([])

  const load = useCallback(() => axios.get(`${API}/api/inbound`).then(r => setOrders(r.data)), [])
  const loadDetail = (id) => axios.get(`${API}/api/inbound/${id}`).then(r => {
    setDetail(r.data)
    const rf = {}
    r.data.details.forEach(d => { rf[d.id] = { qty_actual: d.qty_expected, damage_qty: 0 } })
    setReceiveForm(rf)
  })

  useEffect(() => {
    load()
    axios.get(`${API}/api/products`).then(r => setProducts(r.data))
  }, [])

  function addDetailRow() { setForm(f => ({ ...f, details: [...f.details, { sku:"P001", qty_expected:10 }] })) }
  function removeDetailRow(i) { setForm(f => ({ ...f, details: f.details.filter((_,j) => j!==i) })) }
  function updateDetailRow(i, field, val) {
    setForm(f => { const d = [...f.details]; d[i] = { ...d[i], [field]: val }; return { ...f, details: d } })
  }

  function submitCreate() {
    const body = { ...form, details: form.details.map(d => ({ sku: d.sku, qty_expected: parseInt(d.qty_expected) })) }
    axios.post(`${API}/api/inbound`, body)
      .then(() => { load(); setShowCreate(false); setForm({ warehouse_id:"W1", supplier:"", details:[{ sku:"P001", qty_expected:100 }] }) })
      .catch(e => alert(e.response?.data?.detail || "建立失敗"))
  }

  function submitReceive() {
    const body = { details: Object.entries(receiveForm).map(([id, v]) => ({ detail_id:parseInt(id), qty_actual:parseInt(v.qty_actual), damage_qty:parseInt(v.damage_qty)||0 })) }
    axios.post(`${API}/api/inbound/${detail.order.order_id}/receive`, body)
      .then(r => { loadDetail(detail.order.order_id); load(); alert(`驗收完成！${r.data.auto_claims?.length ? `自動建立 ${r.data.auto_claims.length} 筆 Claim` : ""}`) })
      .catch(e => alert(e.response?.data?.detail || "驗收失敗"))
  }

  function cancelOrder(id) {
    if (!confirm(`確認取消 ${id}？`)) return
    axios.patch(`${API}/api/inbound/${id}/cancel`).then(() => { load(); setDetail(null) }).catch(e => alert(e.response?.data?.detail))
  }

  if (detail) return (
    <>
      <div style={S.topbar}>
        <div>
          <div style={{ fontSize:13, color:"#888", fontFamily:"monospace" }}>{detail.order.order_id}</div>
          <div style={S.topbarTitle}>入庫驗收</div>
        </div>
        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          <StatusTag status={detail.order.status} />
          {detail.order.status === "DRAFT" && (
            <button style={S.btnDanger} onClick={() => cancelOrder(detail.order.order_id)}>取消</button>
          )}
          <button style={S.btn} onClick={() => setDetail(null)}>← 返回</button>
        </div>
      </div>
      <div style={S.content}>
        <div style={S.card}>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12, fontSize:13 }}>
            <div><div style={{ color:"#888", fontSize:11, marginBottom:3 }}>供應商</div>{detail.order.supplier}</div>
            <div><div style={{ color:"#888", fontSize:11, marginBottom:3 }}>倉庫</div>{detail.order.warehouse_id}</div>
            <div><div style={{ color:"#888", fontSize:11, marginBottom:3 }}>建立時間</div>{detail.order.created_at?.slice(0,16)}</div>
          </div>
        </div>
        {detail.claims?.length > 0 && (
          <div style={S.alertYellow}>自動建立 {detail.claims.length} 筆 Claim：{detail.claims.map(c => c.claim_id).join(", ")}</div>
        )}
        <div style={S.sectionLabel}>驗收明細</div>
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["SKU","品名","預期數量","實際到貨","損壞數量","短少","溢收"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {detail.details.map(d => (
                <tr key={d.id}>
                  <td style={S.tdMono}>{d.sku}</td>
                  <td style={S.td}>{d.product_name}</td>
                  <td style={S.td}>{d.qty_expected}</td>
                  <td style={S.td}>
                    {detail.order.status === "DRAFT" ? (
                      <input type="number" style={{ ...S.input, width:80 }} value={receiveForm[d.id]?.qty_actual ?? d.qty_expected}
                        onChange={e => setReceiveForm(f => ({ ...f, [d.id]: { ...f[d.id], qty_actual: e.target.value } }))} />
                    ) : <span style={{ fontWeight:600 }}>{d.qty_actual ?? "—"}</span>}
                  </td>
                  <td style={S.td}>
                    {detail.order.status === "DRAFT" ? (
                      <input type="number" style={{ ...S.input, width:70 }} value={receiveForm[d.id]?.damage_qty ?? 0}
                        onChange={e => setReceiveForm(f => ({ ...f, [d.id]: { ...f[d.id], damage_qty: e.target.value } }))} />
                    ) : <span style={{ color: d.damage_qty > 0 ? "#e24b4a":"#888" }}>{d.damage_qty ?? 0}</span>}
                  </td>
                  <td style={{ ...S.td, color:"#e24b4a", fontWeight:600 }}>{d.shortage_qty || 0}</td>
                  <td style={{ ...S.td, color:"#16a34a" }}>{d.excess_qty || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {detail.order.status === "DRAFT" && (
          <button style={S.btnPrimary} onClick={submitReceive}>確認驗收</button>
        )}
      </div>
    </>
  )

  return (
    <>
      <div style={S.topbar}>
        <div>
          <div style={S.topbarTitle}>入庫作業</div>
          <div style={S.topbarSub}>供應商來貨驗收管理</div>
        </div>
        <button style={S.btnPrimary} onClick={() => setShowCreate(true)}>+ 建立入庫單</button>
      </div>
      <div style={S.content}>
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["訂單號","倉庫","供應商","狀態","建立日","操作"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {orders.length === 0 && <EmptyRow cols={6} />}
              {orders.map(o => (
                <tr key={o.order_id} style={{ cursor:"pointer" }} onClick={() => loadDetail(o.order_id)}>
                  <td style={S.tdMono}>{o.order_id}</td>
                  <td style={S.td}>{o.warehouse_id} {o.warehouse_name}</td>
                  <td style={S.td}>{o.supplier}</td>
                  <td style={S.td}><StatusTag status={o.status} /></td>
                  <td style={{ ...S.td, color:"#888" }}>{o.created_at?.slice(0,10)}</td>
                  <td style={S.td}><button style={S.btn} onClick={e => { e.stopPropagation(); loadDetail(o.order_id) }}>查看</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showCreate && (
        <div style={S.modal} onClick={() => setShowCreate(false)}>
          <div style={S.modalBox} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize:16, fontWeight:600, marginBottom:16 }}>建立入庫單</div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
              <div style={S.formGroup}>
                <label style={S.label}>入庫倉庫</label>
                <select style={S.select} value={form.warehouse_id} onChange={e => setForm(f => ({ ...f, warehouse_id:e.target.value }))}>
                  <option value="W1">W1 北區倉</option><option value="W2">W2 中區倉</option><option value="W3">W3 南區倉</option>
                </select>
              </div>
              <div style={S.formGroup}>
                <label style={S.label}>供應商</label>
                <input style={S.input} value={form.supplier} onChange={e => setForm(f => ({ ...f, supplier:e.target.value }))} placeholder="供應商名稱" />
              </div>
            </div>
            <div style={S.sectionLabel}>品項明細</div>
            {form.details.map((d, i) => (
              <div key={i} style={{ display:"flex", gap:8, marginBottom:8, alignItems:"center" }}>
                <select style={{ ...S.select, flex:2 }} value={d.sku} onChange={e => updateDetailRow(i,"sku",e.target.value)}>
                  {products.map(p => <option key={p.sku} value={p.sku}>{p.sku} {p.name}</option>)}
                </select>
                <input type="number" style={{ ...S.input, width:90 }} value={d.qty_expected} onChange={e => updateDetailRow(i,"qty_expected",e.target.value)} placeholder="預期數量" />
                <button style={{ ...S.btn, color:"#e24b4a", flexShrink:0 }} onClick={() => removeDetailRow(i)}>✕</button>
              </div>
            ))}
            <button style={{ ...S.btn, marginBottom:16 }} onClick={addDetailRow}>+ 新增品項</button>
            <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
              <button style={S.btn} onClick={() => setShowCreate(false)}>取消</button>
              <button style={S.btnPrimary} onClick={submitCreate}>建立</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ── Transfer Page ─────────────────────────────────────────────────────────────
function TransferPage() {
  const [orders, setOrders] = useState([])
  const [detail, setDetail] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ from_wh:"W1", to_wh:"W2", details:[{ sku:"P001", qty_ordered:50 }] })
  const [issueForm, setIssueForm] = useState({})
  const [receiveForm, setReceiveForm] = useState({})
  const [products, setProducts] = useState([])

  const load = useCallback(() => axios.get(`${API}/api/transfers`).then(r => setOrders(r.data)), [])
  const loadDetail = (id) => axios.get(`${API}/api/transfers/${id}`).then(r => {
    setDetail(r.data)
    const isf = {}, rcf = {}
    r.data.details.forEach(d => {
      isf[d.id] = { qty_issued: d.qty_ordered }
      rcf[d.id] = { qty_received: d.qty_issued || d.qty_ordered }
    })
    setIssueForm(isf); setReceiveForm(rcf)
  })

  useEffect(() => { load(); axios.get(`${API}/api/products`).then(r => setProducts(r.data)) }, [])

  function addRow() { setForm(f => ({ ...f, details:[...f.details, { sku:"P001", qty_ordered:10 }] })) }
  function removeRow(i) { setForm(f => ({ ...f, details:f.details.filter((_,j) => j!==i) })) }
  function updateRow(i, fld, val) { setForm(f => { const d=[...f.details]; d[i]={...d[i],[fld]:val}; return {...f,details:d} }) }

  function submitCreate() {
    const body = { ...form, details: form.details.map(d => ({ sku:d.sku, qty_ordered:parseInt(d.qty_ordered) })) }
    axios.post(`${API}/api/transfers`, body).then(() => { load(); setShowCreate(false) }).catch(e => alert(e.response?.data?.detail))
  }
  function submitIssue() {
    const body = { details: Object.entries(issueForm).map(([id,v]) => ({ detail_id:parseInt(id), qty_issued:parseInt(v.qty_issued) })) }
    axios.post(`${API}/api/transfers/${detail.order.order_id}/issue`, body).then(() => loadDetail(detail.order.order_id)).catch(e => alert(e.response?.data?.detail))
  }
  function submitReceive() {
    const body = { details: Object.entries(receiveForm).map(([id,v]) => ({ detail_id:parseInt(id), qty_received:parseInt(v.qty_received) })) }
    axios.post(`${API}/api/transfers/${detail.order.order_id}/receive`, body)
      .then(r => { loadDetail(detail.order.order_id); load(); r.data.auto_claims?.length && alert(`自動建立 ${r.data.auto_claims.length} 筆 TRANSFER_SHORTAGE Claim`) })
      .catch(e => alert(e.response?.data?.detail))
  }
  function submitComplete() {
    axios.post(`${API}/api/transfers/${detail.order.order_id}/complete`).then(() => { loadDetail(detail.order.order_id); load() }).catch(e => alert(e.response?.data?.detail))
  }

  if (detail) return (
    <>
      <div style={S.topbar}>
        <div>
          <div style={{ fontSize:13, color:"#888", fontFamily:"monospace" }}>{detail.order.order_id}</div>
          <div style={S.topbarTitle}>{detail.order.from_name} → {detail.order.to_name}</div>
        </div>
        <div style={{ display:"flex", gap:8 }}>
          <StatusTag status={detail.order.status} />
          <button style={S.btn} onClick={() => setDetail(null)}>← 返回</button>
        </div>
      </div>
      <div style={S.content}>
        {detail.claims?.length > 0 && (
          <div style={S.alertYellow}>關聯 Claim：{detail.claims.map(c => `${c.claim_id}(${c.status})`).join(", ")}</div>
        )}
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["SKU","品名","訂購","出庫","收貨","短少","溢收"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {detail.details.map(d => (
                <tr key={d.id}>
                  <td style={S.tdMono}>{d.sku}</td>
                  <td style={S.td}>{d.product_name}</td>
                  <td style={S.td}>{d.qty_ordered}</td>
                  <td style={S.td}>
                    {detail.order.status === "DRAFT"
                      ? <input type="number" style={{ ...S.input, width:80 }} value={issueForm[d.id]?.qty_issued ?? d.qty_ordered} onChange={e => setIssueForm(f => ({ ...f, [d.id]:{qty_issued:e.target.value} }))} />
                      : <span style={{ fontWeight:600 }}>{d.qty_issued ?? "—"}</span>}
                  </td>
                  <td style={S.td}>
                    {detail.order.status === "IN_TRANSIT"
                      ? <input type="number" style={{ ...S.input, width:80 }} value={receiveForm[d.id]?.qty_received ?? d.qty_issued} onChange={e => setReceiveForm(f => ({ ...f, [d.id]:{qty_received:e.target.value} }))} />
                      : <span style={{ fontWeight:600 }}>{d.qty_received ?? "—"}</span>}
                  </td>
                  <td style={{ ...S.td, color:"#e24b4a", fontWeight:600 }}>{d.shortage_qty || 0}</td>
                  <td style={{ ...S.td, color:"#16a34a" }}>{d.excess_qty || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ display:"flex", gap:8 }}>
          {detail.order.status === "DRAFT" && <button style={S.btnPrimary} onClick={submitIssue}>確認出庫</button>}
          {detail.order.status === "IN_TRANSIT" && <button style={S.btnBlue} onClick={submitReceive}>確認收貨</button>}
          {detail.order.status === "RECEIVED" && <button style={S.btnSuccess} onClick={submitComplete}>結單</button>}
        </div>
      </div>
    </>
  )

  return (
    <>
      <div style={S.topbar}>
        <div><div style={S.topbarTitle}>轉倉作業</div><div style={S.topbarSub}>倉轉倉調撥管理</div></div>
        <button style={S.btnPrimary} onClick={() => setShowCreate(true)}>+ 建立調撥單</button>
      </div>
      <div style={S.content}>
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["訂單號","出貨倉","收貨倉","狀態","建立日","操作"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {orders.length === 0 && <EmptyRow cols={6} />}
              {orders.map(o => (
                <tr key={o.order_id} style={{ cursor:"pointer" }} onClick={() => loadDetail(o.order_id)}>
                  <td style={S.tdMono}>{o.order_id}</td>
                  <td style={S.td}>{o.from_wh} {o.from_name}</td>
                  <td style={S.td}>{o.to_wh} {o.to_name}</td>
                  <td style={S.td}><StatusTag status={o.status} /></td>
                  <td style={{ ...S.td, color:"#888" }}>{o.created_at?.slice(0,10)}</td>
                  <td style={S.td}><button style={S.btn} onClick={e => { e.stopPropagation(); loadDetail(o.order_id) }}>查看</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {showCreate && (
        <div style={S.modal} onClick={() => setShowCreate(false)}>
          <div style={S.modalBox} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize:16, fontWeight:600, marginBottom:16 }}>建立調撥單</div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
              <div style={S.formGroup}><label style={S.label}>出貨倉</label>
                <select style={S.select} value={form.from_wh} onChange={e => setForm(f => ({ ...f, from_wh:e.target.value }))}>
                  <option value="W1">W1 北區倉</option><option value="W2">W2 中區倉</option><option value="W3">W3 南區倉</option>
                </select>
              </div>
              <div style={S.formGroup}><label style={S.label}>收貨倉</label>
                <select style={S.select} value={form.to_wh} onChange={e => setForm(f => ({ ...f, to_wh:e.target.value }))}>
                  <option value="W1">W1 北區倉</option><option value="W2">W2 中區倉</option><option value="W3">W3 南區倉</option>
                </select>
              </div>
            </div>
            {form.details.map((d,i) => (
              <div key={i} style={{ display:"flex", gap:8, marginBottom:8 }}>
                <select style={{ ...S.select, flex:2 }} value={d.sku} onChange={e => updateRow(i,"sku",e.target.value)}>
                  {products.map(p => <option key={p.sku} value={p.sku}>{p.sku} {p.name}</option>)}
                </select>
                <input type="number" style={{ ...S.input, width:90 }} value={d.qty_ordered} onChange={e => updateRow(i,"qty_ordered",e.target.value)} />
                <button style={{ ...S.btn, color:"#e24b4a" }} onClick={() => removeRow(i)}>✕</button>
              </div>
            ))}
            <button style={{ ...S.btn, marginBottom:16 }} onClick={addRow}>+ 新增</button>
            <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
              <button style={S.btn} onClick={() => setShowCreate(false)}>取消</button>
              <button style={S.btnPrimary} onClick={submitCreate}>建立</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ── Outbound Page ─────────────────────────────────────────────────────────────
function OutboundPage() {
  const [orders, setOrders] = useState([])
  const [detail, setDetail] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ warehouse_id:"W1", customer:"", details:[{ sku:"P001", qty_ordered:30 }] })
  const [pickForm, setPickForm] = useState({})
  const [products, setProducts] = useState([])

  const load = useCallback(() => axios.get(`${API}/api/outbound`).then(r => setOrders(r.data)), [])
  const loadDetail = (id) => axios.get(`${API}/api/outbound/${id}`).then(r => {
    setDetail(r.data)
    const pf = {}
    r.data.details.forEach(d => { pf[d.id] = { qty_picked: d.qty_ordered, damage_qty: 0 } })
    setPickForm(pf)
  })

  useEffect(() => { load(); axios.get(`${API}/api/products`).then(r => setProducts(r.data)) }, [])

  function addRow() { setForm(f => ({ ...f, details:[...f.details,{sku:"P001",qty_ordered:10}] })) }
  function removeRow(i) { setForm(f => ({ ...f, details:f.details.filter((_,j) => j!==i) })) }
  function updateRow(i,fld,val) { setForm(f => { const d=[...f.details]; d[i]={...d[i],[fld]:val}; return {...f,details:d} }) }

  function submitCreate() {
    const body = { ...form, details:form.details.map(d => ({ sku:d.sku, qty_ordered:parseInt(d.qty_ordered) })) }
    axios.post(`${API}/api/outbound`, body).then(() => { load(); setShowCreate(false) }).catch(e => alert(e.response?.data?.detail))
  }
  function submitPick() {
    const body = { details: Object.entries(pickForm).map(([id,v]) => ({ detail_id:parseInt(id), qty_picked:parseInt(v.qty_picked), damage_qty:parseInt(v.damage_qty)||0 })) }
    axios.post(`${API}/api/outbound/${detail.order.order_id}/pick`, body)
      .then(r => { loadDetail(detail.order.order_id); load(); r.data.auto_claims?.length && alert(`自動建立 ${r.data.auto_claims.length} 筆 Claim`) })
      .catch(e => alert(e.response?.data?.detail))
  }

  if (detail) return (
    <>
      <div style={S.topbar}>
        <div>
          <div style={{ fontSize:13, color:"#888", fontFamily:"monospace" }}>{detail.order.order_id}</div>
          <div style={S.topbarTitle}>揀貨出庫 · {detail.order.customer}</div>
        </div>
        <div style={{ display:"flex", gap:8 }}><StatusTag status={detail.order.status} /><button style={S.btn} onClick={() => setDetail(null)}>← 返回</button></div>
      </div>
      <div style={S.content}>
        {detail.claims?.length > 0 && <div style={S.alertYellow}>自動 Claim：{detail.claims.map(c=>c.claim_id).join(", ")}</div>}
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["SKU","品名","訂購","揀貨","損壞","短少"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {detail.details.map(d => (
                <tr key={d.id}>
                  <td style={S.tdMono}>{d.sku}</td><td style={S.td}>{d.product_name}</td>
                  <td style={S.td}>{d.qty_ordered}</td>
                  <td style={S.td}>
                    {detail.order.status === "DRAFT"
                      ? <input type="number" style={{ ...S.input, width:80 }} value={pickForm[d.id]?.qty_picked ?? d.qty_ordered} onChange={e => setPickForm(f => ({ ...f, [d.id]:{...f[d.id],qty_picked:e.target.value} }))} />
                      : <span style={{ fontWeight:600 }}>{d.qty_picked ?? "—"}</span>}
                  </td>
                  <td style={S.td}>
                    {detail.order.status === "DRAFT"
                      ? <input type="number" style={{ ...S.input, width:70 }} value={pickForm[d.id]?.damage_qty ?? 0} onChange={e => setPickForm(f => ({ ...f, [d.id]:{...f[d.id],damage_qty:e.target.value} }))} />
                      : <span style={{ color:"#e24b4a" }}>{d.damage_qty || 0}</span>}
                  </td>
                  <td style={{ ...S.td, color:"#e24b4a", fontWeight:600 }}>{d.shortage_qty || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {detail.order.status === "DRAFT" && <button style={S.btnPrimary} onClick={submitPick}>確認出庫</button>}
      </div>
    </>
  )

  return (
    <>
      <div style={S.topbar}>
        <div><div style={S.topbarTitle}>出貨作業</div><div style={S.topbarSub}>客戶出貨揀貨管理</div></div>
        <button style={S.btnPrimary} onClick={() => setShowCreate(true)}>+ 建立出貨單</button>
      </div>
      <div style={S.content}>
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["訂單號","倉庫","客戶","狀態","建立日","操作"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {orders.length === 0 && <EmptyRow cols={6} />}
              {orders.map(o => (
                <tr key={o.order_id} style={{ cursor:"pointer" }} onClick={() => loadDetail(o.order_id)}>
                  <td style={S.tdMono}>{o.order_id}</td>
                  <td style={S.td}>{o.warehouse_id} {o.warehouse_name}</td>
                  <td style={S.td}>{o.customer}</td>
                  <td style={S.td}><StatusTag status={o.status} /></td>
                  <td style={{ ...S.td, color:"#888" }}>{o.created_at?.slice(0,10)}</td>
                  <td style={S.td}><button style={S.btn} onClick={e => { e.stopPropagation(); loadDetail(o.order_id) }}>查看</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {showCreate && (
        <div style={S.modal} onClick={() => setShowCreate(false)}>
          <div style={S.modalBox} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize:16, fontWeight:600, marginBottom:16 }}>建立出貨單</div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
              <div style={S.formGroup}><label style={S.label}>出貨倉庫</label>
                <select style={S.select} value={form.warehouse_id} onChange={e => setForm(f => ({ ...f, warehouse_id:e.target.value }))}>
                  <option value="W1">W1 北區倉</option><option value="W2">W2 中區倉</option><option value="W3">W3 南區倉</option>
                </select>
              </div>
              <div style={S.formGroup}><label style={S.label}>客戶</label>
                <input style={S.input} value={form.customer} onChange={e => setForm(f => ({ ...f, customer:e.target.value }))} placeholder="客戶名稱" />
              </div>
            </div>
            {form.details.map((d,i) => (
              <div key={i} style={{ display:"flex", gap:8, marginBottom:8 }}>
                <select style={{ ...S.select, flex:2 }} value={d.sku} onChange={e => updateRow(i,"sku",e.target.value)}>
                  {products.map(p => <option key={p.sku} value={p.sku}>{p.sku} {p.name}</option>)}
                </select>
                <input type="number" style={{ ...S.input, width:90 }} value={d.qty_ordered} onChange={e => updateRow(i,"qty_ordered",e.target.value)} />
                <button style={{ ...S.btn, color:"#e24b4a" }} onClick={() => removeRow(i)}>✕</button>
              </div>
            ))}
            <button style={{ ...S.btn, marginBottom:16 }} onClick={addRow}>+ 新增</button>
            <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
              <button style={S.btn} onClick={() => setShowCreate(false)}>取消</button>
              <button style={S.btnPrimary} onClick={submitCreate}>建立</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ── Cycle Count Page ──────────────────────────────────────────────────────────
function CycleCountPage() {
  const [counts, setCounts] = useState([])
  const [detail, setDetail] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ warehouse_id:"W1", count_type:"MANUAL", location_id:"", skus:"" })
  const [submitForm, setSubmitForm] = useState({})

  const load = useCallback(() => axios.get(`${API}/api/cycle-counts`).then(r => setCounts(r.data)), [])
  const loadDetail = (id) => axios.get(`${API}/api/cycle-counts/${id}`).then(r => {
    setDetail(r.data)
    const sf = {}
    r.data.details.forEach(d => { sf[d.id] = { qty_actual: d.qty_system } })
    setSubmitForm(sf)
  })

  useEffect(() => { load() }, [])

  function submitCreate() {
    const body = {
      warehouse_id: form.warehouse_id,
      count_type: form.count_type,
      location_id: form.location_id || null,
      skus: form.skus ? form.skus.split(",").map(s => s.trim()).filter(Boolean) : null,
    }
    axios.post(`${API}/api/cycle-counts`, body).then(r => {
      load(); setShowCreate(false)
      alert(`已建立盤點單 ${r.data.count_id}，共 ${r.data.detail_lines} 筆`)
    }).catch(e => alert(e.response?.data?.detail))
  }

  function submitCount() {
    const body = { details: Object.entries(submitForm).map(([id,v]) => ({ detail_id:parseInt(id), qty_actual:parseInt(v.qty_actual)||0 })) }
    axios.post(`${API}/api/cycle-counts/${detail.count.count_id}/submit`, body)
      .then(r => {
        loadDetail(detail.count.count_id); load()
        const { clean_lines, auto_claims, surplus_lines } = r.data
        alert(`盤點完成！正確 ${clean_lines} 筆，短少 ${auto_claims.length} 筆（已建 Claim），盈餘 ${surplus_lines.length} 筆`)
      })
      .catch(e => alert(e.response?.data?.detail))
  }

  if (detail) return (
    <>
      <div style={S.topbar}>
        <div>
          <div style={{ fontSize:13, color:"#888", fontFamily:"monospace" }}>{detail.count.count_id}</div>
          <div style={S.topbarTitle}>盤點明細 · {detail.count.warehouse_name}</div>
        </div>
        <div style={{ display:"flex", gap:8 }}><StatusTag status={detail.count.status} /><button style={S.btn} onClick={() => setDetail(null)}>← 返回</button></div>
      </div>
      <div style={S.content}>
        {detail.claims?.length > 0 && <div style={S.alertYellow}>盤點短少自動建立 {detail.claims.length} 筆 Claim</div>}
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["儲位","SKU","品名","系統庫存","實際數量","差異"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {detail.details.map(d => {
                const diff = d.difference ?? (d.qty_actual != null ? d.qty_actual - d.qty_system : null)
                return (
                  <tr key={d.id}>
                    <td style={S.tdMono}>{d.location_id}</td>
                    <td style={S.tdMono}>{d.sku}</td>
                    <td style={S.td}>{d.product_name}</td>
                    <td style={S.td}>{d.qty_system}</td>
                    <td style={S.td}>
                      {detail.count.status === "IN_PROGRESS"
                        ? <input type="number" style={{ ...S.input, width:80 }} value={submitForm[d.id]?.qty_actual ?? d.qty_system}
                            onChange={e => setSubmitForm(f => ({ ...f, [d.id]:{qty_actual:e.target.value} }))} />
                        : <span style={{ fontWeight:600 }}>{d.qty_actual ?? "—"}</span>}
                    </td>
                    <td style={{ ...S.td, fontWeight:600, color: diff == null ? "#888" : diff < 0 ? "#e24b4a" : diff > 0 ? "#16a34a" : "#888" }}>
                      {diff == null ? "—" : diff > 0 ? `+${diff}` : diff}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {detail.count.status === "IN_PROGRESS" && <button style={S.btnPrimary} onClick={submitCount}>提交盤點結果</button>}
      </div>
    </>
  )

  return (
    <>
      <div style={S.topbar}>
        <div><div style={S.topbarTitle}>庫內盤點</div><div style={S.topbarSub}>實地盤點與差異調整</div></div>
        <button style={S.btnPrimary} onClick={() => setShowCreate(true)}>+ 建立盤點單</button>
      </div>
      <div style={S.content}>
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["盤點號","倉庫","盤點類型","項目數","短少行","狀態","建立日"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {counts.length === 0 && <EmptyRow cols={7} />}
              {counts.map(c => (
                <tr key={c.count_id} style={{ cursor:"pointer" }} onClick={() => loadDetail(c.count_id)}>
                  <td style={S.tdMono}>{c.count_id}</td>
                  <td style={S.td}>{c.warehouse_id} {c.warehouse_name}</td>
                  <td style={S.td}>{c.count_type}</td>
                  <td style={S.td}>{c.detail_count || 0}</td>
                  <td style={{ ...S.td, color: c.shortage_lines > 0 ? "#e24b4a":"#888", fontWeight:600 }}>{c.shortage_lines || 0}</td>
                  <td style={S.td}><StatusTag status={c.status} /></td>
                  <td style={{ ...S.td, color:"#888" }}>{c.created_at?.slice(0,10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {showCreate && (
        <div style={S.modal} onClick={() => setShowCreate(false)}>
          <div style={S.modalBox} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize:16, fontWeight:600, marginBottom:16 }}>建立盤點單</div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
              <div style={S.formGroup}><label style={S.label}>倉庫</label>
                <select style={S.select} value={form.warehouse_id} onChange={e => setForm(f => ({ ...f, warehouse_id:e.target.value }))}>
                  <option value="W1">W1 北區倉</option><option value="W2">W2 中區倉</option><option value="W3">W3 南區倉</option>
                </select>
              </div>
              <div style={S.formGroup}><label style={S.label}>盤點類型</label>
                <select style={S.select} value={form.count_type} onChange={e => setForm(f => ({ ...f, count_type:e.target.value }))}>
                  <option value="MANUAL">人工盤點</option><option value="SCHEDULED">排程盤點</option>
                </select>
              </div>
            </div>
            <div style={S.formGroup}><label style={S.label}>指定儲位（選填，不填=整倉PICKING+BUFFER）</label>
              <input style={S.input} placeholder="例如 W1-PICK-001" value={form.location_id} onChange={e => setForm(f => ({ ...f, location_id:e.target.value }))} />
            </div>
            <div style={S.formGroup}><label style={S.label}>指定品項（選填，逗號分隔，如 P001,P002）</label>
              <input style={S.input} placeholder="不填則盤全部品項" value={form.skus} onChange={e => setForm(f => ({ ...f, skus:e.target.value }))} />
            </div>
            <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
              <button style={S.btn} onClick={() => setShowCreate(false)}>取消</button>
              <button style={S.btnPrimary} onClick={submitCreate}>建立並快照庫存</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ── Claims Page (Internal + Cross) ────────────────────────────────────────────
function ClaimsPage({ crossWarehouse }) {
  const [claims, setClaims] = useState([])
  const [detail, setDetail] = useState(null)
  const [approvals, setApprovals] = useState([])
  const [actionNote, setActionNote] = useState("")
  const [cbCategory, setCbCategory] = useState("")
  const [showApprovals, setShowApprovals] = useState(false)

  const load = useCallback(() => {
    const param = crossWarehouse ? "cross_warehouse=true" : "cross_warehouse=false"
    axios.get(`${API}/api/claims?${param}`).then(r => setClaims(r.data))
    if (!crossWarehouse) axios.get(`${API}/api/approvals`).then(r => setApprovals(r.data))
  }, [crossWarehouse])

  const loadDetail = (id) => axios.get(`${API}/api/claims/${id}`).then(r => setDetail(r.data))
  useEffect(() => { load(); setDetail(null) }, [load])

  function doAction(endpoint, body = {}) {
    axios.post(`${API}/api/claims/${detail.claim.claim_id}/${endpoint}`, { actor:"warehouse_mgr", note:actionNote, ...body })
      .then(() => { loadDetail(detail.claim.claim_id); load(); setActionNote("") })
      .catch(e => alert(e.response?.data?.detail))
  }
  function doApproval(apvId, action) {
    axios.post(`${API}/api/approvals/${apvId}/${action}`, { actor:"manager", note:actionNote })
      .then(() => { load(); setActionNote(""); loadDetail(detail?.claim?.claim_id) })
      .catch(e => alert(e.response?.data?.detail))
  }

  const pageTitle = crossWarehouse ? "跨倉 Claim" : "內部問題帳"
  const pageSub = crossWarehouse ? "調撥短少 / 調撥溢出（跨倉帳務）" : "損壞品 / 盤點差異 / 進貨短少 / 揀貨短少"
  const pendingApprovals = approvals.filter(a => a.status === "PENDING")

  if (detail) return (
    <>
      <div style={S.topbar}>
        <div>
          <div style={{ fontSize:13, color:"#888", fontFamily:"monospace" }}>{detail.claim.claim_id}</div>
          <div style={S.topbarTitle}><ClaimTypeTag type={detail.claim.claim_type} /></div>
        </div>
        <div style={{ display:"flex", gap:8 }}>
          <StatusTag status={detail.claim.status} />
          <button style={S.btn} onClick={() => setDetail(null)}>← 返回</button>
        </div>
      </div>
      <div style={S.content}>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
          <div style={S.card}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"6px 20px" }}>
              {[
                ["關聯單據", detail.claim.t_code],
                ["責任方", detail.claim.responsible_party],
                ["物理倉", detail.claim.physical_wh + " " + detail.claim.physical_wh_name],
                ["帳務倉", detail.claim.account_wh + " " + detail.claim.account_wh_name],
                ["短少數量", detail.claim.shortage_qty || 0],
                ["溢出數量", detail.claim.excess_qty || 0],
                ["建立時間", detail.claim.created_at?.slice(0,16)],
                ["結案時間", detail.claim.resolved_at?.slice(0,16) || "—"],
              ].map(([k,v]) => (
                <div key={k} style={{ padding:"5px 0", borderBottom:"1px solid #f4f3f0" }}>
                  <div style={{ fontSize:11, color:"#888", marginBottom:2 }}>{k}</div>
                  <div style={{ fontSize:13, fontWeight:500 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>
          <div style={S.card}>
            <div style={{ fontSize:13, fontWeight:600, marginBottom:12 }}>事件 Log</div>
            {detail.logs.map((l, i) => (
              <div key={i} style={{ display:"flex", gap:8, marginBottom:10 }}>
                <div style={{ width:7, height:7, borderRadius:"50%", background:"#2563eb", marginTop:5, flexShrink:0 }} />
                <div>
                  <div style={{ fontSize:13 }}><strong>{l.action}</strong>　<span style={{ color:"#888" }}>{l.actor}</span></div>
                  {l.note && <div style={{ fontSize:12, color:"#666", marginTop:2 }}>{l.note}</div>}
                  <div style={{ fontSize:11, color:"#bbb", marginTop:1 }}>{l.timestamp?.slice(0,16)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* State machine actions */}
        {["PENDING","INVESTIGATING","IN_COLLECT_BUFFER"].includes(detail.claim.status) && (
          <div style={S.card}>
            <div style={{ fontSize:13, fontWeight:600, marginBottom:12 }}>操作</div>
            <div style={S.formGroup}><label style={S.label}>備註</label><input style={S.input} value={actionNote} onChange={e => setActionNote(e.target.value)} placeholder="說明" /></div>
            <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
              {detail.claim.status === "PENDING" && <>
                <button style={S.btnBlue} onClick={() => doAction("investigate")}>開始調查</button>
                <button style={S.btnDanger} onClick={() => doAction("reject")}>拒絕</button>
              </>}
              {detail.claim.status === "INVESTIGATING" && <>
                {!crossWarehouse && (
                  <>
                    <select style={{ ...S.select, width:160 }} value={cbCategory} onChange={e => setCbCategory(e.target.value)}>
                      <option value="">自動推斷區域</option>
                      <option value="SHORT">SHORT 短少</option>
                      <option value="DAMAGE">DAMAGE 損壞</option>
                      <option value="COUNT">COUNT 盤點</option>
                      <option value="QUALITY">QUALITY 品質</option>
                      <option value="SPEC">SPEC 規格</option>
                    </select>
                    <button style={S.btnBlue} onClick={() => doAction("move-to-cb", { cb_category: cbCategory || undefined })}>移入集貨緩衝</button>
                  </>
                )}
                <button style={S.btnSuccess} onClick={() => doAction("resolve", { resolution:"ADJUSTED" })}>結案（調整）</button>
                <button style={S.btnDanger} onClick={() => doAction("reject")}>拒絕</button>
              </>}
              {detail.claim.status === "IN_COLLECT_BUFFER" && <>
                <button style={{ ...S.btn, color:"#713f12", borderColor:"#fca5a5" }} onClick={() => doAction("move-to-disuse")}>申請除帳</button>
                <button style={S.btnSuccess} onClick={() => doAction("resolve", { resolution:"RESOLVED" })}>直接結案</button>
                <button style={S.btnDanger} onClick={() => doAction("reject")}>拒絕</button>
              </>}
            </div>
          </div>
        )}
      </div>
    </>
  )

  return (
    <>
      <div style={S.topbar}>
        <div><div style={S.topbarTitle}>{pageTitle}</div><div style={S.topbarSub}>{pageSub}</div></div>
        {!crossWarehouse && pendingApprovals.length > 0 && (
          <button style={{ ...S.btnPrimary, background:"#d97706" }} onClick={() => setShowApprovals(true)}>
            待審批除帳 {pendingApprovals.length}
          </button>
        )}
      </div>
      <div style={S.content}>
        <div style={S.tableWrap}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead><tr>{["Claim ID","類型","關聯單據","物理倉","帳務倉","短少","狀態","建立日"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {claims.length === 0 && <EmptyRow cols={8} />}
              {claims.map(c => (
                <tr key={c.claim_id} style={{ cursor:"pointer" }} onClick={() => loadDetail(c.claim_id)}>
                  <td style={S.tdMono}>{c.claim_id}</td>
                  <td style={S.td}><ClaimTypeTag type={c.claim_type} /></td>
                  <td style={S.tdMono}>{c.t_code}</td>
                  <td style={S.td}>{c.physical_wh} <span style={{ color:"#888", fontSize:12 }}>{c.physical_wh_name}</span></td>
                  <td style={S.td}>{c.account_wh} <span style={{ color:"#888", fontSize:12 }}>{c.account_wh_name}</span></td>
                  <td style={{ ...S.td, color: c.shortage_qty > 0 ? "#e24b4a":"#888", fontWeight:600 }}>{c.shortage_qty}</td>
                  <td style={S.td}><StatusTag status={c.status} /></td>
                  <td style={{ ...S.td, color:"#888" }}>{c.created_at?.slice(0,10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showApprovals && (
        <div style={S.modal} onClick={() => setShowApprovals(false)}>
          <div style={S.modalBox} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize:16, fontWeight:600, marginBottom:16 }}>待審批除帳申請</div>
            <table style={{ width:"100%", borderCollapse:"collapse" }}>
              <thead><tr>{["審批號","Claim","倉庫","短少","建立日","操作"].map(h => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
              <tbody>
                {pendingApprovals.map(a => (
                  <tr key={a.approval_id}>
                    <td style={S.tdMono}>{a.approval_id}</td>
                    <td style={S.tdMono}>{a.ref_id}</td>
                    <td style={S.td}>{a.warehouse_name}</td>
                    <td style={{ ...S.td, color:"#e24b4a" }}>{a.shortage_qty}</td>
                    <td style={S.td}>{a.created_at?.slice(0,10)}</td>
                    <td style={S.td}>
                      <button style={{ ...S.btnSuccess, marginRight:6 }} onClick={() => doApproval(a.approval_id,"approve")}>核准</button>
                      <button style={S.btnDanger} onClick={() => doApproval(a.approval_id,"reject-approval")}>拒絕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ display:"flex", gap:8, marginTop:12 }}>
              <input style={S.input} placeholder="審批備註（選填）" value={actionNote} onChange={e => setActionNote(e.target.value)} />
              <button style={S.btn} onClick={() => setShowApprovals(false)}>關閉</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ── AI Chat Page ──────────────────────────────────────────────────────────────
function AIChatPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior:"smooth" }) }, [messages])

  function send() {
    const msg = input.trim()
    if (!msg || loading) return
    setMessages(m => [...m, { role:"user", text:msg }])
    setInput(""); setLoading(true)
    axios.post(`${API}/agent/chat`, { message:msg }, { timeout:90000 })
      .then(r => setMessages(m => [...m, { role:"ai", text:r.data.reply, categories:r.data.categories, log:r.data.decision_log }]))
      .catch(err => {
        const isTimeout = err.code === "ECONNABORTED" || err.message?.includes("timeout")
        setMessages(m => [...m, { role:"ai", text: isTimeout ? "回應逾時，請再試一次（AI 約需 20–40 秒）" : `連線失敗：${err.response?.status || err.message}` }])
      })
      .finally(() => setLoading(false))
  }

  const catColors = { inventory:"#0891b2", claim:"#d97706", transfer:"#7c3aed", report:"#16a34a" }
  const catLabels = { inventory:"庫存 Agent", claim:"Claim Agent", transfer:"調撥 Agent", report:"報表 Agent" }
  const suggests = ["P001 庫存現況？", "哪些品項低於安全庫存？", "W2 有哪些未結 Claim？", "給我全倉異常摘要"]

  return (
    <>
      <div style={S.topbar}>
        <div><div style={S.topbarTitle}>AI 倉庫助手</div><div style={S.topbarSub}>多代理人系統 · 庫存 / Claim / 調撥 / 報表分析</div></div>
      </div>
      <div style={{ display:"flex", flexDirection:"column", flex:1, minHeight:0 }}>
        <div style={{ flex:1, overflowY:"auto", padding:"20px 28px" }}>
          {messages.length === 0 && (
            <div style={{ textAlign:"center", color:"#aaa", marginTop:40 }}>
              <div style={{ fontSize:36, marginBottom:12 }}>🤖</div>
              <div style={{ fontSize:14, marginBottom:20 }}>你好！我是倉庫 AI 助手</div>
              <div style={{ display:"flex", gap:8, justifyContent:"center", flexWrap:"wrap" }}>
                {suggests.map(q => (
                  <button key={q} onClick={() => setInput(q)} style={{ ...S.btn, fontSize:12, color:"#2563eb", borderColor:"#bfdbfe" }}>{q}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} style={{ marginBottom:16, display:"flex", justifyContent:msg.role==="user"?"flex-end":"flex-start" }}>
              {msg.role==="ai" && <div style={{ width:28, height:28, borderRadius:"50%", background:"#1a1a1a", display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, color:"#fff", marginRight:8, flexShrink:0, marginTop:2 }}>AI</div>}
              <div style={{ maxWidth:"72%" }}>
                <div style={{ background:msg.role==="user"?"#1a1a1a":"#fff", color:msg.role==="user"?"#fff":"#1a1a1a", padding:"12px 16px", borderRadius:msg.role==="user"?"16px 16px 4px 16px":"16px 16px 16px 4px", border:msg.role==="ai"?"1px solid #ebebeb":"none", fontSize:13, lineHeight:1.7, whiteSpace:"pre-wrap" }}>
                  {msg.text}
                </div>
                {msg.categories?.length > 0 && (
                  <div style={{ display:"flex", gap:4, marginTop:6, flexWrap:"wrap" }}>
                    {msg.categories.map(c => <span key={c} style={{ fontSize:10, fontWeight:500, padding:"2px 8px", borderRadius:4, background:catColors[c]+"18", color:catColors[c], border:`1px solid ${catColors[c]}44` }}>{catLabels[c]||c}</span>)}
                  </div>
                )}
                {msg.log && <DecisionLog log={msg.log} />}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display:"flex", alignItems:"center", gap:8, color:"#888", fontSize:13 }}>
              <div style={{ width:28, height:28, borderRadius:"50%", background:"#1a1a1a", display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, color:"#fff" }}>AI</div>
              <div style={{ background:"#fff", border:"1px solid #ebebeb", borderRadius:"16px 16px 16px 4px", padding:"12px 16px" }}>AI 分析中，約需 20–40 秒⋯</div>
            </div>
          )}
          <div ref={endRef} />
        </div>
        <div style={{ padding:"12px 28px", borderTop:"1px solid #ebebeb", background:"#fff", display:"flex", gap:8, flexShrink:0 }}>
          <input style={{ ...S.input, flex:1 }} placeholder="詢問庫存、Claim、調撥建議..." value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key==="Enter" && !e.shiftKey && send()} disabled={loading} />
          <button style={{ ...S.btnPrimary, flexShrink:0 }} onClick={send} disabled={loading}>送出</button>
        </div>
      </div>
    </>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [page, setPage] = useState("dashboard")
  const [claimCounts, setClaimCounts] = useState({ internal:0, cross:0 })

  useEffect(() => {
    const loadCounts = () => {
      axios.get(`${API}/api/claims?cross_warehouse=false`).then(r => {
        const open = r.data.filter(c => !["RESOLVED","WRITTEN_OFF","REJECTED"].includes(c.status)).length
        setClaimCounts(prev => ({ ...prev, internal:open }))
      }).catch(() => {})
      axios.get(`${API}/api/claims?cross_warehouse=true`).then(r => {
        const open = r.data.filter(c => !["RESOLVED","WRITTEN_OFF","REJECTED"].includes(c.status)).length
        setClaimCounts(prev => ({ ...prev, cross:open }))
      }).catch(() => {})
    }
    loadCounts()
  }, [page])

  const nav = (id, label, badge, bStyle) => (
    <div style={page===id ? S.navItemActive : S.navItem} onClick={() => setPage(id)}>
      <span>{label}</span>
      {badge > 0 && <span style={bStyle || S.badge}>{badge}</span>}
    </div>
  )

  const pages = {
    "dashboard":      <DashboardPage onNavigate={setPage} />,
    "inventory":      <InventoryPage />,
    "inbound":        <InboundPage />,
    "transfer":       <TransferPage />,
    "outbound":       <OutboundPage />,
    "cycle-count":    <CycleCountPage />,
    "internal-claims":<ClaimsPage crossWarehouse={false} />,
    "cross-claims":   <ClaimsPage crossWarehouse={true} />,
    "ai-chat":        <AIChatPage />,
  }

  return (
    <div style={S.app}>
      <div style={S.sidebar}>
        <div style={S.sidebarLogo}>
          <div style={{ width:28, height:28, background:"#fff", borderRadius:6, display:"flex", alignItems:"center", justifyContent:"center", fontSize:13, fontWeight:700, color:"#1a1a1a" }}>W</div>
          <div>
            <div style={S.sidebarLogoText}>WMS Pro</div>
            <div style={S.sidebarLogoSub}>三倉庫存系統</div>
          </div>
        </div>

        <div style={S.navSection}>總覽</div>
        {nav("dashboard", "倉庫總覽")}
        {nav("inventory", "庫存看板")}

        <div style={S.navSection}>作業管理</div>
        {nav("inbound",  "入庫作業")}
        {nav("transfer", "轉倉作業")}
        {nav("outbound", "出貨作業")}
        {nav("cycle-count", "庫內盤點")}

        <div style={S.navSection}>問題帳管理</div>
        {nav("internal-claims", "內部問題帳", claimCounts.internal, S.badgeYellow)}
        {nav("cross-claims",    "跨倉 Claim",  claimCounts.cross)}

        <div style={S.navSection}>AI 工具</div>
        {nav("ai-chat", "AI 倉庫助手")}

        <div style={{ marginTop:"auto", padding:"12px 16px", borderTop:"1px solid #2d2d2d" }}>
          <div style={{ fontSize:11, color:"#555" }}>倉庫主管</div>
          <div style={{ fontSize:12, color:"#888", marginTop:2 }}>W1 · W2 · W3</div>
        </div>
      </div>

      <div style={S.main}>
        {pages[page]}
      </div>
    </div>
  )
}
