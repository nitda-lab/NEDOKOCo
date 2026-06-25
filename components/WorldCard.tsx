import { formatCount, parseTags, relativeTime, type World } from "@/lib/worlds";

export function WorldCard({ world }: { world: World }) {
  const tags = parseTags(world.tags);
  return (
    <a
      href={world.vrc_url}
      target="_blank"
      rel="noreferrer"
      className="group block overflow-hidden rounded-xl border border-[#2a2350] bg-card no-underline text-ink transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/40"
    >
      {world.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={world.image_url}
          alt={world.name}
          loading="lazy"
          className="h-40 w-full object-cover"
        />
      )}
      <div className="p-3">
        <div className="truncate text-base font-bold">{world.name}</div>
        <div className="mt-0.5 truncate text-xs opacity-70">by {world.author_name}</div>
        {tags.length > 0 && (
          <div className="mt-2 truncate text-xs text-accent">
            {tags.map((t) => `#${t}`).join("　")}
          </div>
        )}
        <div className="mt-2 flex items-center gap-3 text-xs opacity-70">
          <span>❤ {formatCount(world.favorites)}</span>
          {world.capacity && <span>👥 {world.capacity}</span>}
          {world.vrc_updated_at && <span>🕒 {relativeTime(world.vrc_updated_at)}</span>}
        </div>
      </div>
    </a>
  );
}
