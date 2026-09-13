export type ThreadStatus = "UNASSIGNED" | "ASSIGNED" | "CLOSED" | "PENDING";
export type MessageDirection = "INBOUND" | "OUTBOUND";
export type MessageStatus = "SENT" | "DELIVERED" | "READ" | "FAILED";
export type LeadStage = "NEW" | "QUALIFIED" | "VEHICLE_PROPOSED" | "QUOTE_SENT" | "FCR_VERIFIED" | "WON" | "LOST";

export interface ChatMessage {
  id: string;
  threadId: string;
  direction: MessageDirection;
  senderName?: string;
  senderPhone?: string;
  content: string;
  status: MessageStatus;
  timestamp: string;
  aiUnderstandingId?: string;
  aiSuggestionId?: string;
}

export interface CustomerContext {
  id: string;
  fullName: string;
  phoneE164: string;
  email?: string;
  country: string;
  fcrEligible: boolean;
  notes?: string;
  createdAt: string;
}

export interface LeadContext {
  id: string;
  customerId: string;
  stage: LeadStage;
  targetVehicle?: string;
  budgetMinEur?: number;
  budgetMaxEur?: number;
  assignedAgentName?: string;
  updatedAt: string;
}

export interface ConversationThread {
  id: string;
  customerId: string;
  customerName: string;
  customerPhone: string;
  channel: "WHATSAPP";
  status: ThreadStatus;
  unreadCount: number;
  lastMessageSnippet: string;
  lastActivityAt: string;
  assignedAgentId?: string;
  assignedAgentName?: string;
  customer: CustomerContext;
  lead?: LeadContext;
}

export interface InboxFilter {
  status?: "ALL" | "MINE" | "UNASSIGNED" | "CLOSED";
  searchQuery?: string;
  [key: string]: unknown;
}
