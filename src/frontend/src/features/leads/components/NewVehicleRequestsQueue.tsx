import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Car, ShieldCheck, CheckCircle2, ArrowRight, Clock, User } from "lucide-react";
import { apiClient } from "../../../shared/api/client";

interface VehicleRequestItem {
  id: string;
  customerName: string;
  customerPhone: string;
  make: string;
  model: string;
  minYear?: number;
  maxYear?: number;
  fuelType?: string;
  transmission?: string;
  budgetEur?: number;
  fcrCompatible: boolean;
  destinationPort: string;
  status: string;
  conversationId?: string;
  createdAt: string;
}

interface NewVehicleRequestsQueueProps {
  onSelectConversation?: (conversationId: string) => void;
}

export const NewVehicleRequestsQueue: React.FC<NewVehicleRequestsQueueProps> = ({ onSelectConversation }) => {
  const { data: requests = [], isLoading, refetch } = useQuery<VehicleRequestItem[]>({
    queryKey: ["new-vehicle-requests-queue"],
    queryFn: async () => {
      try {
        const res = await apiClient.get<any>("/vehicle-requests");
        const list = Array.isArray(res.data) ? res.data : res.data?.data || [];
        return list.map((v: any) => ({
          id: v.id,
          customerName: v.customer_name || v.customer_phone_e164 || "Client WhatsApp",
          customerPhone: v.customer_phone_e164 || "+216 -- --- ---",
          make: v.make || "Marque non spécifiée",
          model: v.model || "Modèle non spécifié",
          minYear: v.min_year,
          maxYear: v.max_year,
          fuelType: v.fuel_type || "Diesel",
          transmission: v.transmission || "Automatique",
          budgetEur: v.budget_eur,
          fcrCompatible: v.fcr_compatible ?? true,
          destinationPort: v.destination_port || "Rades",
          status: v.status || "NEW",
          conversationId: v.conversation_id,
          createdAt: v.created_at || new Date().toISOString(),
        }));
      } catch {
        return [];
      }
    },
    refetchInterval: 3000,
  });

  if (isLoading) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 font-mono">
        Chargement des demandes véhicules qualifiées...
      </div>
    );
  }

  if (requests.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center text-xs text-slate-400 font-sans space-y-2">
        <Car className="w-8 h-8 text-blue-400 mx-auto opacity-80" />
        <h4 className="font-semibold text-slate-200">Aucune nouvelle demande véhicule</h4>
        <p className="text-slate-500 max-w-sm mx-auto text-[11px]">
          L'Agent IA qualifie automatiquement les intentions d'achat dès confirmation des clients sur WhatsApp.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3 font-sans">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
          <Car className="w-4 h-4 text-emerald-400" />
          NEW VEHICLE REQUESTS ({requests.length})
        </h3>
        <button
          onClick={() => refetch()}
          className="text-[11px] text-blue-400 hover:underline font-mono"
        >
          Actualiser
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {requests.map((req) => (
          <div
            key={req.id}
            className="bg-slate-900 border border-emerald-900/50 hover:border-emerald-600/80 rounded-xl p-4 transition-all space-y-3 shadow-lg group flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="font-bold text-slate-100 text-sm flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-blue-400" />
                    {req.customerName}
                  </h4>
                  <p className="text-xs text-slate-400 font-mono">{req.customerPhone}</p>
                </div>
                {req.fcrCompatible ? (
                  <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-emerald-950 text-emerald-300 border border-emerald-700/60 rounded-full flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    FCR 5 ans OK
                  </span>
                ) : (
                  <span className="px-2 py-0.5 text-[10px] font-mono bg-slate-800 text-slate-400 rounded-full">
                    Standard
                  </span>
                )}
              </div>

              <div className="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1 text-xs">
                <div className="text-sm font-bold text-emerald-300 flex items-center gap-1.5">
                  <span>🚗 {req.make} {req.model}</span>
                </div>
                <div className="grid grid-cols-2 gap-1 text-[11px] text-slate-300 pt-1 border-t border-slate-800/80 font-mono">
                  <span>Année: {req.minYear ? `${req.minYear}+` : "Tout"}</span>
                  <span>Moteur: {req.fuelType}</span>
                  <span>Boîte: {req.transmission}</span>
                  <span className="text-emerald-400 font-semibold">
                    Budget: {req.budgetEur ? `${req.budgetEur.toLocaleString()} €` : "Non fixé"}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 mt-3">
              <span className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(req.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>

              {req.conversationId && (
                <button
                  onClick={() => onSelectConversation?.(req.conversationId!)}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs rounded transition-all flex items-center gap-1.5 shadow-sm group-hover:translate-x-0.5"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Voir Discussion WhatsApp
                  <ArrowRight className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
