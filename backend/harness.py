import time
from datetime import datetime
from typing import Any, Callable

VALID_CLAIM_STATUSES = {"待審查", "異議中", "已結案", "已拒絕"}
VALID_WAREHOUSE_IDS = {"W1", "W2", "W3"}


class WarehouseHarness:
    def __init__(self):
        self._log: list[dict] = []

    def validate_tool_result(self, tool_name: str, result: Any) -> tuple[bool, str]:
        if result is None:
            return False, "工具回傳 None"
        if isinstance(result, dict) and "error" in result:
            return False, f"工具回報錯誤：{result['error']}"
        validators = {
            "get_inventory": self._val_inventory,
            "compare_inventory": self._val_compare,
            "check_safety_stock": self._val_list_nonneg,
            "get_claim": self._val_claim,
            "list_claims": self._val_claims_list,
            "suggest_transfer": self._val_transfer_suggestion,
            "get_anomalies": self._val_anomalies,
        }
        fn = validators.get(tool_name)
        return fn(result) if fn else (True, "ok")

    def _val_inventory(self, r):
        for wh in r.get("warehouses", []):
            if wh.get("quantity", -1) < 0:
                return False, "庫存數量不可為負數"
            if wh.get("warehouse_id") not in VALID_WAREHOUSE_IDS:
                return False, f"未知倉庫 ID：{wh.get('warehouse_id')}"
        return True, "ok"

    def _val_compare(self, r):
        for wh in r.get("surplus_warehouses", []) + r.get("deficit_warehouses", []):
            if wh.get("quantity", -1) < 0:
                return False, "比較結果包含負庫存"
        return True, "ok"

    def _val_list_nonneg(self, r):
        if not isinstance(r, list):
            return False, "應回傳 list"
        for item in r:
            if item.get("shortage", 0) <= 0:
                return False, f"shortage 應 > 0"
        return True, "ok"

    def _val_claim(self, r):
        if r.get("status") and r["status"] not in VALID_CLAIM_STATUSES:
            return False, f"非法 claim 狀態：{r['status']}"
        if r.get("qty", 1) <= 0:
            return False, "異議數量應 > 0"
        return True, "ok"

    def _val_claims_list(self, r):
        if not isinstance(r, list):
            return False, "應回傳 list"
        for item in r:
            ok, msg = self._val_claim(item)
            if not ok:
                return False, msg
        return True, "ok"

    def _val_transfer_suggestion(self, r):
        if r.get("suggested_qty", 0) < 0:
            return False, "建議調撥數量不可為負數"
        return True, "ok"

    def _val_anomalies(self, r):
        if r.get("severity") not in {"高", "中", "低"}:
            return False, f"非法 severity：{r.get('severity')}"
        return True, "ok"

    def add_reasoning(self, step: str, reasoning: str, data: Any = None):
        self._log.append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "step": step,
            "reasoning": reasoning,
            "data": data,
        })

    def get_decision_log(self) -> list[dict]:
        return list(self._log)

    def clear_log(self):
        self._log.clear()

    def fallback(self, tool_name: str, error: str) -> dict:
        msg = f"[Harness] {tool_name} 失敗：{error}"
        self.add_reasoning("fallback", msg)
        return {"error": True, "tool": tool_name, "message": msg}

    def call_tool(self, tool_name: str, tool_fn: Callable, **kwargs) -> Any:
        self.add_reasoning("tool_call", f"呼叫 {tool_name}", data=kwargs)
        t0 = time.perf_counter()
        try:
            result = tool_fn(**kwargs)
        except Exception as e:
            return self.fallback(tool_name, str(e))
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        ok, msg = self.validate_tool_result(tool_name, result)
        if not ok:
            self.add_reasoning("validation_failed", f"{tool_name} 驗證失敗：{msg}", data=result)
            return self.fallback(tool_name, f"驗證失敗：{msg}")
        self.add_reasoning("tool_result", f"{tool_name} 完成（{elapsed}ms）", data=result)
        return result
