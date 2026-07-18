import argparse
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from supabase import create_client, Client

# Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("❌ Supabase credentials bulunamadı!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ISTANBUL_TZ = ZoneInfo('Europe/Istanbul')

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
    difficulty_mult = calculate_difficulty_multiplier(vote_distribution)
    change_mult = calculate_change_multiplier(change_percent)
    streak_mult = calculate_streak_multiplier(current_streak)
    
    effective_streak_mult = streak_mult if accuracy == 'exact' else 1.0
    total_points = base_points * difficulty_mult * change_mult * effective_streak_mult
    
    return round(total_points)

def get_user_streak(user_id):
    """Kullanıcının mevcut streak'ini al"""
    try:
        result = supabase.table('users').select('current_streak, last_prediction_date').eq('id', user_id).single().execute()
        
        if not result.data:
            return 0
        
        current_streak = result.data.get('current_streak', 0)
        last_date_str = result.data.get('last_prediction_date')
        
        if not last_date_str:
            return 0
        
        last_date = datetime.fromisoformat(last_date_str).date()
        today = datetime.now().date()
        days_diff = (today - last_date).days
        
        if days_diff > 1:
            return 0
        
        return current_streak
    except:
        return 0

def update_user_streak(user_id, is_correct, prediction_date):
    """Kullanıcının streak'ini güncelle"""
    try:
        result = supabase.table('users').select('current_streak, best_streak, last_prediction_date').eq('id', user_id).single().execute()
        
        current_streak = result.data.get('current_streak', 0) if result.data else 0
        best_streak = result.data.get('best_streak', 0) if result.data else 0
        last_date_str = result.data.get('last_prediction_date') if result.data else None
        
        if is_correct:
            if last_date_str:
                last_date = datetime.fromisoformat(last_date_str).date()
                days_diff = (prediction_date.date() - last_date).days
                
                if days_diff <= 1:
                    current_streak += 1
                else:
                    current_streak = 1
            else:
                current_streak = 1
            
            if current_streak > best_streak:
                best_streak = current_streak
        else:
            current_streak = 0
        
        supabase.table('users').update({
            'current_streak': current_streak,
            'best_streak': best_streak,
            'last_prediction_date': prediction_date.date().isoformat()
        }).eq('id', user_id).execute()
        
    except Exception as e:
        print(f"❌ Update streak error: {e}")

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
        
        print(f"✅ {len(votes)} tahmin bulundu")
        
        processed_count = 0
        skipped_count = 0

        existing_response = supabase.table('prediction_results').select(
            'user_id, poll_id'
        ).eq('result_date', target_date_str).execute()
        existing_results = {
            (row['user_id'], row['poll_id'])
            for row in (existing_response.data or [])
        }

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
                'close_price, date'
            ).eq(
                'symbol', symbol
            ).lt(
                'date', target_date_str
            ).order(
                'date', desc=True
            ).limit(1).execute()
            
            current_price_response = supabase.table('daily_prices').select(
                'close_price'
            ).eq('symbol', symbol).eq('date', target_date_str).limit(1).execute()

            if not prev_price_response.data or not current_price_response.data:
                print(f"⚠️ {symbol} için fiyat bulunamadı")
                skipped_count += 1
                continue

            previous_price_row = prev_price_response.data[0]
            current_price_row = current_price_response.data[0]
            prediction_date_str = previous_price_row['date']
            prev_price = float(previous_price_row['close_price'])
            current_price = float(current_price_row['close_price'])
            
            change_percent = ((current_price - prev_price) / prev_price) * 100
            actual_result = calculate_actual_result(change_percent)
            accuracy_level = calculate_accuracy_level(vote_type, actual_result)
            is_correct = accuracy_level == 'exact'
            
            current_streak = get_user_streak(user_id)
            
            vote_distribution = vote_distributions[poll_id]
            
            points = calculate_hybrid_points(
                vote_type, actual_result, vote_distribution, 
                change_percent, current_streak
            )
            
            difficulty_mult = calculate_difficulty_multiplier(vote_distribution)
            change_mult = calculate_change_multiplier(change_percent)
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
            
            update_user_streak(user_id, is_correct, target_date)
            
            print(f"✅ {symbol}: {vote_type} vs {actual_result} = {points} pts")
            processed_count += 1
        
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
