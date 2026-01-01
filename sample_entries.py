from enhanced_trainer import EnhancedHelsinkiTrainer
trainer = EnhancedHelsinkiTrainer()
chk_pairs, en_pairs = trainer.prepare_enhanced_training_data()

print('Sample Chuukese->English entries:')
for i, entry in enumerate(chk_pairs[:10]):
    print(f'{i+1}. "{entry.get("chuukese")}" -> "{entry.get("english")}"')

print('\nSample English->Chuukese entries:')
for i, entry in enumerate(en_pairs[:10]):
    print(f'{i+1}. "{entry.get("english")}" -> "{entry.get("chuukese")}"')