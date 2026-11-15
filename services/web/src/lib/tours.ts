export interface TourStep {
  /** Matches `data-tour` on the highlighted element; a step whose target is missing is skipped. */
  target: string;
  /** [ru, en] */
  title: [string, string];
  text: [string, string];
}

export interface Tour {
  /** Stored on the profile once seen; a new id shows the tour again, so add new tours instead of editing ids. */
  id: string;
  path: string;
  steps: TourStep[];
}

/** Tours for the same screen run back to back in this order. */
export const TOURS: Tour[] = [
  {
    id: "home",
    path: "/",
    steps: [
      {
        target: "summary",
        title: ["Твоя норма на день", "Your daily target"],
        text: [
          "Здесь видно, сколько калорий осталось. Полоски ниже показывают белки, жиры и углеводы.",
          "This shows how many calories are left. The bars below are protein, fat and carbs.",
        ],
      },
      {
        target: "snap",
        title: ["Сфотографируй еду", "Snap your food"],
        text: [
          "Я узнаю блюдо и посчитаю КБЖУ. Если что-то неясно, переспрошу.",
          "I'll recognize the dish and count the macros. If something is unclear, I'll ask.",
        ],
      },
      {
        target: "add",
        title: ["Все способы добавить еду", "Every way to log food"],
        text: [
          "Текст, голос, штрихкод, ручной ввод, рецепты и блюда, которые ты уже ел.",
          "Text, voice, barcode, manual entry, recipes and meals you've had before.",
        ],
      },
      {
        target: "days",
        title: ["Прошлые дни", "Past days"],
        text: ["Листай неделю назад и дописывай забытое.", "Go back up to a week and add what you forgot."],
      },
      {
        target: "activity",
        title: ["Вода, шаги и вес", "Water, steps and weight"],
        text: [
          "Отмечай прямо здесь. Шаги и тренировки добавляют калорий к норме.",
          "Log them right here. Steps and workouts add calories to your target.",
        ],
      },
    ],
  },
  {
    id: "home-ai",
    path: "/",
    steps: [
      {
        target: "assistant",
        title: ["AI-помощник", "AI assistant"],
        text: [
          "Задай вопрос о питании или тренировках, он видит твой дневник. По понедельникам там появляется разбор недели.",
          "Ask about food or training, it sees your diary. Every Monday a weekly review shows up there.",
        ],
      },
      {
        target: "suggestions",
        title: ["Что приготовить", "What to cook"],
        text: [
          "Рецепты подбираются под то, сколько белка и калорий тебе осталось сегодня.",
          "Recipes are picked for the protein and calories you have left today.",
        ],
      },
    ],
  },
  {
    id: "add",
    path: "/add",
    steps: [
      {
        target: "add-modes",
        title: ["Выбери способ", "Pick a way"],
        text: [
          "Фото, текст или голос посчитает AI. Штрихкод и история добавляют еду без распознавания.",
          "AI handles photo, text and voice. Barcode and history add food without recognition.",
        ],
      },
      {
        target: "add-photo",
        title: ["Как снять точнее", "For a better estimate"],
        text: [
          "Снимай сверху при хорошем свете, чтобы было видно всю тарелку. Граммовку потом можно поправить.",
          "Shoot from above in good light with the whole plate in view. You can fix the grams later.",
        ],
      },
    ],
  },
  {
    id: "workouts",
    path: "/workouts",
    steps: [
      {
        target: "workout-start",
        title: ["Тренировка", "Workout"],
        text: [
          "Начни тренировку и записывай подходы по ходу: вес и повторы.",
          "Start a workout and log sets as you go: weight and reps.",
        ],
      },
      {
        target: "workout-links",
        title: ["Упражнения и прогресс", "Exercises and progress"],
        text: [
          "Техника, рабочие мышцы и рост результатов по каждому упражнению.",
          "Technique, muscles worked and progress for every exercise.",
        ],
      },
      {
        target: "templates",
        title: ["Свои программы", "Your routines"],
        text: [
          "Сохрани программу один раз и запускай её в одно касание.",
          "Save a routine once and start it with one tap.",
        ],
      },
    ],
  },
  {
    id: "recipes",
    path: "/recipes",
    steps: [
      {
        target: "recipe-filters",
        title: ["Фильтры", "Filters"],
        text: [
          "«Закроет остаток дня» покажет рецепты, которые впишутся в то, что осталось съесть.",
          "\"Fits what's left today\" shows recipes that match what you still have to eat.",
        ],
      },
      {
        target: "recipe-new",
        title: ["Свой рецепт", "Your own recipe"],
        text: [
          "Добавь рецепт, и КБЖУ на порцию посчитается само. Им можно поделиться со всеми.",
          "Add a recipe and macros per serving are counted for you. You can share it with everyone.",
        ],
      },
    ],
  },
  {
    id: "stats",
    path: "/stats",
    steps: [
      {
        target: "stats-period",
        title: ["Период", "Period"],
        text: ["Смотри неделю, месяц или дольше.", "Look at a week, a month or longer."],
      },
      {
        target: "stats-weight",
        title: ["Вес и тренд", "Weight and trend"],
        text: [
          "Взвешивайся утром пару раз в неделю. Тренд сглаживает скачки воды и показывает настоящую динамику.",
          "Weigh in a couple of mornings a week. The trend smooths out water swings and shows the real direction.",
        ],
      },
    ],
  },
  {
    id: "assistant",
    path: "/assistant",
    steps: [
      {
        target: "assistant-input",
        title: ["Спроси что угодно", "Ask anything"],
        text: [
          "Например, почему вес стоит или чем добрать белок. Ответ учитывает твой дневник и цель.",
          "Like why your weight is stuck or how to get more protein. Answers use your diary and goal.",
        ],
      },
      {
        target: "assistant-photo",
        title: ["Меню и холодильник", "Menu and fridge"],
        text: [
          "Пришли фото меню, подскажу, что заказать. Фото холодильника, предложу, что приготовить.",
          "Send a menu photo and I'll tell you what to order. A fridge photo, and I'll suggest what to cook.",
        ],
      },
      {
        target: "assistant-chats",
        title: ["Все чаты", "All chats"],
        text: [
          "Здесь история разговоров и еженедельные разборы.",
          "Your past conversations and weekly reviews live here.",
        ],
      },
    ],
  },
];

export const TOUR_IDS = TOURS.map((t) => t.id);
