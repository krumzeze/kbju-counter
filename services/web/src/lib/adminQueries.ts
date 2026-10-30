import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { adminApi, type UserQuery } from "../api/client";
import type { UserDetail } from "../api/types";

export const useDashboard = () =>
  useQuery({ queryKey: ["admin", "dashboard"], queryFn: adminApi.dashboard, refetchInterval: 60_000 });

export const useUsers = (query: UserQuery) =>
  useQuery({
    queryKey: ["admin", "users", query],
    queryFn: () => adminApi.users(query),
    placeholderData: keepPreviousData,
  });

export const useUser = (id: number) =>
  useQuery({ queryKey: ["admin", "user", id], queryFn: () => adminApi.user(id) });

export function useUserAction<T>(id: number, action: (arg: T) => Promise<UserDetail>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: action,
    onSuccess: (user) => {
      client.setQueryData(["admin", "user", id], user);
      client.invalidateQueries({ queryKey: ["admin", "users"] });
      client.invalidateQueries({ queryKey: ["admin", "dashboard"] });
    },
  });
}

export const usePromos = () => useQuery({ queryKey: ["admin", "promos"], queryFn: adminApi.promos });

export const useSegments = () =>
  useQuery({ queryKey: ["admin", "segments"], queryFn: adminApi.segments });

export const useBroadcasts = () =>
  useQuery({
    queryKey: ["admin", "broadcasts"],
    queryFn: adminApi.broadcasts,
    refetchInterval: (query) =>
      query.state.data?.some((b) => b.status === "sending") ? 2_000 : false,
  });

export const useReferrers = () =>
  useQuery({ queryKey: ["admin", "referrals"], queryFn: adminApi.referrals });

export const useActions = (offset: number) =>
  useQuery({
    queryKey: ["admin", "actions", offset],
    queryFn: () => adminApi.actions(offset),
    placeholderData: keepPreviousData,
  });

export const usePrefs = () => useQuery({ queryKey: ["admin", "prefs"], queryFn: adminApi.prefs });

export function useAdminMutation<T, R>(fn: (arg: T) => Promise<R>, ...keys: string[]) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () =>
      Promise.all(keys.map((key) => client.invalidateQueries({ queryKey: ["admin", key] }))),
  });
}
