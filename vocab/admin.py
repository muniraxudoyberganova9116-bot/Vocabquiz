import csv
import io

from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from .models import Flashcard, FlashcardReview, Profile, Unit, UnitProgress


class FlashcardInline(admin.TabularInline):
    model = Flashcard
    extra = 3
    fields = ('word', 'ipa', 'part_of_speech', 'definition', 'example')


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'card_count')
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [FlashcardInline]
    change_list_template = 'admin/vocab/unit/change_list.html'

    def card_count(self, obj):
        return obj.flashcards.count()
    card_count.short_description = 'Flashcards'

    def get_urls(self):
        urls = super().get_urls()
        custom = [path('import-csv/', self.admin_site.admin_view(self.csv_import_view), name='vocab_unit_csv_import')]
        return custom + urls

    def csv_import_view(self, request):
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file or not csv_file.name.endswith('.csv'):
                self.message_user(request, 'Please upload a .csv file.', messages.ERROR)
                return redirect('..')

            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
            required = {'unit', 'word', 'definition'}
            if not required.issubset({f.strip().lower() for f in (reader.fieldnames or [])}):
                self.message_user(
                    request,
                    'CSV must have columns: unit, word, definition (optional: ipa, part_of_speech, example)',
                    messages.ERROR,
                )
                return redirect('..')

            created_units = 0
            created_cards = 0
            for row in reader:
                unit_title = row.get('unit', '').strip()
                word = row.get('word', '').strip()
                definition = row.get('definition', '').strip()
                if not unit_title or not word or not definition:
                    continue
                unit, u_new = Unit.objects.get_or_create(title=unit_title)
                if u_new:
                    created_units += 1
                _, c_new = Flashcard.objects.get_or_create(
                    unit=unit,
                    word=word,
                    defaults={
                        'definition': definition,
                        'ipa': row.get('ipa', '').strip(),
                        'part_of_speech': row.get('part_of_speech', '').strip(),
                        'example': row.get('example', '').strip(),
                    },
                )
                if c_new:
                    created_cards += 1

            self.message_user(
                request,
                f'Imported {created_cards} new cards across {created_units} new units.',
            )
            return redirect('..')

        return render(request, 'admin/vocab/unit/csv_import.html')


@admin.register(Flashcard)
class FlashcardAdmin(admin.ModelAdmin):
    list_display = ('word', 'ipa', 'part_of_speech', 'unit', 'short_definition')
    list_filter = ('unit', 'part_of_speech')
    search_fields = ('word', 'definition', 'example')
    autocomplete_fields = ('unit',)
    list_select_related = ('unit',)
    fieldsets = (
        (None, {'fields': ('unit', 'word', 'ipa', 'part_of_speech')}),
        ('Content', {'fields': ('definition', 'example')}),
    )

    def short_definition(self, obj):
        return (obj.definition[:80] + '…') if len(obj.definition) > 80 else obj.definition
    short_definition.short_description = 'Definition'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_score', 'words_mastered')
    search_fields = ('user__username',)
    readonly_fields = ('user',)
    list_select_related = ('user',)


@admin.register(UnitProgress)
class UnitProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'unit', 'is_completed', 'accuracy_pct')
    list_filter = ('is_completed', 'unit')
    search_fields = ('user__username', 'unit__title')
    list_select_related = ('user', 'unit')
    readonly_fields = ('user', 'unit')

    def accuracy_pct(self, obj):
        return f'{obj.accuracy or 0:.0f}%'
    accuracy_pct.short_description = 'Accuracy'


@admin.register(FlashcardReview)
class FlashcardReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'flashcard', 'next_review', 'interval', 'repetitions', 'ease_factor')
    list_filter = ('next_review',)
    search_fields = ('user__username', 'flashcard__word')
    list_select_related = ('user', 'flashcard')
    readonly_fields = ('user', 'flashcard')
