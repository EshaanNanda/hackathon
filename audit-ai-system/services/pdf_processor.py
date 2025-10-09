import tempfile
import os
from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from supabase_client import supabase
from config import settings

# Initialize Gemini embeddings
embeddings = None

def get_embeddings():
    global embeddings
    if embeddings is None:
        embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            task_type="retrieval_document"
        )
    return embeddings


async def process_all_pdfs():
    """Process all unprocessed PDFs from Supabase Storage"""
    embeddings = get_embeddings()
    
    # Get unprocessed documents
    response = supabase.table('audit_documents').select('*').eq('processed', False).execute()
    
    if not response.data:
        return {"message": "No PDFs to process", "processed": 0}
    
    all_chunks_text = []
    processed_count = 0
    
    for doc in response.data:
        print(f"Processing: {doc['filename']}")
        
        try:
            # Download PDF from Storage
            file_bytes = supabase.storage.from_('audit-documents').download(doc['storage_path'])
            
            # Save temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name
            
            # Load PDF
            loader = PyPDFLoader(tmp_path)
            pages = loader.load()
            
            # Split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )
            chunks = text_splitter.split_documents(pages)
            
            # Generate embeddings and store
            for idx, chunk in enumerate(chunks):
                embedding = embeddings.embed_query(chunk.page_content)
                
                supabase.table('document_chunks').insert({
                    'document_id': doc['id'],
                    'chunk_text': chunk.page_content,
                    'chunk_index': idx,
                    'embedding': embedding,
                    'metadata': chunk.metadata
                }).execute()
                
                all_chunks_text.append(chunk.page_content)
            
            # Mark as processed
            supabase.table('audit_documents').update({
                'processed': True
            }).eq('id', doc['id']).execute()
            
            processed_count += 1
            
            # Cleanup temp file
            os.unlink(tmp_path)
            
        except Exception as e:
            print(f"Error processing {doc['filename']}: {str(e)}")
            continue
    
    return {
        "message": f"Successfully processed {processed_count} PDFs",
        "processed": processed_count,
        "chunks_created": len(all_chunks_text)
    }
