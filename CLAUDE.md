# vrc-buisui-bot

VRChatのぶい睡ワールドを推薦するDiscord Bot。

## 技術スタック

- Python 3.11+
- py-cord 2.8（Discord slash commands）
- SQLAlchemy 2.0 + aiosqlite（async ORM、SQLite）
- vrchatapi（VRChat非公式API、ワールド検索・詳細取得）
- python-dotenv

## 設計方針

- DB操作は必ず `db/repository.py` 経由。cogからmodelを直接触らない
- `collector/` はbotプロセスと独立して動作できるよう設計する
- vrchatapi は同期ライブラリなので `asyncio.to_thread()` でラップする

## 起動方法

```
pip install -r requirements.txt
cp .env.example .env   # 各種APIキーを記入
python main.py
```

## 必要なAPIキー

- `DISCORD_BOT_TOKEN`: Discord Developer Portal で取得
- `VRC_USERNAME` / `VRC_PASSWORD`: Bot専用VRChatアカウント（2FA無効推奨）
