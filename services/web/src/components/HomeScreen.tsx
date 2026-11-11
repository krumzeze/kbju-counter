import { useEffect, useState } from "react";
import { tr } from "../lib/i18n";
import { webApp } from "../lib/telegram";
import { Icon } from "./Icon";

const SEEN_KEY = "belok.homeScreen.firstSeen";
const DISMISSED_KEY = "belok.homeScreen.dismissed";
const OFFER_AFTER_DAYS = 2;

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // the offer may show again next time
  }
}

/** True while the shortcut can be added: Telegram supports it and it is not on the home screen yet. */
function useCanAdd(): boolean {
  const [canAdd, setCanAdd] = useState(false);
  useEffect(() => {
    if (!webApp?.checkHomeScreenStatus || !webApp.addToHomeScreen) return;
    webApp.checkHomeScreenStatus((status) => setCanAdd(status === "missed" || status === "unknown"));
    const added = () => setCanAdd(false);
    webApp.onEvent?.("homeScreenAdded", added);
    return () => webApp?.offEvent?.("homeScreenAdded", added);
  }, []);
  return canAdd;
}

const add = () => webApp?.addToHomeScreen?.();

export function HomeScreenLink() {
  if (!useCanAdd()) return null;
  return (
    <button type="button" className="card premium-note home-screen-link" onClick={add}>
      <span>{tr("Добавить на главный экран", "Add to home screen")}</span>
      <Icon name="chevron" />
    </button>
  );
}

/** One-time offer, shown from the user's third day with the app on this device. */
export function HomeScreenOffer() {
  const canAdd = useCanAdd();
  const [dismissed, setDismissed] = useState(() => read(DISMISSED_KEY) !== null);
  const [seasoned] = useState(() => {
    const first = read(SEEN_KEY);
    if (!first) {
      write(SEEN_KEY, String(Date.now()));
      return false;
    }
    return Date.now() - Number(first) >= OFFER_AFTER_DAYS * 86_400_000;
  });
  if (!canAdd || dismissed || !seasoned) return null;

  const close = () => {
    write(DISMISSED_KEY, "1");
    setDismissed(true);
  };
  return (
    <div className="card home-offer">
      <div>
        <strong>{tr("Белок на главном экране", "Belok on your home screen")}</strong>
        <p className="muted small">
          {tr("Открывай дневник в одно касание, без поиска бота.", "Open your diary in one tap, no need to find the bot.")}
        </p>
      </div>
      <div className="home-offer-actions">
        <button
          type="button"
          className="btn btn-primary small"
          onClick={() => {
            add();
            close();
          }}
        >
          {tr("Добавить", "Add")}
        </button>
        <button type="button" className="btn-ghost" onClick={close}>
          {tr("Не сейчас", "Not now")}
        </button>
      </div>
    </div>
  );
}
