import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { ProblemDetails } from "../types";
import { toast } from "../components/feedback/toast";

export class ApiError extends Error {
  public status: number;
  public title: string;
  public detail: string;
  public type?: string;
  public instance?: string;
  public correlationId?: string;
  public validationErrors?: Record<string, string[]>;

  constructor(problem: ProblemDetails, status: number) {
    super(problem.detail || problem.title || "An API error occurred");
    this.name = "ApiError";
    this.status = problem.status || status;
    this.title = problem.title || "API Error";
    this.detail = problem.detail || "An unexpected server error occurred.";
    this.type = problem.type;
    this.instance = problem.instance;
    this.correlationId = problem.correlation_id;
    this.validationErrors = problem.errors;
  }
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

let isLoggingOut = false;

export function clearAuthSession(): void {
  localStorage.removeItem("crm_access_token");
  sessionStorage.removeItem("crm_access_token");
  window.dispatchEvent(new CustomEvent("auth:unauthorized"));
}

// Request Interceptor: Attach JWT Bearer token & correlation ID (SEC-001, ADR 0008)
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("crm_access_token") || sessionStorage.getItem("crm_access_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Inject client-side request correlation ID if not set using crypto.randomUUID() where available
    if (config.headers && !config.headers["X-Correlation-ID"]) {
      const uuid = typeof crypto !== "undefined" && crypto.randomUUID 
        ? crypto.randomUUID() 
        : `req_${Math.random().toString(36).substring(2, 11)}`;
      config.headers["X-Correlation-ID"] = uuid;
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// Response Interceptor: RFC 7807 problem details parsing & 401 Unauthorized handling (ADR 0008)
apiClient.interceptors.response.use(
  (response) => {
    // Return inner data payload if wrapped in standard { success: true, data: ... } envelope
    if (response.data && typeof response.data === "object" && "success" in response.data && "data" in response.data) {
      return response.data;
    }
    return response;
  },
  (error: AxiosError<ProblemDetails>) => {
    const status = error.response?.status || 500;
    const rawData = error.response?.data;
    const requestUrl = error.config?.url || "";

    let problem: ProblemDetails;
    if (rawData && typeof rawData === "object" && "title" in rawData) {
      problem = rawData;
    } else {
      problem = {
        type: "https://api.carexport.com/errors/unexpected-error",
        title: status >= 500 ? "Server Error" : "Request Error",
        status: status,
        detail: error.message || "An unexpected error occurred while communicating with the server.",
        correlation_id: (error.config?.headers?.["X-Correlation-ID"] as string) || undefined,
      };
    }

    const apiError = new ApiError(problem, status);

    const isAuthEndpoint = requestUrl.includes("/auth/login") || requestUrl.includes("/auth/token");

    // 401 Unauthorized handling
    if (status === 401 && !isAuthEndpoint) {
      if (!isLoggingOut) {
        isLoggingOut = true;
        clearAuthSession();
        toast.error("Session Inactive", "Requête non authentifiée - Mode démonstration actif.");
        setTimeout(() => { isLoggingOut = false; }, 3000);
      }
    } else {
      // Dispatch operational Toast alert for RFC 7807 error
      toast.error(apiError.title, apiError.detail, apiError.correlationId);
    }

    return Promise.reject(apiError);
  }
);

