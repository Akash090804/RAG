import logging
import os
from typing import List, Dict, Any
from datetime import datetime

from app.services.search import HybridSearcher
from app.services.extractor import extract_text_from_content
import google.generativeai as genai

logger = logging.getLogger(__name__)

class DocumentStore:
    def __init__(self):
        self.searcher = HybridSearcher()
        self.document_metadata = {}

    def add_document(self, content: str, metadata: Dict[str, Any]):
        """Add a document to the store with metadata"""
        doc_id = len(self.document_metadata)
        self.document_metadata[doc_id] = {
            **metadata,
            'added_at': datetime.now().isoformat(),
            'doc_id': doc_id
        }
        self.searcher.add_documents([content], [self.document_metadata[doc_id]])

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search documents using hybrid search"""
        results = self.searcher.hybrid_search(query, k=k)
        return [
            {
                'content': r.content,
                'score': r.score,
                'metadata': r.metadata
            }
            for r in results
        ]

class EnhancedRAG:
    def __init__(self, api_key: str):
        self.doc_store = DocumentStore()
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('models/gemini-2.0-flash-001')
        
        # Set up generation config
        self.generation_config = {
            "temperature": 0.3,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 4096,
        }

    def add_document(self, content: str, source: str, doc_type: str, additional_metadata: Dict[str, Any] = None):
        """Add a document to the RAG system"""
        metadata = {
            'source': source,
            'doc_type': doc_type,
            'added_at': datetime.now().isoformat(),
            **(additional_metadata or {})
        }
        self.doc_store.add_document(content, metadata)

    def process_file(self, content: bytes, filename: str, file_type: str):
        """Process a file and add it to the system"""
        try:
            # Extract text from file
            text = extract_text_from_content(content, filename)
            
            # Add to document store
            self.add_document(
                content=text,
                source=filename,
                doc_type=file_type,
                additional_metadata={'file_type': file_type}
            )
            return True
        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")
            return False

    def answer_question(self, question: str, max_context: int = 5) -> Dict[str, Any]:
        """Answer a question using RAG with enhanced context"""
        try:
            # Search for relevant context
            search_results = self.doc_store.search(question, k=max_context)
            
            if not search_results:
                return {
                    'answer': "I could not find any relevant information to answer your question.",
                    'sources': [],
                    'confidence': 0.0
                }

            # Prepare context with source information
            context_parts = []
            sources = []
            
            for result in search_results:
                context_parts.append(f"[Source: {result['metadata'].get('source', 'Unknown')}]\n{result['content']}")
                sources.append({
                    'source': result['metadata'].get('source', 'Unknown'),
                    'doc_type': result['metadata'].get('doc_type', 'Unknown'),
                    'relevance_score': result['score']
                })

            # Create enhanced prompt
            prompt = (
                "You are a knowledgeable assistant tasked with answering questions based on the provided sources. "
                "Please provide detailed, accurate answers while citing your sources.\n\n"
                "Instructions:\n"
                "1. Answer comprehensively using information from ALL relevant sources\n"
                "2. If sources contain conflicting information, acknowledge this\n"
                "3. If the answer requires combining information from multiple sources, explain how they connect\n"
                "4. If the answer is not in the sources, clearly state this\n"
                "5. Maintain academic rigor in your response\n\n"
                "Sources:\n"
                f"{'-' * 80}\n"
                f"{chr(10).join(context_parts)}\n"
                f"{'-' * 80}\n\n"
                f"Question: {question}\n\n"
                "Please provide a detailed answer with source citations:"
            )

            # Generate response
            response = self.model.generate_content(prompt)
            
            if response and hasattr(response, 'text'):
                # Clean up the response
                answer = response.text
                # Remove markdown symbols
                answer = answer.replace('**', '')
                answer = answer.replace('*', '')
                # Fix newlines and spaces
                answer = answer.replace('\\n', ' ')
                answer = answer.replace('\n', ' ')
                # Remove multiple spaces
                answer = ' '.join(answer.split())
                # Fix common formatting issues
                answer = answer.replace(' .', '.')
                answer = answer.replace(' ,', ',')
                answer = answer.replace('( ', '(')
                answer = answer.replace(' )', ')')
                # Add proper sentence spacing
                answer = answer.replace('.', '. ').replace('  ', ' ')
            else:
                answer = "Could not generate an answer from the available information."

            return {
                'answer': answer,
                'sources': sources,
                'confidence': sum(s['relevance_score'] for s in sources) / len(sources)
            }

        except Exception as e:
            logger.error(f"Error in RAG pipeline: {e}", exc_info=True)
            return {
                'answer': f"An error occurred while processing your question: {str(e)}",
                'sources': [],
                'confidence': 0.0
            }