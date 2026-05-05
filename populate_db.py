import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SATvocab.settings')
django.setup()

from vocab.models import Unit, Flashcard

def run():
    # Unit 1
    unit1, created = Unit.objects.get_or_create(title="Essential GRE Verbs")
    
    words_unit1 = [
        {"word": "Mitigate", "definition": "Make less severe, serious, or painful."},
        {"word": "Mollify", "definition": "Appease the anger or anxiety of someone."},
        {"word": "Obfuscate", "definition": "Render obscure, unclear, or unintelligible."},
        {"word": "Placate", "definition": "Make someone less angry or hostile."},
        {"word": "Repudiate", "definition": "Refuse to accept or be associated with."},
    ]
    
    for w in words_unit1:
        Flashcard.objects.get_or_create(unit=unit1, word=w["word"], defaults={"definition": w["definition"]})
        
    # Unit 2
    unit2, created = Unit.objects.get_or_create(title="Advanced SAT Adjectives")
    
    words_unit2 = [
        {"word": "Ephemeral", "definition": "Lasting for a very short time."},
        {"word": "Capricious", "definition": "Given to sudden and unaccountable changes of mood or behavior."},
        {"word": "Fastidious", "definition": "Very attentive to and concerned about accuracy and detail."},
        {"word": "Irresolute", "definition": "Showing or feeling hesitancy; uncertain."},
        {"word": "Lucid", "definition": "Expressed clearly; easy to understand."},
    ]
    
    for w in words_unit2:
        Flashcard.objects.get_or_create(unit=unit2, word=w["word"], defaults={"definition": w["definition"]})

    print("Successfully added units and flashcards.")

if __name__ == '__main__':
    run()
