import re

POSITIVE = {
    "happy","great","good","excellent","love","amazing","thank","thanks","fast",
    "helpful","perfect","satisfied","awesome","wonderful","pleased","glad"
}
NEGATIVE = {
    "bad","terrible","awful","hate","angry","frustrated","disappointed","late",
    "broken","wrong","refund","unacceptable","annoyed","poor","worst","issue","problem"
}
URGENT = {
    "urgent","immediately","asap","emergency","critical","fraud","hacked","stolen",
    "chargeback","unacceptable","locked","security"
}
EMOTIONS = {
    "frustration": {"frustrated","angry","annoyed","unacceptable","terrible","disappointed"},
    "satisfaction": {"happy","great","excellent","love","amazing","satisfied","perfect"},
    "concern": {"worried","concerned","problem","issue","wrong","late","broken"},
}


def analyze(text: str):
    words = set(re.findall(r"[a-zA-Z']+", text.lower()))
    pos = len(words & POSITIVE)
    neg = len(words & NEGATIVE)
    sentiment = "positive" if pos > neg else "negative" if neg > pos else "neutral"
    emotion = "neutral"
    for label, vocab in EMOTIONS.items():
        if words & vocab:
            emotion = label
            break
    urgent_score = len(words & URGENT)
    urgency = "critical" if urgent_score >= 2 else "high" if urgent_score == 1 or (neg >= 2 and emotion == "frustration") else "normal"
    escalated = urgency in {"high", "critical"}
    return {
        "sentiment": sentiment,
        "emotion": emotion,
        "urgency": urgency,
        "escalated": escalated,
    }
