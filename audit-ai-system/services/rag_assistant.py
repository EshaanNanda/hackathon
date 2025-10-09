from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from supabase_client import supabase
from config import settings

# Global instances
embeddings = None
llm = None
vector_store = None
qa_chain = None


def get_embeddings():
    """Initialize embeddings (lazy loading)"""
    global embeddings
    if embeddings is None:
        embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY
        )
    return embeddings


def get_llm():
    """Initialize LLM (lazy loading)"""
    global llm
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",  # Use from settings (gemini-1.5-flash)
            temperature=0.3,
            google_api_key=settings.GOOGLE_API_KEY
        )
    return llm


def get_vector_store():
    """Initialize vector store (lazy loading)"""
    global vector_store
    if vector_store is None:
        emb = get_embeddings()
        vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=emb,
            table_name="document_chunks",
            query_name="match_document"
        )
    return vector_store


def get_qa_chain():
    """Initialize QA chain (lazy loading)"""
    global qa_chain
    if qa_chain is None:
        model = get_llm()
        store = get_vector_store()
        
        prompt_template = """You are an expert audit analyst assistant. Use the following audit document excerpts to answer the question accurately.

IMPORTANT: If asked about an "overall compliance score" and you see individual compliance percentages (like SOX 89%, ISO 94%), you can mention those but clarify they are individual metrics, not an overall score.

If the answer is not in the provided context, clearly state that you don't have that information.

Context:
{context}

Question: {question}

Answer:"""

        
        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        # Create QA chain with simple retriever
        qa_chain = RetrievalQA.from_chain_type(
            llm=model,
            chain_type="stuff",
            retriever=store.as_retriever(
                search_kwargs={"k": 5}  # FIXED: Removed match_count
            ),
            return_source_documents=False,
            chain_type_kwargs={"prompt": PROMPT}
        )
    return qa_chain


async def ask_question(question: str):
    """Answer questions using RAG from audit documents"""
    try:
        print(f"Processing question: {question}")
        
        # Get or initialize the QA chain
        chain = get_qa_chain()
        
        print("Querying documents...")
        
        # Run the query
        response = chain.invoke({"query": question})
        
        print(f"Generated answer: {response['result'][:100]}...")
        
        return {
            "question": question,
            "answer": response['result']
        }
        
    except Exception as e:
        print(f"Error processing question: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "question": question,
            "answer": f"Sorry, I encountered an error while processing your question. Please try rephrasing or ask something else."
        }
