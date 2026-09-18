from sqlalchemy.orm import Session

from app.domain import Profile
from app.models import Company


def upsert_company(session: Session, profile: Profile) -> Company:
    company = session.get(Company, profile.ticker) or Company(ticker=profile.ticker)
    company.name = profile.name
    company.sector = profile.sector
    company.industry = profile.industry
    company.sector_etf = profile.sector_etf
    session.add(company)
    return company
