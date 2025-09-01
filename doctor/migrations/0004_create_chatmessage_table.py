from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0003_rename_doctorchatmessage_chatmessage_and_more'),  # replace with last migration filename
    ]

    operations = [
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender', models.CharField(choices=[('patient','Patient'),('doctor','Doctor'),('bot','Bot')], max_length=10)),
                ('message', models.TextField()),
                ('language', models.CharField(choices=[('en','English'),('fr','French')], default='en', max_length=10)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='doctor.conversation')),
            ],
            options={
                'db_table': 'doctor_chatmessage',
                'ordering': ('timestamp',),
            },
        ),
    ]
