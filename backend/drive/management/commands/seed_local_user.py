import getpass
import sys

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from drive.models import StorageAccount, User


class Command(BaseCommand):
    help = "Create a local account without exposing its password in process arguments."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--display-name", default="")
        parser.add_argument("--password-stdin", action="store_true", help="Read one password line from stdin for automation.")
        parser.add_argument("--if-missing", action="store_true", help="Leave an existing account and its credentials unchanged.")

    def handle(self, *args, **options):
        username = options["username"]
        if User.objects.filter(username=username).exists():
            if options["if_missing"]:
                self.stdout.write(f"Local account already exists: {username}. Credentials were not changed.")
                return
            raise CommandError("That username already exists; its password was not changed.")
        if options["password_stdin"]:
            password = sys.stdin.readline().rstrip("\r\n")
        else:
            password = getpass.getpass("Choose a local password (at least 12 characters): ")
            if password != getpass.getpass("Confirm password: "):
                raise CommandError("Passwords do not match.")
        user = User(username=username, first_name=options["display_name"])
        try:
            user.full_clean(exclude=["password"])
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from None
        with transaction.atomic():
            user.set_password(password)
            user.save()
            StorageAccount.objects.create(user=user)
        self.stdout.write(self.style.SUCCESS(f"Created local account: {username}"))
