import { parseTags, type World } from "@/lib/worlds";

export function WorldCard({ world }: { world: World }) {
  const tags = parseTags(world.tags);
  return (
    <a
      href={world.vrc_url}
      target="_blank"
      rel="noreferrer"
      style={{
        display: "block", background: "var(--card)", borderRadius: 12,
        overflow: "hidden", textDecoration: "none", color: "var(--text)",
        border: "1px solid #2a2350",
      }}
    >
      {world.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={world.image_url} alt={world.name} style={{ width: "100%", height: 160, objectFit: "cover" }} />
      )}
      <div style={{ padding: 12 }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{world.name}</div>
        <div style={{ fontSize: 12, opacity: 0.7, marginTop: 2 }}>by {world.author_name}</div>
        {tags.length > 0 && (
          <div style={{ marginTop: 8, fontSize: 12, color: "var(--accent)" }}>
            {tags.map((t) => `#${t}`).join("　")}
          </div>
        )}
        {world.capacity && (
          <div style={{ marginTop: 6, fontSize: 12, opacity: 0.7 }}>👥 最大 {world.capacity} 人</div>
        )}
      </div>
    </a>
  );
}
