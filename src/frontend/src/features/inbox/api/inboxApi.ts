import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../../shared/api/client";
import { inboxKeys } from "../../../shared/api/queryKeys";
import { ConversationThread, ChatMessage, InboxFilter } from "../types";

// Mock Fallback Data for Inbox Workstation Demonstration
export const MOCK_THREADS: ConversationThread[] = [
  {
    id: "th_01h9x8a1",
    customerId: "cust_991",
    customerName: "Mohamed Ben Ali",
    customerPhone: "+216 98 123 456",
    channel: "WHATSAPP",
    status: "ASSIGNED",
    unreadCount: 2,
    lastMessageSnippet: "Bonjour, je cherche une BMW X5 2022 éligible FCR avec TVA déductible.",
    lastActivityAt: "2026-09-13T17:42:00Z",
    assignedAgentId: "agent_01",
    assignedAgentName: "Sami Khedira",
    customer: {
      id: "cust_991",
      fullName: "Mohamed Ben Ali",
      phoneE164: "+21698123456",
      email: "m.benali@gmail.com",
      country: "Tunisia",
      fcrEligible: true,
      notes: "Client sérieux. Privilégie SUV allemand récent.",
      createdAt: "2026-08-10T10:00:00Z",
    },
    lead: {
      id: "lead_501",
      customerId: "cust_991",
      stage: "QUALIFIED",
      targetVehicle: "BMW X5 xDrive30d (2022-2023)",
      budgetMinEur: 45000,
      budgetMaxEur: 55000,
      assignedAgentName: "Sami Khedira",
      updatedAt: "2026-09-13T16:30:00Z",
    },
    activeAiUnderstanding: {
      id: "ai_und_901",
      threadId: "th_01h9x8a1",
      messageId: "msg_103",
      extractedVehicleModel: "BMW X5 xDrive30d",
      extractedYearMin: 2022,
      extractedYearMax: 2023,
      extractedBudgetMinEur: 45000,
      extractedBudgetMaxEur: 55000,
      extractedFcrEligible: true,
      confidenceScore: 0.94,
      status: "PROVISIONAL",
      createdAt: "2026-09-13T17:42:05Z",
    },
    activeAiSuggestion: {
      id: "ai_sug_901",
      threadId: "th_01h9x8a1",
      messageId: "msg_103",
      suggestedText: "Bonjour M. Ben Ali, nous pouvons vous établir immédiatement un devis FCR avec TVA déductible (Netto) pour la BMW X5 2022. Souhaitez-vous recevoir la simulation complète par PDF ?",
      reasoningSnippet: "Reconnaissance d'intention d'achat FCR confirmée. Correspondance exacte du modèle BMW X5.",
      confidenceScore: 0.91,
      status: "PROVISIONAL",
      createdAt: "2026-09-13T17:42:10Z",
    },
  },
  {
    id: "th_01h9x8a2",
    customerId: "cust_992",
    customerName: "Youssef Trabelsi",
    customerPhone: "+216 22 987 654",
    channel: "WHATSAPP",
    status: "UNASSIGNED",
    unreadCount: 1,
    lastMessageSnippet: "Quel est le délai de livraison pour l'Allemagne vers Tunis ?",
    lastActivityAt: "2026-09-13T16:15:00Z",
    customer: {
      id: "cust_992",
      fullName: "Youssef Trabelsi",
      phoneE164: "+21622987654",
      country: "Tunisia",
      fcrEligible: false,
      notes: "Demande d'information délais transport maritime.",
      createdAt: "2026-09-12T14:20:00Z",
    },
    lead: {
      id: "lead_502",
      customerId: "cust_992",
      stage: "NEW",
      targetVehicle: "Mercedes-Benz C200",
      budgetMinEur: 30000,
      budgetMaxEur: 38000,
      updatedAt: "2026-09-13T16:15:00Z",
    },
  },
  {
    id: "th_01h9x8a3",
    customerId: "cust_993",
    customerName: "Karim Mansour",
    customerPhone: "+33 6 12 34 56 78",
    channel: "WHATSAPP",
    status: "CLOSED",
    unreadCount: 0,
    lastMessageSnippet: "Merci pour le devis FCR, je reviens vers vous lundi.",
    lastActivityAt: "2026-09-12T11:00:00Z",
    assignedAgentId: "agent_01",
    assignedAgentName: "Sami Khedira",
    customer: {
      id: "cust_993",
      fullName: "Karim Mansour",
      phoneE164: "+33612345678",
      email: "karim.m@outlook.fr",
      country: "France / Tunisia",
      fcrEligible: true,
      notes: "Résident en France (TRE), droit FCR confirmé.",
      createdAt: "2026-09-01T09:15:00Z",
    },
    lead: {
      id: "lead_503",
      customerId: "cust_993",
      stage: "QUOTE_SENT",
      targetVehicle: "Audi Q5 40 TDI 2023",
      budgetMinEur: 40000,
      budgetMaxEur: 48000,
      assignedAgentName: "Sami Khedira",
      updatedAt: "2026-09-12T11:00:00Z",
    },
  },
];

const MOCK_MESSAGES: Record<string, ChatMessage[]> = {
  th_01h9x8a1: [
    {
      id: "msg_101",
      threadId: "th_01h9x8a1",
      direction: "INBOUND",
      senderName: "Mohamed Ben Ali",
      senderPhone: "+216 98 123 456",
      content: "Bonjour, je cherche une BMW X5 2022 éligible FCR avec TVA déductible en Tunisie.",
      status: "READ",
      timestamp: "2026-09-13T17:35:00Z",
    },
    {
      id: "msg_102",
      threadId: "th_01h9x8a1",
      direction: "OUTBOUND",
      senderName: "Sami Khedira",
      content: "Bonjour M. Ben Ali, nous avons plusieurs modèles disponibles répondant parfaitement aux critères FCR Netto.",
      status: "DELIVERED",
      timestamp: "2026-09-13T17:38:00Z",
    },
    {
      id: "msg_103",
      threadId: "th_01h9x8a1",
      direction: "INBOUND",
      senderName: "Mohamed Ben Ali",
      senderPhone: "+216 98 123 456",
      content: "Pouvez-vous me préparer une simulation de tarif complet avec douane et certificat FCR ?",
      status: "READ",
      timestamp: "2026-09-13T17:42:00Z",
    },
  ],
  th_01h9x8a2: [
    {
      id: "msg_201",
      threadId: "th_01h9x8a2",
      direction: "INBOUND",
      senderName: "Youssef Trabelsi",
      senderPhone: "+216 22 987 654",
      content: "Quel est le délai de livraison pour l'Allemagne vers Tunis ?",
      status: "READ",
      timestamp: "2026-09-13T16:15:00Z",
    },
  ],
  th_01h9x8a3: [
    {
      id: "msg_301",
      threadId: "th_01h9x8a3",
      direction: "INBOUND",
      senderName: "Karim Mansour",
      senderPhone: "+33 6 12 34 56 78",
      content: "Merci pour le devis FCR, je reviens vers vous lundi.",
      status: "READ",
      timestamp: "2026-09-12T11:00:00Z",
    },
  ],
};

export function useThreads(filter?: InboxFilter) {
  return useQuery({
    queryKey: inboxKeys.threads(filter),
    queryFn: async () => {
      try {
        const queryParams: Record<string, any> = {};
        if (filter?.status && filter.status !== "ALL") {
          queryParams.status = filter.status;
        }
        const res = await apiClient.get<any>("/conversations", { params: queryParams });
        const rawList = Array.isArray(res.data) ? res.data : (res.data?.data || []);
        if (rawList.length > 0) {
          return rawList.map((c: any) => ({
            id: c.id,
            customerId: c.customer_id || c.customerId || `cust_${c.id}`,
            customerName: c.customer_name || c.customerName || c.customer_phone_e164 || "Client WhatsApp",
            customerPhone: c.customer_phone_e164 || c.customerPhone || "+216 -- --- ---",
            channel: "WHATSAPP",
            status: c.status || "UNASSIGNED",
            mode: c.mode || "AI",
            conversationState: c.conversation_state || c.conversationState || "AI_ACTIVE",
            handoffReason: c.handoff_reason,
            handoffSummary: c.handoff_summary,
            draftData: c.draft_data,
            unreadCount: c.unread_count || 0,
            lastMessageSnippet: c.last_message_content || c.lastMessageSnippet || "Message reçu",
            lastActivityAt: c.last_message_at || c.lastActivityAt || new Date().toISOString(),
            assignedAgentId: c.assigned_agent_id,
            assignedAgentName: c.assigned_agent_name,
            customer: {
              id: c.customer_id || `cust_${c.id}`,
              fullName: c.customer_name || c.customer_phone_e164 || "Client WhatsApp",
              phoneE164: c.customer_phone_e164 || "+216 -- --- ---",
              fcrEligible: true,
              country: "Tunisia",
              createdAt: c.created_at || new Date().toISOString(),
            },
            activeAiUnderstanding: c.active_ai_understanding,
            activeAiSuggestion: c.active_ai_suggestion,
          }));
        }
        return [];
      } catch (err) {
        console.warn("Failed to fetch backend conversations, using fallback", err);
        return [];
      }
    },
    refetchInterval: 3000,
    staleTime: 2000,
  });
}

export function useThreadMessages(threadId?: string) {
  return useQuery({
    queryKey: inboxKeys.messages(threadId || ""),
    enabled: Boolean(threadId),
    queryFn: async () => {
      try {
        const res = await apiClient.get<any>(`/conversations/${threadId}/messages`);
        const rawMsgs = Array.isArray(res.data) ? res.data : (res.data?.data || []);
        return rawMsgs.map((m: any) => ({
          id: m.id,
          threadId: m.conversation_id || threadId,
          direction: m.direction?.toUpperCase() === "OUTBOUND" ? "OUTBOUND" : "INBOUND",
          senderName: m.sender_type === "Customer" ? "Client" : (m.sender_type === "AI_Bot" ? "🤖 Agent IA" : "Conseiller Commercial"),
          content: m.content || "",
          status: m.delivery_status || "DELIVERED",
          timestamp: m.created_at || new Date().toISOString(),
        }));
      } catch {
        return MOCK_MESSAGES[threadId || ""] || [];
      }
    },
    refetchInterval: 3000,
    staleTime: 2000,
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ threadId, content }: { threadId: string; content: string }) => {
      try {
        const res = await apiClient.post<any>(`/conversations/${threadId}/messages`, { content });
        const m = res.data?.data || res.data;
        return {
          id: m.id || `msg_${Date.now()}`,
          threadId,
          direction: "OUTBOUND" as const,
          senderName: "Conseiller Commercial",
          content: m.content || content,
          status: "SENT" as const,
          timestamp: m.created_at || new Date().toISOString(),
        };
      } catch (err) {
        console.error("Failed to post outbound message:", err);
        throw err;
      }
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: inboxKeys.messages(variables.threadId) });
      queryClient.invalidateQueries({ queryKey: inboxKeys.all });
    },
  });
}

export function useTakeoverConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (threadId: string) => {
      const res = await apiClient.post<any>(`/conversations/${threadId}/takeover`);
      return res.data?.data || res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: inboxKeys.all });
    },
  });
}

export function useResumeAiConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (threadId: string) => {
      const res = await apiClient.post<any>(`/conversations/${threadId}/resume-ai`);
      return res.data?.data || res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: inboxKeys.all });
    },
  });
}
