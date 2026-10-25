interface TelegramBackButton {
  show(): void;
  hide(): void;
  onClick(cb: () => void): void;
  offClick(cb: () => void): void;
}

interface TelegramWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  ready(): void;
  expand(): void;
  BackButton: TelegramBackButton;
  HapticFeedback?: { notificationOccurred(type: "success" | "error" | "warning"): void };
}

interface Window {
  Telegram?: { WebApp: TelegramWebApp };
  onTelegramAuth?: (user: Record<string, string | number>) => void;
}
