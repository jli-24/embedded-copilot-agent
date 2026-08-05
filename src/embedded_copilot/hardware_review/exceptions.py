class HardwareReviewError(RuntimeError):
    code = "REVIEW_ERROR"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)


class ReviewUnavailable(HardwareReviewError):
    code = "REVIEW_UNAVAILABLE"


class ReviewRejected(HardwareReviewError):
    code = "REVIEW_REJECTED"
