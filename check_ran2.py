import json

with open('training_data/chuukese_to_english_validated.json', 'r') as f:
    data = json.load(f)

ran_entries = [entry for entry in data if 'ran' in entry.get('chuukese', '')]
print(f'Found {len(ran_entries)} entries containing "ran" in chuukese')
for entry in ran_entries[:5]:
    print(f'Chuukese: {entry.get("chuukese")}')
    print(f'English: {entry.get("english")}')
    print(f'Original: {entry.get("original_chuukese")}')
    print('---')