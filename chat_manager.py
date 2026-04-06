from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI()


def refine_query(chat_history: list) -> str:
    try:
        messages = [{
            "role": "system",
            "content": "ユーザーの会話から検索用クエリを1文で生成。説明禁止。"
        }]

        for role, msg in chat_history:

            #role変換
            if role == "ai":
                role = "assistant"
            elif role != "user":
                role = "user"

            messages.append({
                "role": role,
                "content": str(msg)
            })

        response = client.responses.create(
            model="gpt-4o-mini",
            input=messages,
            temperature=0.2
        )


        return response.output[0].content[0].text.strip()

    except Exception as e:
        print("🔥 OpenAI ERROR:", e)
        return "検索クエリ生成失敗"
