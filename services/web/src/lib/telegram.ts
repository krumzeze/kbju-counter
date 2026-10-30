import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export const webApp: TelegramWebApp | undefined = window.Telegram?.WebApp?.initData
  ? window.Telegram.WebApp
  : undefined;

export const isMiniApp = webApp !== undefined;

export function haptic(type: "success" | "error" | "warning") {
  webApp?.HapticFeedback?.notificationOccurred(type);
}

export function confirmAction(message: string): Promise<boolean> {
  if (webApp?.showConfirm) {
    return new Promise((resolve) => webApp.showConfirm!(message, resolve));
  }
  return Promise.resolve(window.confirm(message));
}

export function shareLink(url: string, text: string) {
  const share = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
  if (webApp?.openTelegramLink) webApp.openTelegramLink(share);
  else window.open(share, "_blank", "noopener");
}

const ROOT_PATHS = new Set(["/", "/workouts", "/weight", "/profile", "/admin"]);

export function useTelegramBackButton() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!webApp) return;
    const back = () => navigate(-1);
    if (ROOT_PATHS.has(location.pathname)) {
      webApp.BackButton.hide();
    } else {
      webApp.BackButton.show();
      webApp.BackButton.onClick(back);
    }
    return () => webApp.BackButton.offClick(back);
  }, [location.pathname, navigate]);
}
