"""
SCORM Packager — Builds SCORM 1.2 and SCORM 2004 (4th Edition) compliant ZIP packages.

SCORM 1.2 structure:
  imsmanifest.xml
  shared/
    api.js           ← SCORM 1.2 API shim
    style.css
  lesson-<n>/
    index.html       ← slide player HTML
    content.json     ← slide data
    audio/           ← TTS narration MP3s
  quiz-<n>/
    index.html       ← quiz player HTML
    quiz.json        ← questions JSON

SCORM 2004 additionally includes:
  adlcp_rootv1p2.xsd / imsmd_rootv1p2p1.xsd schemata references
  sequencing rules in imsmanifest.xml
"""

import os
import io
import json
import zipfile
import uuid
from datetime import datetime
from typing import Optional
from xml.etree.ElementTree import (
    Element, SubElement, tostring, indent
)


# ── SCORM 1.2 API shim (minimal, browser-side) ────────────────────────────────
SCORM_12_API_JS = r"""
var API = {
  _data: {},
  _initialized: false,
  _finished: false,

  LMSInitialize: function(s) {
    this._initialized = true;
    this._data["cmi.core.lesson_status"] = "incomplete";
    this._data["cmi.core.score.raw"] = "";
    this._data["cmi.suspend_data"] = "";
    return "true";
  },
  LMSGetValue: function(e) { return this._data[e] || ""; },
  LMSSetValue: function(e, v) {
    this._data[e] = v;
    if (e === "cmi.core.lesson_status") {
      parent.postMessage({type:"scorm_status", value:v}, "*");
    }
    if (e === "cmi.core.score.raw") {
      parent.postMessage({type:"scorm_score", value:v}, "*");
    }
    return "true";
  },
  LMSCommit: function(s) { return "true"; },
  LMSFinish: function(s) {
    this._finished = true;
    parent.postMessage({type:"scorm_finish"}, "*");
    return "true";
  },
  LMSGetLastError: function() { return "0"; },
  LMSGetErrorString: function(e) { return ""; },
  LMSGetDiagnostic: function(e) { return ""; }
};
window.API = API;
"""

# ── SCORM 2004 API shim ────────────────────────────────────────────────────────
SCORM_2004_API_JS = r"""
var API_1484_11 = {
  _data: {},
  _initialized: false,
  _finished: false,

  Initialize: function(s) {
    this._initialized = true;
    this._data["cmi.completion_status"] = "incomplete";
    this._data["cmi.success_status"] = "unknown";
    this._data["cmi.score.raw"] = "";
    this._data["cmi.score.scaled"] = "";
    this._data["cmi.suspend_data"] = "";
    return "true";
  },
  GetValue: function(e) { return this._data[e] !== undefined ? this._data[e] : ""; },
  SetValue: function(e, v) {
    this._data[e] = v;
    if (e === "cmi.completion_status" || e === "cmi.success_status") {
      parent.postMessage({type:"scorm_status", key:e, value:v}, "*");
    }
    if (e === "cmi.score.raw") {
      parent.postMessage({type:"scorm_score", value:v}, "*");
    }
    return "true";
  },
  Commit: function(s) { return "true"; },
  Terminate: function(s) {
    this._finished = true;
    parent.postMessage({type:"scorm_finish"}, "*");
    return "true";
  },
  GetLastError: function() { return "0"; },
  GetErrorString: function(e) { return ""; },
  GetDiagnostic: function(e) { return ""; }
};
window.API_1484_11 = API_1484_11;
"""

# ── Shared CSS ─────────────────────────────────────────────────────────────────
SHARED_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 15px;
       line-height: 1.6; color: #1f2328; background: #ffffff; overflow: hidden; }
.slide-container { width: 100vw; height: 100vh; display: flex; flex-direction: column; }
.slide-header { background: #1e2761; color: #fff; padding: 16px 28px; font-size: 20px; font-weight: 700; }
.slide-body { flex: 1; padding: 28px 40px; overflow-y: auto; }
.slide-body ul { padding-left: 24px; }
.slide-body li { margin-bottom: 8px; font-size: 16px; }
.slide-body p { margin-bottom: 12px; font-size: 15px; }
.slide-nav { background: #f7f8fa; border-top: 1px solid #e5e7eb; padding: 12px 24px;
             display: flex; justify-content: space-between; align-items: center; }
.btn { background: #1e2761; color: #fff; border: none; padding: 10px 22px;
       border-radius: 5px; cursor: pointer; font-size: 14px; font-weight: 600; }
.btn:hover { background: #2d3a8c; }
.btn:disabled { background: #94a3b8; cursor: not-allowed; }
.progress-bar { height: 4px; background: #e5e7eb; position: fixed; top: 0; left: 0; right: 0; z-index: 100; }
.progress-fill { height: 100%; background: #3b82d4; transition: width 0.3s; }
.slide-count { font-size: 13px; color: #57606a; }
"""

# ── Lesson player HTML ─────────────────────────────────────────────────────────
LESSON_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{lesson_title}</title>
<link rel="stylesheet" href="../shared/style.css">
<script src="../shared/api.js"></script>
</head>
<body>
<div class="progress-bar"><div class="progress-fill" id="pb" style="width:0%"></div></div>
<div class="slide-container">
  <div class="slide-header" id="slide-title">Loading...</div>
  <div class="slide-body" id="slide-body"></div>
  <div class="slide-nav">
    <button class="btn" id="btn-prev" onclick="prevSlide()" disabled>← Previous</button>
    <span class="slide-count" id="slide-count"></span>
    <button class="btn" id="btn-next" onclick="nextSlide()">Next →</button>
  </div>
</div>
<audio id="narration" hidden></audio>
<script>
const slides = {slides_json};
let current = 0;

function initSCORM() {{
  if (typeof API !== 'undefined') {{
    API.LMSInitialize("");
    API.LMSSetValue("cmi.core.lesson_status", "incomplete");
  }} else if (typeof API_1484_11 !== 'undefined') {{
    API_1484_11.Initialize("");
    API_1484_11.SetValue("cmi.completion_status", "incomplete");
  }}
}}

function completeSCORM() {{
  if (typeof API !== 'undefined') {{
    API.LMSSetValue("cmi.core.lesson_status", "completed");
    API.LMSSetValue("cmi.core.score.raw", "100");
    API.LMSFinish("");
  }} else if (typeof API_1484_11 !== 'undefined') {{
    API_1484_11.SetValue("cmi.completion_status", "completed");
    API_1484_11.SetValue("cmi.success_status", "passed");
    API_1484_11.SetValue("cmi.score.raw", "100");
    API_1484_11.Terminate("");
  }}
}}

function renderSlide(n) {{
  const s = slides[n];
  document.getElementById('slide-title').textContent = s.title;
  document.getElementById('slide-body').innerHTML = '<p>' + s.body.split('\\n').join('</p><p>') + '</p>';
  document.getElementById('slide-count').textContent = (n+1) + ' / ' + slides.length;
  document.getElementById('pb').style.width = ((n+1)/slides.length*100) + '%';
  document.getElementById('btn-prev').disabled = n === 0;
  document.getElementById('btn-next').textContent = n === slides.length-1 ? 'Finish ✓' : 'Next →';
  if (s.audio_url) {{
    const aud = document.getElementById('narration');
    aud.src = s.audio_url; aud.play().catch(()=>{{}});
  }}
}}

function nextSlide() {{
  if (current < slides.length - 1) {{ current++; renderSlide(current); }}
  else {{ completeSCORM(); }}
}}
function prevSlide() {{ if (current > 0) {{ current--; renderSlide(current); }} }}

window.onload = function() {{ initSCORM(); renderSlide(0); }};
</script>
</body>
</html>
"""

# ── Quiz player HTML ───────────────────────────────────────────────────────────
QUIZ_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{quiz_title}</title>
<link rel="stylesheet" href="../shared/style.css">
<script src="../shared/api.js"></script>
<style>
.quiz-wrap {{ max-width: 700px; margin: 0 auto; padding: 32px 20px; }}
.question {{ background: #f7f8fa; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
.question h3 {{ font-size: 15px; margin-bottom: 14px; color: #1f2328; }}
.option {{ display: flex; align-items: flex-start; gap: 10px; padding: 10px; border-radius: 5px;
           cursor: pointer; margin-bottom: 6px; border: 1px solid #e5e7eb; background: #fff; }}
.option:hover {{ background: #eff6ff; border-color: #3b82d4; }}
.option.correct {{ background: #d1fae5; border-color: #16a34a; }}
.option.wrong {{ background: #fee2e2; border-color: #dc2626; }}
.explanation {{ font-size: 13px; color: #57606a; margin-top: 10px; padding: 8px; background: #f0fdf4;
               border-left: 3px solid #16a34a; border-radius: 0 5px 5px 0; display: none; }}
.score-box {{ text-align: center; padding: 40px; }}
.score-big {{ font-size: 64px; font-weight: 700; color: #1e2761; }}
</style>
</head>
<body>
<div class="quiz-wrap">
  <h2 style="color:#1e2761; margin-bottom:20px;">{quiz_title}</h2>
  <div id="quiz-content"></div>
  <button class="btn" id="submit-btn" onclick="submitQuiz()" style="margin-top:16px;">Submit Answers</button>
</div>
<script>
const quiz = {quiz_json};
let answered = {{}};

function initSCORM() {{
  if (typeof API !== 'undefined') API.LMSInitialize("");
  else if (typeof API_1484_11 !== 'undefined') API_1484_11.Initialize("");
}}

function submitSCORM(score, passed) {{
  const s = String(Math.round(score));
  if (typeof API !== 'undefined') {{
    API.LMSSetValue("cmi.core.score.raw", s);
    API.LMSSetValue("cmi.core.lesson_status", passed ? "passed" : "failed");
    API.LMSFinish("");
  }} else if (typeof API_1484_11 !== 'undefined') {{
    API_1484_11.SetValue("cmi.score.raw", s);
    API_1484_11.SetValue("cmi.score.scaled", String((score/100).toFixed(2)));
    API_1484_11.SetValue("cmi.success_status", passed ? "passed" : "failed");
    API_1484_11.SetValue("cmi.completion_status", "completed");
    API_1484_11.Terminate("");
  }}
}}

function renderQuiz() {{
  let html = '';
  quiz.questions.forEach((q, qi) => {{
    html += '<div class="question"><h3>Q' + (qi+1) + '. ' + q.question_text + '</h3>';
    q.options.forEach(opt => {{
      html += '<div class="option" id="opt-'+qi+'-'+opt.id+'" onclick="selectOpt('+qi+',\\''+opt.id+'\\')">' +
              '<b>' + opt.id.toUpperCase() + '.</b> ' + opt.text + '</div>';
    }});
    html += '<div class="explanation" id="exp-'+qi+'">'+q.explanation+'</div></div>';
  }});
  document.getElementById('quiz-content').innerHTML = html;
}}

function selectOpt(qi, oid) {{
  answered[qi] = oid;
  quiz.questions[qi].options.forEach(o => {{
    document.getElementById('opt-'+qi+'-'+o.id).style.background = '';
    document.getElementById('opt-'+qi+'-'+o.id).style.border = '';
  }});
  document.getElementById('opt-'+qi+'-'+oid).style.background = '#dbeafe';
  document.getElementById('opt-'+qi+'-'+oid).style.border = '2px solid #3b82d4';
}}

function submitQuiz() {{
  let correct = 0;
  quiz.questions.forEach((q, qi) => {{
    const chosen = answered[qi];
    const correct_opt = q.options.find(o => o.correct);
    document.getElementById('exp-'+qi).style.display = 'block';
    if (chosen) {{
      const el = document.getElementById('opt-'+qi+'-'+chosen);
      if (chosen === correct_opt.id) {{ el.className = 'option correct'; correct++; }}
      else {{ el.className = 'option wrong'; document.getElementById('opt-'+qi+'-'+correct_opt.id).className = 'option correct'; }}
    }}
  }});
  const score = Math.round((correct / quiz.questions.length) * 100);
  const passed = score >= {passing_score};
  document.getElementById('submit-btn').style.display = 'none';
  document.getElementById('quiz-content').innerHTML += '<div class="score-box"><div class="score-big">' + score + '%</div>' +
    '<p style="font-size:18px; margin-top:8px;">' + (passed ? '✅ Passed!' : '❌ Not quite — review and retry') + '</p></div>';
  submitSCORM(score, passed);
}}

window.onload = function() {{ initSCORM(); renderQuiz(); }};
</script>
</body>
</html>
"""


# ── Main packager ──────────────────────────────────────────────────────────────

class SCORMPackager:
    """
    Builds a SCORM 1.2 or 2004 ZIP from course data.

    Usage:
        packager = SCORMPackager(course_data, scorm_version="2004")
        zip_bytes = await packager.build()
    """

    def __init__(self, course_data: dict, scorm_version: str = "2004",
                 org_name: str = "i3 Technologies", language: str = "en"):
        self.course = course_data
        self.version = scorm_version          # "1.2" or "2004"
        self.org_name = org_name
        self.lang = language
        self.course_id = course_data.get("id", str(uuid.uuid4()))
        self.buf = io.BytesIO()
        self.zf = zipfile.ZipFile(self.buf, mode="w", compression=zipfile.ZIP_DEFLATED)

    def _write(self, path: str, data: str | bytes):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.zf.writestr(path, data)

    def _build_manifest_12(self) -> str:
        """Build imsmanifest.xml for SCORM 1.2."""
        manifest = Element("manifest", {
            "identifier": f"i3-{self.course_id}",
            "version": "1.0",
            "xmlns": "http://www.imsproject.org/xsd/imscp_rootv1p1p2",
            "xmlns:adlcp": "http://www.adlnet.org/xsd/adlcp_rootv1p2",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": (
                "http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd "
                "http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd"
            ),
        })

        # Metadata
        meta = SubElement(manifest, "metadata")
        SubElement(meta, "schema").text = "ADL SCORM"
        SubElement(meta, "schemaversion").text = "1.2"

        # Organizations
        orgs = SubElement(manifest, "organizations", {"default": f"org-{self.course_id}"})
        org = SubElement(orgs, "organization", {"identifier": f"org-{self.course_id}"})
        SubElement(org, "title").text = self.course["title"]

        # Items — one per lesson + quiz
        resources = SubElement(manifest, "resources")
        item_idx = 1

        for mod_i, mod in enumerate(self.course.get("modules", [])):
            mod_item = SubElement(org, "item", {
                "identifier": f"mod-{mod_i+1}",
                "isvisible": "true",
            })
            SubElement(mod_item, "title").text = mod["title"]

            for les_i, lesson in enumerate(mod.get("lessons", [])):
                les_id = f"lesson-{mod_i+1}-{les_i+1}"
                les_item = SubElement(mod_item, "item", {
                    "identifier": f"item-{les_id}",
                    "identifierref": f"res-{les_id}",
                    "isvisible": "true",
                })
                SubElement(les_item, "title").text = lesson["title"]
                # adlcp:masteryscore
                SubElement(les_item, "adlcp:masteryscore").text = "80"

                SubElement(resources, "resource", {
                    "identifier": f"res-{les_id}",
                    "type": "webcontent",
                    "adlcp:scormtype": "sco",
                    "href": f"{les_id}/index.html",
                })
                item_idx += 1

                # Quiz item
                if lesson.get("quiz"):
                    qid = f"quiz-{mod_i+1}-{les_i+1}"
                    q_item = SubElement(mod_item, "item", {
                        "identifier": f"item-{qid}",
                        "identifierref": f"res-{qid}",
                        "isvisible": "true",
                    })
                    SubElement(q_item, "title").text = lesson["quiz"]["title"]
                    SubElement(q_item, "adlcp:masteryscore").text = "80"
                    SubElement(resources, "resource", {
                        "identifier": f"res-{qid}",
                        "type": "webcontent",
                        "adlcp:scormtype": "sco",
                        "href": f"{qid}/index.html",
                    })

        # Shared resources
        SubElement(resources, "resource", {
            "identifier": "res-shared",
            "type": "webcontent",
            "adlcp:scormtype": "asset",
            "href": "shared/api.js",
        })

        indent(manifest, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(manifest, encoding="unicode")

    def _build_manifest_2004(self) -> str:
        """Build imsmanifest.xml for SCORM 2004 4th Edition."""
        manifest = Element("manifest", {
            "identifier": f"i3-{self.course_id}",
            "version": "1",
            "xmlns": "http://www.imsglobal.org/xsd/imscp_v1p1",
            "xmlns:adlcp": "http://www.adlnet.org/xsd/adlcp_v1p3p2",
            "xmlns:adlseq": "http://www.adlnet.org/xsd/adlseq_v1p3p2",
            "xmlns:adlnav": "http://www.adlnet.org/xsd/adlnav_v1p3p2",
            "xmlns:imsss": "http://www.imsglobal.org/xsd/imsss",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": (
                "http://www.imsglobal.org/xsd/imscp_v1p1 imscp_v1p1.xsd "
                "http://www.adlnet.org/xsd/adlcp_v1p3p2 adlcp_v1p3p2.xsd"
            ),
        })

        meta = SubElement(manifest, "metadata")
        SubElement(meta, "schema").text = "ADL SCORM"
        SubElement(meta, "schemaversion").text = "2004 4th Edition"

        orgs = SubElement(manifest, "organizations", {"default": f"org-{self.course_id}"})
        org = SubElement(orgs, "organization", {
            "identifier": f"org-{self.course_id}",
            "adlseq:objectivesGlobalToSystem": "false",
        })
        SubElement(org, "title").text = self.course["title"]

        resources = SubElement(manifest, "resources")

        for mod_i, mod in enumerate(self.course.get("modules", [])):
            mod_item = SubElement(org, "item", {
                "identifier": f"mod-{mod_i+1}",
                "isvisible": "true",
            })
            SubElement(mod_item, "title").text = mod["title"]

            for les_i, lesson in enumerate(mod.get("lessons", [])):
                les_id = f"lesson-{mod_i+1}-{les_i+1}"
                les_item = SubElement(mod_item, "item", {
                    "identifier": f"item-{les_id}",
                    "identifierref": f"res-{les_id}",
                    "isvisible": "true",
                })
                SubElement(les_item, "title").text = lesson["title"]

                # SCORM 2004 sequencing
                seq = SubElement(les_item, "imsss:sequencing")
                objectives = SubElement(seq, "imsss:objectives")
                pobj = SubElement(objectives, "imsss:primaryObjective", {
                    "objectiveID": f"obj-{les_id}",
                    "satisfiedByMeasure": "true",
                })
                SubElement(pobj, "imsss:minNormalizedMeasure").text = "0.8"

                SubElement(resources, "resource", {
                    "identifier": f"res-{les_id}",
                    "type": "webcontent",
                    "adlcp:scormType": "sco",
                    "href": f"{les_id}/index.html",
                })

                if lesson.get("quiz"):
                    qid = f"quiz-{mod_i+1}-{les_i+1}"
                    q_item = SubElement(mod_item, "item", {
                        "identifier": f"item-{qid}",
                        "identifierref": f"res-{qid}",
                        "isvisible": "true",
                    })
                    SubElement(q_item, "title").text = lesson["quiz"]["title"]
                    q_seq = SubElement(q_item, "imsss:sequencing")
                    q_obj = SubElement(q_seq, "imsss:objectives")
                    q_pobj = SubElement(q_obj, "imsss:primaryObjective", {
                        "objectiveID": f"obj-{qid}",
                        "satisfiedByMeasure": "true",
                    })
                    SubElement(q_pobj, "imsss:minNormalizedMeasure").text = "0.8"
                    SubElement(resources, "resource", {
                        "identifier": f"res-{qid}",
                        "type": "webcontent",
                        "adlcp:scormType": "sco",
                        "href": f"{qid}/index.html",
                    })

        indent(manifest, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(manifest, encoding="unicode")

    def _write_shared(self):
        """Write shared API shim + CSS."""
        api_js = SCORM_12_API_JS if self.version == "1.2" else SCORM_2004_API_JS
        # Include both for maximum LMS compatibility
        combined = SCORM_12_API_JS + "\n" + SCORM_2004_API_JS
        self._write("shared/api.js", combined)
        self._write("shared/style.css", SHARED_CSS)

    def _write_lesson(self, mod_i: int, les_i: int, lesson: dict):
        """Write lesson player HTML + content.json."""
        les_id = f"lesson-{mod_i+1}-{les_i+1}"
        slides = lesson.get("slides", [])

        # Build slide data for JS
        slide_data = []
        for s_i, s in enumerate(slides):
            slide_data.append({
                "title":     s.get("title", f"Slide {s_i+1}"),
                "body":      s.get("body", ""),
                "audio_url": f"audio/slide-{s_i+1}.mp3" if s.get("has_audio") else "",
            })

        html = LESSON_HTML_TEMPLATE.format(
            lang=self.lang,
            lesson_title=lesson["title"],
            slides_json=json.dumps(slide_data, ensure_ascii=False),
        )
        self._write(f"{les_id}/index.html", html)
        self._write(f"{les_id}/content.json", json.dumps(lesson, ensure_ascii=False, indent=2))

    def _write_quiz(self, mod_i: int, les_i: int, quiz: dict):
        """Write quiz player HTML + quiz.json."""
        qid = f"quiz-{mod_i+1}-{les_i+1}"
        html = QUIZ_HTML_TEMPLATE.format(
            lang=self.lang,
            quiz_title=quiz.get("title", "Knowledge Check"),
            quiz_json=json.dumps(quiz, ensure_ascii=False),
            passing_score=quiz.get("passing_score", 80),
        )
        self._write(f"{qid}/index.html", html)
        self._write(f"{qid}/quiz.json", json.dumps(quiz, ensure_ascii=False, indent=2))

    def build(self) -> bytes:
        """
        Assemble and return the SCORM ZIP as bytes.
        Caller is responsible for uploading to SeaweedFS S3.
        """
        # 1. Manifest
        if self.version == "1.2":
            manifest_xml = self._build_manifest_12()
        else:
            manifest_xml = self._build_manifest_2004()
        self._write("imsmanifest.xml", manifest_xml)

        # 2. Shared assets
        self._write_shared()

        # 3. Lessons + quizzes
        for mod_i, mod in enumerate(self.course.get("modules", [])):
            for les_i, lesson in enumerate(mod.get("lessons", [])):
                self._write_lesson(mod_i, les_i, lesson)
                if lesson.get("quiz"):
                    self._write_quiz(mod_i, les_i, lesson["quiz"])

        # 4. Course metadata
        self._write("metadata.json", json.dumps({
            "id":       self.course_id,
            "title":    self.course["title"],
            "version":  self.version,
            "created":  datetime.utcnow().isoformat() + "Z",
            "org":      self.org_name,
        }, indent=2))

        self.zf.close()
        return self.buf.getvalue()


def build_scorm_package(course_data: dict, scorm_version: str = "2004",
                         org_name: str = "i3 Technologies", language: str = "en") -> bytes:
    """Convenience wrapper — builds and returns SCORM ZIP bytes."""
    p = SCORMPackager(course_data, scorm_version, org_name, language)
    return p.build()
