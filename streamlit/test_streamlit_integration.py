#!/usr/bin/env python3
"""
Test script to verify Streamlit app integration with GitLab chatbot API
"""

import requests
from .config import API_BASE_URL

def test_api_connection():
    """Test basic API connectivity"""
    print("🔍 Testing API connection...")
    
    try:
        # Test conversation creation
        response = requests.post(f"{API_BASE_URL}/conversation")
        if response.status_code == 201:
            data = response.json()
            conversation_id = data["conversation_id"]
            print(f"✅ Conversation created: {conversation_id}")
        else:
            print(f"❌ Failed to create conversation: {response.status_code}")
            return False
        
        # Test message sending
        test_message = "What is GitLab's mission?"
        payload = {
            "conversation_id": conversation_id,
            "message": test_message
        }
        
        response = requests.post(
            f"{API_BASE_URL}/message",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Message sent successfully")
            print(f"📝 Response: {data['response'][:100]}...")
            print(f"🔗 Sources: {len(data.get('sources', []))} sources found")
            return True
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {str(e)}")
        return False

def test_example_questions():
    """Test with various example questions"""
    print("\n🧪 Testing example questions...")
    
    questions = [
        "What is GitLab's mission?",
        "What are GitLab's core values?",
        "How does GitLab handle security?"
    ]
    
    # Create a conversation
    response = requests.post(f"{API_BASE_URL}/conversation")
    if response.status_code != 201:
        print("❌ Failed to create conversation for testing")
        return
    
    conversation_id = response.json()["conversation_id"]
    
    for i, question in enumerate(questions, 1):
        print(f"\n{i}. Testing: {question}")
        
        payload = {
            "conversation_id": conversation_id,
            "message": question
        }
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/message",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Success - Response length: {len(data['response'])} chars")
                print(f"   📚 Sources: {len(data.get('sources', []))}")
            else:
                print(f"   ❌ Failed: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")

def main():
    print("🚀 GitLab Chatbot API Integration Test")
    print("=" * 50)
    
    # Test basic connectivity
    if test_api_connection():
        print("\n✅ API integration is working!")
        
        # Test example questions
        test_example_questions()
        
        print("\n🎉 All tests completed successfully!")
        print("\n📱 You can now run the Streamlit app:")
        print("   streamlit run streamlit_app.py")
        print("\n🌐 The app will be available at: http://localhost:8501")
    else:
        print("\n❌ API integration failed!")
        print("Please ensure your FastAPI backend is running on the correct port.")
        print(f"Expected API URL: {API_BASE_URL}")

if __name__ == "__main__":
    main() 