# test_gemini_django.py
import os
import django
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# Set the correct settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'healthstack.settings')  # ← CHANGE TO YOUR ACTUAL PROJECT NAME

try:
    django.setup()
    print("✅ Django setup successful")
    
    from chatbot.ai_service import get_ai_response
    
    # Test the function
    response = get_ai_response("What is a common headache remedy?", "en")
    print(f"✅ Gemini response: {response}")
    
except Exception as e:
    print(f"❌ Error: {e}")