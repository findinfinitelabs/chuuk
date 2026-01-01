import json

with open('training_data/chuukese_to_english_validated.json', 'r') as f:
    data = json.load(f)

water_entries = [entry for entry in data if 'water' in entry.get('english', '').lower()]
print(f'Found {len(water_entries)} entries containing "water" in english')
for entry in water_entries[:3]:
    print(f'Chuukese: {entry.get("chuukese")}')
    print(f'English: {entry.get("english")}')
    print(f'Original: {entry.get("original_chuukese")}')
    print('---')