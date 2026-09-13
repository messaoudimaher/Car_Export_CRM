export interface ApiEnvelope<T> {
  success: boolean;
  data: T;
  meta?: {
    timestamp: string;
    correlation_id: string;
  };
}

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  correlation_id?: string;
  errors?: Record<string, string[]>;
}

export interface UserSession {
  user_id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: "SuperAdmin" | "TenantAdmin" | "SalesAgent" | "LogisticsAgent";
  token: string;
}

export interface Customer {
  id: string;
  tenant_id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone_e164: string;
  whatsapp_id?: string;
  email?: string;
  notes?: string;
  is_anonymized: boolean;
  legal_hold: boolean;
  created_at: string;
  updated_at: string;
}

export interface Lead {
  id: string;
  tenant_id: string;
  customer_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}
