import os

from openai import OpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CHAT_MODEL = "deepseek/deepseek-v4-flash:free"

SYSTEM_PROMPT = """\
あなたはVRChatでぶい睡（VR睡眠）を楽しむボット「ねむねむbot」です。
いつも眠そうで、ゆったりとした口調で話します。
語尾に「…zzz」「〜ねむ」「〜眠い」などをつけたり、ぼんやりした返答をします。
返答は短く2〜3文程度にしてください。"""


def chat_reply(user_text: str) -> str:
    if not OPENROUTER_API_KEY:
        return "ねむ…APIキーが見つからないよ…zzz"
    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            max_tokens=256,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text or "…"},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"chat_reply error: {e}")
        return "ねむ…うまく聞こえなかったよ…zzz"
