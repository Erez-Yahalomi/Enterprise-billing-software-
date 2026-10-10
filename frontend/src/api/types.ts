export interface Customer {
  id: string;
  name: string;
  email: string;
  country: string | null;
  status: string;
  tenant_id: string;
}

export interface Product {
  id: string;
  name: string;
  code: string;
}

export interface PricePlan {
  id: string;
  product_id: string;
  name: string;
  version: number;
  monthly_price_cents: number;
  included_users: number;
  additional_user_price_cents: number;
  included_api_calls: number;
  overage_api_price_cents_per_unit: number;
  ai_token_price_cents_per_1k: number;
  storage_gb_price_cents: number;
  is_active: boolean;
}

export interface Subscription {
  id: string;
  customer_id: string;
  price_plan_id: string;
  status: string;
  quantity_users: number;
  started_at: string;
  canceled_at: string | null;
}

export interface InvoiceLineItem {
  id: string;
  description: string;
  kind: string;
  amount_cents: number;
}

export interface Invoice {
  id: string;
  customer_id: string;
  subscription_id: string;
  period_start: string;
  period_end: string;
  status: string;
  subtotal_cents: number;
  line_items: InvoiceLineItem[];
}

export interface Payment {
  id: string;
  payment_intent_id: string;
  invoice_id: string;
  customer_id: string;
  amount_cents: number;
  status: string;
  provider: string;
}

export interface UsageByDayItem {
  day: string;
  event_type: string;
  total_quantity: number;
}

export interface ChatToolCall {
  tool: string;
  status: string;
}

export interface ChatResponse {
  reply: string;
  tool_calls: ChatToolCall[];
  pending_approval_id: string | null;
  answered_by?: "gemini" | "ollama" | "rules";
  answer_status?: "answered" | "needs_info" | "not_understood";
}

export interface ApprovalRequest {
  id: string;
  tool: string;
  parameters: Record<string, unknown>;
  status: string;
  requested_by: string;
  resolved_by: string | null;
  resolved_at: string | null;
  result: Record<string, unknown> | null;
}

export function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

/** YYYY-MM-DD in the browser's local timezone (toISOString would shift the day for non-UTC users). */
export function toLocalIsoDate(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export function currentMonthBounds(): { start: string; end: string } {
  const now = new Date();
  return {
    start: toLocalIsoDate(new Date(now.getFullYear(), now.getMonth(), 1)),
    end: toLocalIsoDate(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
  };
}
