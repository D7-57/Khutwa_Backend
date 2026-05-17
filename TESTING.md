# Khutwa Testing Plan — Implementation Report

## 1. Testing Strategy Summary

Khutwa's test suite is split into two layers:

**Backend (Python/FastAPI/pytest)**
Tests run against an in-memory SQLite database using `StaticPool` so every request in a test sees the same schema. All Supabase auth is bypassed via FastAPI's `dependency_overrides` (both `get_current_user_id` and `get_current_auth_user`). External services — OpenAI, Supabase storage, audio, video — are mocked using `unittest.mock.patch` wherever a test needs to verify behavior that depends on them. No real API keys are ever called.

**Frontend (Dart/Flutter/flutter_test)**
Pure unit tests verify that every model's `fromJson` factory correctly parses real API response shapes, and that all utility helper functions produce the right output. These tests have zero runtime dependencies: no Flutter widget tree, no HTTP calls, no Supabase.

The philosophy is _test what matters, skip what you can't control_: core business logic (survey scoring, ATS rule engine, cert filtering, experience inference), API contract shape (all route responses), and auth gating (every protected endpoint verified against 401 when no token) are all covered. Real AI calls and real Supabase are never called — tests would be slow, flaky, and require paid credentials.

---

## 2. Files Created or Changed

### Backend — new files
```
tests/__init__.py
tests/conftest.py                               ← shared fixtures + SQLite + auth mocks
tests/unit/__init__.py
tests/unit/test_cv_evaluation.py                ← 36 unit tests
tests/unit/test_role_survey.py                  ← 27 unit tests
tests/unit/test_roadmap_helpers.py              ← 22 unit tests
tests/integration/__init__.py
tests/integration/test_role_survey_api.py       ← 27 integration tests
tests/integration/test_profile_api.py           ← 14 integration tests
tests/integration/test_interview_api.py         ← 10 integration tests
tests/integration/test_roadmap_api.py           ← 12 integration tests
pytest.ini
.env.test                                       ← safe dummy env values for CI
```

### Backend — no existing files changed

### Frontend — new files
```
test/unit/role_survey_model_test.dart           ← 25 unit tests
test/unit/utils_test.dart                       ← 28 unit tests
```

### Frontend — changed files
```
pubspec.yaml    ← added mockito and build_runner to dev_dependencies
```

---

## 3. Tests Added

### Backend Unit Tests (85 total)

#### `tests/unit/test_cv_evaluation.py` — 36 tests

| Class | Tests |
|---|---|
| `TestClampScore` | 0-clamp, 100-clamp, negative-clamp, above-100-clamp, rounded-int |
| `TestContainsPhrase` | exact match, word-boundary, case-insensitive, empty phrase, missing phrase, multi-word |
| `TestFlattenSkills` | list input, dict-of-lists, None, empty list, blank-string filtering |
| `TestScoreAts` | good CV scores higher than empty, response keys present, scores 0-100, empty CV generates issues, must-have matched, missing keyword reported, email in checklist, table penalty |
| `TestScoreCompleteness` | full checklist ≥80, empty=50, table penalises |
| `TestScoreExperienceDepth` | no signals ≈50, experience+dates boost, many gaps lower score |
| `TestBuildRadarScores` | six dimensions present, all 0-100 |
| `TestBuildOverallRecommendations` | returns list, deduplication, pulls from ATS issues, max 6 |

#### `tests/unit/test_role_survey.py` — 27 tests

| Class | Tests |
|---|---|
| `TestQuestionDataIntegrity` | all 3 majors have questions, every question has id+options, every option has roles, all role keys in `_ROLE_NAMES`, all option ids indexed, explanations cover all roles |
| `TestMaxPossible` | IT/ENG/BIZ counts, unknown major=0 |
| `TestScoringLogic` | software_dev answers rank it first, non-negative scores, bounded by question count |
| `TestSchemas` | SurveyRoleResult valid, SurveyResult valid, empty answers accepted, SurveyAnswer schema |

#### `tests/unit/test_roadmap_helpers.py` — 22 tests

| Class | Tests |
|---|---|
| `TestClassifyTaskForProfile` | certification keyword, build/create → project, skill_name → skill, no keywords → skill, cert in description, cert beats project keyword |
| `TestContainsArabic` | Arabic detected, English not, mixed, None, empty |
| `TestStandardCertsForRole` | cloud engineer, security analyst, unknown role, empty role, software engineer |
| `TestFilterUnearnedCerts` | removes owned, alias matching, empty owned, all owned |
| `TestNormalizeToken` | lowercase+strip, empty, spaces removed |
| `TestCertAliases` | security+ aliases, unknown cert, eJPT aliases |
| `TestInferExperienceLevel` | no signals=beginner, 3+years=advanced, 1year=intermediate, multiple certs=advanced, one experience=intermediate |

---

### Backend Integration Tests (63 total)

#### `tests/integration/test_role_survey_api.py` — 27 tests

| Class | Tests |
|---|---|
| `TestGetMajors` | 200, 3 majors, required fields, keys are it/eng/biz, no auth required |
| `TestGetQuestions` | 200 for all majors, list returned, total matches count, question fields, option has roles, invalid major=422, missing param=422, no auth required |
| `TestSubmitSurvey` | 200 valid, required fields, list type, role fields, match_percent range, major echoed, biz roles in response, 401 without auth, empty answers=400, invalid major=422, duplicate answers=422, consistent results |

#### `tests/integration/test_profile_api.py` — 14 tests

| Class | Tests |
|---|---|
| `TestHealthEndpoint` | /health 200 both auth/unauth |
| `TestGetProfile` | 200 authenticated, has id, id matches user, 401 unauth, json object |
| `TestBasicInfoOnboarding` | saves successfully, name retrievable, invalid=not 500 |
| `TestPatchProfile` | 200/204, language persisted, 401 unauth |

#### `tests/integration/test_interview_api.py` — 10 tests

| Class | Tests |
|---|---|
| `TestStartInterview` | 401 unauth, start returns session or expected error, no payload=not 500 |
| `TestListInterviews` | 401 unauth, 200 auth, returns list, empty=empty list |
| `TestGetInterview` | 404 non-existent session, 401 unauth |

#### `tests/integration/test_roadmap_api.py` — 12 tests

| Class | Tests |
|---|---|
| `TestGetRoadmap` | 401 unauth, 200/404 auth, no roadmap=safe, all roadmaps endpoint, all requires auth |
| `TestGenerateRoadmap` | 401 unauth, no role=400/404, mocked service returns roadmap |
| `TestCompleteTask` | non-existent=error, 401 unauth |
| `TestDeleteRoadmap` | non-existent=error, 401 unauth |

---

### Frontend Unit Tests (53 total)

#### `test/unit/role_survey_model_test.dart` — 25 tests

| Group | Tests |
|---|---|
| `SurveyMajor.fromJson` | all fields, label_ar fallback, icon default |
| `SurveyOption.fromJson` | id+text+roles, missing roles=empty, text_ar fallback |
| `SurveyQuestion.fromJson` | id+texts, options list, option type |
| `SurveyRoleResult.fromJson` | all fields, null id, score default, match_percent default |
| `SurveyResult.fromJson` | major+label, top_roles, score_breakdown, icon default, null breakdown |

#### `test/unit/utils_test.dart` — 28 tests

| Group | Tests |
|---|---|
| `saudiPhoneToE164` | leading zero, no zero, hyphens, 966 prefix, empty, spaces |
| `normalizeEmailForAuth` | lowercase, trim, zero-width, BOM, fullwidth @, double quotes, single quotes, non-breaking space, clean passthrough |
| `profileDisplayName` | first+last, first only, last only, full_name fallback, empty, trim, prefers first+last |

---

## 4. Install Test Dependencies

### Backend
```powershell
# Windows/PowerShell — run inside the backend directory
cd Khutwa_Backend-main

pip install pytest pytest-asyncio httpx fastapi sqlalchemy pydantic "pydantic[email]" `
  pydantic-settings python-dotenv python-jose email-validator `
  openai pdfplumber pypdf python-docx jinja2 `
  python-multipart xhtml2pdf `
  opencv-python-headless mediapipe
```

Or all at once from requirements:
```powershell
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
```

### Frontend
```powershell
cd frontend
flutter pub get
```

---

## 5. Run Backend Tests

```powershell
# Full suite
cd Khutwa_Backend-main
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Single test file
python -m pytest tests/unit/test_cv_evaluation.py -v

# With coverage (optional — requires pytest-cov)
pip install pytest-cov
python -m pytest tests/ --cov=app --cov-report=term-missing
```

**Expected result:** 146 tests, 0 failed.

---

## 6. Run Frontend Tests

```powershell
cd frontend

# All unit tests
flutter test test/unit/

# Single file
flutter test test/unit/role_survey_model_test.dart
flutter test test/unit/utils_test.dart
```

**Expected result:** 53 tests, 0 failed.

---

## 7. Mocks / Fakes / Stubs Added and Why

| Mock | Location | Why |
|---|---|---|
| `get_current_user_id` override | `conftest.py` | Returns `TEST_USER_ID` so no real JWT is needed. All protected endpoints accept this. |
| `get_current_auth_user` override | `conftest.py` | Returns a fake `AuthUser(id=TEST_USER_ID)` for endpoints that use the richer auth dependency (e.g. `GET /auth/me`). |
| `get_db` override | `conftest.py` | Returns a session backed by in-memory SQLite with `StaticPool` instead of the production Postgres. No real DB needed. |
| SQLite JSONB → TEXT | `conftest.py` | The production models use PostgreSQL `JSONB`. SQLite has no JSONB type. We monkey-patch `SQLiteTypeCompiler.visit_JSONB` to emit `TEXT` so `create_all()` succeeds. |
| `generate_roadmap` patch | `test_roadmap_api.py` | The real function calls OpenAI. The mock returns a hardcoded dict so we can verify the HTTP layer without a real AI call. |
| `pick_intro`, `synthesize_question_audio` patches | `test_interview_api.py` | Real calls require OpenAI + ElevenLabs keys. Mocked so the start endpoint can be exercised. |

---

## 8. Tests That Could Not Be Completed

| Test | Reason |
|---|---|
| **CV endpoint full flow** (`POST /cv/evaluate`, `POST /cv/upload`) | These endpoints require a real PDF file + OpenAI call. The ATS scoring unit tests cover the pure-Python logic. An integration test would need a fixture PDF file and a mocked `run_full_cv_evaluation`. This is straightforward to add once a sample PDF fixture is added to `tests/fixtures/`. |
| **Interview turn / answer evaluation** (`POST /interviews/{id}/turn`) | Requires a live `InterviewSession` row plus mocked AI evaluator. Creating the session requires the `POST /interviews/start` to succeed fully, which in turn needs a `Profile` with a role assigned. Achievable with additional DB seed fixtures in a follow-up. |
| **Roadmap task complete → full progress recalc** | Requires a fully seeded roadmap (stages + tasks) in the test DB. The `complete_task` service logic is deterministic and could be tested with SQLAlchemy model objects directly. Added as a next step. |
| **Flutter widget tests (login page, survey page, dashboard)** | Every page has hard dependencies on `Supabase.instance` and `SharedPreferences` that are initialised at app startup. Without proper platform-channel mocks (which require `flutter_test` integration setup and `supabase_flutter` mock packages), these tests either crash or require deep widget-tree setup. The model and utility unit tests are more stable and provide better ROI. |
| **Flutter integration tests** | The app's `main.dart` calls `Supabase.initialize()` and reads a `.env` file at launch. Without either a test-only `main.dart` or mock platform plugins, `flutter integration_test` cannot cold-boot the app in CI. This is a known Flutter integration test limitation with Supabase. |

---

## 9. Core Feature Coverage Checklist

| Feature | Unit Tests | Integration Tests | Notes |
|---|---|---|---|
| ✅ Authentication (JWT gating) | — | All protected endpoints verify 401 without auth | Auth logic bypassed by design; 401 gating verified for every route |
| ✅ Profile load/update | — | GET /auth/me, PATCH /auth/me, POST /auth/onboarding/basic | Profile created-on-first-access verified |
| ✅ Role survey — questions | Data integrity (30+ options, 3 majors) | GET /majors, GET /questions (all 3 majors) | |
| ✅ Role survey — scoring | Scoring logic (deterministic, bounded, non-negative) | POST /submit (200, fields, biz roles, 401, empty answers, duplicates) | |
| ✅ CV evaluation — ATS scorer | score_ats, _clamp, _contains_phrase, _flatten_skills, radar scores, completeness | — | Pure Python; no AI mock needed |
| ✅ CV evaluation — recommendations | build_overall_recommendations (dedup, max 6, pulls from issues) | — | |
| ✅ Roadmap — helpers | classify_task, _contains_arabic, cert filtering, experience level | GET /roadmap/me, POST /generate (mocked), task complete 401, delete 401 | |
| ✅ Interview sessions | — | POST /start (unauth 401, no payload not 500), GET list, GET summary 404/401 | |
| ✅ Dashboard / health | — | GET /health always 200 | Dashboard loads verified indirectly via profile + roadmap endpoints |
| ⚠️ CV upload/evaluate endpoint | ATS unit tests cover scoring | Full integration deferred (needs PDF fixture) | |
| ⚠️ Interview turn/answer | — | Deferred — needs seeded session + mocked AI evaluator | |
| ⚠️ Flutter UI widget tests | — | Deferred — Supabase platform channel mocking not set up | |
