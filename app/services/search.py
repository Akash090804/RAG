import numpy as np
from typing import List, Dict, Any, Tuple
import logging
from collections import defaultdict
import faiss
from langchain_huggingface import HuggingFaceEmbeddings
from functools import lru_cache
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SearchResult:
    def __init__(self, content: str, score: float, metadata: Dict[str, Any] = None):
        self.content = content
        self.score = score
        self.metadata = metadata or {}

class HybridSearcher:
    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
        self.index = None
        self.documents = []
        self.document_metadata = []
        self.cache = {}
        self.cache_ttl = timedelta(hours=24)

    @lru_cache(maxsize=1000)
    def get_embedding(self, text: str) -> np.ndarray:
        """Cache embeddings for better performance"""
        return self.embeddings.embed_query(text)

    def add_documents(self, documents: List[str], metadata: List[Dict[str, Any]] = None):
        """Add documents to the search index"""
        if not documents:
            return

        if metadata is None:
            metadata = [{}] * len(documents)

        # Get embeddings for all documents
        embeddings = [self.get_embedding(doc) for doc in documents]
        embeddings_matrix = np.vstack(embeddings)

        # Initialize or update FAISS index
        if self.index is None:
            self.index = faiss.IndexFlatL2(embeddings_matrix.shape[1])
        
        self.index.add(embeddings_matrix.astype('float32'))
        self.documents.extend(documents)
        self.document_metadata.extend(metadata)

    def semantic_search(self, query: str, k: int = 5) -> List[SearchResult]:
        """Perform semantic search using embeddings"""
        if not self.index:
            return []

        query_embedding = self.get_embedding(query)
        D, I = self.index.search(np.array([query_embedding]).astype('float32'), k)
        
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < len(self.documents):
                results.append(SearchResult(
                    content=self.documents[idx],
                    score=1.0 / (1.0 + score),  # Convert distance to similarity score
                    metadata=self.document_metadata[idx]
                ))
        return results

    def lexical_search(self, query: str, documents: List[str], k: int = 5) -> List[SearchResult]:
        """Perform keyword-based search"""
        # Tokenize query and documents
        query_terms = set(self._tokenize(query.lower()))
        
        results = []
        for idx, doc in enumerate(documents):
            doc_terms = set(self._tokenize(doc.lower()))
            
            # Calculate TF-IDF-like score
            overlap = len(query_terms & doc_terms)
            if overlap > 0:
                # Score based on term overlap and document length
                score = overlap / (len(query_terms) * np.log(1 + len(doc_terms)))
                results.append(SearchResult(
                    content=doc,
                    score=score,
                    metadata=self.document_metadata[idx] if idx < len(self.document_metadata) else {}
                ))
        
        return sorted(results, key=lambda x: x.score, reverse=True)[:k]

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for lexical search"""
        return re.findall(r'\w+', text)

    def hybrid_search(self, query: str, k: int = 5) -> List[SearchResult]:
        """Combine semantic and lexical search using RRF"""
        cache_key = f"{query}_{k}"
        
        # Check cache
        if cache_key in self.cache:
            cache_time, results = self.cache[cache_key]
            if datetime.now() - cache_time < self.cache_ttl:
                return results

        # Perform both types of search
        semantic_results = self.semantic_search(query, k=k)
        lexical_results = self.lexical_search(query, self.documents, k=k)

        # Combine results using RRF
        all_results = {}
        
        # Process semantic results
        for rank, result in enumerate(semantic_results):
            rrf_score = 1 / (rank + 60)  # RRF constant of 60
            all_results[result.content] = {
                'score': rrf_score,
                'metadata': result.metadata
            }

        # Process lexical results
        for rank, result in enumerate(lexical_results):
            content = result.content
            if content in all_results:
                all_results[content]['score'] += 1 / (rank + 60)
            else:
                all_results[content] = {
                    'score': 1 / (rank + 60),
                    'metadata': result.metadata
                }

        # Create final ranked results
        final_results = [
            SearchResult(
                content=content,
                score=data['score'],
                metadata=data['metadata']
            )
            for content, data in all_results.items()
        ]
        
        # Sort by combined score
        final_results.sort(key=lambda x: x.score, reverse=True)
        final_results = final_results[:k]

        # Cache results
        self.cache[cache_key] = (datetime.now(), final_results)
        
        return final_results

    def clear_cache(self):
        """Clear the search cache"""
        self.cache.clear()
        self.get_embedding.cache_clear()