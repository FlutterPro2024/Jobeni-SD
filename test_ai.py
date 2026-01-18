import os
from app.openrouter_ai import openrouter_ai

print("🚀 جاري اختبار محركات جوبيني الـ 100...")
try:
    response = openrouter_ai.get_ai_response("هل أنت مستعد للعمل كخبير في منصة جوبيني السودان؟")
    print("\n✅ رد المحرك:")
    print("-" * 30)
    print(response)
    print("-" * 30)
except Exception as e:
    print(f"❌ فشل الاختبار بسبب: {e}")
