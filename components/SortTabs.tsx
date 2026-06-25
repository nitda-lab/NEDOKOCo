import Link from "next/link";

import type { SortKey } from "@/lib/worlds";

const TABS: { key: SortKey; label: string }[] = [
  { key: "updated", label: "新着" },
  { key: "popularity", label: "人気" },
  { key: "favorites", label: "お気に入り" },
];

export function SortTabs({ active }: { active: SortKey }) {
  return (
    <div className="flex gap-2">
      {TABS.map((t) => (
        <Link
          key={t.key}
          href={`/?sort=${t.key}`}
          scroll={false}
          className={`rounded-full px-4 py-1.5 text-sm no-underline transition ${
            active === t.key ? "bg-accent text-white" : "bg-card text-ink/80 hover:text-ink"
          }`}
        >
          {t.label}
        </Link>
      ))}
    </div>
  );
}
