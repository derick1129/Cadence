"""LiveKit room and WebRTC participant token generation."""

from datetime import timedelta

from livekit.api import AccessToken, VideoGrants

from backend.app.core.settings import settings


def generate_livekit_token(
    room_name: str,
    participant_identity: str,
    session_id: str,
    ttl_seconds: int = 3600,
) -> str:
    """Generate a signed LiveKit WebRTC AccessToken with room join permissions.

    Args:
        room_name: Unique room identifier.
        participant_identity: Caller identity or browser client identifier.
        session_id: Cadence session ID embedded in participant metadata.
        ttl_seconds: Duration before token expiry (default 1 hour).

    Returns:
        Signed JWT string ready for frontend WebRTC connection.
    """
    token = (
        AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        .with_identity(participant_identity)
        .with_metadata(session_id)
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .with_ttl(timedelta(seconds=ttl_seconds))
    )
    return str(token.to_jwt())
