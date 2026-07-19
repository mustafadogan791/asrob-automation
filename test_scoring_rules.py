import unittest

from scoring_rules import (
    StreakState,
    accuracy_level,
    actual_result,
    change_multiplier,
    difficulty_multiplier,
    hybrid_points,
    streak_multiplier,
)


class ScoringRulesTests(unittest.TestCase):
    def test_neutral_band_is_half_percent(self):
        self.assertEqual(actual_result(0.5), 'neutral')
        self.assertEqual(actual_result(-0.5), 'neutral')
        self.assertEqual(actual_result(0.51), 'positive')
        self.assertEqual(actual_result(-0.51), 'negative')

    def test_partial_accuracy_is_removed(self):
        self.assertEqual(accuracy_level('positive', 'positive'), 'exact')
        self.assertEqual(accuracy_level('positive', 'neutral'), 'wrong')
        self.assertEqual(accuracy_level('neutral', 'negative'), 'wrong')

    def test_minority_choice_gets_higher_difficulty(self):
        distribution = {'positive': 80, 'neutral': 0, 'negative': 20}
        self.assertEqual(difficulty_multiplier(distribution, 'positive'), 1.2)
        self.assertEqual(difficulty_multiplier(distribution, 'negative'), 1.8)

    def test_correct_neutral_uses_one_times_change_multiplier(self):
        self.assertEqual(change_multiplier(0.2, 'neutral'), 1.0)
        self.assertEqual(change_multiplier(-0.5, 'neutral'), 1.0)

    def test_wrong_prediction_always_scores_zero(self):
        points = hybrid_points(
            'positive',
            'negative',
            {'positive': 10, 'neutral': 0, 'negative': 90},
            -4.0,
            10,
        )
        self.assertEqual(points, 0)

    def test_correct_minority_neutral_combines_all_multipliers(self):
        points = hybrid_points(
            'neutral',
            'neutral',
            {'positive': 80, 'neutral': 20, 'negative': 0},
            0.3,
            2,
        )
        self.assertEqual(points, 22)

    def test_nine_correct_and_one_wrong_completes_successful_block(self):
        state = StreakState()
        for _ in range(9):
            state.add_prediction(True)
        state.add_prediction(False)
        self.assertEqual(state.current_streak, 1)
        self.assertEqual(state.block_total, 0)

    def test_six_correct_block_increments_streak(self):
        state = StreakState(current_streak=1, best_streak=1)
        for is_correct in ([True] * 6 + [False] * 4):
            state.add_prediction(is_correct)
        self.assertEqual(state.current_streak, 2)
        self.assertEqual(state.best_streak, 2)
        self.assertEqual(streak_multiplier(state.current_streak), 1.2)

    def test_failed_block_drops_only_one_level(self):
        state = StreakState(current_streak=4, best_streak=6)
        for is_correct in ([True] * 5 + [False] * 5):
            state.add_prediction(is_correct)
        self.assertEqual(state.current_streak, 3)
        self.assertEqual(state.best_streak, 6)

    def test_incomplete_block_does_not_change_streak(self):
        state = StreakState(current_streak=3, best_streak=3)
        for _ in range(9):
            state.add_prediction(False)
        self.assertEqual(state.current_streak, 3)
        self.assertEqual(state.block_total, 9)


if __name__ == '__main__':
    unittest.main()
