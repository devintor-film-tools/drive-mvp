from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("drive", "0003_upload_error_code")]
    operations = [
        migrations.AddField(model_name="file", name="trashed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="file", name="revision", field=models.PositiveBigIntegerField(default=1)),
    ]
