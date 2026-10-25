import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ProfileInput } from "../api/types";

export const useMe = () => useQuery({ queryKey: ["me"], queryFn: api.me });

export const useDay = (day: string) =>
  useQuery({ queryKey: ["day", day], queryFn: () => api.day(day) });

export const useWeights = () => useQuery({ queryKey: ["weights"], queryFn: api.weights });

export const useExercises = () => useQuery({ queryKey: ["exercises"], queryFn: api.exercises });

export const useProgress = (exercise: string) =>
  useQuery({ queryKey: ["progress", exercise], queryFn: () => api.progress(exercise) });

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
