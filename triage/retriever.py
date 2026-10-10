"""
Knowledge base search and context retriever.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from django.db.models import Q

from core.models import KnowledgeArticle, Client


@dataclass
class RetrievedContext:
    article: KnowledgeArticle
    source_identifier: str
    source_title: str
    source_version: str
    supporting_passage: str
    relevance_score: float


class KnowledgeRetriever:
    """Retrieves relevant policy and instructional articles from the local knowledge base."""

    def search_relevant_articles(
        self,
        query_text: str,
        category: Optional[str] = None,
        client: Optional[Client] = None,
        limit: int = 3
    ) -> List[RetrievedContext]:
        """
        Search knowledge base using keyword matching and relevance heuristics.
        Applies client-specific visibility restrictions.
        """
        if client and client.is_confidential:
            # Confidential clients bypass knowledge retrieval for external AI
            return []

        # Base query: published articles that are either global or specific to this client
        base_qs = KnowledgeArticle.objects.filter(is_published=True)
        if client:
            base_qs = base_qs.filter(Q(client_specific=client) | Q(client_specific__isnull=True))
        else:
            base_qs = base_qs.filter(client_specific__isnull=True)

        # Keyword tokenization
        tokens = [t.lower().strip() for t in query_text.replace('\n', ' ').split() if len(t.strip()) > 3]
        
        matches: List[RetrievedContext] = []

        for article in base_qs:
            score = 0.0
            art_text = f"{article.title} {article.category} {' '.join(article.tags)} {article.content}".lower()

            # Check category alignment
            if category and article.category.lower().replace(' ', '_') in category.lower():
                score += 0.4

            # Check keyword hits
            hit_count = 0
            for token in tokens:
                if token in art_text:
                    hit_count += 1
            
            if tokens:
                score += (hit_count / len(tokens)) * 0.6

            # Extract best supporting passage
            if score > 0.15:
                passage = self._extract_best_passage(article.content, tokens)
                matches.append(RetrievedContext(
                    article=article,
                    source_identifier=article.slug,
                    source_title=article.title,
                    source_version=str(article.version),
                    supporting_passage=passage,
                    relevance_score=min(round(score, 2), 1.0)
                ))

        # Sort by relevance
        matches.sort(key=lambda x: x.relevance_score, reverse=True)
        return matches[:limit]

    def _extract_best_passage(self, content: str, tokens: List[str]) -> str:
        """Extract paragraph or section containing highest concentration of query tokens."""
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        if not paragraphs:
            return content[:300]

        best_p = paragraphs[0]
        max_hits = 0

        for p in paragraphs:
            p_lower = p.lower()
            hits = sum(1 for t in tokens if t in p_lower)
            if hits > max_hits:
                max_hits = hits
                best_p = p

        return best_p[:400]
