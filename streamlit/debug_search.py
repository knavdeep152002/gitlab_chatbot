#!/usr/bin/env python3

from gitlab_chatbot.db.crud_helper import document_crud
from gitlab_chatbot.utils.hybrid_search import generate_rag_context, hybrid_search
from sqlalchemy import text
import ast

def debug_search():
    session = document_crud.get_sync_session()
    
    # Test 1: Check vector dimensions
    print("=== Testing Vector Dimensions ===")
    result = session.execute(text("SELECT content_vector FROM documents WHERE content_vector IS NOT NULL LIMIT 3")).fetchall()
    for i, row in enumerate(result):
        try:
            vector_list = ast.literal_eval(row[0])
            print(f"Vector {i+1} dimensions: {len(vector_list)}")
        except Exception as e:
            print(f"Error parsing vector {i+1}: {e}")
    
    # Test 2: Check if fulltext index exists
    print("\n=== Testing Fulltext Index ===")
    index_count = session.execute(text("SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'documents' AND indexname LIKE '%content_tsv%'")).scalar()
    print(f"Fulltext indexes found: {index_count}")
    
    # Test 3: Test hybrid search directly
    print("\n=== Testing Hybrid Search ===")
    try:
        matches = hybrid_search(session, "business continuity plan testing", top_k=3)
        print(f"Found {len(matches)} matches")
        for i, match in enumerate(matches):
            print(f"Match {i+1}: {match.content[:100]}...")
            print(f"Score: {match.final_score}")
    except Exception as e:
        print(f"Error in hybrid search: {e}")
    
    # Test 4: Test RAG context generation
    print("\n=== Testing RAG Context Generation ===")
    try:
        context, sources = generate_rag_context(session, "business continuity plan testing", top_k=3)
        print(f"Context length: {len(context)}")
        print(f"Sources: {sources}")
        print(f"Context preview: {context[:200]}...")
    except Exception as e:
        print(f"Error in RAG context generation: {e}")
    
    session.close()

if __name__ == "__main__":
    debug_search() 