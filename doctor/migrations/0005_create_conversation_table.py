from django.db import migrations, models
from django.conf import settings  # to reference the User model

class Migration(migrations.Migration):

    initial = True  # Marks this as the initial creation for this model

    dependencies = [
        ('doctor', '0004_create_chatmessage_table'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),  # ensure User model exists
    ]

    operations = [
        migrations.CreateModel(
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('patient', models.ForeignKey(
                    on_delete=models.CASCADE,
                    related_name='doctor_conversations',
                    to=settings.AUTH_USER_MODEL
                )),
                ('doctor', models.ForeignKey(
                    on_delete=models.SET_NULL,
                    null=True,
                    blank=True,
                    related_name='doctor_chats',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'doctor_conversation',
            },
        ),
    ]
