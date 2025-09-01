# chatbot/migrations/0002_add_forwarded_to_doctor.py (or similar)
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('chatbot', '0001_initial'),  # Make sure this matches your initial migration
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='forwarded_to_doctor',
            field=models.BooleanField(default=False),
        ),
    ]