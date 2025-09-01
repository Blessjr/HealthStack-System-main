from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        # Replace '0005_merge_20250828_1422' with whatever your latest chatbot migration is
        ('chatbot', '0005_merge_20250828_1422'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatsession',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]