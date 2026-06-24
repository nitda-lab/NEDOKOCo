import { sql } from "@/lib/db";

export const dynamic = "force-dynamic";

async function getStatus() {
  const total = await sql`SELECT COUNT(*)::int AS c FROM worlds`;
  const unscored = await sql`SELECT COUNT(*)::int AS c FROM worlds WHERE ai_sleep_score IS NULL`;
  const qualified = await sql`SELECT COUNT(*)::int AS c FROM worlds WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1`;
  const state = await sql`SELECT key, value FROM app_state WHERE key IN ('last_collect_at','last_status')`;
  const s: Record<string, string> = {};
  for (const r of state.rows) s[r.key as string] = r.value as string;
  return {
    total: total.rows[0].c, unscored: unscored.rows[0].c, qualified: qualified.rows[0].c,
    lastCollectAt: s["last_collect_at"] || "-", lastStatus: s["last_status"] || "-",
  };
}

export default async function Admin() {
  const st = await getStatus();
  return (
    <main style={{ maxWidth: 700, margin: "0 auto", padding: 24 }}>
      <h1 style={{ color: "var(--accent)" }}>管理画面</h1>
      <ul>
        <li>総ワールド数: {st.total}</li>
        <li>未採点: {st.unscored}</li>
        <li>提案対象(qualified): {st.qualified}</li>
        <li>最終収集: {st.lastCollectAt}</li>
        <li>最終ステータス: {st.lastStatus}</li>
      </ul>
      <p style={{ opacity: 0.7, fontSize: 13 }}>
        収集の手動実行・VRChat ログイン/OTP は Python 関数
        <code> /api/cron/collect</code> ・ <code>/api/admin/vrc-login</code> ・ <code>/api/admin/vrc-otp</code>
        を <code>ADMIN_TOKEN</code> 付きで呼び出してください（README 参照）。
      </p>
    </main>
  );
}
