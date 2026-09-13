import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";
import { ProblemDetails } from "../types";

export const apiClient: AxiosInstance = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

// Request Interceptor: Attach JWT Bearer token & correlation ID
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("crm_access_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Inject client-side request correlation ID if not set
    if (config.headers && !config.headers["X-Correlation-ID"]) {
      config.headers["X-Correlation-ID"] = `req_${Math.random().toString(36).substring(2, 11)}`;
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// Response Interceptor: RFC 7807 problem details error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ProblemDetails>) => {
    if (error.response?.data) {
      const problem = error.response.data;
      console.error(`[API Error ${problem.status || error.response.status}] ${problem.title || "Request Error"}: ${problem.detail || error.message}`);
    }
    return Promise.reject(error);
  }
);
