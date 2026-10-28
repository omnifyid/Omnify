from datetime import date

from pydantic import BaseModel


class SalesByDay(BaseModel):
    day: date
    order_count: int
    total_revenue: int


class SalesReport(BaseModel):
    days: list[SalesByDay]
    total_orders: int
    total_revenue: int


class TopItem(BaseModel):
    item_name: str
    quantity_sold: int
    total_revenue: int


class TopItemsReport(BaseModel):
    items: list[TopItem]


class StaffStat(BaseModel):
    operator_id: str
    full_name: str
    order_count: int
    total_revenue: int


class StaffReport(BaseModel):
    staff: list[StaffStat]


class PaymentBreakdownItem(BaseModel):
    payment_method: str
    order_count: int
    total_revenue: int


class PaymentReport(BaseModel):
    breakdown: list[PaymentBreakdownItem]


class DashboardSales(BaseModel):
    order_count: int
    total_revenue: int
    avg_order_value: int


class MenuCategorySummary(BaseModel):
    category_name: str
    item_count: int
    quantity_sold: int
    total_revenue: int


class MenuItemSummary(BaseModel):
    item_name: str
    base_price: int
    quantity_sold: int
    total_revenue: int


class MenuDashboardReport(BaseModel):
    total_items: int
    available_items: int
    total_categories: int
    categories: list[MenuCategorySummary]
    items: list[MenuItemSummary]


class DashboardReport(BaseModel):
    sales: DashboardSales
    top_items: list[TopItem]
    payments: list[PaymentBreakdownItem]
    menu: MenuDashboardReport
