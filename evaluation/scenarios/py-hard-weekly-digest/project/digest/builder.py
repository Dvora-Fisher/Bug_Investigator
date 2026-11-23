def build_digest(user, items: list[dict]) -> dict | None:
    """The email for one user, or None when there is nothing new to show (we never send empty digests)."""
    visible = [i for i in items if i["topic"] not in user.prefs.muted_topics]
    if not visible:
        return None
    lines = [f"- {i['title']}" for i in visible[:10]]
    return {"to": user.email, "subject": f"Your weekly digest ({len(visible)} updates)", "body": "\n".join(lines)}
