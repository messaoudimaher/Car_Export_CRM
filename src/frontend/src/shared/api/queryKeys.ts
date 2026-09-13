export interface FilterParams {
  q?: string;
  status?: string;
  category?: string;
  lead_id?: string;
  customer_id?: string;
  page?: number;
  limit?: number;
  offset?: number;
  [key: string]: unknown;
}

export const inboxKeys = {
  all: ["inbox"] as const,
  threads: (filters?: FilterParams) => [...inboxKeys.all, "threads", filters || {}] as const,
  thread: (id: string) => [...inboxKeys.all, "thread", id] as const,
  messages: (threadId: string) => [...inboxKeys.all, "messages", threadId] as const,
};

export const customerKeys = {
  all: ["customers"] as const,
  list: (filters?: FilterParams) => [...customerKeys.all, "list", filters || {}] as const,
  detail: (id: string) => [...customerKeys.all, "detail", id] as const,
};

export const leadKeys = {
  all: ["leads"] as const,
  list: (filters?: FilterParams) => [...leadKeys.all, "list", filters || {}] as const,
  detail: (id: string) => [...leadKeys.all, "detail", id] as const,
};

export const vehicleKeys = {
  all: ["vehicles"] as const,
  list: (filters?: FilterParams) => [...vehicleKeys.all, "list", filters || {}] as const,
  detail: (id: string) => [...vehicleKeys.all, "detail", id] as const,
};

export const quoteKeys = {
  all: ["quotes"] as const,
  list: (filters?: FilterParams) => [...quoteKeys.all, "list", filters || {}] as const,
  detail: (id: string) => [...quoteKeys.all, "detail", id] as const,
};

export const documentKeys = {
  all: ["documents"] as const,
  list: (filters?: FilterParams) => [...documentKeys.all, "list", filters || {}] as const,
  detail: (id: string) => [...documentKeys.all, "detail", id] as const,
};

export const followupKeys = {
  all: ["followups"] as const,
  list: (filters?: FilterParams) => [...followupKeys.all, "list", filters || {}] as const,
};

export const gdprKeys = {
  all: ["gdpr"] as const,
  customerStatus: (customerId: string) => [...gdprKeys.all, "customer", customerId] as const,
};
