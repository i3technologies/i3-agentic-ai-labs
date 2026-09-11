-- Migration 004: Seed AI Interview questions from IBM C1000-207 exam domains
-- Apply: psql evalos_db < migrations/004_interview_questions_seed.sql
-- Prerequisite: 003_ai_features.sql must be applied first
-- Note: IDs are auto-generated UUIDs

INSERT INTO ai_interview_questions (text, type, language, rubric, time_limit, sort_order, is_active)
VALUES
(
  'Explain the difference between an IBM watsonx Orchestrate Skill and an Agent. When would you use one over the other? Provide a concrete real-world example for each.',
  'text',
  NULL,
  'Complete answer must cover:
- Skill: a single-purpose callable unit (API connector, automation, tool). Stateless. Used when wrapping a specific action.
- Agent: an AI-powered orchestrator that plans and invokes multiple skills to accomplish a multi-step goal. Has reasoning loop.
- Use skill when: you need a discrete, repeatable action (e.g. Create Salesforce Lead).
- Use agent when: you need multi-step planning (e.g. Onboard new customer = lookup CRM + create account + send welcome email).
- Concrete examples provided.',
  420,
  1,
  true
),
(
  'A customer wants to build an IBM watsonx Orchestrate automation that: (1) receives a Slack message, (2) extracts the customer name, (3) looks up the customer in Salesforce, (4) creates a support ticket in ServiceNow, and (5) replies in Slack. Describe the architecture you would build, naming the specific IBM watsonx Orchestrate components you would use at each step.',
  'text',
  NULL,
  'Complete answer covers:
- Trigger: Slack Skill (event trigger on incoming message)
- NLP/Extraction: LLM skill or built-in entity extraction to get customer name
- Salesforce lookup: Salesforce connector Skill (GET /contacts)
- ServiceNow ticket creation: ServiceNow connector Skill (POST /incident)
- Slack reply: Slack Skill (POST message)
- Orchestration: Agent or Automation Flow that sequences these skills
- Optional: error handling, conditional logic, variable passing between steps',
  480,
  2,
  true
),
(
  'What is the purpose of IBM watsonx Orchestrate''s "Automation Builder"? How does it differ from directly using the "Skills Catalog"? Describe the typical workflow for creating a new automation from scratch.',
  'text',
  NULL,
  'Complete answer:
- Skills Catalog: pre-built, ready-to-use skills from IBM and third parties. No code needed.
- Automation Builder: visual low-code tool for creating new custom automations/skills by defining triggers, actions, and decision logic.
- Automation Builder workflow: (1) Define trigger event, (2) Add action steps, (3) Configure variable passing, (4) Add decision points/conditions, (5) Test and publish.
- Difference: Catalog = consume existing skills; Builder = create new skills/automations.',
  360,
  3,
  true
),
(
  E'You are integrating a custom REST API into IBM watsonx Orchestrate. Write a JavaScript function that:\n1. Makes a GET request to https://api.example.com/customers?email={email}\n2. Returns only { id, name, plan } from the response\n3. Handles the case where the customer is not found (404) by returning null\n4. Handles network/other errors by throwing with a descriptive message\n\nUse async/await. Do not use axios — use native fetch.',
  'code',
  'javascript',
  'Correct solution must:
- Use async/await (not .then chains)
- Use fetch() correctly with the email query param
- Handle 404 return null explicitly
- Handle non-OK responses with a thrown error including status code
- Destructure/pick only { id, name, plan } from response JSON
- Handle fetch() network error (try/catch)
- Be syntactically valid JavaScript',
  600,
  4,
  true
),
(
  E'Write a Python function that parses an IBM watsonx Orchestrate webhook payload and extracts structured data.\n\nThe webhook payload looks like:\n{\n  "event": "automation.completed",\n  "timestamp": "2026-09-10T14:30:00Z",\n  "automation": { "id": "auto-123", "name": "Customer Onboarding" },\n  "outputs": { "customer_id": "cust-456", "ticket_id": "tick-789", "status": "success" },\n  "metadata": { "triggered_by": "user@example.com", "environment": "production" }\n}\n\nWrite a function parse_webhook(payload: dict) -> dict that:\n1. Validates the event type is "automation.completed"\n2. Returns { automation_id, automation_name, customer_id, ticket_id, status, triggered_by }\n3. Raises ValueError if event type is not "automation.completed"\n4. Raises KeyError with a clear message if any required field is missing',
  'code',
  'python',
  'Correct solution must:
- Define function with type hint (dict -> dict)
- Check event == "automation.completed", raise ValueError if not
- Extract all 6 required fields from nested structure
- Handle missing fields with descriptive KeyError messages
- Return flat dict with correct keys
- Be syntactically valid Python 3',
  600,
  5,
  true
);
