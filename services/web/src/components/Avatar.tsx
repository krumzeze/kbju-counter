import { useState } from "react";
import { webApp } from "../lib/telegram";

export function Avatar({ name }: { name: string | null }) {
  const photo = webApp?.initDataUnsafe?.user?.photo_url;
  const [broken, setBroken] = useState(false);
  return (
    <span className="avatar-img">
      {photo && !broken ? (
        <img src={photo} alt="" onError={() => setBroken(true)} />
      ) : (
        (name?.replace(/^@/, "")[0] ?? "B").toUpperCase()
      )}
    </span>
  );
}
