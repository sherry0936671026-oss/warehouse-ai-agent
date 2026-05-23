from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from ai_agent import run_warehouse_agent
from agent_db import ensure_ready
from tools.inventory_tools import get_inventory, check_safety_stock
from tools.analytics_tools import get_kpi, get_anomalies
from sqlmodel import Session, select
from database import get_session, create_db
from models import Warehouse, Item, ClaimEvent, EventLog
from datetime import datetime
from groq import Groq
import json

class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"
    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False, default=str).encode("utf-8")

app = FastAPI(default_response_class=UTF8JSONResponse)
import os
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db()
    ensure_ready()  # 初始化 AI agent 資料庫


class AgentChatRequest(BaseModel):
    message: str


@app.post("/agent/chat")
def agent_chat(body: AgentChatRequest):
    result = run_warehouse_agent(body.message)
    return result


@app.get("/agent/decision-log")
def decision_log_demo():
    """示範端點：對「全倉異常摘要」跑一次 agent 並回傳 decision log。"""
    result = run_warehouse_agent("給我全倉的異常摘要")
    return {"decision_log": result["decision_log"]}


@app.get("/agent/inventory/{sku}")
def agent_inventory(sku: str, warehouse_id: str = None):
    return get_inventory(sku, warehouse_id)


@app.get("/agent/safety-stock")
def agent_safety_stock(warehouse_id: str = None):
    return check_safety_stock(warehouse_id)


@app.get("/agent/kpi/{warehouse_id}")
def agent_kpi(warehouse_id: str):
    return get_kpi(warehouse_id)


@app.get("/agent/anomalies")
def agent_anomalies():
    return get_anomalies()

# 取得所有倉庫
@app.get("/warehouses")
def get_warehouses(session: Session = Depends(get_session)):
    return session.exec(select(Warehouse)).all()

# 取得所有 Claim 事件
@app.get("/claims")
def get_claims(session: Session = Depends(get_session)):
    return session.exec(select(ClaimEvent)).all()

# 取得單一 Claim 詳細
@app.get("/claims/{event_id}")
def get_claim(event_id: str, session: Session = Depends(get_session)):
    claim = session.get(ClaimEvent, event_id)
    if not claim:
        raise HTTPException(status_code=404, detail="找不到此 Claim")
    logs = session.exec(select(EventLog).where(EventLog.event_id == event_id)).all()
    return {"claim": claim, "logs": logs}

# 建立新 Claim
@app.post("/claims")
def create_claim(claim: ClaimEvent, session: Session = Depends(get_session)):
    claim.created_at = datetime.now()
    session.add(claim)
    log = EventLog(event_id=claim.event_id, action="建立", actor_wh=claim.from_wh, note=claim.note)
    session.add(log)
    session.commit()
    session.refresh(claim)
    return claim
    session.add(claim)
    log = EventLog(event_id=claim.event_id, action="建立", actor_wh=claim.from_wh, note=claim.note)
    session.add(log)
    session.commit()
    session.refresh(claim)
    return claim

# 更新 Claim 狀態（確認／異議／待審查）
@app.patch("/claims/{event_id}/status")
def update_status(event_id: str, status: str, actor_wh: str, note: str = "", session: Session = Depends(get_session)):
    claim = session.get(ClaimEvent, event_id)
    if not claim:
        raise HTTPException(status_code=404, detail="找不到此 Claim")
    claim.status = status
    log = EventLog(event_id=event_id, action=status, actor_wh=actor_wh, note=note)
    session.add(log)
    session.commit()
    return {"ok": True, "status": status}

@app.get("/claims/{event_id}/ai-summary")
def ai_summary(event_id: str, session: Session = Depends(get_session)):
    claim = session.get(ClaimEvent, event_id)
    if not claim:
        raise HTTPException(status_code=404, detail="找不到此 Claim")
    logs = session.exec(select(EventLog).where(EventLog.event_id == event_id)).all()
    
    prompt = f"""你是一個倉庫管理 AI 助手，請用繁體中文分析以下異常帳務事件，給出簡短摘要和建議行動。

事件 ID：{claim.event_id}
PRB 代碼：{claim.prb_code}（1-2=進貨短少，1-5=其他異常，1-7=移除效期短少）
商品 ID：{claim.item_id}
發起倉庫：{claim.from_wh}
對象倉庫：{claim.to_wh}
短少數量：{claim.qty_claimed} 件
備註：{claim.note or '無'}
目前狀態：{claim.status}
事件 log：{[f"{l.action} by {l.actor_wh}: {l.note}" for l in logs]}

請用以下格式回答：
【摘要】2-3句話說明這筆異常
【建議行動】條列式，最多3點"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )
    
    return {"summary": response.choices[0].message.content}
# 檢查重複 Claim
@app.get("/claims/check-duplicate")
def check_duplicate(from_wh: str, to_wh: str, item_id: str, session: Session = Depends(get_session)):
    from datetime import timedelta
    seven_days_ago = datetime.now() - timedelta(days=7)
    existing = session.exec(
        select(ClaimEvent).where(
            ClaimEvent.item_id == item_id,
            ClaimEvent.status != "已結案",
            ((ClaimEvent.from_wh == from_wh) & (ClaimEvent.to_wh == to_wh)) |
            ((ClaimEvent.from_wh == to_wh) & (ClaimEvent.to_wh == from_wh)),
            ClaimEvent.created_at >= seven_days_ago
        )
    ).all()
    return {"duplicates": [c.event_id for c in existing]}

# 結案 API
@app.patch("/claims/{event_id}/close")
def close_claim(
    event_id: str,
    close_type: str,
    actor_wh: str,
    note: str = "",
    session: Session = Depends(get_session)
):
    claim = session.get(ClaimEvent, event_id)
    if not claim:
        raise HTTPException(status_code=404, detail="找不到此 Claim")
    
    # 檢查是否已結案
    existing_close = session.exec(
        select(EventLog).where(
            EventLog.event_id == event_id,
            EventLog.action == "已結案"
        )
    ).first()
    if existing_close:
        raise HTTPException(status_code=400, detail="此 Claim 已結案，不能重複結案")
    
    claim.status = "已結案"
    log = EventLog(
        event_id=event_id,
        action="已結案",
        actor_wh=actor_wh,
        note=f"{close_type}｜{note}"
    )
    session.add(log)
    session.commit()
    return {"ok": True}