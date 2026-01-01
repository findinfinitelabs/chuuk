import json

with open('training_data/chuukese_to_english_validated.json', 'r') as f:
    data = json.load(f)

ran_entries = [entry for entry in data if entry.get('chuukese', '').strip() == 'ran' or entry.get('original_chuukese', '').strip() == 'ran']
print(f'Found {len(ran_entries)} entries with chuukese "ran"')
for entry in ran_entries[:3]:
    print(entry)