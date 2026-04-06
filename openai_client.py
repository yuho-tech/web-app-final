from dotenv import load_dotenv
from openai import OpenAI
import numpy as np

load_dotenv()

client = OpenAI()

def get_embedding(text: str, model: str = "text-embedding-3-small") -> np.ndarray:
    """
    テキストをembeddingに変換してnumpy配列で返す
    ranking_AI.pyと完全互換
    """
    # 改行除去（API安定化）
    text = text.replace("\n", " ")

    resp = client.embeddings.create(
        input=text,
        model=model
    )

    # float32で統一（メモリ＆速度最適化）
    return np.array(resp.data[0].embedding, dtype=np.float32)
