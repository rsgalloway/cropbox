from dataclasses import dataclass


@dataclass
class TrimRange:
    start: float
    end: float

    def normalized(self) -> "TrimRange":
        start = min(self.start, self.end)
        end = max(self.start, self.end)
        return TrimRange(start=start, end=end)
