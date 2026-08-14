from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.config import get_digest_llm
from src.pipeline.content_filters import filter_review_noise, filter_syllabus_noise


class WorkloadDigest(BaseModel):
    syllabus_digest: str = Field(
        ...,
        description="Condensed syllabus text, preserving verbatim wording of grading breakdowns and "
        "exam/coding/team-project/reading/lab requirements.",
    )
    review_digest: str = Field(
        ...,
        description="Condensed review text, preserving verbatim wording of workload-relevant sentences "
        "from the AI-generated summary and most agreed review.",
    )


DIGEST_SYSTEM_PROMPT = """You compress noisy, web-scraped course syllabus and instructor review text down to \
the content relevant to estimating academic workload intensity, for downstream analysis by another model.

Rules:
1. Keep every sentence, phrase, or number related to grading weights, exams, coding/programming assignments, \
team/group projects, reading load, essays, and lab/hands-on requirements.
2. Preserve the original wording verbatim wherever possible - do not paraphrase away specific numbers, \
percentages, hour estimates, or quotes. Downstream analysis will cite direct quotes from your output, so \
rewording destroys that ability.
3. Drop only content that carries no workload signal (leftover navigation fragments, unrelated logistics).
4. Never invent or infer facts that are not present in the source text.
5. If a section has no workload-relevant content, return an empty string for it."""

DIGEST_USER_PROMPT = """## Syllabus (pre-filtered, Markdown)
{filtered_syllabus}

## Instructor Reviews (pre-filtered, Markdown)
{filtered_reviews}

Produce the condensed syllabus_digest and review_digest."""


def build_digest_chain():
    llm = get_digest_llm()
    structured_llm = llm.with_structured_output(WorkloadDigest)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", DIGEST_SYSTEM_PROMPT),
            ("human", DIGEST_USER_PROMPT),
        ]
    )
    return prompt | structured_llm


def build_workload_digest(raw_syllabus: str, raw_reviews: str) -> WorkloadDigest:
    filtered_syllabus = filter_syllabus_noise(raw_syllabus)
    filtered_reviews = filter_review_noise(raw_reviews)

    chain = build_digest_chain()
    return chain.invoke(
        {
            "filtered_syllabus": filtered_syllabus or "(No syllabus text found)",
            "filtered_reviews": filtered_reviews or "(No review text found)",
        }
    )
