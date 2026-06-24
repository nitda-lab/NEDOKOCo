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
};

export async function getSuggestedWorlds(count = 5): Promise<World[]> {
  const { rows } = await sql<World>`
    SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url
    FROM worlds
    WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
    ORDER BY RANDOM()
    LIMIT ${count}
  `;
  return rows;
}

export async function getQualifiedWorlds(limit: number, offset: number): Promise<World[]> {
  const { rows } = await sql<World>`
    SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url
    FROM worlds
    WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
    ORDER BY fetched_at DESC NULLS LAST
    LIMIT ${limit} OFFSET ${offset}
  `;
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
