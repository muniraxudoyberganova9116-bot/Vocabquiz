import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SATvocab.settings')
django.setup()

from vocab.models import Unit, Flashcard

def run():
    u1, _ = Unit.objects.get_or_create(title="Unit 1")
    w1 = [
        ("erratic", "unpredictable, inconsistent, irregular"),
        ("secluded", "hard to reach, hidden away"),
        ("fluctuate", "to rise and fall irregularly"),
        ("exalt", "to praise, to worship"),
        ("admonish", "to warn or scold someone"),
        ("abrupt", "sudden, unexpected, without warning"),
        ("content", "satisfied"),
        ("eccentric", "uncommon, strange"),
        ("mired", "stuck in mud"),
        ("colloquial", "used in casual conversation")
    ]
    for w, d in w1:
        Flashcard.objects.get_or_create(unit=u1, word=w, defaults={"definition": d})

    u2, _ = Unit.objects.get_or_create(title="Unit 2")
    w2 = [
        ("reconcile", "settle one’s differences, make compatible, bring back to peace"),
        ("alienate", "to cause someone to feel isolated or lonely"),
        ("distinguish", "to tell the difference between"),
        ("adequate", "sufficient, enough, acceptable"),
        ("contend", "1) to deal with someone or something 2) to claim or state a belief confidently"),
        ("skeptical", "having doubts"),
        ("enfranchise", "to give the right to vote"),
        ("sophisticated", "1) having a lot of worldly experience and knowledge 2) complicated"),
        ("radical", "1) thorough, complete, extensive 2) fundamental, essential 3) revolutionary, extreme"),
        ("formulate", "to create or think up")
    ]
    for w, d in w2:
        Flashcard.objects.get_or_create(unit=u2, word=w, defaults={"definition": d})

    print("Added Unit 1 and Unit 2 words!")

if __name__ == '__main__':
    run()