from django.core.management.base import BaseCommand
from django.utils import timezone
from events.models import Event

class Command(BaseCommand):
    help = 'Update event types based on current date'
    
    def handle(self, *args, **options):
        today = timezone.now().date()
        updated_count = 0
        
        # Get all events
        events = Event.objects.all()
        
        for event in events:
            old_type = event.event_type
            
            # Determine new type based on date
            if event.date > today:
                new_type = 'upcoming'
            elif event.date == today:
                new_type = 'ongoing'
            else:
                new_type = 'past'
            
            # Update if changed
            if old_type != new_type:
                event.event_type = new_type
                event.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Updated "{event.title}" from {old_type} to {new_type}'
                    )
                )
        
        if updated_count == 0:
            self.stdout.write(
                self.style.SUCCESS('All events are already up to date!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {updated_count} events'
                )
            )