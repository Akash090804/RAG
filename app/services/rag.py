import logging
import os
from dotenv import load_dotenv

from app.services.extractor import fetch_content, extract_text_from_content

# --- LangChain Imports for a Full RAG Pipeline ---
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage


load_dotenv()

# --- 1. LLM CONFIGURATION (Points to the HackRx Endpoint) ---
hackrx_api_key = os.getenv("HACKRX_API_KEY")
if not hackrx_api_key:
    raise ValueError("HACKRX_API_KEY not found in .env file. Please add it.")

llm = ChatOpenAI(
    model="gpt-5-nano",
    api_key=hackrx_api_key,
    base_url="https://register.hackrx.in/llm/openai",
    default_headers={"x-subscription-key": hackrx_api_key}
)

# --- 2. EMBEDDING MODEL CONFIGURATION ---
# We use a popular, lightweight, and effective model from Hugging Face
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# --- 3. RAG PROMPT TEMPLATE ---
# This defines how we'll instruct the LLM
prompt = ChatPromptTemplate.from_template("""
Answer the following question based only on the provided context.
If the answer is not in the context, state that you could not find the answer.

<context>
{context}
</context>

Question: {input}
""")

logger = logging.getLogger(__name__)


def answer_generic_question(url: str, question: str) -> str:
    """
    Handles a generic question about a URL using a full, production-grade RAG pipeline.
    """
    try:
        logger.info(f"Initiating full RAG pipeline for question: '{question}' on URL: {url}")
        
        # --- Step I: FETCH AND EXTRACT (The "Retrieval" part of RAG) ---
        content_bytes = fetch_content(url)
        context_text = extract_text_from_content(content_bytes, url)
        
        # --- Step II: CHUNK (Split the document into smaller pieces) ---
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        docs = text_splitter.split_text(context_text)
        logger.info(f"Split document into {len(docs)} chunks.")
        
       
        vector_store = FAISS.from_texts(docs, embedding=embeddings)
        logger.info("Created in-memory FAISS vector store.")
        
        # --- Step IV: CREATE THE RAG CHAIN ---
        # This chain combines all the components into a single, runnable object
        
        # This part creates a retriever that finds and returns relevant documents
        retriever = vector_store.as_retriever()
        
        # This part chains the prompt and the LLM to process the retrieved documents
        question_answer_chain = create_stuff_documents_chain(llm, prompt)
        
        # This is the final chain that ties retrieval and generation together
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)
        
        # --- Step V: INVOKE THE CHAIN (The "Generation" part of RAG) ---
        logger.info("Invoking the RAG chain...")
        response = rag_chain.invoke({"input": question})
        
        answer = response.get("answer", "No answer could be generated.")
        logger.info(f"RAG chain generated answer: '{answer}'")
        return answer
        
    except Exception as e:
        logger.error(f"Error in the full RAG pipeline for URL {url}: {e}", exc_info=True)
        return f"An error occurred during the RAG process: {e}"