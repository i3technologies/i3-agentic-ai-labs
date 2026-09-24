# EvalOS — User Guide

> **Platform:** EvalOS by i3 Technologies Limited  
> **URL:** https://evalos.i3technologies.co.ke  
> **Version:** Phases 1, 2 & 3

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Taking Exams](#2-taking-exams)
3. [Understanding Your Results](#3-understanding-your-results)
4. [Study Coach](#4-study-coach)
5. [AI Interview Practice](#5-ai-interview-practice)
6. [Coding Lab](#6-coding-lab)
7. [Certification Readiness (CertReady)](#7-certification-readiness-certready)
8. [Digital Badges & Credentials](#8-digital-badges--credentials)
9. [Skills Passport](#9-skills-passport)
10. [Assessment Marketplace](#10-assessment-marketplace)
11. [AI Engineering Assessment Mode](#11-ai-engineering-assessment-mode)
12. [Frequently Asked Questions](#12-frequently-asked-questions)

---

## 1. Getting Started

### 1.1 Signing In

1. Open **https://evalos.i3technologies.co.ke** in your browser.
2. Click **Sign In with i3 Account**. You are redirected to the i3 Keycloak SSO page.
3. Enter your i3 email and password. Complete MFA if enabled on your account.
4. You land on your **Dashboard**, which shows available exams, recent scores, and earned credentials.

> Your session lasts 8 hours. You will be asked to sign in again after that period.

### 1.2 Dashboard Overview

| Section | What you see |
|---|---|
| Available Exams | All published exams you are eligible to attempt. Locked exams display the prerequisite requirement. |
| Recent Attempts | Your last 10 attempts with score, pass/fail status, and links to results. |
| Credentials | Earned digital badges with verification codes. |
| Leaderboard | Top performers across your cohort (anonymized). |

---

## 2. Taking Exams

### 2.1 Starting an Exam

1. Click an exam card on your Dashboard.
2. Read the instructions — note the **time limit**, **pass threshold**, and **attempts remaining**.
3. Click **Start Exam**. The timer begins immediately.
4. For **Single Choice (SC)** questions: select one option.  
   For **Multiple Response (MR)** questions: select all correct options (2–3 answers).
5. Your answers save automatically as you go. You can change answers before submitting.
6. When done, click **Submit Exam** → confirm in the prompt.

### 2.2 Attempt Rules

| Rule | Detail |
|---|---|
| Attempt limit | Default 5 per exam. Remaining count shown on the exam card. |
| Pass threshold | Typically 70%. IBM watsonx sets require 68–90%. Always shown on the exam page. |
| Prerequisites | Some exams require passing an earlier set first. A lock icon shows the required exam. |
| Resume | If you lose connection, resume the in-progress attempt within 30 minutes by reopening the exam link. |
| Time limit | Countdown timer is always visible. When it reaches zero, answers are automatically submitted. |

### 2.3 Integrity Monitoring

EvalOS monitors sessions to protect the value of your credential. Monitoring is **proportionate and explainable** — it flags unusual patterns for human review, never for automatic penalty.

| What is monitored | Why |
|---|---|
| Tab switches | Indicates possible reference to external materials |
| Fullscreen exits | Indicates possible screen sharing or looking up answers |
| Clipboard use | Copy/paste of question or answer text |
| Device binding | The device you start on is recorded; changing devices mid-exam raises a review flag |

> **Your rights:** A human reviewer (not an algorithm) makes all final decisions about flagged sessions. You will be contacted if your session requires review, and you have the right to appeal.

---

## 3. Understanding Your Results

### 3.1 Score Report

After submitting you see:

- **Overall score** — percentage and raw correct/total
- **Pass / Fail** — relative to the exam threshold
- **Domain Breakdown** — your score in each topic area
- **Performance Band** — see table below

### 3.2 Performance Bands

| Band | Score Range | What it means |
|---|---|---|
| **EXCEPTIONAL** | ≥ 95% | Outstanding mastery — fast-track admission / immediate certification recommendation |
| **PRODUCTION_READY** | 80–94% | Strong working knowledge — ready for the certification exam |
| **EMERGING** | 65–79% | Good foundation with targeted gaps — study plan recommended |
| **DEVELOPING** | 50–64% | Core concepts need reinforcement — follow the Study Coach plan |
| **NOT_READY** | < 50% | Fundamental review required before retaking |

---

## 4. Study Coach

After any graded attempt the **Study Coach** generates a personalized report powered by i3's on-cluster AI (Qwen). It identifies your weakest domains and provides a targeted 3-day study plan.

### What the Study Coach gives you

- Overall assessment in 2 sentences
- 2 concrete tips per weak domain, referencing specific IBM concepts and features
- Key misconceptions identified from your wrong answers
- A 3-day study plan with daily concrete tasks
- Personalized encouragement

### How to access

Results page → click **Get Study Coach Report**. Generation takes 15–30 seconds.

> The Study Coach resets context with each attempt. Memory-aware coaching (persistent across attempts) is being introduced in Phase 2.

---

## 5. AI Interview Practice

The **AI Interview** section lets you practice behavioral and technical questions with instant AI evaluation and structured feedback.

### 5.1 Question Types

| Type | Format | How it's evaluated |
|---|---|---|
| Text | Open-ended behavioral or conceptual questions | AI scorer checks coverage, accuracy, IBM terminology, and depth against a rubric |
| Code | Monaco editor with language selector | AI code reviewer checks correctness, approach, edge cases, and code quality |

### 5.2 Scoring

| Score Range | Meaning |
|---|---|
| 90–100 | All rubric points covered with accurate terminology |
| 70–89 | Most points covered, minor gaps or imprecision |
| 50–69 | Core concept present but important details missing |
| 30–49 | Partially correct, significant gaps |
| 0–29 | Fundamentally incorrect or no substantive answer |

A score of 60 or above is considered passing for interview questions.

---

## 6. Coding Lab

The Coding Lab provides a Monaco editor (VS Code-style) with direct code execution on the secure EvalOS sandbox cluster.

### Supported Languages

Python · JavaScript · TypeScript · Go · Java · SQL · Bash

### Key Features

- Write and run code directly in the browser
- Code is executed in an isolated container — no external network access
- AI review powered by Qwen Coder provides hints and feedback
- All execution environments are ephemeral — disposed of after evaluation

> **Important:** Do not include API keys, passwords, or personally identifiable information in your code submissions. Code may be reviewed by AI agents and human evaluators.

---

## 7. Certification Readiness (CertReady)

After completing a graded exam, check your **Certification Readiness** — a prediction of your likelihood of passing the real IBM certification exam.

### Readiness Bands

| Band | Predicted Pass Probability | Recommendation |
|---|---|---|
| **READY** | ≥ 70% | Book the certification exam now |
| **ALMOST_READY** | 55–69% | Focus 2–3 hours on weak domains, then retake |
| **NEEDS_PREPARATION** | 35–54% | Complete 2 more full practice sets first |
| **NOT_READY** | < 35% | Review fundamentals from the IBM study guide |

### How to access

Results page → **Check Certification Readiness**

Each readiness report also provides a list of concrete **Next Actions** specific to your weak domains.

---

## 8. Digital Badges & Credentials

When you pass an exam above the badge threshold, you can claim an **Open Badges 3.0** verifiable digital credential.

### Claiming a Badge

1. On your results page, click **Claim My Badge** (only visible if your score meets the minimum).
2. Your credential is issued instantly. You receive a **Verification Code** and a **Verify URL**.
3. Share the Verify URL on LinkedIn, your CV, or with employers. Anyone can verify authenticity.
4. Download the full Open Badges 3.0 JSON-LD credential for import into wallet apps (Badgr, Credly).

### Current Badges Available

| Badge | Minimum Score | Based On |
|---|---|---|
| IBM watsonx Orchestrate AI Engineer Associate | 70% | C1000-207 practice exam sets |

### Credential Validity

Credentials are valid for **3 years** from issuance date. Renewal requires retaking the assessment. Revoked credentials are marked invalid at the verification URL immediately.

---

## 9. Skills Passport

Your **Skills Passport** is your portable professional identity — a longitudinal record of every skill demonstrated across all assessments, labs, and certifications on EvalOS.

### What it contains

| Section | Content |
|---|---|
| Skill Proficiency | Multi-dimensional score per skill (0–100) across competency, technology, and sub-skill levels |
| Credentials | All verified digital badges earned, with issue dates and verification links |
| Lab Evidence | Practical evidence artifacts from coding labs (Phase 3) |
| Employability | Matching programmes and roles based on your evidence profile |
| Overall Tier | BEGINNER → INTERMEDIATE → ADVANCED → EXPERT |

### Sharing your Passport

From your Passport page → click **Make Public**. A unique share token is generated — share this URL with employers or admissions offices.

> Your passport is **private by default**. Public visibility is entirely opt-in and can be reversed at any time from your account settings.

---

## 10. Assessment Marketplace

The EvalOS Marketplace is a library of community-authored and specialist assessments beyond the core i3 curriculum.

### Browsing and Purchasing

- Filter by skill tag, difficulty level, or price
- Free assessments are immediately accessible
- Paid assessments can be purchased via M-Pesa, card, or institutional billing

### Publishing Your Own Assessment

Any registered author can:

1. Create a draft listing via the Marketplace page → **Create Assessment**
2. Submit for i3 content review (typically 5 business days)
3. Earn **75%** of each sale once published

---

## 11. AI Engineering Assessment Mode

EvalOS offers three exam tiers that measure different aspects of engineering ability in the AI era:

| Mode | AI Tools | What is measured |
|---|---|---|
| **Closed Book** | Forbidden | Pure unaided knowledge and technical skill |
| **AI Allowed** | Permitted | Human + AI collaboration quality — can you use AI effectively? |
| **AI Engineering** | Required | Prompt quality, output verification, hallucination detection, AI-native architecture and security |

### Scoring Dimensions (AI Engineering mode)

| Dimension | Description |
|---|---|
| Technical correctness | Is the final solution correct and well-structured? |
| Prompt quality | Were prompts specific, well-scoped, and contextually rich? |
| Hallucination catching | Did you identify and correct AI errors? |
| Output verification | Did you test or validate AI-generated output before submitting? |

### Tips for AI Engineering Mode

- **Verify every AI output** — the evaluator checks whether you tested or validated AI-generated code
- **Write specific prompts** — vague prompts score lower on prompt quality
- **Catch and correct errors** — intentional AI mistakes may be injected; spotting and fixing them boosts your score
- **Document your reasoning** — explain why you accepted or modified the AI suggestion

---

## 12. Frequently Asked Questions

**I accidentally closed the browser during an exam. Can I resume?**  
Yes — open the same exam link within 30 minutes and click **Resume Attempt**. Your answers are saved automatically. Resuming from a different device may trigger a review flag.

---

**My score seems incorrect. What can I do?**  
Contact `support@i3technologies.co.ke` with your attempt ID (visible on the results page). All graded attempts are stored and can be reviewed by the assessments team.

---

**My session was flagged for review. Does this mean I failed?**  
No. A flag means a human reviewer will look at your session. You are not penalized until a reviewer makes a decision. You will receive an email within 3 business days. You may also submit an appeal with any context you feel is relevant.

---

**How do I share my badge with an employer?**  
Go to your **Credentials** section, find the badge, and copy the Verify URL. You can also download the Open Badges 3.0 JSON-LD file for import into LinkedIn or badge wallet apps.

---

**What is the difference between a score of 68% and 70%?**  
The pass threshold varies by exam. IBM watsonx Orchestrate certification readiness exams pass at **68%**. Standard EvalOS assessments pass at **70%**. The threshold is always shown on the exam start page and in your results.

---

**I passed Set 6. What happens next?**  
Passing Set 6 automatically queues you for enrolment consideration in the associated programme. You will receive an email from the admissions team with next steps. Your results are also shared with the Admissions service via the assessment integration.

---

**Can I retake an exam I failed?**  
Yes, up to the attempt limit (default 5 per exam). Failed attempts are shown on your dashboard. The Study Coach report is available after every attempt to help you improve.

---

**What does the AI Engineering mode require?**  
You must use AI tools (such as the in-platform assistant) as part of your solution. The evaluator measures your ability to prompt effectively, verify AI outputs, and catch AI-generated errors — not just the final answer.

---

**Is my data private?**  
Yes. All assessment data is encrypted at rest and in transit. Your Skills Passport is private by default. Webcam or audio monitoring (Phase 2+) requires explicit consent before each session, with a defined retention window and appeals process, compliant with the Kenya Data Protection Act 2019.

---

*EvalOS User Guide · i3 Technologies Limited · ARCH-EVALOS-2026-V2*  
*Source: `Evalos-Modernisation/EvalOS_Technical_Implementation_Guide.md`*
