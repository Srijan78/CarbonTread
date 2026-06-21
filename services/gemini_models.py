from typing import Optional, List
from pydantic import BaseModel, Field


class ExtractedEvent(BaseModel):
    category: str = Field(
        description="Must be exactly: transport, food, energy, or other"
    )
    subtype: str = Field(
        description="Must be one of the recognized subtypes: car, uber_ola, "
                    "auto_rickshaw, bus, metro, train, flight, two_wheeler, "
                    "walk_cycle, vegetarian_day, non_vegetarian_day, vegan_day, "
                    "mixed, electricity_bill, lpg_refill, png_usage, ac_usage"
    )
    description: str = Field(
        description="Brief user-friendly description of what was logged"
    )
    value: float = Field(description="Numeric quantity extracted from input")
    unit: str = Field(
        description="Raw unit of measurement as stated (e.g. km, days, units, kWh, kg, cylinder)"
    )
    confidence: str = Field(
        description="Must be exactly: high, medium, or low"
    )
    unrecognized: Optional[str] = Field(
        None,
        description="Explanation if activity is unrecognized or contains leftover text"
    )


class SuggestionItem(BaseModel):
    action: str = Field(description="Actionable suggestion text (Plex Sans)")
    category: str = Field(
        description="Must be exactly: transport, food, or energy"
    )
    co2_saved_kg: float = Field(
        description="Estimated CO2 saved in kg, quantitative value"
    )
    difficulty: str = Field(
        description="Must be exactly: easy, medium, or hard"
    )
    reasoning: str = Field(
        description="One-line logic justifying the recommendation"
    )


class SuggestionsOutput(BaseModel):
    suggestions: List[SuggestionItem] = Field(
        description="A list of up to 3 suggestions"
    )
