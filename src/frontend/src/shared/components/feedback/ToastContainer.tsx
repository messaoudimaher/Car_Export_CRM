import React, { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Info, AlertTriangle, X } from "lucide-react";
import { ToastMessage, toastStore } from "./toast";

export const ToastContainer: React.FC = () => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    return toastStore.subscribe((updatedToasts) => {
      setToasts(updatedToasts);
    });
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col space-y-2 max-w-md w-full px-2 pointer-events-none">
      {toasts.map((item) => {
        const isError = item.type === "error";
        const isSuccess = item.type === "success";
        const isWarning = item.type === "warning";

        return (
          <div
            key={item.id}
            className={`pointer-events-auto flex items-start p-3.5 rounded-lg border shadow-lg transition-all duration-200 ${
              isError
                ? "bg-crm-card border-crm-danger/40 text-crm-text"
                : isSuccess
                ? "bg-crm-card border-crm-success/40 text-crm-text"
                : isWarning
                ? "bg-crm-card border-crm-warning/40 text-crm-text"
                : "bg-crm-card border-crm-border text-crm-text"
            }`}
          >
            <div className="flex-shrink-0 mr-3 mt-0.5">
              {isSuccess && <CheckCircle2 className="w-5 h-5 text-crm-success" />}
              {isError && <AlertCircle className="w-5 h-5 text-crm-danger" />}
              {isWarning && <AlertTriangle className="w-5 h-5 text-crm-warning" />}
              {!isSuccess && !isError && !isWarning && <Info className="w-5 h-5 text-crm-primary" />}
            </div>

            <div className="flex-1 min-w-0 pr-2">
              <h4 className="text-sm font-semibold leading-tight">{item.title}</h4>
              {item.detail && (
                <p className="text-xs text-crm-muted mt-1 leading-normal break-words">
                  {item.detail}
                </p>
              )}
              {item.correlationId && (
                <div className="text-[10px] font-mono text-crm-muted/70 mt-1">
                  ID: {item.correlationId}
                </div>
              )}
            </div>

            <button
              onClick={() => toastStore.dismiss(item.id)}
              className="flex-shrink-0 text-crm-muted hover:text-crm-text p-1 rounded transition-colors"
              title="Dismiss"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
