from django.core.management.base import BaseCommand
from django.utils import timezone
from events.models import Event
import pytz

class Command(BaseCommand):
    help = 'Update event types and registration status using Nepal timezone (Asia/Kathmandu)'
    
    def handle(self, *args, **options):
        # Nepal timezone
        nepal_tz = pytz.timezone('Asia/Kathmandu')
        nepal_now = timezone.now().astimezone(nepal_tz)
        nepal_today = nepal_now.date()
        
        self.stdout.write(f'🇳🇵 Current Nepal time: {nepal_now.strftime("%Y-%m-%d %H:%M:%S %Z")}')
        self.stdout.write(f'🇳🇵 Nepal date: {nepal_today}')
        
        events = Event.objects.all()
        updated_count = 0
        
        for event in events:
            old_type = event.event_type
            old_reg_status = event.registration_status
            
            # Manually set correct event type using Nepal date
            if event.date > nepal_today:
                event.event_type = 'upcoming'
            elif event.date == nepal_today:
                event.event_type = 'ongoing'
            else:
                event.event_type = 'past'
            
            # Recalculate registration status using Nepal time
            event.registration_status = event.calculate_registration_status()
            
            # Save if changed
            if old_type != event.event_type or old_reg_status != event.registration_status:
                event.save()
                updated_count += 1
                self.stdout.write(
                    f"✅ Updated '{event.title}': {old_type} → {event.event_type} | Reg: {old_reg_status} → {event.registration_status}"
                )
            else:
                self.stdout.write(
                    f"ℹ️ '{event.title}' already correct: {event.event_type} | Reg: {event.registration_status}"
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'🇳🇵 Successfully updated {updated_count} events using Nepal timezone!')
        )