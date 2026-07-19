from dataclasses import dataclass


BLOCK_SIZE = 10
MIN_CORRECT_PER_BLOCK = 6


@dataclass
class StreakState:
    current_streak: int = 0
    best_streak: int = 0
    block_total: int = 0
    block_correct: int = 0

    def add_prediction(self, is_correct):
        """Tahmini bloğa ekle; yalnızca her 10 tahminde seriyi değiştir."""
        self.block_total += 1
        if is_correct:
            self.block_correct += 1

        if self.block_total < BLOCK_SIZE:
            return

        if self.block_correct >= MIN_CORRECT_PER_BLOCK:
            self.current_streak += 1
            self.best_streak = max(self.best_streak, self.current_streak)
        else:
            self.current_streak = max(0, self.current_streak - 1)

        self.block_total = 0
        self.block_correct = 0


def actual_result(change_percent):
    if change_percent > 0.5:
        return 'positive'
    if change_percent < -0.5:
        return 'negative'
    return 'neutral'


def accuracy_level(prediction, actual):
    return 'exact' if prediction == actual else 'wrong'


def difficulty_multiplier(vote_distribution, prediction):
    """Azınlık yönünü doğru seçen kullanıcıya daha yüksek çarpan ver."""
    total = sum(vote_distribution.values())
    if total == 0:
        return 1.0

    selected_votes = vote_distribution.get(prediction, 0)
    selected_percentage = selected_votes / total
    return round(1.0 + (1.0 - selected_percentage), 2)


def change_multiplier(change_percent, actual):
    """Nötr doğru sonuç ×1; yönlü sonuçlarda hareket büyüklüğü bonusu."""
    if actual == 'neutral':
        return 1.0

    change_abs = abs(change_percent)
    if change_abs < 1.0:
        return 0.5
    if change_abs < 2.0:
        return 0.8
    if change_abs < 5.0:
        return 1.0
    if change_abs < 10.0:
        return 1.3
    return 1.5


def streak_multiplier(streak):
    if streak < 2:
        return 1.0
    if streak <= 3:
        return 1.2
    if streak <= 6:
        return 1.5
    if streak <= 9:
        return 1.8
    return 2.5


def hybrid_points(
    prediction,
    actual,
    vote_distribution,
    change_percent,
    current_streak,
):
    if accuracy_level(prediction, actual) == 'wrong':
        return 0

    points = (
        10.0
        * difficulty_multiplier(vote_distribution, prediction)
        * change_multiplier(change_percent, actual)
        * streak_multiplier(current_streak)
    )
    return round(points)
