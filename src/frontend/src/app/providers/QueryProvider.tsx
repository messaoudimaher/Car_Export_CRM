import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "../../shared/api/client";

export function createConfiguredQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60 * 1000, // Default stale time 60 seconds
        gcTime: 10 * 60 * 1000, // Garbage collection time 10 minutes
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // Fail fast with 0 retries on HTTP 4xx client errors
          if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
            return false;
          }
          // Retry up to 3 times on 5xx server errors or network drops
          return failureCount < 3;
        },
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      },
      mutations: {
        retry: false, // Mutations fail fast to avoid duplicate state mutations
      },
    },
  });
}

export const queryClient = createConfiguredQueryClient();

interface QueryProviderProps {
  children: React.ReactNode;
}

export const QueryProvider: React.FC<QueryProviderProps> = ({ children }) => {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};
