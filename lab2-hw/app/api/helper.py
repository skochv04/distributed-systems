from datetime import datetime
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse


def convert_salary(salary_min, salary_max, currency, exchange_rates):
    """Convert salary to EUR"""
    if currency and currency != "EUR" and currency in exchange_rates:
        rate = exchange_rates[currency]

        try:
            salary_min = float(salary_min) if salary_min else 0
            salary_max = float(salary_max) if salary_max else 0
        except ValueError:
            salary_min = salary_max = 0

        salary_min = int(salary_min * rate) if salary_min else 0
        salary_max = int(salary_max * rate) if salary_max else 0

    return salary_min, salary_max, "EUR"


def format_datetime(iso_string: str) -> str:
    formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]

    for fmt in formats:
        try:
            dt = datetime.strptime(iso_string, fmt)
            return dt.strftime("%d-%m-%Y at %H:%M")
        except ValueError:
            continue

    return iso_string


def calculate_average_month_salary(salary_min, salary_max, year_period=False):
    """Calculate average month salary in EUR"""
    if salary_min is None or salary_max is None:
        return 0

    try:
        salary_min = float(salary_min)
        salary_max = float(salary_max)
    except ValueError:
        return 0

    if 0 < salary_min < 1000:
        salary_min *= 100
    if 0 < salary_max < 1000:
        salary_max *= 100

    return ((salary_max - salary_min) // 24 if year_period else (salary_max - salary_min) // 2) \
        if (salary_min and salary_max) else 0


def clean_url_params(url: str) -> str:
    """Clean URL from empty parameters"""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    cleaned_params = {key: value[0] for key, value in query_params.items() if value[0]}
    cleaned_query = urlencode(cleaned_params)
    cleaned_url = parsed_url._replace(query=cleaned_query)
    return urlunparse(cleaned_url)
