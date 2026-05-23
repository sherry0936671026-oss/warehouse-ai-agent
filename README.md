# Warehouse AI Agent

**倉庫異議 & 調撥決策多代理人系統**

> 「不是技術練習，是真實痛點的解法。」

---

## 這個系統解決什麼問題？

我在酷澎擔任倉庫主管期間，每週都在處理同一個痛點：

**跨倉轉運發生短少時，沒有系統能同時回答這三個問題：**
1. 異議單的責任歸屬是什麼？現在到哪個處理階段了？
2. 這個品項在其他倉庫還有多少庫存？能補嗎？
3. 如果要調撥，從哪個倉調最合理？

現行作法是靠 **Google 表單 + Email + 人工查 WMS**，三個問題要分三個地方處理。

這個系統把三件事整合成一個對話介面，讓 AI Agent 幫你查、分析、給建議。

---

## 系統架構

```
使用者問題
    │
    ▼
[Router Agent]  判斷意圖（inventory / claim / transfer / report）
    │
    ├──▶ [Inventory Agent]   跨倉庫存查詢 + 低庫存偵測
    ├──▶ [Claim Agent]       異議單追蹤 + 重複 claim 檢查
    ├──▶ [Transfer Agent]    調撥方案建議（依餘裕量排序）
    └──▶ [Report Agent]      KPI 分析 + 全倉異常摘要
              │
              ▼
        [Harness Layer]
        ├── 工具結果驗證（數字合理性、狀態合法值）
        ├── Reasoning Log（每步決策可視化）
        └── Fallback（工具失敗時的標準回應）
              │
              ▼
        [整合 Agent]  輸出最終回答 + 建議行動
```

---

## 功能展示

### AI 倉庫對話
- 自然語言查詢，系統自動路由到對應的子 Agent
- 每個回答都附帶「決策推理」可展開查看
- 顯示哪些 Agent 被啟動（Inventory / Claim / Transfer / Report）

**範例問句：**
- `P001 現在哪個倉庫最多？`
- `有哪些異議單還在待審查？`
- `P003 北區倉庫存不夠，建議從哪裡調？`
- `給我全倉的異常摘要`

### 庫存看板
- 三倉庫存橫條圖（含安全庫存基準線，純 CSS 實作）
- 低庫存警示列表（即時顯示全部品項）
- AI 調撥建議卡片（選 SKU + 目標倉 → 一鍵分析）

### Claim 管理
- Claim 建立、狀態更新、補貨 / 轉帳結案流程
- 重複 Claim 警示（7 天內同倉庫 + 同品項）
- AI 自動摘要（分析異常原因 + 建議行動）
- 主管 KPI 總覽（各倉結案率、異議率）

---

## Harness 設計亮點

```python
class WarehouseHarness:
    def call_tool(self, tool_name, tool_fn, **kwargs):
        # 1. 記錄呼叫（reasoning log）
        # 2. 執行工具函數
        # 3. 驗證結果合理性（數量不為負、狀態值合法）
        # 4. 失敗時回傳標準化 fallback，不讓整個請求崩潰
```

這個設計讓每次 AI 決策都有完整的推理軌跡，可以在前端直接展示給使用者看。

---

## 技術架構

```
Frontend           Backend              AI
React (Vite)  ──▶  FastAPI         ──▶  Claude claude-sonnet-4-6
axios              SQLite (2個)          Multi-Agent + Tool Use
                   ├── warehouse_agent.db   (AI agent 資料)
                   └── warehouse_claim.db   (Claim CRUD)
```

| 層 | 技術 |
|----|------|
| 前端 | React 19, Vite, axios |
| 後端 | FastAPI, SQLModel, SQLite |
| AI | Anthropic Claude claude-sonnet-4-6, Groq llama-3.3-70b |
| 部署 | Railway（後端）, Netlify（前端）|

---

## 本地啟動

```bash
# 1. Clone
git clone https://github.com/sherry0936671026-oss/warehouse-ai-agent.git
cd warehouse-ai-agent

# 2. Backend
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # 填入 ANTHROPIC_API_KEY 和 GROQ_API_KEY
python3 seed.py                 # 建立 Claim 假資料
uvicorn main:app --reload       # 啟動於 http://localhost:8000
# AI agent 資料會在首次啟動時自動建立

# 3. Frontend（另開終端機）
cd frontend
npm install
cp .env.example .env            # 本機用預設值即可
npm run dev                     # 啟動於 http://localhost:5173
```

---

## 部署到 Railway + Netlify

### Backend → Railway

1. [Railway](https://railway.app) 新建 project → 連接此 repo
2. Root directory 設為 `backend`
3. 環境變數：`ANTHROPIC_API_KEY`、`GROQ_API_KEY`
4. Railway 自動偵測 `Procfile` 啟動

### Frontend → Netlify

1. [Netlify](https://netlify.com) 連接此 repo
2. Base: `frontend`，Build: `npm run build`，Publish: `dist`
3. 環境變數：`VITE_API_URL=https://你的railway網址.up.railway.app`

---

## 作者

**劉又瑄 Sherry Liu**
倉庫主管 → Supply Chain AI Engineer

熟悉電商倉儲實際作業（酷澎 Coupang），具備 AI 系統設計與全端開發能力。

[LinkedIn](https://www.linkedin.com/in/sherry-liu-356a41405) · [GitHub](https://github.com/sherry0936671026-oss)
