import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../../../shared/api/client";
import { inboxKeys } from "../../../shared/api/queryKeys";
import { ConversationThread, ChatMessage, InboxFilter } from "../types";

// Mock Fallback Data for Inbox Workstation Demonstration
const MOCK_THREADS: ConversationThread[] = [
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
        const res = await apiClient.get<ConversationThread[]>("/conversations", { params: filter });
        return res.data;
      } catch {
        // Return filtered mock data on backend pending or network disconnect
        let threads = [...MOCK_THREADS];
        if (filter?.status && filter.status !== "ALL") {
          if (filter.status === "MINE") {
            threads = threads.filter((t) => t.assignedAgentId === "agent_01");
          } else {
            threads = threads.filter((t) => t.status === filter.status);
          }
        }
        if (filter?.searchQuery) {
          const q = filter.searchQuery.toLowerCase();
          threads = threads.filter(
            (t) =>
              t.customerName.toLowerCase().includes(q) ||
              t.customerPhone.includes(q) ||
              t.lastMessageSnippet.toLowerCase().includes(q)
          );
        }
        return threads;
      }
    },
    staleTime: 5000,
  });
}

export function useThreadMessages(threadId?: string) {
  return useQuery({
    queryKey: inboxKeys.messages(threadId || ""),
    enabled: Boolean(threadId),
    queryFn: async () => {
      try {
        const res = await apiClient.get<ChatMessage[]>(`/conversations/${threadId}/messages`);
        return res.data;
      } catch {
        return MOCK_MESSAGES[threadId || ""] || [];
      }
    },
    staleTime: 5000,
  });
}

export function useSendMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ threadId, content }: { threadId: string; content: string }) => {
      try {
        const res = await apiClient.post<ChatMessage>(`/conversations/${threadId}/messages`, { content });
        return res.data;
      } catch {
        const newMsg: ChatMessage = {
          id: `msg_${Date.now()}`,
          threadId,
          direction: "OUTBOUND",
          senderName: "Conseiller Commercial",
          content,
          status: "SENT",
          timestamp: new Date().toISOString(),
        };
        if (!MOCK_MESSAGES[threadId]) {
          MOCK_MESSAGES[threadId] = [];
        }
        MOCK_MESSAGES[threadId].push(newMsg);
        return newMsg;
      }
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: inboxKeys.messages(variables.threadId) });
      queryClient.invalidateQueries({ queryKey: inboxKeys.all });
    },
  });
}
