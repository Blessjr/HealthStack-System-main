import csv
import random
from datetime import datetime, timedelta

patient_msgs = [
    "Hi doctor, I've been feeling unwell.",
    "I have a headache and slight fever.",
    "My stomach hurts after eating.",
    "I'm experiencing back pain.",
    "I have a rash on my arm.",
    "Can I get a prescription for my allergy?",
    "I've been coughing for 3 days.",
    "Is this medicine safe during pregnancy?",
    "I need advice on managing stress.",
    "What are the side effects of this drug?",
    "I'm feeling dizzy and tired.",
    "How often should I take this medication?",
    "My child has a fever and is vomiting.",
    "Can you recommend something for my cold?",
    "I think I might have the flu.",
    "I'm allergic to penicillin.",
    "How long will the recovery take?",
    "Is it normal to have side effects?",
    "Can I exercise while on this medication?",
    "I have trouble sleeping lately.",
    "What should I do if the pain worsens?",
    "Are there any foods I should avoid?",
    "Can I get a refill for my prescription?",
    "I'm experiencing chest pain.",
    "I have trouble breathing sometimes.",
    "My skin is itchy and swollen.",
    "How do I know if I need surgery?",
    "I want to schedule a check-up.",
    "Is this condition hereditary?",
    "Should I see a specialist?",
    "How do I manage my diabetes better?"
]

doctor_responses = [
    "How long have you had these symptoms?",
    "Have you taken any medication yet?",
    "Please describe the severity of your pain.",
    "Are you experiencing any other symptoms?",
    "You should schedule a physical exam soon.",
    "I recommend rest and plenty of fluids.",
    "Let's run some tests to be sure.",
    "Make sure to take the medicine with food.",
    "Avoid strenuous activity for the next few days.",
    "If symptoms worsen, contact me immediately.",
    "That sounds serious, please visit the ER.",
    "Take the prescribed dosage daily.",
    "Monitor your temperature and keep hydrated.",
    "We will need to do a blood test.",
    "Try to get at least 8 hours of sleep.",
    "Avoid allergens and irritants for now.",
    "I can prescribe an alternative medication.",
    "Follow up with me in one week.",
    "Use a cold compress and avoid scratching.",
    "Make sure to keep track of your symptoms."
]

num_conversations = 2000

with open('chat_data.csv', mode='w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['conversation_id', 'sender', 'message', 'timestamp'])
    
    base_time = datetime.now() - timedelta(days=365)
    
    for convo_id in range(1, num_conversations + 1):
        num_msgs = random.randint(4, 10)
        convo_start = base_time + timedelta(minutes=convo_id * 10)
        
        for i in range(num_msgs):
            sender = 'patient' if i % 2 == 0 else 'doctor'
            if sender == 'patient':
                msg = random.choice(patient_msgs)
            else:
                msg = random.choice(doctor_responses)
            
            timestamp = convo_start + timedelta(minutes=i * random.randint(1,3))
            writer.writerow([convo_id, sender, msg, timestamp.strftime('%Y-%m-%d %H:%M:%S')])
