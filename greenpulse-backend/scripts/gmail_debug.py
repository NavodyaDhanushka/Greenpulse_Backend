import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.notification_agent import _get_service, GARDEN_QUERY

service = _get_service()

profile = service.users().getProfile(userId="me").execute()
print("Connected account:", profile["emailAddress"])
print("Total messages in mailbox:", profile["messagesTotal"])

tests = [
    ("any mail, last 7 days", "newer_than:7d"),
    ("garden query", GARDEN_QUERY),
    ("simple keywords", "rain OR garden OR plant"),
]
for label, q in tests:
    r = service.users().messages().list(
        userId="me", q=q, maxResults=5, includeSpamTrash=True
    ).execute()
    print(f"{label}: {len(r.get('messages', []))} result(s)")