import json
import numpy as np
import os
import ast

# ------------------------
# Tips読み込み
# ------------------------
def load_tips_json(path="tips_db.json"):
    base_dir = os.path.dirname(__file__)  # tips_engine.pyの場所
    file_path = os.path.join(base_dir, path)

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------
# コサイン類似度
# ------------------------
def to_vector(v):
    if isinstance(v, str):
        v = ast.literal_eval(v)
    return np.array(v, dtype=float)

def cosine_similarity(vec1, vec2):
    vec1 = to_vector(vec1)
    vec2 = to_vector(vec2)

    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

# ------------------------
# 最適なTips取得
# ------------------------
def get_best_tip(page_embedding, tips_data):
    best_score = -1
    best_tip = None

    for tip in tips_data:
        tip_embedding = tip["embedding"]

        score = cosine_similarity(page_embedding, tip_embedding)

        if score > best_score:
            best_score = score
            best_tip = tip

    return best_tip, best_score
