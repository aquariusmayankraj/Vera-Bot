# Vera Studio — पूरा setup और manual deployment

इस ZIP में frontend और backend दोनों हैं। यह Vera bot project है; Flutter Smart Crop project नहीं है।

**कोई deployment अपने-आप नहीं होगा।** आपको पहले Render पर backend और फिर Netlify पर frontend deploy करना है। GitHub/Render/Netlify account या API key ZIP में नहीं है।

## 1. कौन-सा folder कहाँ जाएगा?

```text
vera-fullstack/
├── frontend/                 → Netlify: इसी folder को publish करें
│   ├── index.html
│   ├── config.js             → Render URL केवल यहाँ बदलना है
│   ├── styles.css
│   ├── _headers
│   └── src/
├── backend/                  → Render: Python Web Service
│   ├── bot.py
│   ├── start.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── vera/
│   └── tests/
├── render.yaml
├── netlify.toml
├── scripts/
├── docs/
└── INSTRUCTIONS_HINDI.md
```

Frontend static HTML/CSS/JavaScript है। कोई npm install, npm build, React या Vite setup आवश्यक नहीं है। Backend पुराने deterministic FastAPI bot का updated version है। **इस frontend के साथ ZIP वाला नया backend deploy करें**, क्योंकि website के isolated demo endpoints पुराने backend में नहीं थे।

## 2. Backend को Render पर deploy करें

### Repository बनाना

ZIP extract करें। `vera-fullstack` के **अंदर वाली files/folders** अपने Git repository root में रखें। यानी repository में सीधे `backend`, `frontend`, `render.yaml` दिखने चाहिए, उनके ऊपर एक अतिरिक्त `vera-fullstack` folder नहीं। `.env`, virtual environment या SQLite database commit न करें; `.gitignore` दिया है।

Render की standard Python Web Service विधि repository से source लेती है। पूरी ZIP को Netlify की तरह Render dropzone में upload करने का step यहाँ नहीं है।

### Render service settings

Render में अपनी repository चुनकर नया **Web Service** बनाएँ:

| Setting | Value |
|---|---|
| Language/runtime | Python 3 |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python start.py` |
| Health Check Path | `/v1/healthz` |
| Python version environment | `PYTHON_VERSION=3.13.5` |

`start.py` Render के `PORT` को पढ़ता है और `0.0.0.0` पर listen करता है। Render में PORT को 8080 force करने की आवश्यकता नहीं। Root Directory `backend` होने पर commands में `backend/` दोबारा न लिखें।

यदि आपने केवल `backend` की **contents** अलग repository में upload की हैं, तो Root Directory **खाली** रखें। उस repository में `bot.py`, `start.py`, `requirements.txt` सीधे root पर होंगे।

Repository root का `render.yaml` एक optional Blueprint है। Manual settings देना भी ठीक है; दोनों विधियाँ एक साथ करके duplicate services न बनाएँ। Blueprint की default compute choice Free है, persistent disk शामिल नहीं है। किसी paid plan को चुनने से पहले उसकी लागत खुद देखें।

### Render environment variables

```dotenv
PYTHON_VERSION=3.13.5
TEAM_NAME=Your Team Name
TEAM_MEMBERS=Your Full Name
CONTACT_EMAIL=your-email@example.com
DB_PATH=data/vera.sqlite3
DEMO_ENABLED=true
DOCS_ENABLED=true
CORS_ORIGINS=*
FRONTEND_URL=
```

पहली connection testing में `CORS_ORIGINS=*` रखा है। Netlify URL मिलने के बाद इसे अपनी exact website origin से बदलें, जैसे:

```dotenv
CORS_ORIGINS=https://my-vera-site.netlify.app
FRONTEND_URL=https://my-vera-site.netlify.app
```

ये example URLs हैं, live project addresses नहीं। Exact origin में `/playground`, `/#api`, trailing slash या quotes न लगाएँ। दो origins के लिए comma इस्तेमाल करें:

```dotenv
CORS_ORIGINS=https://my-vera-site.netlify.app,http://localhost:5500
```

Custom domain लगाते समय उसका origin भी जोड़ें। Preview deployment का hostname अलग हो सकता है; उसे explicitly अनुमति दें या testing के लिए wildcard रखें। CORS browser access control है, authentication नहीं।

`API_TOKEN` को खाली छोड़ने पर challenge/demo writes public हैं। Synthetic test data ही डालें। Token enable करने पर frontend Settings के password field में भरना होगा; evaluator को भी वही auth भेजना आना चाहिए। Token को `config.js` में **कभी नहीं** डालना।

`TEARDOWN_TOKEN` अलग secret है। खाली रहने पर destructive reset endpoint disabled (403) है। UI में database delete button नहीं है। `New session` पुराने backend data को delete नहीं करता।

### Backend deploy होने के बाद

अपना actual Render HTTPS base URL copy करें। उदाहरण:

```text
https://my-vera-api.onrender.com
```

Browser में base URL खोलने पर अब **“Your backend is running”** landing page मिलेगा। `/v1/healthz` पर JSON health, `/v1/metadata` पर team details, और `/docs` पर API explorer मिलेगा। Chat interface अलग Netlify URL पर रहेगा; `FRONTEND_URL` set करने से backend landing page पर उसका link दिखेगा।

## 3. Frontend में केवल एक जगह Render URL paste करें

File खोलें:

```text
frontend/config.js
```

यह line बदलें:

```js
API_BASE_URL: "",
```

अपने backend के actual live base URL से:

```js
API_BASE_URL: "https://my-vera-api.onrender.com",
```

बाकी config जैसा है रहने दें। URL के अंत में `/v1`, `/v1/tick`, `/demo` या `/docs` **नहीं** लगाना। Frontend सभी API paths इसी एक base URL से बनाता है। कोई search-and-replace पूरे project में नहीं करना है।

यह file PUBLIC है, इसलिए केवल URL और display settings ही रखें। Netlify environment में variable डालने भर से static `config.js` नहीं बदलता; इस no-build version में इसी file को edit करके redeploy करें।

### Website Settings वाला alternative

Frontend के “Connect backend” button से URL भी set कर सकते हैं। वह URL केवल **उसी browser** में save होगा। सभी visitors के लिए `config.js` में URL set करके Netlify पर नई deployment करें। पुराना browser override file वाले URL से पहले use होता है। उसे हटाने के लिए Settings → **Use config.js default** → Save & test connection करें।

API token केवल page memory में रहता है; refresh के बाद दोबारा भरें। Backend address edit करने पर पुराना token field साफ होता है ताकि दूसरे host पर secret न चला जाए।

## 4. Frontend को Netlify पर deploy करें

Netlify login करके manual deploy / Drop क्षेत्र में **`frontend` folder** drag-and-drop करें। जिस folder को upload कर रहे हैं, उसके अंदर सीधे `index.html`, `config.js`, `styles.css` और `src` होने चाहिए।

**पूरी project root, backend, .env या database को static site के रूप में publish न करें।**

इस frontend के लिए build command खाली है; `dist` या `build` folder बनाने की आवश्यकता नहीं। Site live होने पर Netlify का public URL खोलें। Site/team visibility settings में public access verify करें।

Git integration इस्तेमाल कर रहे हैं तो repository root वाला `netlify.toml` publish directory `frontend` set करता है। Base directory खाली और build command खाली रखें। यदि केवल frontend contents का अलग repository है, तो publish directory repository root (`.`) होगा।

बाद में Render URL बदलना हो: `frontend/config.js` edit करके इसी frontend folder को Netlify site के Deploys dropzone में दोबारा upload करें। Git deployment हो तो file commit/push करें।

## 5. Interface कैसे use करें?

**Playground:** business, trigger और response language चुनें; Start demo conversation दबाएँ। Backend को category, merchant और trigger भेजे जाते हैं; फिर `/demo/v1/tick` का वास्तविक response दिखता है। Reply type करें या quick reply दबाएँ। STOP पर conversation end होती है। New session नया synthetic recipient बनाता है; पुराने recipient का STOP हटाया नहीं जाता।

**Context editor:** category/merchant/trigger JSON बदलें। Customer outreach के लिए customer object, customer scope और purpose-specific consent चाहिए। Import JSON में top-level `category`, `merchant`, `trigger`, optional `customer` रखें। Custom dates/consent/history अपने-आप नहीं बदलते; expired या unsafe context पर suppression वैध है। Demo session IDs regenerate होते हैं; exact IDs/version testing के लिए API console use करें।

**API console:** सभी पाँच endpoints test कर सकते हैं। Default sandbox database है। Challenge mode के POST requests real evaluation state बदलते हैं; confirmation dialog आता है। Evaluation चल रही हो तब वहाँ writes न करें। Current chat की reply console से भेजने के बजाय chat composer से भेजें ताकि turn count synchronize रहे।

**Export:** chat/context/request log JSON download मिलता है। उसमें आपकी entered data हो सकती है; उसे public share करने से पहले देखें। Refresh पर browser transcript/log हट जाते हैं, backend state अपने आप reset नहीं होती।

Backend बंद या wrong URL होने पर app fake/local replies नहीं बनाती। Connection error दिखता है। Reply response खो जाए तो Retry reply उसी timestamp/body/turn number को भेजता है। Tick दोबारा भेजने पर dedup के कारण empty actions आ सकती हैं; नए demo के लिए New session दबाएँ।

## 6. Netlify और Render के URL का फर्क

```text
Netlify URL  → इंसान interface/chat देखने के लिए खोलेंगे
Render URL   → frontend APIs call करेगा; challenge judge इसी URL को call करेगा
```

Original challenge submission में **Render base URL** दें, Netlify URL नहीं। पाँच required routes:

```text
POST /v1/context
POST /v1/tick
POST /v1/reply
GET  /v1/healthz
GET  /v1/metadata
```

Frontend chat अतिरिक्त `/demo/v1/...` endpoints use करती है। उनका database अलग है, इसलिए ordinary sandbox testing judge state को modify नहीं करती। Demo endpoints public sandbox हैं, हर visitor के लिए private account system नहीं है।

## 7. Render Free की storage limitation — महत्वपूर्ण

Render के official docs के अनुसार Free Web Service 15 मिनट idle रहने पर sleep हो सकती है और wake-up लगभग एक मिनट ले सकता है। Restart, redeploy या spin-down पर local files/SQLite data मिटता है। Free web service में persistent disk attach नहीं होता। यह package उन platform limits को bypass नहीं करता।

इसलिए quick demo के लिए Free चल सकता है, लेकिन retained conversation state और cold-start-sensitive evaluation के लिए वही configuration पर्याप्त नहीं है। Durable SQLite रखने का इस package में supported setup:

1. Render में अपने चुने हुए paid Web Service compute plan पर जाएँ। लागत provider dashboard में check करें।
2. Persistent disk attach करें; mount path `/var/data` रखें।
3. `DB_PATH=/var/data/vera.sqlite3` set करें। `DEMO_DB_PATH` खाली रहने दें; demo file इसी disk पर `vera.sqlite3.demo` बनेगी।
4. One instance और one worker रखें। Default `start.py` यही करता है।

**केवल DB_PATH बदलना या केवल paid compute चुनना data durable नहीं बनाता; path के नीचे actual persistent disk attached होना जरूरी है।** पुराने ephemeral database का auto migration इस code में नहीं है। Backup/migration आवश्यक हो तो पुराने data को सुरक्षित तरीके से अलग migrate करें। PostgreSQL adapter इस ZIP में implement नहीं है; सिर्फ DATABASE_URL डालने से engine PostgreSQL use नहीं करेगा।

App में `STATE_TTL_HOURS=24` default lazy inactivity cleanup भी है। Storage persistent होने पर भी लगातार 24 घंटे inactivity के बाद अगला write पुराने evaluation state को साफ कर सकता है। यह per-record daily scheduler नहीं है। आवश्यकता के अनुसार environment value (1–168 hours) बदलें। Public demo पर unlimited traffic/multi-user security का दावा नहीं है।

Sources: https://render.com/docs/free ; https://render.com/docs/disks

## 8. Local testing — Mac/Linux

पहला terminal, project root से:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python start.py
```

दूसरा terminal, project root से:

```bash
python3 -m http.server 5500 --directory frontend
```

Open `http://localhost:5500`। Backend `http://localhost:8080` होगा। `index.html` को double-click करके file:// पर न खोलें।

8080 busy हो तो backend को `PORT=8097 python start.py` से चलाएँ और frontend Settings में `http://localhost:8097` set करें। यह केवल local example है; public Netlify को हमेशा HTTPS Render URL दें।

## 9. Windows PowerShell

पहला terminal:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python start.py
```

Activation blocked हो तो execution policy बदलना आवश्यक नहीं; सीधे venv Python use करें:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start.py
```

दूसरा terminal, project root से:

```powershell
py -m http.server 5500 --directory frontend
```

## 10. Tests

```bash
# backend folder में:
pip install -r requirements-dev.txt
python -m pytest -q

# project root में; Node केवल test के लिए:
node --test tests/frontend.test.mjs

# running backend के sandbox पर:
python3 scripts/smoke_check.py --base-url http://localhost:8080
```

Results और exact testing limitations: `docs/TEST_REPORT.md`। Cloud deployment या public URL इस package के साथ नहीं बनाया गया।

## 11. Common errors

| Problem | क्या check करें |
|---|---|
| Frontend खुल रहा है, reply नहीं | `config.js` URL, Render service, CORS और DEMO_ENABLED check करें |
| `/demo/v1/...` पर 404 | इसी ZIP वाला updated backend deploy करें; DEMO_ENABLED=true रखें |
| केवल backend page/JSON दिख रहा है | Interface वाला Netlify URL खोलें; backend app अलग है |
| `requirements.txt` नहीं मिल रही | Whole repo के लिए Render Root Directory `backend` होना चाहिए |
| `ModuleNotFoundError: vera` | केवल bot.py नहीं; पूरा backend folder deploy करें |
| CORS error | exact HTTPS Netlify origin allowed हो; redeploy/config propagation के बाद test करें |
| 401 | API_TOKEN enabled है; Settings password में correct token भरें |
| Wrong URL/Mixed content | Netlify HTTPS से HTTP localhost नहीं चलेगा; public HTTPS Render URL दें |
| Config बदला, पुराना URL चल रहा | Settings में Use config.js default दबाएँ; फिर reload/reconnect करें |
| 409 | same context का lower version या same reply turn का changed body; valid higher version/new session लें |
| No action/suppressed | missing facts, expiry, consent, STOP या dedup हो सकता है; यह network error जरूरी नहीं |
| Redeploy के बाद context missing | Free/ephemeral SQLite खो सकता है; new demo शुरू करें या durable disk setup करें |
| Netlify 404/blank | upload folder में सीधे index.html और पूरा src मौजूद हो; browser console देखें |
| Public site login माँग रही | Netlify site/team visibility को review करें |

## 12. Scope

No paid AI key required. Rule-based Hindi/Hinglish/English templates हैं, unrestricted LLM conversation या complete translation service नहीं। Real WhatsApp delivery, GBP publishing, completed bookings और production multi-tenant login included नहीं हैं। यह independent challenge project है, official magicpin service नहीं। Original challenge material को अपना independently written work बताकर प्रस्तुत न करें; rules/attribution review करें।

Provider documentation checked on 2026-09-22:
- https://render.com/docs/deploy-fastapi
- https://render.com/docs/free
- https://render.com/docs/disks
- https://docs.netlify.com/deploy/create-deploys/
- https://fastapi.tiangolo.com/tutorial/cors/
