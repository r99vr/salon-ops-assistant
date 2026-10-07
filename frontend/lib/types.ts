export type Salon = {
  id: number;
  name: string;
  approver: "owner" | "manager";
  channel: "simulator" | "telegram" | "whatsapp";
  currency: string;
  summary_time: string;
  morning_time: string;
  tasks_time: string;
  supplier_reminder_minutes: number;
  cleaning_grace_minutes: number;
  timezone: string;
};

export type Issue = { id: number; description: string; reported_by: string | null; created_at: string; image_url: string | null };

export type Item = {
  id: number;
  name: string;
  aliases: string;
  kind: "consumable" | "device";
  unit: string;
  quantity: number;
  min_qty: number;
  target_qty: number;
  unit_price: number;
  supplier_id: number | null;
  supplier: string | null;
  status: "ok" | "broken";
  is_low: boolean;
  section_id: number;
  section: string;
  updated_at: string;
  issue?: Issue | null;
};

export type Run = {
  id: number;
  task_id: number;
  title: string;
  date: string;
  due_at: string;
  status: "pending" | "overdue" | "done" | "missed";
  done_at: string | null;
  proof_url: string | null;
  reminded_at: string | null;
  escalated_at: string | null;
  staff: string | null;
};

export type OrderLine = { id: number; item_id: number; name: string; unit: string; qty: number; unit_price: number };

export type Order = {
  id: number;
  status: "draft" | "awaiting_approval" | "sent" | "confirmed" | "received" | "cancelled";
  date: string;
  supplier: { id: number; name: string; rep_name: string };
  lines: OrderLine[];
  estimated_total: number;
  approved_at: string | null;
  sent_at: string | null;
  supplier_reply: string | null;
  supplier_replied_at: string | null;
  reminded_at: string | null;
  received_at: string | null;
  created_at: string;
};

export type Invoice = {
  id: number;
  supplier: string;
  invoice_no: string;
  total: number;
  date: string;
  image_url: string | null;
  lines: { item_id: number | null; name: string; qty: number; unit_price: number | null }[];
  order_id: number | null;
  extraction: string;
  uploaded_by: string | null;
  created_at: string;
};

export type Msg = {
  id: number;
  phone: string;
  name: string;
  role: "staff" | "owner" | "manager" | "supplier" | "unknown";
  direction: "in" | "out";
  body: string;
  media_url: string | null;
  kind: string;
  channel: string;
  transport: string;
  created_at: string;
  classification?: { type: string; source: string; confidence: number } | null;
};

export type Overview = {
  salon: Salon;
  now: string;
  stats: {
    low_count: number;
    items_count: number;
    devices_count: number;
    broken_count: number;
    tasks_done: number;
    tasks_total: number;
    open_orders: number;
    month_spend: number;
  };
  low_items: Item[];
  broken_devices: Item[];
  today_tasks: Run[];
  open_orders: Order[];
  spend_series: { date: string; total: number }[];
  task_week: { date: string; done: number; total: number }[];
  activity: Msg[];
  alerts: Msg[];
};

export type Section = {
  id: number;
  name: string;
  icon: string;
  staff: { id: number; name: string; color: string } | null;
  items: Item[];
};

export type Supplier = {
  id: number;
  name: string;
  category: string;
  rep_name: string;
  rep_phone: string;
  telegram_linked: boolean;
  invite_code: string;
  invite_link: string | null;
};

export type Staff = {
  id: number;
  name: string;
  phone: string;
  role: "owner" | "manager" | "worker";
  title: string;
  color: string;
  active: boolean;
  sections: string[];
  telegram_linked: boolean;
  invite_code: string;
  invite_link: string | null;
};

export type Contact = {
  phone: string;
  name: string;
  subtitle: string;
  role: Msg["role"];
  color: string;
  last: Msg | null;
};
