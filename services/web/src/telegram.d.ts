interface TelegramBackButton {
  show(): void;
  hide(): void;
  onClick(cb: () => void): void;
  offClick(cb: () => void): void;
}

interface TelegramWebApp {
  initData: string;
  initDataUnsafe?: { user?: { language_code?: string } };
  colorScheme: "light" | "dark";
  ready(): void;
  expand(): void;
  BackButton: TelegramBackButton;
  HapticFeedback?: { notificationOccurred(type: "success" | "error" | "warning"): void };
  showConfirm?(message: string, callback: (confirmed: boolean) => void): void;
  openTelegramLink?(url: string): void;
  openLink?(url: string): void;
}

interface Window {
  Telegram?: { WebApp: TelegramWebApp };
  onTelegramAuth?: (user: Record<string, string | number>) => void;
}
