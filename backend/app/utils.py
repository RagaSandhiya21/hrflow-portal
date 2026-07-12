from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import HolidayCalendar


def count_business_days(db: Session, org_id: int, start: date, end: date) -> float:
    """
    Counts days between start and end (inclusive) that are not a weekend
    (Sat/Sun) and not in the org's holiday_calendar. This is the DB-backed
    version of the proposal's "leave applications blocked on public
    holidays and weekends" rule (Module 2).
    """
    holiday_dates = {
        h.holiday_date
        for h in db.query(HolidayCalendar.holiday_date)
        .filter(
            HolidayCalendar.org_id == org_id,
            HolidayCalendar.holiday_date >= start,
            HolidayCalendar.holiday_date <= end,
        )
        .all()
    }

    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holiday_dates:  # Mon=0 ... Sun=6
            count += 1
        current += timedelta(days=1)
    return float(count)
