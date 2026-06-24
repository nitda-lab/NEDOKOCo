# デプロイ手順（Vercel）

## 1. Neon (Postgres) を用意
Vercel ダッシュボード → Storage → Create Database → Neon。
発行された `DATABASE_URL` をプロジェクトの環境変数に設定。

## 2. 環境変数を設定
`.env.example` の「Web版 追加設定」をすべて Vercel の Environment Variables に登録。
`CRON_SECRET` `ADMIN_TOKEN` は十分長いランダム文字列にする。

## 3. デプロイ
リポジトリを Vercel に接続。Next.js はリポジトリ直下（`app/` `lib/` `components/` `package.json`）、
Python関数は `api/` 直下にあり、`vercel.json` で同居デプロイされる。
Vercel プロジェクトの **Root Directory は リポジトリ直下（`./`）** のままにすること。
環境変数（`DATABASE_URL` / `POSTGRES_URL` 等）は必ず **Production を含む全環境** に設定する。

## 4. 初回 VRChat ログイン
```bash
curl -X POST https://<your-app>/api/admin/vrc-login -H "Authorization: Bearer $ADMIN_TOKEN"
# => {"status":"email_otp"} ならメールに届いた6桁コードで:
curl -X POST https://<your-app>/api/admin/vrc-otp -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"code":"123456"}'
# => {"status":"ok"}
```

## 5. 収集の確認
Cron は 10 分間隔で `/api/cron/collect` を叩く。手動実行:
```bash
curl -X POST https://<your-app>/api/cron/collect -H "Authorization: Bearer $ADMIN_TOKEN"
```
`/admin`（要ログイン）で収集状況を確認。

## 6. 再認証が必要になったら
`last_status` が `auth_required` になったら手順 4 を再実行（OTP を再入力）。
通常は `twoFactorAuth` クッキーで自動再ログインされるため最長 ~30 日に 1 度程度。
