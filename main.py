from fastapi import FastAPI, Request, Form, HTTPException, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pywebpush import webpush, WebPushException
import json, os, datetime

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ─── VAPID 푸시 설정 ──────────────────────────────────────
VAPID_PUBLIC  = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAET3PeIQswflC0InM_YXGSKDltCi2hBiV8SVsoFLAvRLTrZFtlR9yYnpW8jDttfG8w5NNL5RXBok2p64HUQ4DSg"
VAPID_PRIVATE = "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg20NpX_XWC_lRY2OfpWr9SgAqJQ5iN30VQZHBChOXc4KhRANCAARPc94hCzB-ULQicz9hcZIoOW0KLaEGJXxJWygUsC9EtOtkW2VH3LlielbyMO218bzDk00vlFcGiTanrgdRDgNK"
VAPID_CLAIMS  = {"sub":"mailto:you@yourdomain.com"}

# ─── 데이터 파일 경로 ────────────────────────────────────
DATA_FILE    = "data.json"
CLASSES_FILE = "classes.json"

# ─── PWA 구독 저장 ───────────────────────────────────────
subscriptions = []

# ─── 데이터 입출력 헬퍼 ──────────────────────────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_classes():
    if not os.path.exists(CLASSES_FILE):
        return []
    with open(CLASSES_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_classes(classes):
    with open(CLASSES_FILE, "w", encoding="utf-8") as f:
        json.dump(classes, f, ensure_ascii=False, indent=2)

# ─── 공통 유틸 ──────────────────────────────────────────
def get_weeks():
    today = datetime.date.today()
    return [f"{today.year}년 {today.month}월 {n}째주" for n in range(1,5)]

def get_day_nums(week_str):
    parts = week_str.split()
    year  = int(parts[0][:-1]); month = int(parts[1][:-1]); week = int(parts[2][:-2])
    first = datetime.date(year, month, 1)
    wd    = first.weekday()
    start = first + datetime.timedelta(days=(7-wd) if wd else 0) + datetime.timedelta(weeks=week-1)
    return [f"{(start + datetime.timedelta(days=i)).month}/{(start + datetime.timedelta(days=i)).day}" for i in range(5)]

def send_push(week, info):
    payload = {"title":f"{week} 알림", "body":"내일 숙제와 준비물을 확인해 주세요."}
    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE,
                vapid_claims=VAPID_CLAIMS
            )
        except WebPushException as ex:
            print("Push failed:", ex)

# ─── 랜딩 페이지 ────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

# ─── 관리자 페이지 ──────────────────────────────────────
# ─── 관리자 페이지 ──────────────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    classes = load_classes()
    return templates.TemplateResponse("admin.html", {"request": request, "classes": classes})

@app.post("/admin/add", response_class=RedirectResponse)
def admin_add(
    name: str = Form(...),
    teacher_code: str = Form(...),
    parent_code: str = Form(...),
):
    classes = load_classes()
    # 새 반 추가
    classes.append({"name": name, "teacher_code": teacher_code, "parent_code": parent_code})
    save_classes(classes)
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/update", response_class=RedirectResponse)
def admin_update(
    name: str = Form(...),
    teacher_code: str = Form(...),
    parent_code: str = Form(...),
):
    classes = load_classes()
    for cls in classes:
        if cls["name"] == name:
            cls["teacher_code"] = teacher_code
            cls["parent_code"]  = parent_code
            break
    save_classes(classes)
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/delete", response_class=RedirectResponse)
def admin_delete(name: str = Form(...)):
    classes = load_classes()
    classes = [c for c in classes if c["name"] != name]
    save_classes(classes)
    return RedirectResponse("/admin", status_code=303)
# ─── 선생님 로그인 & 작성 페이지 ─────────────────────────
@app.get("/teacher", response_class=HTMLResponse)
def teacher(request: Request, week: str = None, teacher_code: str = Cookie(None)):
    # 로그인 검사
    classes = load_classes()
    if not teacher_code:
        return templates.TemplateResponse("teacher_login.html", {
            "request": request,
            "classes": [c["name"] for c in classes]
        })
    cls = next((c for c in classes if c["teacher_code"] == teacher_code), None)
    if not cls:
        resp = templates.TemplateResponse("teacher_login.html", {
            "request": request,
            "classes": [c["name"] for c in classes],
            "error": "코드가 유효하지 않습니다."
        })
        resp.delete_cookie("teacher_code")
        return resp

    # 작성 화면 로드
    weeks    = get_weeks()
    selected = week or weeks[0]
    data     = load_data()
    info     = data.get(selected, {
        "homeworks":   [""]*5,
        "materials":   [""]*5,
        "day_nums":    get_day_nums(selected),
        "published":   False,
        "subject":     "",
        "holidays":    [False]*5,
        "principles":  [""]*7,
        "english":     "",
        "pray":        "",
        "notice_all":  ""
    })
    return templates.TemplateResponse("teacher.html", {
        "request": request,
        "weeks": weeks,
        "selected_week": selected,
        "info": info,
        "class_name": cls["name"]
    })

@app.post("/teacher_login", response_class=Response)
def teacher_login(response: Response, class_name: str = Form(...), code: str = Form(...)):
    classes = load_classes()
    cls = next((c for c in classes if c["name"] == class_name and c["teacher_code"] == code), None)
    if not cls:
        raise HTTPException(status_code=401, detail="코드가 틀렸습니다.")
    redirect = RedirectResponse("/teacher", status_code=303)
    redirect.set_cookie("teacher_code", code, httponly=True)
    return redirect

@app.post("/teacher", response_class=RedirectResponse)
def save_teacher(
    week: str = Form(...),
    published: str = Form(None),
    homework_0: str = Form(""), material_0: str = Form(""),
    homework_1: str = Form(""), material_1: str = Form(""),
    homework_2: str = Form(""), material_2: str = Form(""),
    homework_3: str = Form(""), material_3: str = Form(""),
    homework_4: str = Form(""), material_4: str = Form(""),
    subject: str = Form(""),
    principle_0: str = Form(""), principle_1: str = Form(""),
    principle_2: str = Form(""), principle_3: str = Form(""),
    principle_4: str = Form(""), principle_5: str = Form(""), principle_6: str = Form(""),
    english: str = Form(""), pray: str = Form(""), notice_all: str = Form("")
):
    data = load_data()
    data[week] = {
        "homeworks":  [homework_0, homework_1, homework_2, homework_3, homework_4],
        "materials":  [material_0, material_1, material_2, material_3, material_4],
        "day_nums":   get_day_nums(week),
        "published":  (published == "yes"),
        "subject":     subject,
        "holidays":    [False]*5,
        "principles":  [principle_0, principle_1, principle_2, principle_3, principle_4, principle_5, principle_6],
        "english":     english,
        "pray":        pray,
        "notice_all":  notice_all
    }
    save_data(data)
    if published == "yes":
        send_push(week, data[week])
    return RedirectResponse(f"/teacher?week={week}", status_code=303)

# ─── 학부모 로그인 & 확인 페이지 ─────────────────────────
@app.get("/parent", response_class=HTMLResponse)
def parent(request: Request, week: str = None, parent_code: str = Cookie(None)):
    classes = load_classes()
    if not parent_code:
        return templates.TemplateResponse("parent_login.html", {
            "request": request,
            "classes": [c["name"] for c in classes]
        })

    cls = next((c for c in classes if c["parent_code"] == parent_code), None)
    if not cls:
        resp = templates.TemplateResponse("parent_login.html", {
            "request": request,
            "classes": [c["name"] for c in classes],
            "error": "코드가 유효하지 않습니다."
        })
        resp.delete_cookie("parent_code")
        return resp

    data = load_data()
    published_weeks = [w for w,i in data.items() if i.get("published")]
    if not published_weeks:
        raise HTTPException(status_code=404, detail="배포된 주간학습안내가 없습니다.")
    published_weeks.sort(reverse=True)
    selected = week if week in published_weeks else published_weeks[0]
    weeks = published_weeks[:4]

    # 기본 구조 병합
    raw = data[selected]
    default = {
        "homeworks":  [""]*5,
        "materials":  [""]*5,
        "day_nums":   get_day_nums(selected),
        "published":  True,
        "subject":     "",
        "holidays":    [False]*5,
        "principles":  [""]*7,
        "english":     "",
        "pray":        "",
        "notice_all":  ""
    }
    info = {**default, **raw}

    # **여기**가 핵심—딕셔너리 끝에 쉼표 없이 중괄호 닫기**
    return templates.TemplateResponse("parent.html", {
        "request": request,
        "weeks": weeks,
        "selected_week": selected,
        "info": info,
        "class_name": cls["name"]
    })
@app.post("/parent_login", response_class=Response)
def parent_login(response: Response, class_name: str = Form(...), code: str = Form(...)):
    classes = load_classes()
    cls = next((c for c in classes if c["name"] == class_name and c["parent_code"] == code), None)
    if not cls:
        raise HTTPException(status_code=401, detail="코드가 틀렸습니다.")
    redirect = RedirectResponse("/parent", status_code=303)
    redirect.set_cookie("parent_code", code, httponly=True)
    return redirect

@app.post("/parent", response_class=HTMLResponse)
def parent_post(request: Request, week: str = Form(...)):
    return parent(request, week)

# ─── PWA 구독 & 푸시 ───────────────────────────────────
@app.post("/subscribe")
async def subscribe(request: Request):
    sub = await request.json()
    if sub not in subscriptions:
        subscriptions.append(sub)
    return JSONResponse({"status": "subscribed"})
