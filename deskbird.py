import requests
import json
from datetime import datetime, timedelta
import time

def load_config(config_path='config.json'):
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise Exception(f"Config file not found at {config_path}")

def authenticate(email, password, app_key):
    """Get authentication token."""
    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={app_key}'
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json",
        "origin": "https://app.deskbird.com",
    }
    payload = {
        "returnSecureToken": True,
        "email": email,
        "password": password,
        "clientType": "CLIENT_TYPE_WEB",
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Authentication failed: {response.text}")
    
    return response.json()['idToken']

def book_seat(bearer_token, seat_info, booking_date, workspace_id):
    """Book a seat for a specific date."""
    # Convert date to timestamps (9:00 to 19:00)
    booking_date = datetime.strptime(booking_date, '%Y-%m-%d')
    start_time = int(booking_date.replace(hour=9).timestamp() * 1000)
    end_time = int(booking_date.replace(hour=19).timestamp() * 1000)

    url = "https://api.deskbird.com/v1.1/bookings"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "authorization": f"Bearer {bearer_token}",
        "content-type": "application/json",
        "origin": "https://app.deskbird.com",
    }

    payload = {
        "bookings": [{
            "bookingStartTime": start_time,
            "bookingEndTime": end_time,
            "isAnonymous": False,
            "resourceId": seat_info['resource_id'],
            "zoneItemId": seat_info['zone_item_id'],
            "workspaceId": workspace_id,
        }]
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Booking failed: {response.text}")
    
    return response.json()

def get_user_bookings(bearer_token):
    """Get user's upcoming bookings."""
    url = "https://api.deskbird.com/v1.1/user/bookings"
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "authorization": f"Bearer {bearer_token}",
        "origin": "https://app.deskbird.com"
    }
    
    # Query parameters
    params = {
        "skip": 0,
        "limit": 20,
        "includeInstances": "true",
        "upcoming": "true"
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Failed to get bookings: {response.text}")
    
    return response.json()

def display_booking_summary(bookings_data):
    """Display a clean summary of upcoming bookings."""
    total_count = bookings_data['totalCount']
    results = bookings_data['results']
    
    print(f"\nYou have {total_count} upcoming booking(s):")
    
    for booking in results:
        # Convert timestamps to readable dates
        start_time = datetime.fromtimestamp(booking['bookingStartTime']/1000)
        date_str = start_time.strftime('%A, %B %d, %Y')
        time_str = start_time.strftime('%H:%M')
        
        # Get seat information
        seat_name = booking['zoneItemName']
        zone_name = booking['zone']['name']
        resource_id = booking['resourceId']
        zone_item_id = booking['zoneItemId']
        
        print(f"- {date_str} starting at {time_str}: {seat_name} ({zone_name})")
        print(f"  Resource ID: {resource_id}, Zone Item ID: {zone_item_id}")

def check_in_booking(bearer_token, booking_id, zone_item_id):
    """Check-in a booking for today's booking using its bookingId and zoneItemId."""
    url = f"https://api.deskbird.com/v1.1/bookings/{booking_id}/check-in"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "authorization": f"Bearer {bearer_token}",
        "content-type": "application/json",
        "origin": "https://app.deskbird.com",
    }

    payload = {
        "qrCodeZoneItemId": zone_item_id
    }

    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"Check-in failed: {response.text}")
    
    return response.json()

def get_next_occurrence(target_weekday, max_days=10):
    """Get the date of the next occurrence of a given weekday within max_days from now.
    target_weekday: int (0=Monday, ..., 6=Sunday)
    Returns: date string in YYYY-MM-DD format or None if not found within max_days.
    """
    today = datetime.now().date()
    today_weekday = today.weekday() # Monday=0, Tuesday=1, etc.
    
    # Calculate how many days until next target_weekday
    if target_weekday <= today_weekday:
        days_ahead = target_weekday + 7 - today_weekday
    else:
        days_ahead = target_weekday - today_weekday

    # If days_ahead is 0, it means it's today - we want a future occurrence, not today.
    # Also ensure days_ahead <= max_days
    if days_ahead == 0 or days_ahead > max_days:
        return None

    next_date = today + timedelta(days=days_ahead)
    return next_date.strftime('%Y-%m-%d')

def get_upcoming_occurrences(target_weekday, max_days=10):
    """Get all occurrences of a given weekday within max_days from today.
    
    target_weekday: int (0=Monday, ..., 6=Sunday)
    max_days: int (how far to look ahead)
    
    Returns: List of date strings in YYYY-MM-DD format.
    """
    today = datetime.now().date()
    occurrences = []

    for days_ahead in range(1, max_days + 1):  # Start from tomorrow
        next_date = today + timedelta(days=days_ahead)
        if next_date.weekday() == target_weekday:
            occurrences.append(next_date.strftime('%Y-%m-%d'))

    return occurrences  # List of all matching dates within range

def main():
    try:
        # Load configuration
        config = load_config('config.json')
        # target_date = (datetime.now() + timedelta(days=6)).strftime('%Y-%m-%d')
        
        # Authenticate
        bearer_token = authenticate(
            config['credentials']['email'],
            config['credentials']['password'],
            config['credentials']['app_key']
        )

        weekdays_map = {
            "Mon": 0,
            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6
        }
        target_days = config.get('target_days', [])
        exclude_dates = set(config.get('exclude_dates', []))
        
        for day_str in target_days:
            if day_str not in weekdays_map:
                print(f"Unknown day '{day_str}' in target_days.")
                continue

            target_wd = weekdays_map[day_str]
            

            """
            target_date = get_next_occurrence(target_wd, max_days=11)
            if target_date is None:
                print(f"No suitable upcoming {day_str} within 6 days found. Skipping.")
                continue
            """
            target_dates = get_upcoming_occurrences(target_wd, max_days=10)
            if not target_dates:
                print(f"No suitable upcoming {day_str} within 11 days found. Skipping.")
                continue
            for target_date in target_dates:
                if target_date in exclude_dates:
                    print(f"Skipping {target_date} (excluded)")
                    continue
                # Book seat
                for seat in config['favorite_seats']: # We loop through all available seats in order 
                    result = book_seat(
                        bearer_token,
                        config['favorite_seats'][seat], # seat info
                        target_date,
                        config['workspace_id']
                    )
                    if result['successfulBookings'] == []:
                        print(f'Booking {seat} has failed for {target_date}, moving on to the next favoured seat')
                        time.sleep(0.2)
                    else: 
                        print(f"Successfully booked seat {seat} for {target_date}")
                        # print("Booking details:", json.dumps(result, indent=2))
                        break # we don't try to book further seats

        # Get user's bookings
        bookings = get_user_bookings(bearer_token)
        display_booking_summary(bookings)

        # Check-in today's bookings if any
        today = datetime.now().date()
        for booking in bookings['results']:
            start_time = datetime.fromtimestamp(booking['bookingStartTime']/1000)
            booking_date = start_time.date()
            if booking_date == today:
                if booking['checkInStatus'] == 'checkedIn':
                    print('Booking for today is already checked-in, not trying')
                    continue
                print(f'One booking found for today, checking-in')
                booking_id = booking['id']    # should look like 15621063
                zone_item_id = booking['zoneItemId'] # should look like 731088
                try:
                    check_in_response = check_in_booking(bearer_token, booking_id, zone_item_id)
                    print(f"Successfully checked in booking {booking_id} for today")
                    print(f"{check_in_response}")
                except Exception as e:
                    print(f"Error during check-in of booking {booking_id}: {str(e)}")                
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()
