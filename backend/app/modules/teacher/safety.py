"""Child-safety checks around the model (blueprint sections 8 and 10).

Input: messages that suggest distress or danger never go to the model. The student gets
a fixed, careful reply that points to a trusted adult, and the event is flagged for human
review in the audit log.

This is a first, deliberately simple keyword check. It will miss things and it will
sometimes trigger on harmless messages; both are reviewed in the pilot (blueprint
section 12, "Human testing").
"""

import re

_DISTRESS = re.compile(
    r"\b("
    r"kill (my ?self|me)|suicid\w*|want to die|wanna die|end my life|"
    r"hurt (my ?self|me)|self[- ]?harm|cut(ting)? myself|"
    r"no reason to live|better off dead|"
    r"(he|she|they|someone|somebody) (hits|hurts|touches) me|abus(e|ed|ing) me"
    r")\b",
    re.IGNORECASE,
)

SAFE_RESPONSE = (
    "I'm really glad you told me. I'm an AI teacher, so I can't help with this the way a "
    "person can, and you deserve real support. Please talk to a trusted adult today, such "
    "as a parent, guardian, teacher or school counsellor. If you are in danger right now, "
    "call your local emergency number. I'm here for maths whenever you're ready."
)

# Used when the model declines, fails, or keeps trying to reveal the answer.
FALLBACK_RESPONSES = {
    "refusal": "Let's get back to our maths. Have a look at the question on the board.",
    "leak": "Let's take it one step at a time. What do you think the first step is?",
    "unavailable": "Sorry, I'm having trouble thinking right now. Please try again in a moment.",
    "board_only": "Have a look at the board.",
    "empty": "Let's take it one step at a time. What do you think the first step is?",
}


def is_distress(text: str) -> bool:
    return bool(_DISTRESS.search(text))
