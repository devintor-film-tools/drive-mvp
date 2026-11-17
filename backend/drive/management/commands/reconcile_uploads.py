from django.core.management.base import BaseCommand

from drive.models import User
from drive.services import clean_orphans, reconcile_user


class Command(BaseCommand):
    help = "Fence expired attempts and optionally collect tracked unreferenced blobs."

    def add_arguments(self, parser):
        parser.add_argument("--cleanup", action="store_true", help="Remove orphan blobs from failed attempts older than the grace period.")

    def handle(self, *args, **options):
        changed = sum(reconcile_user(user) for user in User.objects.iterator())
        removed = clean_orphans() if options["cleanup"] else 0
        self.stdout.write(f"Reconciled {changed} uploads; processed {removed} orphan attempts.")
