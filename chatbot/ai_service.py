import google.generativeai as genai
from django.http import JsonResponse
from django.conf import settings

# Configure Gemini with API key
genai.configure(api_key=settings.GEMINI_API_KEY)

def get_ai_response(message, language='en'):
    try:
        # Load Gemini model
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Enhanced medical context prompt
        if language == 'fr':
            prompt = f"""Vous êtes un assistant médical professionnel nommé MediAI. 
            Répondez de manière empathique, précise et utile aux questions de santé.
            Fournissez des informations médicales générales, des conseils de premiers soins,
            et recommandez de consulter un médecin pour les problèmes sérieux.
            Soyez concis mais complet. Ne posez pas de diagnostic définitif.

            Patient: {message}
            MediAI:"""
        else:
            prompt = f"""You are a professional medical assistant named MediAI.
            Respond empathetically, accurately, and helpfully to health questions.
            Provide general medical information, first aid advice,
            and recommend seeing a doctor for serious issues.
            Be concise yet thorough. Do not give definitive diagnoses.

            Patient: {message}
            MediAI:"""
        
        # Send user message
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print(f"AI service error: {e}")
        # Return None to trigger CSV fallback in calling code
        return None