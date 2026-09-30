"""共享导航图标配置；不改变路由、名称或业务权限。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.access.security import current_user, require
from app.core.database import connection

router = APIRouter(prefix="/api/v1/menu-icons")
# 固定菜单与图标白名单；契约测试核对桌面登记表，防止新增入口遗漏。
MENU_KEYS = {
    'group:catalog',
    'group:finance',
    'group:production',
    'group:purchase',
    'group:sales',
    'group:system',
    'group:warehouse',
    'route:boms',
    'route:catalog',
    'route:customers',
    'route:finance',
    'route:financePayments',
    'route:financeSources',
    'route:goodsReceipts',
    'route:home',
    'route:inventoryLedger',
    'route:inventoryReports',
    'route:inventoryValuation',
    'route:materialIssues',
    'route:materialReturns',
    'route:menuManagement',
    'route:otherInbounds',
    'route:permissionCatalog',
    'route:productionCompletions',
    'route:productionCosts',
    'route:purchase',
    'route:purchaseReports',
    'route:purchaseRequests',
    'route:purchaseReturns',
    'route:receipts',
    'route:roles',
    'route:sales',
    'route:salesReturns',
    'route:settings',
    'route:shipments',
    'route:stock',
    'route:stockAdjustments',
    'route:stocktakes',
    'route:suppliers',
    'route:transfers',
    'route:users',
    'route:warehouseOutbounds',
    'route:warehouses',
    'route:workOrders',
}
ICON_KEYS = {
    'archive',
    'box',
    'catalog',
    'chart',
    'dashboard',
    'file',
    'finance',
    'history',
    'menu',
    'production',
    'purchase',
    'sales',
    'search',
    'settings',
    'shield',
    'stack',
    'team',
    'truck',
    'user',
    'warehouse',
}

class MenuIconInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    icon: str | None
    version: int = Field(ge=0, strict=True)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if value not in MENU_KEYS:
            raise ValueError("菜单不存在")
        return value

    @field_validator("icon")
    @classmethod
    def validate_icon(cls, value: str | None) -> str | None:
        if value is not None and value not in ICON_KEYS:
            raise ValueError("请选择内置图标")
        return value

@router.get("")
def list_menu_icons(_: dict = Depends(current_user)) -> list[dict]:
    # 所有登录用户使用同一份配置；是否可进入页面仍取决于原有权限。
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT key, icon, version FROM menu_icons ORDER BY key")]

@router.put("")
def save_menu_icon(payload: MenuIconInput, actor: dict = Depends(require("users.manage"))) -> dict:
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT icon, version FROM menu_icons WHERE key = ?", (payload.key,)).fetchone()
        version = row["version"] if row else 0
        # 按菜单逐项比较版本，不覆盖其他管理员在读取后保存的修改。
        if version != payload.version:
            raise HTTPException(409, "该图标已被其他管理员修改，请重新加载后再保存")
        db.execute("""INSERT INTO menu_icons(key, icon, version) VALUES (?, ?, ?)
                      ON CONFLICT(key) DO UPDATE SET icon=excluded.icon, version=excluded.version""",
                   (payload.key, payload.icon, version + 1))
        db.execute("""INSERT INTO menu_icon_changes(menu_key, before_icon, after_icon, changed_by)
                      VALUES (?, ?, ?, ?)""", (payload.key, row["icon"] if row else None, payload.icon, actor["id"]))
        return {"key": payload.key, "icon": payload.icon, "version": version + 1}
