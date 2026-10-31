import type { CatalogItem, MuscleGroup, SetValues } from "../api/types";
import { locale, tr } from "./i18n";

export const GROUPS: MuscleGroup[] = [
  "delts",
  "chest",
  "arms",
  "abs",
  "back",
  "legs",
  "glutes",
  "calves",
  "cardio",
];

export const groupLabel = (g: MuscleGroup) =>
  ({
    delts: tr("Дельты", "Shoulders"),
    chest: tr("Грудь", "Chest"),
    arms: tr("Руки", "Arms"),
    abs: tr("Пресс", "Abs"),
    back: tr("Спина", "Back"),
    legs: tr("Ноги", "Legs"),
    glutes: tr("Ягодицы", "Glutes"),
    calves: tr("Голени", "Calves"),
    cardio: tr("Кардио", "Cardio"),
  })[g];

export const GROUP_MUSCLES: Record<MuscleGroup, string[]> = {
  delts: ["shoulders"],
  chest: ["chest"],
  arms: ["biceps", "triceps", "forearms"],
  abs: ["abdominals"],
  back: ["lats", "middle back", "lower back", "traps"],
  legs: ["quadriceps", "hamstrings", "adductors", "abductors"],
  glutes: ["glutes"],
  calves: ["calves"],
  cardio: ["heart"],
};

const MUSCLES: Record<string, [string, string]> = {
  shoulders: ["Дельты", "Shoulders"],
  chest: ["Грудные", "Chest"],
  biceps: ["Бицепс", "Biceps"],
  triceps: ["Трицепс", "Triceps"],
  forearms: ["Предплечья", "Forearms"],
  abdominals: ["Пресс", "Abs"],
  lats: ["Широчайшие", "Lats"],
  "middle back": ["Середина спины", "Middle back"],
  "lower back": ["Поясница", "Lower back"],
  traps: ["Трапеции", "Traps"],
  neck: ["Шея", "Neck"],
  quadriceps: ["Квадрицепс", "Quads"],
  hamstrings: ["Бицепс бедра", "Hamstrings"],
  adductors: ["Приводящие", "Adductors"],
  abductors: ["Отводящие", "Abductors"],
  glutes: ["Ягодичные", "Glutes"],
  calves: ["Икры", "Calves"],
};

export const muscleLabel = (m: string) => {
  const pair = MUSCLES[m];
  return pair ? tr(pair[0], pair[1]) : m;
};

export const EQUIPMENT = [
  "barbell",
  "dumbbell",
  "machine",
  "cable",
  "body only",
  "kettlebells",
  "e-z curl bar",
  "bands",
  "medicine ball",
  "exercise ball",
  "other",
];

const EQUIPMENT_LABELS: Record<string, [string, string]> = {
  barbell: ["Штанга", "Barbell"],
  dumbbell: ["Гантели", "Dumbbells"],
  machine: ["Тренажёры", "Machines"],
  cable: ["Блоки и кроссовер", "Cables"],
  "body only": ["Свой вес", "Bodyweight"],
  kettlebells: ["Гири", "Kettlebells"],
  "e-z curl bar": ["EZ-гриф", "EZ bar"],
  bands: ["Резинки", "Bands"],
  "medicine ball": ["Медбол", "Medicine ball"],
  "exercise ball": ["Фитбол", "Exercise ball"],
  other: ["Другое", "Other"],
};

export const equipmentLabel = (e: string) => {
  const pair = EQUIPMENT_LABELS[e];
  return pair ? tr(pair[0], pair[1]) : e;
};

export const EQUIPMENT_COVER: Record<string, string> = {
  barbell: "Barbell_Bench_Press_-_Medium_Grip",
  dumbbell: "Dumbbell_Bicep_Curl",
  machine: "Leg_Press",
  cable: "Cable_Crossover",
  "body only": "Pushups",
  kettlebells: "Alternating_Kettlebell_Press",
  "e-z curl bar": "EZ-Bar_Curl",
  bands: "Band_Pull_Apart",
  "medicine ball": "Medicine_Ball_Chest_Pass",
  "exercise ball": "Exercise_Ball_Crunch",
  other: "Ab_Roller",
};

export const levelLabel = (l: string) =>
  ({ beginner: tr("Новичок", "Beginner"), intermediate: tr("Средний", "Intermediate") })[l] ?? l;

// Staples most people look for first; everything else follows alphabetically.
const POPULAR = [
  "Barbell_Bench_Press_-_Medium_Grip",
  "Barbell_Full_Squat",
  "Barbell_Deadlift",
  "Pullups",
  "Wide-Grip_Lat_Pulldown",
  "Seated_Cable_Rows",
  "Leg_Press",
  "Dumbbell_Shoulder_Press",
  "Side_Lateral_Raise",
  "Barbell_Curl",
  "Triceps_Pushdown",
  "Romanian_Deadlift",
  "Barbell_Incline_Bench_Press_-_Medium_Grip",
  "Dumbbell_Bench_Press",
  "Incline_Dumbbell_Press",
  "Dumbbell_Flyes",
  "Cable_Crossover",
  "Butterfly",
  "Pushups",
  "Dips_-_Chest_Version",
  "Smith_Machine_Bench_Press",
  "Barbell_Squat",
  "Smith_Machine_Squat",
  "Hack_Squat",
  "Goblet_Squat",
  "Leg_Extensions",
  "Lying_Leg_Curls",
  "Seated_Leg_Curl",
  "Barbell_Lunge",
  "Dumbbell_Lunges",
  "Bodyweight_Walking_Lunge",
  "Barbell_Hip_Thrust",
  "Barbell_Glute_Bridge",
  "Standing_Calf_Raises",
  "Seated_Calf_Raise",
  "Chin-Up",
  "Close-Grip_Front_Lat_Pulldown",
  "Bent_Over_Barbell_Row",
  "One-Arm_Dumbbell_Row",
  "T-Bar_Row_with_Handle",
  "Hyperextensions_Back_Extensions",
  "Barbell_Shrug",
  "Standing_Military_Press",
  "Seated_Barbell_Military_Press",
  "Arnold_Dumbbell_Press",
  "Front_Dumbbell_Raise",
  "Face_Pull",
  "Reverse_Flyes",
  "Dumbbell_Bicep_Curl",
  "Hammer_Curls",
  "EZ-Bar_Curl",
  "Preacher_Curl",
  "Concentration_Curls",
  "Triceps_Pushdown_-_Rope_Attachment",
  "EZ-Bar_Skullcrusher",
  "Dips_-_Triceps_Version",
  "Bench_Dips",
  "Standing_Dumbbell_Triceps_Extension",
  "Close-Grip_Barbell_Bench_Press",
  "Plank",
  "Crunches",
  "Cable_Crunch",
  "Flat_Bench_Lying_Leg_Raise",
  "Russian_Twist",
  "Ab_Roller",
  "Running_Treadmill",
  "Walking_Treadmill",
  "Bicycling_Stationary",
  "Elliptical_Trainer",
  "Rowing_Stationary",
  "Stairmaster",
  "Rope_Jumping",
];
const RANK = new Map(POPULAR.map((id, i) => [id, i]));

export function sortCatalog(items: CatalogItem[]): CatalogItem[] {
  const collator = new Intl.Collator(locale());
  return [...items].sort((a, b) => {
    const ra = RANK.get(a.id) ?? Infinity;
    const rb = RANK.get(b.id) ?? Infinity;
    return ra !== rb ? ra - rb : collator.compare(a.name, b.name);
  });
}

const normalize = (s: string) => s.toLowerCase().replace(/ё/g, "е");

export function searchCatalog(items: CatalogItem[], query: string): CatalogItem[] {
  const words = normalize(query).split(/\s+/).filter(Boolean);
  if (!words.length) return items;
  return items.filter((x) => {
    const hay = normalize(`${x.name} ${x.id.replace(/_/g, " ")} ${x.primary.map(muscleLabel).join(" ")}`);
    return words.every((w) => hay.includes(w));
  });
}

export const imageUrl = (id: string, frame = 0) => `/exercise-img/${id}/${frame}.jpg`;

export function formatSet(s: SetValues): string {
  if (s.duration_s) return `${Math.round(s.duration_s / 60)} ${tr("мин", "min")}`;
  if (!s.weight_kg) return `${s.reps} ${tr("повт.", "reps")}`;
  return `${s.weight_kg}×${s.reps}`;
}

export const kg = (n: number) =>
  `${Math.round(n).toLocaleString(locale())} ${tr("кг", "kg")}`;

export const compact = (n: number) =>
  n.toLocaleString(locale(), { notation: "compact", maximumFractionDigits: 1 });

export function duration(fromIso: string, toIso?: string | null): string {
  const ms = (toIso ? new Date(toIso).getTime() : Date.now()) - new Date(fromIso).getTime();
  const minutes = Math.max(0, Math.floor(ms / 60000));
  const h = Math.floor(minutes / 60);
  return h ? `${h} ${tr("ч", "h")} ${minutes % 60} ${tr("мин", "min")}` : `${minutes} ${tr("мин", "min")}`;
}
