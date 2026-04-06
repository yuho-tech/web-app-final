"""
ranking_ai.py — Tech0 Search v3.0
OpenAI埋め込みベースの文脈理解型検索
"""

import numpy as np
from typing import List
from datetime import datetime
import os
import json
from openai_client import get_embedding

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """コサイン類似度"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)


class SearchEngineAI:
    """OpenAI 埋め込みベースの検索エンジン"""

    def __init__(self):
        self.pages = []
        self.embeddings = []  # ページ埋め込みを保持

    def build_index(self, pages: list):
        self.pages = []
        self.embeddings = []

        for p in pages:
            if p.get("embedding"):
                emb = np.array(json.loads(p["embedding"]), dtype=np.float32)

                # 👇 ここだけ追加（整合性維持のため）
                self.pages.append(p)
                self.embeddings.append(emb)

            else:
                # ❌ fallback禁止（API呼ばない）
                continue

        if self.embeddings:
            self.embeddings = np.array(self.embeddings)
        else:
            self.embeddings = np.array([])



    def search(self, query: str, top_n: int = 20) -> list:
        """検索を実行"""
        if not self.pages or not query.strip():
            return []

        query_emb = get_embedding(query)
        sims = [cosine_sim(query_emb, e) for e in self.embeddings]

        results = []
        for idx, base_score in enumerate(sims):
            if base_score > 0.01:
                page = self.pages[idx].copy()
                final_score = self._calculate_final_score(page, base_score, query)
                page["relevance_score"] = round(float(final_score) * 100, 1)
                page["base_score"] = round(float(base_score) * 100, 1)
                results.append(page)

        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_n]

    def _calculate_final_score(self, page: dict, base_score: float, query: str) -> float:
        """従来のボーナスロジックをそのまま利用"""
        score = base_score
        query_lower = query.lower()

        # タイトルマッチボーナス
        title = page.get("title", "").lower()
        if query_lower == title:
            score *= 1.8
        elif query_lower in title:
            score *= 1.4

        # キーワードマッチボーナス
        keywords = page.get("keywords", [])
        if isinstance(keywords, str):
            keywords = keywords.split(",")
        keywords_lower = [k.strip().lower() for k in keywords]
        if query_lower in keywords_lower:
            score *= 1.3

        # 新鮮度ボーナス（90日以内）
        crawled_at = page.get("crawled_at", "")
        if crawled_at:
            try:
                crawled = datetime.fromisoformat(crawled_at.replace("Z", "+00:00"))
                days_old = (datetime.now() - crawled.replace(tzinfo=None)).days
                if days_old <= 90:
                    recency_bonus = 1 + (0.2 * (90 - days_old) / 90)
                    score *= recency_bonus
            except Exception:
                pass

        return score


# ── シングルトン ─────────────────────────
_engine = None


def get_engine() -> SearchEngineAI:
    global _engine
    if _engine is None:
        _engine = SearchEngineAI()
    return _engine


def rebuild_index(pages: List[dict]):
    engine = get_engine()
    engine.build_index(pages)
