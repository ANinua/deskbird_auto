import os
import time
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dateutil import parser as dateparser
from deskbird import (
    authenticate,
    book_seat,
    get_user_bookings,
    check_in_booking,
    get_upcoming_occurrences
)

app = FastAPI(title="Deskbird Auto API")

EMAIL = os.environ.get("DESKBIRD_EMAIL")
PASSWORD = os.environ.get("DESKBIRD_PASSWORD")
APP_KEY = os.environ.get("DESKBIRD_APP_KEY")


class SeatInfo(BaseModel):
    resource_id: str
    zone_item_id: int


class RunRequest(BaseModel):
    workspace_id: str
    favorite_seats: dict[str, SeatInfo]
    target_days: list[str]
    exclude_dates: list[str] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run(req: RunRequest):
    if not all([EMAIL, PASSWORD, APP_KEY]):
        raise HTTPException(500, "Missing credentials in environment")

    # Authenticate
    token = authenticate(EMAIL, PASSWORD, APP_KEY)

    weekdays_map = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    bookings_made = []
    bookings_failed = []
    bookings_skipped = []

    def to_yyyy_mm_dd(date_str: str) -> str:
        """Parse date string in any common format and return YYYY-MM-DD."""
        # Try dd/mm/yyyy and dd-mm-yyyy first (ambiguous formats)
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        # Fall back to dateutil for ISO and other formats (YYYY-MM-DD, etc.)
        return dateparser.parse(date_str.strip()).strftime("%Y-%m-%d")

    def to_dd_mm_yyyy(date_str: str) -> str:
        """Convert YYYY-MM-DD to dd/mm/yyyy for display."""
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")

    # Normalize exclude_dates to YYYY-MM-DD for internal comparison
    normalized_excludes = set()
    for d in req.exclude_dates:
        try:
            normalized_excludes.add(to_yyyy_mm_dd(d))
        except Exception:
            pass  # skip unparseable dates

    # Book seats for each target day
    for day_str in req.target_days:
        if day_str not in weekdays_map:
            continue
        target_dates = get_upcoming_occurrences(weekdays_map[day_str], max_days=10)
        for target_date in target_dates:
            if target_date in normalized_excludes:
                bookings_skipped.append({"date": to_dd_mm_yyyy(target_date), "status": "excluded"})
                continue
            booked = False
            for seat_name, seat_info in req.favorite_seats.items():
                result = book_seat(
                    token,
                    {"resource_id": seat_info.resource_id, "zone_item_id": seat_info.zone_item_id},
                    target_date,
                    req.workspace_id
                )
                if result.get("successfulBookings"):
                    bookings_made.append({"seat": seat_name, "date": to_dd_mm_yyyy(target_date), "status": "success"})
                    booked = True
                    break
                time.sleep(0.2)
            if not booked:
                bookings_failed.append({"date": to_dd_mm_yyyy(target_date), "status": "all_seats_unavailable"})

    # Get bookings and check-in today's
    bookings = get_user_bookings(token)
    checkins = []
    today = datetime.now().date()

    for booking in bookings.get("results", []):
        booking_date = datetime.fromtimestamp(booking["bookingStartTime"] / 1000).date()
        if booking_date == today and booking.get("checkInStatus") != "checkedIn":
            try:
                check_in_booking(token, booking["id"], booking["zoneItemId"])
                checkins.append({"booking_id": booking["id"], "status": "success"})
            except Exception as e:
                checkins.append({"booking_id": booking["id"], "status": "failed", "error": str(e)})

    return {
        "bookings_made": bookings_made,
        "bookings_failed": bookings_failed,
        "bookings_skipped": bookings_skipped,
        "checkins": checkins,
        "upcoming_bookings": bookings.get("results", [])
    }
