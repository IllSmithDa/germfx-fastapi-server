# app/main.py
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.routes import account_danger, account_recovery, admin_activities, admin_drug_details, admin_drug_indexes, admin_usage_limits, admin_users, articles, auth, billing, drug_detail_export, google_auth, reactions, drug_detail, email, safety_warnings, saved_items, side_effects, suggestions, usage_limits, user_feedback, user_medications, user_detail, reports, reports_export, recalls, user_settings, symptom_logs, rxnorm_test, dailymed_test, brave_search_test

app = FastAPI(title="GermFx FastAPI Backend")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://localhost:3000",
    "https://germfx-client.netlify.app/",
    "https://sidefx-client.netlify.app/",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://192.168.1.25:8081",
    "http://192.168.68.54:8000",
    "http://192.168.68.51:8000",
    # "https://app.GermFx.ai",  # add production when ready
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

Base.metadata.create_all(bind=engine)

# ---- Centralized API router (single source of truth for prefixes) ----
api = APIRouter(prefix="/api")

# “service” areas (auth, meds, suggestions)
api.include_router(auth.router, prefix="/auth", tags=["auth"])
api.include_router(drug_detail.router, prefix="/medications", tags=["medications"])
api.include_router(suggestions.router, prefix="/suggestions", tags=["suggestions"])

# “user” area (notice: our per-file routers have no prefix now)
api.include_router(symptom_logs.router, prefix="/symptom-logs", tags=["symptom-logs"])
api.include_router(user_medications.router, prefix="/user-medications", tags=["user-medications"])
api.include_router(user_detail.router, prefix="/users", tags=["user-detail"])
api.include_router(email.router, prefix="/auth", tags=["email"])  # <-- email routes under /auth
api.include_router(account_danger.router, prefix="/auth", tags=["account-danger"])  # <-- account danger routes under /auth
api.include_router(account_recovery.router, prefix="/auth", tags=["account-recovery"])  # <-- account recovery routes under /auth
api.include_router(admin_activities.router, prefix="/admin", tags=["admin-activities"])  # <-- admin activities under /admin    
api.include_router(articles.router, prefix="/articles", tags=["articles"])  # <-- content routes under /content
api.include_router(reports.router, prefix="/reports", tags=["user-reports"])
api.include_router(reports_export.router, prefix="/reports", tags=["export-reports"])  # <-- reports export routes under /reports
api.include_router(side_effects.router, prefix="/side-effects", tags=["side-effects"])
api.include_router(safety_warnings.router, prefix="/safety-warnings", tags=["safety-warnings"])
api.include_router(recalls.router, prefix="/recalls", tags=["recalls"])  # <-- recalls routes under /recalls\
api.include_router(saved_items.router, prefix="/saved-items", tags=["saved-items"])  # <-- saved items routes under /saved-items
api.include_router(reactions.router, prefix="/reactions", tags=["content-reactions"])  # <-- content reactions routes under /reactions
api.include_router(google_auth.router, prefix="/auth/google", tags=["google-auth"])  # <-- google auth routes under /auth/google
api.include_router(user_settings.router, prefix="/user-settings", tags=["user-settings"])  # <-- user settings routes under /user-settings
api.include_router(drug_detail_export.router, prefix="/drug-details")
api.include_router(rxnorm_test.router, prefix="/rxnorm")
api.include_router(dailymed_test.router, prefix="/dailymed", tags=["dailymed-test"])
api.include_router(brave_search_test.router, prefix="/brave-search", tags=["brave-barcode-search-test"])
api.include_router(admin_users.router, prefix="/admin", tags=["admin-users"])
api.include_router(admin_drug_indexes.router, prefix="/admin", tags=["admin-drug-indexes"])
api.include_router(admin_usage_limits.router, prefix="/admin/usage-limits", tags=["admin-usage-limits"])
api.include_router(usage_limits.router,prefix="/usage-limits", tags=["usage-limits"])
api.include_router(billing.router, prefix="/billing", tags=["billing"])
api.include_router(admin_drug_details.router, prefix="/admin", tags=["admin-drug-detail"])
api.include_router(user_feedback.router, prefix="/feedback", tags=["user-feedback"])
api.include_router(user_feedback.admin_router, prefix="/admin/feedback", tags=["admin-feedback"])
# Mount the API group
app.include_router(api)

# (Optional) health check
@app.get("/healthz")
def healthz():
    return {"ok": True}
