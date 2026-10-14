from django.core.management.base import BaseCommand

from rabbits import purge


class Command(BaseCommand):
    help = "Remove rabbits past their Recently deleted retention, and abandoned add-flow photo uploads."

    def handle(self, *args, **options):
        result = purge.run()
        self.stdout.write(f"Purged {result['rabbits']} rabbits and {result['pending photos']} pending photos.")
