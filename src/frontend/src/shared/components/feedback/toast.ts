export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  detail?: string;
  correlationId?: string;
  duration?: number;
}

type ToastListener = (toasts: ToastMessage[]) => void;

class ToastStore {
  private toasts: ToastMessage[] = [];
  private listeners: Set<ToastListener> = new Set();

  subscribe(listener: ToastListener): () => void {
    this.listeners.add(listener);
    listener(this.toasts);
    return () => {
      this.listeners.delete(listener);
    };
  }

  show(toast: Omit<ToastMessage, "id">): string {
    const id = `toast_${Math.random().toString(36).substring(2, 9)}`;
    const newToast: ToastMessage = {
      id,
      duration: 5000,
      ...toast,
    };
    this.toasts = [...this.toasts, newToast];
    this.notify();

    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, newToast.duration);
    }
    return id;
  }

  dismiss(id: string): void {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this.notify();
  }

  clear(): void {
    this.toasts = [];
    this.notify();
  }

  private notify(): void {
    this.listeners.forEach((listener) => listener(this.toasts));
  }
}

export const toastStore = new ToastStore();

export const toast = {
  success: (title: string, detail?: string) =>
    toastStore.show({ type: "success", title, detail }),
  error: (title: string, detail?: string, correlationId?: string) =>
    toastStore.show({ type: "error", title, detail, correlationId, duration: 8000 }),
  warning: (title: string, detail?: string) =>
    toastStore.show({ type: "warning", title, detail }),
  info: (title: string, detail?: string) =>
    toastStore.show({ type: "info", title, detail }),
  dismiss: (id: string) => toastStore.dismiss(id),
};
