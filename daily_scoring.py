import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from supabase import create_client, Client
from scoring_rules import (
    StreakState,
    accuracy_level,
    actual_result,
    change_multiplier,
    difficulty_multiplier,
    hybrid_points,
    streak_multiplier,
)
from price_integrity import same_price_series

# Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabase credentials bulunamadı!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ISTANBUL_TZ = ZoneInfo('Europe/Istanbul')
SCORING_V2_START_DATE = os.getenv('SCORING_V2_START_DATE', '2026-07-20')

def calculate_actual_result(change_percent):
    """Fiyat değişimine göre sonucu belirle"""
    return actual_result(change_percent)

def calculate_accuracy_level(prediction, actual):
    """Tahmin doğruluğunu hesapla"""
    return accuracy_level(prediction, actual)

def calculate_difficulty_multiplier(vote_distribution, prediction):
    """Zorluk katsayısı"""
    return difficulty_multiplier(vote_distribution, prediction)

def calculate_change_multiplier(change_percent, actual):
    """Değişim bonusu"""
    return change_multiplier(change_percent, actual)

def calculate_streak_multiplier(streak):
    """Streak bonusu"""
    return streak_multiplier(streak)

def calculate_hybrid_points(prediction, actual, vote_distribution, change_percent, current_streak):
    """Hibrit puan hesaplama"""
    return hybrid_points(
        prediction,
        actual,
        vote_distribution,
        change_percent,
        current_streak,
    )

def load_streak_states():
    """Geçmiş sonuçlardan 10'luk blok serilerini idempotent biçimde kur."""
    states = {}
    page_size = 1000
    start = 0

    while True:
        response = supabase.table('prediction_results').select(
            'user_id, poll_id, result_date, accuracy_level'
        ).gte(
            'result_date', SCORING_V2_START_DATE
        ).order(
            'result_date'
        ).order(
            'poll_id'
        ).range(start, start + page_size - 1).execute()
        rows = response.data or []

        for row in rows:
            user_id = row['user_id']
            state = states.setdefault(user_id, StreakState())
            state.add_prediction(row['accuracy_level'] == 'exact')

        if len(rows) < page_size:
            break
        start += page_size

    return states


def sync_user_streaks(states, user_ids, result_date):
    """Hesaplanan blok serilerini kullanıcı profillerine yansıt."""
    for user_id in user_ids:
        state = states.get(user_id, StreakState())
        supabase.table('users').update({
            'current_streak': state.current_streak,
            'best_streak': state.best_streak,
            'last_prediction_date': result_date,
        }).eq('id', user_id).execute()

def process_daily_predictions(result_date=None):
    """Hedef işlem gününün kapanmış anketlerini idempotent biçimde puanla."""
    target_day = result_date or datetime.now(ISTANBUL_TZ).date()
    target_date = datetime.combine(target_day, datetime.min.time())
    target_date_str = target_day.isoformat()
    
    print(f"\n{'='*60}")
    print(f"🎯 Günlük Puanlama Başlıyor")
    print(f"📅 Sonuçlandırılacak Anket Günü: {target_date_str}")
    print(f"{'='*60}\n")
    
    try:
        votes_response = supabase.table('votes').select(
            '*, polls!inner(symbol, id, date)'
        ).eq(
            'polls.date', target_date_str
        ).not_.is_('user_id', 'null').execute()
        
        votes = votes_response.data if votes_response.data else []
        votes.sort(key=lambda vote: (vote['user_id'], vote['polls']['id']))
        
        print(f"✅ {len(votes)} tahmin bulundu")
        
        processed_count = 0
        skipped_count = 0

        existing_response = supabase.table('prediction_results').select(
            'user_id, poll_id'
        ).eq('result_date', target_date_str).execute()
        existing_result_rows = existing_response.data or []
        existing_results = {
            (row['user_id'], row['poll_id'])
            for row in existing_result_rows
        }
        users_to_sync = {row['user_id'] for row in existing_result_rows}
        streak_states = load_streak_states()

        vote_distributions = {}
        for vote in votes:
            poll_id = vote['polls']['id']
            distribution = vote_distributions.setdefault(
                poll_id,
                {'positive': 0, 'neutral': 0, 'negative': 0},
            )
            distribution[vote['vote_type']] += 1
        
        for vote in votes:
            symbol = vote['polls']['symbol']
            user_id = vote['user_id']
            poll_id = vote['polls']['id']
            vote_type = vote['vote_type']

            if (user_id, poll_id) in existing_results:
                print(f"⏭️  {symbol}: Bu tahmin daha önce puanlandı")
                skipped_count += 1
                continue

            prev_price_response = supabase.table('daily_prices').select(
                'close_price, date, source'
            ).eq(
                'symbol', symbol
            ).lt(
                'date', target_date_str
            ).order(
                'date', desc=True
            ).limit(1).execute()
            
            current_price_response = supabase.table('daily_prices').select(
                'close_price, source'
            ).eq('symbol', symbol).eq('date', target_date_str).limit(1).execute()

            if not prev_price_response.data or not current_price_response.data:
                print(f"⚠️ {symbol} için fiyat bulunamadı")
                skipped_count += 1
                continue

            previous_price_row = prev_price_response.data[0]
            current_price_row = current_price_response.data[0]
            if not same_price_series(
                previous_price_row.get('source'),
                current_price_row.get('source'),
            ):
                print(
                    f"⚠️ {symbol}: fiyat kaynakları farklı "
                    f"({previous_price_row.get('source')} -> "
                    f"{current_price_row.get('source')}); puanlama atlandı"
                )
                skipped_count += 1
                continue
            prediction_date_str = previous_price_row['date']
            prev_price = float(previous_price_row['close_price'])
            current_price = float(current_price_row['close_price'])
            
            change_percent = ((current_price - prev_price) / prev_price) * 100
            actual_result = calculate_actual_result(change_percent)
            accuracy_level = calculate_accuracy_level(vote_type, actual_result)
            is_correct = accuracy_level == 'exact'
            
            streak_state = streak_states.setdefault(user_id, StreakState())
            current_streak = streak_state.current_streak
            
            vote_distribution = vote_distributions[poll_id]
            
            points = calculate_hybrid_points(
                vote_type, actual_result, vote_distribution, 
                change_percent, current_streak
            )
            
            difficulty_mult = calculate_difficulty_multiplier(
                vote_distribution,
                vote_type,
            )
            change_mult = calculate_change_multiplier(
                change_percent,
                actual_result,
            )
            streak_mult = calculate_streak_multiplier(current_streak)
            
            supabase.table('prediction_results').insert({
                'user_id': user_id,
                'poll_id': poll_id,
                'symbol': symbol,
                'vote_type': vote_type,
                'prediction_date': prediction_date_str,
                'result_date': target_date_str,
                'prediction_close_price': prev_price,
                'result_close_price': current_price,
                'actual_change_percent': round(change_percent, 4),
                'actual_result': actual_result,
                'is_correct': is_correct,
                'accuracy_level': accuracy_level,
                'points_earned': points,
                'difficulty_multiplier': difficulty_mult,
                'change_multiplier': change_mult,
                'streak_multiplier': streak_mult,
                'streak_at_prediction': current_streak,
                'vote_distribution': vote_distribution
            }).execute()
            existing_results.add((user_id, poll_id))
            users_to_sync.add(user_id)
            streak_state.add_prediction(is_correct)
            
            print(f"✅ {symbol}: {vote_type} vs {actual_result} = {points} pts")
            processed_count += 1

        if users_to_sync:
            sync_user_streaks(
                streak_states,
                users_to_sync,
                target_date_str,
            )
        
        if processed_count > 0:
            supabase.rpc('update_user_scores').execute()
            supabase.rpc('refresh_stats_and_badges').execute()
       
        
        print(f"\n{'='*60}")
        print(f"🎉 {processed_count} tahmin işlendi, {skipped_count} tahmin atlandı!")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--date',
        help='Test için sonuç tarihi (YYYY-MM-DD); varsayılan İstanbul bugünü.',
    )
    args = parser.parse_args()
    result_date = datetime.fromisoformat(args.date).date() if args.date else None
    process_daily_predictions(result_date)
