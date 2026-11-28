# admin.py ke END me paste karein

from django.contrib import messages as dj_messages, admin
from .models import AIConversation, AIMessage


class AIMessageInline(admin.TabularInline):
    model = AIMessage
    extra = 0
    fields = ("role", "content", "status", "feedback", "feedback_note", "created")
    readonly_fields = fields
    can_delete = False


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    """TaxBuddy Umair AI chats (owner = hashed browser id; CNIC/NTN masked)."""
    list_display = ("title", "updated", "is_deleted", "shared", "n_messages")
    list_filter = ("is_deleted", "updated")
    search_fields = ("title", "messages__content")
    readonly_fields = ("owner", "cid", "title", "created", "updated", "share_token", "is_deleted")
    inlines = [AIMessageInline]

    def has_add_permission(self, request):
        return False

    @admin.display(boolean=True)
    def shared(self, obj):
        return bool(obj.share_token)

    def n_messages(self, obj):
        return obj.messages.count()


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    """Feedback review queue: filter Feedback = 👎, fix the answer, turn it into a VerifiedAnswer."""
    list_display = ("short", "feedback", "feedback_note", "status", "created")
    list_filter = ("feedback", "role", "status", "created")
    search_fields = ("content", "feedback_note")
    readonly_fields = ("conversation", "role", "content", "sources", "status", "imported",
                       "feedback", "feedback_note", "feedback_at", "created")
    actions = ["make_verified_drafts"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role="assistant")

    def has_add_permission(self, request):
        return False

    def short(self, obj):
        return obj.content[:90]

    @admin.action(description="Create draft Verified Answers from selected (question + this answer)")
    def make_verified_drafts(self, request, queryset):
        try:
            from .models import VerifiedAnswer as _VA
        except ImportError:
            self.message_user(request, "VerifiedAnswer model nahi mila — pehle woh deploy karein.", dj_messages.ERROR)
            return
        made = 0
        for m in queryset:
            q = (AIMessage.objects.filter(conversation=m.conversation, role="user", id__lt=m.id)
                 .order_by("-id").first())
            if not q:
                continue
            _VA.objects.create(question=q.content[:2000], answer=m.content,
                               category="From chat feedback", status="draft",
                               last_test_note=(f"User feedback: {m.feedback_note}" if m.feedback_note else ""))
            made += 1
        self.message_user(request, f"{made} draft Verified Answer(s) created — open AI verified answers, "
                                   f"correct the answer, then set status to Verified.", dj_messages.SUCCESS)