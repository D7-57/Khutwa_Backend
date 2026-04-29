from pydantic import BaseModel, Field
from typing import Literal


# ── Q1: Energy source → maps to domain (multi-select, pick 1-3) ──

EnergyChoice = Literal[
    "writing_communicating",
    "analyzing_data",
    "building_coding",
    "designing_visuals",
    "helping_advising",
    "managing_organizing",
    "researching_learning",
]

# ── Q2: Work style → maps to role type (single) ──

WorkStyleChoice = Literal[
    "structured_analytical",    # clear problems, right/wrong answers
    "creative_openended",       # open-ended creative challenges
    "people_coordination",      # coordinating between people/teams
    "builder_maker",            # building things from scratch
]

# ── Q3: Output preference → strong differentiator (multi-select, pick 1-2) ──

OutputChoice = Literal[
    "shipped_built_something",
    "helped_someone",
    "made_something_beautiful",
    "found_an_insight",
    "hit_a_target_closed_deal",
]

# ── Q4: Job priority → filters misaligned paths (single) ──

PriorityChoice = Literal[
    "high_salary",
    "fast_learning",
    "creative_freedom",
    "job_stability",
    "clear_career_ladder",
]


class QuestionnaireAnswers(BaseModel):
    """Structured onboarding questionnaire — drives AI role detection."""

    # Q1 — multi-select (1-3)
    energy_sources: list[EnergyChoice] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="Activities that make you lose track of time (pick 1-3)",
    )

    # Q2 — single
    work_style: WorkStyleChoice = Field(
        ...,
        description="Preferred work environment and problem type",
    )

    # Q3 — multi-select (1-2)
    output_preferences: list[OutputChoice] = Field(
        ...,
        min_length=1,
        max_length=2,
        description="What end-of-day satisfaction looks like (pick 1-2)",
    )

    # Q4 — single
    top_priority: PriorityChoice = Field(
        ...,
        description="Most important factor in first job",
    )

    # Q5 — free text, optional (shown on result screen for refinement)
    background_and_enjoyed: str | None = Field(
        None,
        max_length=500,
        description="Study background + anything they genuinely enjoyed",
    )

    # Q6 — optional, surfaced only if AI asks via follow_up
    considered_roles: str | None = Field(
        None,
        max_length=200,
        description="Any roles they've heard of and found interesting",
    )

    # Language preference for response
    preferred_language: Literal["ar", "en"] = Field(
        "en",
        description="Response language for reasons and follow-ups",
    )
