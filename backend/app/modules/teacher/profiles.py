"""Subject and level profiles: what changes in the teacher from one subject or level to
another. The shared teaching rules (prompts.py) stay the same everywhere.

A subject points to a profile by key (subjects.profile). Add a profile here when a new
kind of subject needs different wording or board use; most new subjects reuse one.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectProfile:
    key: str
    subject_words: str  # "maths", "business and information systems"
    board_rule: str  # how to use the whiteboard in this subject
    hint_1: str  # the conceptual nudge
    hint_2: str  # the first step
    hint_3: str  # the worked example of a similar problem
    other_angle: str  # examples of a different angle for "I don't get it"
    extra_rules: str = ""  # subject-specific safety or style rules


PROFILES: dict[str, SubjectProfile] = {
    "math": SubjectProfile(
        key="math",
        subject_words="maths",
        board_rule='Use "equation" with LaTeX for maths, "step" for one step, "text" for a '
        "short note.",
        hint_1="a conceptual nudge only, such as what a key word in the question means. "
        "No calculation.",
        hint_2="show only the first step of the calculation, not the result.",
        hint_3="work through a similar problem with different numbers, fully. None of its "
        "numbers, including its result, may equal the hidden answer.",
        other_angle="for example with money or a picture in words",
    ),
    "business": SubjectProfile(
        key="business",
        subject_words="business and information systems",
        board_rule='Use "text" for a short definition or heading and "step" for one point '
        'of an explanation. Use "equation" only for a real formula.',
        hint_1="a conceptual nudge only: remind the student what a key term means, "
        "without naming the answer.",
        hint_2="narrow it down: rule out one wrong idea or point at the deciding detail "
        "in the question, without naming the answer.",
        hint_3="explain a similar example from a different business situation, fully. It "
        "must not use or name the hidden answer.",
        other_angle="for example with an everyday business such as a shop, a bank or a "
        "school",
        extra_rules="- This is education, not professional advice: do not give personal "
        "investment, legal or tax advice.",
    ),
    "general": SubjectProfile(
        key="general",
        subject_words="this subject",
        board_rule='Use "text" for a short definition or heading and "step" for one point '
        "of an explanation.",
        hint_1="a conceptual nudge only: remind the student what a key idea means, "
        "without naming the answer.",
        hint_2="narrow it down: point at the detail in the question that decides it, "
        "without naming the answer.",
        hint_3="explain a similar example, fully. It must not use or name the hidden "
        "answer.",
        other_angle="for example with an everyday comparison",
    ),
}


def profile_for(key: str | None) -> SubjectProfile:
    return PROFILES.get(key or "general", PROFILES["general"])


def level_description(grade_level: int) -> str:
    """How to pitch the explanation. Grade 13 means a university or adult learner."""
    if grade_level >= 13:
        return (
            "university or adult learner: use correct technical terms, explain them "
            "briefly, and keep a respectful, adult tone"
        )
    if grade_level >= 9:
        return f"high-school student (grade {grade_level}): clear and direct, define terms"
    if grade_level >= 6:
        return (
            f"middle-school student (grade {grade_level}): simple words, short sentences, "
            "concrete examples"
        )
    return (
        f"young student (grade {grade_level}): very simple words and very short sentences"
    )
