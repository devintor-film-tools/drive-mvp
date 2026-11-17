"""Enforce ownership and attempt identity across rows, including non-ORM writes."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("drive", "0001_initial")]
    operations = [migrations.RunSQL(
        sql="""
            ALTER TABLE drive_file ADD CONSTRAINT file_owner_matches_upload
            FOREIGN KEY (upload_id, owner_id) REFERENCES drive_upload (id, owner_id)
            DEFERRABLE INITIALLY IMMEDIATE;
            ALTER TABLE drive_file ADD CONSTRAINT file_attempt_matches_upload
            FOREIGN KEY (successful_attempt_id, upload_id) REFERENCES drive_uploadattempt (id, upload_id)
            DEFERRABLE INITIALLY IMMEDIATE;
        """,
        reverse_sql="""
            ALTER TABLE drive_file DROP CONSTRAINT file_attempt_matches_upload;
            ALTER TABLE drive_file DROP CONSTRAINT file_owner_matches_upload;
        """,
    )]
