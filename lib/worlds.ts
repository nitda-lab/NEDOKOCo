import { sql } from "@/lib/db";

export type World = {
  world_id: string;
  name: string;
  author_name: string;
  description: string | null;
  image_url: string | null;
  tags: string | null;
  capacity: number | null;
  vrc_url: string;
  favorites: number | null;
  popularity: number | null;
  vrc_updated_at: string | null;
};

export type SortKey = "updated" | "popularity" | "favorites";

export async function getPickupWorlds(count = 6, pool = 100): Promise<World[]> {
  const { rows } = await sql<World>`
    SELECT * FROM (
      SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url,
             favorites, popularity, vrc_updated_at
      FROM worlds
      WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
      ORDER BY vrc_updated_at DESC NULLS LAST
      LIMIT ${pool}
    ) sub
    ORDER BY RANDOM()
    LIMIT ${count}
  `;
  return rows;
}

export async function getWorlds(sort: SortKey, limit: number, offset: number): Promise<World[]> {
  if (sort === "popularity") {
    const { rows } = await sql<World>`
      SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url,
             favorites, popularity, vrc_updated_at
      FROM worlds WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
      ORDER BY popularity DESC NULLS LAST LIMIT ${limit} OFFSET ${offset}`;
    return rows;
  }
  if (sort === "favorites") {
    const { rows } = await sql<World>`
      SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url,
             favorites, popularity, vrc_updated_at
      FROM worlds WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
      ORDER BY favorites DESC NULLS LAST LIMIT ${limit} OFFSET ${offset}`;
    return rows;
  }
  const { rows } = await sql<World>`
    SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url,
           favorites, popularity, vrc_updated_at
    FROM worlds WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
    ORDER BY vrc_updated_at DESC NULLS LAST LIMIT ${limit} OFFSET ${offset}`;
  return rows;
}

export function parseTags(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw) as string[];
    return arr.filter((t) => !t.startsWith("author_tag_")).slice(0, 6);
  } catch {
    return [];
  }
}

export function formatCount(n: number | null): string {
  if (n == null) return "-";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const days = Math.floor((Date.now() - then) / 86400000);
  if (days <= 0) return "今日";
  if (days < 7) return `${days}日前`;
  if (days < 30) return `${Math.floor(days / 7)}週間前`;
  if (days < 365) return `${Math.floor(days / 30)}ヶ月前`;
  return `${Math.floor(days / 365)}年前`;
}
