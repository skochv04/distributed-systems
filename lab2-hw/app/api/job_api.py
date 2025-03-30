import httpx
from starlette.responses import PlainTextResponse

import helper
import requests
import os
from fastapi import FastAPI, Query
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from bs4 import BeautifulSoup
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Authorization"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/EUR"
JOBS_API = [
    {
        "url": "https://jobicy.com/api/v2/remote-jobs?geo={country}&industry={industry}&tag={title}",
        "api_name": "jobicy",
        "params": ["country", "industry", "title"],
        "results": "jobs"
    }
    ,
    {
        "url": "https://jobdataapi.com/api/jobs/?title={title}&location={country}&experience_level={jobLevel}",
        "api_name": "jobdataapi",
        "params": ["country", "title", "jobLevel"],
        "results": "results"
    }
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


class JobLevel(str, Enum):
    any = "any"
    junior = "junior"
    mid = "mid"
    senior = "senior"


class JobType(str, Enum):
    any = "any"
    full_time = "full-time"
    part_time = "part-time"
    contract = "contract"
    internship = "internship"
    temporary = "temporary"
    other = "other"


class Vacancy(BaseModel):
    company_name: str
    company_logo: Optional[str] = None
    job_title: str
    job_countries: List[str]
    job_level: JobLevel
    job_types: List[JobType]
    job_industry: List[str]
    description: Optional[str] = None
    url: str
    publish_date: str
    salary_month: Optional[int] = None
    salary_currency: Optional[str] = "EUR"  # null = EUR

    class Config:
        use_enum_values = True


def convert_job_level(experience_level):
    if experience_level in ["SE", "Senior"]:
        job_level = JobLevel.senior
    elif experience_level in ["MI", "Mid", "Middle"]:
        job_level = JobLevel.mid
    elif experience_level in ["JR", "EN", "Junior"]:
        job_level = JobLevel.junior
    else:
        job_level = JobLevel.any
    return job_level


def get_exchange_rates():
    try:
        response = requests.get(EXCHANGE_API_URL, timeout=5)
        data = response.json()
        return data.get("rates", {})
    except requests.RequestException:
        return {}


def parse_job_data(api_name, job_data, exchange_rates, country):
    """ Parse vacancy from some API and normalize data """

    if not job_data or not isinstance(job_data, dict):
        return None

    if api_name == "jobdataapi":
        company_info = job_data.get("company", {})
        company_name = company_info.get("name", "Unknown")
        company_logo = company_info.get("logo")

        job_title = job_data.get("title", "Unknown")

        if not job_title:
            return None

        countries = [country["name"] for country in job_data.get("countries", [])]
        if country and country not in countries:
            return None

        experience_level = job_data.get("experience_level", "")
        if experience_level is not None:
            experience_level = experience_level.upper()

        job_level = convert_job_level(experience_level)

        job_types = [
            JobType(t["name"].replace(" ", "-").lower()) if t["name"].replace(" ", "_").lower() in JobType.__members__
            else JobType.other
            for t in job_data.get("types", [])
        ]

        description_html = job_data.get("description", "")
        soup = BeautifulSoup(description_html, "html.parser")
        description_text = "\n\n".join(p.get_text(strip=True) for p in soup.find_all(["p", "li"]))

        job_url = job_data.get("application_url", "Unknown")

        publish_date = job_data.get("published", "Unknown")
        if publish_date != "Unknown":
            publish_date = helper.format_datetime(publish_date)

        salary_min = job_data.get("salary_min")
        salary_max = job_data.get("salary_max")
        currency = job_data.get("salary_currency", "EUR")

    elif api_name == "jobicy":
        company_name = job_data.get("companyName", "Unknown")
        company_logo = job_data.get("companyLogo")

        job_title = job_data.get("jobTitle", "Unknown")

        if not job_title:
            return None

        countries = []
        country = job_data.get("jobGeo")
        if country:
            countries.append(country)

        experience_level = job_data.get("jobLevel", "")

        job_level = convert_job_level(experience_level)

        job_types = [
            JobType(t.lower()) if t.lower().replace("-", "_") in JobType.__members__
            else JobType.other
            for t in job_data.get("jobType", [])
        ]

        description_html = job_data.get("jobDescription", "")
        soup = BeautifulSoup(description_html, "html.parser")
        description_text = "\n\n".join(p.get_text(strip=True) for p in soup.find_all(["p", "li"]))

        job_url = job_data.get("url", "Unknown")

        publish_date = job_data.get("pubDate", "Unknown")
        if publish_date != "Unknown":
            publish_date = helper.format_datetime(publish_date)

        salary_min = job_data.get("annualSalaryMin")
        salary_max = job_data.get("annualSalaryMax")
        currency = job_data.get("salaryCurrency", "EUR")

    salary_min, salary_max, currency = helper.convert_salary(
        salary_min, salary_max, currency, exchange_rates
    )
    salary_month = helper.calculate_average_month_salary(salary_min, salary_max)

    salary_month = salary_month if salary_month > 0 else None

    return Vacancy(
        company_name=company_name,
        company_logo=company_logo,
        job_title=job_title,
        job_countries=countries,
        job_level=job_level,
        job_types=job_types,
        job_industry=[],
        description=description_text,
        url=job_url,
        publish_date=publish_date,
        salary_month=salary_month,
        salary_currency="EUR"
    )


@app.exception_handler(429)
async def rate_limit_handler():
    return PlainTextResponse("Too many requests", status_code=429)


@app.get("/search", response_model=List[Vacancy])
@limiter.limit("5/minute")
async def search_jobs(
        request: Request,
        jobTitle: str = Query(..., min_length=2),
        country: Optional[str] = None,
        jobLevel: JobLevel = JobLevel.any,
        jobType: JobType = JobType.any,
        salaryMin: Optional[int] = None,
        salaryMax: Optional[int] = None,
        industry: Optional[str] = None
):
    async with httpx.AsyncClient(timeout=30) as client:
        exchange_res = await client.get(EXCHANGE_API_URL)
        if exchange_res.status_code != 200:
            return JSONResponse(status_code=503, content={"error": "Currency conversion service unavailable"})
        exchange_rates = exchange_res.json().get("rates", {})

        vacancies = []

        for api in JOBS_API:
            job_level_param = jobLevel.value if (jobLevel != JobLevel.any and api["api_name"] != "jobdataapi") else ""
            country = country.lower() if country else ""

            formatted_url = api["url"].format(
                title=jobTitle,
                country=country,
                jobLevel=job_level_param,
                jobType=jobType.value,
                salaryMin=salaryMin or 0,
                salaryMax=salaryMax or 1000000,
                industry=industry.lower() if industry else "",
                location=country or ""
            )

            formatted_url = helper.clean_url_params(formatted_url)
            print(f"Fetching jobs from: {formatted_url}")
            try:
                response = await client.get(formatted_url)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                print(f"HTTP error from {api['api_name']}: {e}")
                continue
            except httpx.RequestError as e:
                print(f"HTTP error from {api['api_name']}: {e}")
                continue
            except ValueError as e:
                print(f"Invalid JSON response from {api['api_name']}: {e}")
                continue

            for job in data.get(api["results"], []):
                vacancy = parse_job_data(api["api_name"], job, exchange_rates, country)
                if vacancy:
                    vacancies.append(vacancy)

        filtered_vacancies = [
            v for v in vacancies
            if (jobLevel == JobLevel.any or jobLevel == v.job_level or v.job_level == JobLevel.any)
               and (jobType == JobType.any or jobType in v.job_types)
               and (v.salary_month is None or (
                    (salaryMin is None or v.salary_month >= salaryMin) and
                    (salaryMax is None or v.salary_month <= salaryMax)
            ))
        ]

        return templates.TemplateResponse("response.html", {"request": request, "vacancies": filtered_vacancies})
