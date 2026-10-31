import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ProfileInput } from "../api/types";

export const useMe = () => useQuery({ queryKey: ["me"], queryFn: api.me });

export const useDay = (day: string) =>
  useQuery({ queryKey: ["day", day], queryFn: () => api.day(day) });

export const useWeights = () => useQuery({ queryKey: ["weights"], queryFn: api.weights });

export const useExercises = () => useQuery({ queryKey: ["exercises"], queryFn: api.exercises });

export const useProgress = (exerciseId: number) =>
  useQuery({ queryKey: ["progress", exerciseId], queryFn: () => api.progress(exerciseId) });

export const useCatalog = () =>
  useQuery({ queryKey: ["catalog"], queryFn: api.catalog, staleTime: Infinity });

export const useCatalogItem = (id: string) =>
  useQuery({ queryKey: ["catalog", id], queryFn: () => api.catalogItem(id), staleTime: Infinity });

export const usePlans = () =>
  useQuery({ queryKey: ["plans"], queryFn: api.plans, staleTime: 10 * 60 * 1000 });

export const useAnalytics = () => useQuery({ queryKey: ["analytics"], queryFn: api.analytics });

export const useWorkouts = () => useQuery({ queryKey: ["workouts"], queryFn: api.workouts });

export const useActiveWorkout = () =>
  useQuery({ queryKey: ["workout", "active"], queryFn: api.activeWorkout });

export const useWorkout = (id: number) =>
  useQuery({ queryKey: ["workout", id], queryFn: () => api.workout(id) });

export const useTemplates = () => useQuery({ queryKey: ["templates"], queryFn: api.templates });

/** Everything derived from logged sets. */
export const WORKOUT_KEYS = ["workout", "workouts", "exercises", "progress", "analytics", "day"];

export function useInvalidate() {
  const client = useQueryClient();
  return (...keys: string[]) =>
    Promise.all(keys.map((key) => client.invalidateQueries({ queryKey: [key] })));
}

export function useSaveProfile() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: ProfileInput) => api.saveProfile(body),
    onSuccess: () => invalidate("me", "day", "weights"),
  });
}
