class LivenessDetectionFailed(Exception):
    """Raised when liveness check fails — possible spoofing attempt."""
    pass


class FaceNotFound(Exception):
    """Raised when no face is detected in the submitted image."""
    pass


class WatchlistHit(Exception):
    """Raised when verified citizen is on active watchlist."""
    def __init__(self, alert_level: str, reason: str, entry_id: int):
        self.alert_level = alert_level
        self.reason = reason
        self.entry_id = entry_id
        super().__init__(f"Watchlist {alert_level}: {reason}")


class NoEmbeddingRegistered(Exception):
    """Raised when citizen has no face embedding in the database yet."""
    pass
