from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("drive", "0002_file_identity_constraints")]
    operations = [migrations.AddField(model_name="upload", name="error_code", field=models.CharField(blank=True, max_length=40))]
