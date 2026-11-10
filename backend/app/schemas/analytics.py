from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_events: int
    critical_events: int
    average_confidence: int
    resolution_rate: int

