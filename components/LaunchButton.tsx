"use client";

import { useState } from "react";
import { createPortal } from "react-dom";

import {
  buildInstanceId,
  buildLaunchUrl,
  extractUserId,
  INSTANCE_TYPES,
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

  function close() {
    setOpen(false);
    setAskId(false);
    setPendingType(null);
    setError("");
  }

  function launch(type: InstanceType, usrId: string | null) {
    const id = buildInstanceId(type, usrId, randomInstanceName());
    if (!id) return;
    window.open(buildLaunchUrl(worldId, id), "_blank", "noopener");
    close();
  }

  function onPick(type: InstanceType) {
    if (!needsUserId(type)) {
      launch(type, null);
      return;
    }
    const saved = (typeof window !== "undefined" && window.localStorage.getItem(STORAGE_KEY)) || "";
    setIdInput(saved);
    setError("");
    setPendingType(type);
    setAskId(true);
  }

  function saveIdAndLaunch() {
    const extracted = extractUserId(idInput);
    if (!extracted) {
      setError("プロフィールURL（…/user/usr_…）か usr_ID を貼り付けてください");
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, extracted);
    if (pendingType) launch(pendingType, extracted);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setAskId(false);
          setOpen(true);
        }}
        className="shrink-0 whitespace-nowrap rounded-md bg-accent px-3 py-1 text-xs font-bold text-white"
      >
        建てる
      </button>

      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
            onClick={close}
          >
            <div
              className="w-full max-w-xs rounded-xl border border-[#2a2350] bg-card p-4 text-ink shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              {!askId ? (
                <>
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm font-bold">インスタンスを建てる</span>
                    <span className="text-xs opacity-60">リージョン: 日本</span>
                  </div>
                  <div className="flex flex-col gap-1">
                    {INSTANCE_TYPES.map((t) => (
                      <button
                        key={t.key}
                        type="button"
                        onClick={() => onPick(t.key)}
                        className="rounded px-3 py-2 text-left text-sm hover:bg-bg"
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <>
                  <div className="mb-1 text-sm font-bold">VRChatプロフィールURLを貼り付け</div>
                  <div className="mb-2 text-[11px] opacity-60">
                    VRChatにログイン中なら自分のプロフィールを開き、URLをコピーして貼り付け
                  </div>
                  <input
                    value={idInput}
                    onChange={(e) => setIdInput(e.target.value)}
                    placeholder="https://vrchat.com/home/user/usr_..."
                    className="mb-2 w-full rounded bg-bg px-2 py-2 text-sm outline-none"
                  />
                  {error && <div className="mb-2 text-[11px] text-red-400">{error}</div>}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setAskId(false)}
                      className="flex-1 rounded bg-bg px-2 py-2 text-sm"
                    >
                      戻る
                    </button>
                    <button
                      type="button"
                      onClick={saveIdAndLaunch}
                      className="flex-1 rounded bg-accent px-2 py-2 text-sm font-bold text-white"
                    >
                      建てる
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
