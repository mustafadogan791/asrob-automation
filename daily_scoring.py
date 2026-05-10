import os
from datetime import datetime, timedelta
from supabase import create_client, Client

# Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabase credentials bulunamadı!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def calculate_actual_result(change_percent):
    """Fiyat değişimine göre sonucu belirle"""
    if change_percent > 1.0:
        return 'positive'
    elif change_percent < -1.0:
        return 'negative'
    else:
        return 'neutral'

def calculate_accuracy_level(prediction, actual):
    """Tahmin doğruluğunu hesapla"""
    if prediction == actual:
        return 'exact'
    
    partial_cases = [
        ('positive', 'neutral'), ('neutral', 'positive'),
        ('negative', 'neutral'), ('neutral', 'negative')
    ]
    
    if (prediction, actual) in partial_cases:
        return 'partial'
    
    return 'wrong'

def calculate_difficulty_multiplier(vote_distribution):
    """Zorluk katsayısı"""
    total = sum(vote_distribution.values())
    if total == 0:
        return 1.0
    
    max_votes = max(vote_distribution.values())
    max_percentage = max_votes / total
    difficulty = 1.0 + (1.0 - max_percentage)
    return round(difficulty, 2)

def calculate_change_multiplier(change_percent):
    """Değişim bonusu"""
    change_abs = abs(change_percent)
    
    if change_abs < 1.0:
        return 0.5
    elif change_abs < 2.0:
        return 0.8
    elif change_abs < 5.0:
        return 1.0
    elif change_abs < 10.0:
        return 1.3
    else:
        return 1.5

def calculate_streak_multiplier(streak):
    """Streak bonusu"""
    if streak < 2:
        return 1.0
    elif streak <= 3:
        return 1.2
    elif streak <= 6:
        return 1.5
    elif streak <= 9:
        return 1.8
    else:
        return 2.5

def calculate_hybrid_points(prediction, actual, vote_distribution, change_percent, current_streak):
    """Hibrit puan hesaplama"""
    accuracy = calculate_accuracy_level(prediction, actual)
    if accuracy == 'wrong':
        return 0
    
    base_points = 10.0
    difficulty_mult = calculate_difficulty_multipl
