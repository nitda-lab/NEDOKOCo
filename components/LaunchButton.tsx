"use client";

import { useState } from "react";

import {
  buildInstanceId,
  buildLaunchUrl,
  INSTANCE_TYPES,
  isValidUserId,
  needsUserId,
  randomInstanceName,
  type InstanceType,
} from "@/lib/launch";

const STORAGE_KEY = "vrc_user_id";

export function LaunchButton({ worldId }: { worldId: string }) {
  const [open, setOpen] = useState(false);
  const [askId, setAskId] = useState(false);
  const [idInput, setIdInput] = useState("");
  const [pendingType, setPendingType] = useState<InstanceType | null>(null);
  const [error, setError] = useState("");

  function launch(type: InstanceType, usrId: string | null) {
    const id = buildInstanceId(type, usrId, randomInstanceName());
    if (!id) return;
    window.open(buildLaunchUrl(worldId, id), "_blank", "noopener");
    setOpen(false);
    setAskId(false);
    setPendingType(null);
    setError("");
  }

  function onPick(type: InstanceType) {
    if (!needsUserId(type)) {
      launch(type, null);
      return;
    }
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (saved && isValidUserId(saved)) {
      launch(type, saved);
      return;
    }
    setPendingType(type);
    setAskId(true);
  }

  function saveIdAndLaunch() {
    if (!isValidUserId(idInput)) {
      setError("usr_ で始まるIDを入力してください");
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, idInput.trim());
    if (pendingType) launch(pendingType, idInput.trim());
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="shrink-0 whitespace-nowrap rounded-md bg-accent px-3 py-1 text-xs font-bold text-white"
      >
        VRChatで建てる
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-[#2a2350] bg-card p-3 shadow-xl">
          {!askId ? (
            <>
              <div className="mb-2 text-xs opacity-70">リージョン: 日本 (JP)</div>
              <div className="flex flex-col gap-1">
                {INSTANCE_TYPES.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => onPick(t.key)}
                    className="rounded px-2 py-1.5 text-left text-sm hover:bg-bg"
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="mb-1 text-xs">VRChatユーザーID (usr_…)</div>
              <div className="mb-2 text-[10px] opacity-60">
                プロフィールURL …/user/usr_xxxx で確認
              </div>
              <input
                value={idInput}
                onChange={(e) => setIdInput(e.target.value)}
                placeholder="usr_xxxxxxxx"
                className="mb-2 w-full rounded bg-bg px-2 py-1 text-sm outline-none"
              />
              {error && <div className="mb-2 text-[10px] text-red-400">{error}</div>}
              <button
                type="button"
                onClick={saveIdAndLaunch}
                className="w-full rounded bg-accent px-2 py-1 text-sm font-bold text-white"
              >
                保存して建てる
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
