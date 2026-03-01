from core import predict_propagation, fetch_url

print("=== MisinfoRadar v3 ===")
print("Enter a NEWS URL or paste text directly, then press Enter.\n")

user_input = input("Your URL or text: ").strip()

if user_input.star
tswith("http://") or user_input.startswith("https://") or user_input.startswith("www."):
    print("\n🔍 Fetching article from URL...")
    result_fetch = fetch_url(user_input)
    if not result_fetch["ok"]:
        print(f"❌ Error: {result_fetch['error']}")
        exit()
    text = result_fetch["text"]
    print(f"✅ Title: {result_fetch.get('title', 'N/A')}")
    print(f"📄 Text preview: {text[:200]}...\n")
else:
    text = user_input

if not text.strip():
    print("No text entered.")
else:
    result = predict_propagation(text)

    print("\n--- RESULTS ---")
    print(f"Language       : {result['input']['lang_name']}")
    print(f"Emotion        : {result['emotion']['dominant_emotion']}")
    print(f"Misinfo Label  : {result['misinformation']['label']}")
    print(f"Misinfo Prob   : {result['misinformation']['misinfo_probability']}")
    print(f"Virality Score : {result['virality_score']}")
    print(f"Risk Tier      : {result['risk_tier']['label']}")
    print(f"Description    : {result['risk_tier']['description']}")
    if result['simulation']:
        sim = result['simulation']
        print(f"\nSimulation     : {sim['total_infected']}/{sim['total_nodes']} nodes infected ({sim['reach_pct']}% reach)")
    print(f"\nRecommendations:")
    for r in result['recommendations']:
        print(f"  {r}")
