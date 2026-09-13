import { QueryClient, QueryKey } from "@tanstack/react-query";

export interface OptimisticContext<T> {
  previousData?: T;
  queryKey: QueryKey;
}

export async function prepareOptimisticUpdate<T>(
  queryClient: QueryClient,
  queryKey: QueryKey,
  updater: (oldData: T | undefined) => T
): Promise<OptimisticContext<T>> {
  // Cancel any outgoing refetches so they don't overwrite our optimistic update
  await queryClient.cancelQueries({ queryKey });

  // Snapshot the previous value
  const previousData = queryClient.getQueryData<T>(queryKey);

  // Optimistically update to the new value
  queryClient.setQueryData<T>(queryKey, updater);

  return { previousData, queryKey };
}

export function rollbackOptimisticUpdate<T>(
  queryClient: QueryClient,
  context?: OptimisticContext<T>
): void {
  if (context?.previousData !== undefined) {
    queryClient.setQueryData(context.queryKey, context.previousData);
  }
}
