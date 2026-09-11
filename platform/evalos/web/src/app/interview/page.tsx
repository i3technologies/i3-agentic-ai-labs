import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import InterviewClient from './interview-client'

// IBM watsonx Orchestrate AI Interview — 5 questions (3 text + 2 code)
// Questions are stored in ai_interview_questions table or hardcoded below.
// This page loads the questions server-side and passes them to the client.

const STATIC_QUESTIONS = [
  {
    id: 'iq-001',
    text: 'Explain the difference between an IBM watsonx Orchestrate Skill and an Agent. When would you use one over the other? Provide a concrete real-world example for each.',
    type: 'text' as const,
    rubric: `A complete answer must cover:
- Skill: a single-purpose callable unit (API connector, automation, tool). Stateless. Used when wrapping a specific action.
- Agent: an AI-powered orchestrator that plans and invokes multiple skills to accomplish a multi-step goal. Has reasoning loop.
- Use skill when: you need a discrete, repeatable action (e.g., "Create Salesforce Lead").
- Use agent when: you need multi-step planning (e.g., "Onboard new customer" = lookup CRM + create account + send welcome email).
- Concrete examples provided.`,
    timeLimit: 420,  // 7 minutes
  },
  {
    id: 'iq-002',
    text: 'A customer wants to build an IBM watsonx Orchestrate automation that: (1) receives a Slack message, (2) extracts the customer name, (3) looks up the customer in Salesforce, (4) creates a support ticket in ServiceNow, and (5) replies in Slack. Describe the architecture you would build, naming the specific IBM watsonx Orchestrate components you would use at each step.',
    type: 'text' as const,
    rubric: `Complete answer covers:
- Trigger: Slack Skill (event trigger on incoming message)
- NLP/Extraction: LLM skill or built-in entity extraction to get customer name
- Salesforce lookup: Salesforce connector Skill (GET /contacts)
- ServiceNow ticket creation: ServiceNow connector Skill (POST /incident)
- Slack reply: Slack Skill (POST message)
- Orchestration: Agent or Automation Flow that sequences these skills
- Optional: error handling, conditional logic, variable passing between steps`,
    timeLimit: 480,  // 8 minutes
  },
  {
    id: 'iq-003',
    text: 'What is the purpose of IBM watsonx Orchestrate\'s "Automation Builder"? How does it differ from directly using the "Skills Catalog"? Describe the typical workflow for creating a new automation from scratch.',
    type: 'text' as const,
    rubric: `Complete answer:
- Skills Catalog: pre-built, ready-to-use skills from IBM and third parties. No code needed.
- Automation Builder: visual low-code tool for creating new custom automations/skills by defining triggers, actions, and decision logic.
- Automation Builder workflow: (1) Define trigger event, (2) Add action steps (pick skills), (3) Configure variable passing, (4) Add decision points/conditions, (5) Test & publish as a reusable skill.
- Difference: Catalog = consume existing skills; Builder = create new skills/automations.`,
    timeLimit: 360,
  },
  {
    id: 'iq-code-001',
    text: `You are integrating a custom REST API into IBM watsonx Orchestrate. Write a JavaScript function that:
1. Makes a GET request to https://api.example.com/customers?email={email}
2. Returns only { id, name, plan } from the response
3. Handles the case where the customer is not found (404) by returning null
4. Handles network/other errors by throwing with a descriptive message

Use async/await. Do not use axios — use native fetch.`,
    type: 'code' as const,
    language: 'javascript',
    rubric: `Correct solution must:
- Use async/await (not .then chains)
- Use fetch() correctly with the email query param
- Handle 404 → return null explicitly
- Handle non-OK responses with a thrown error including status code
- Destructure/pick only { id, name, plan } from response JSON
- Handle fetch() network error (try/catch)
- Be syntactically valid JavaScript`,
    timeLimit: 600,  // 10 minutes
  },
  {
    id: 'iq-code-002',
    text: `Write a Python function that parses an IBM watsonx Orchestrate webhook payload and extracts structured data.

The webhook payload looks like:
{
  "event": "automation.completed",
  "timestamp": "2026-09-10T14:30:00Z",
  "automation": { "id": "auto-123", "name": "Customer Onboarding" },
  "outputs": { "customer_id": "cust-456", "ticket_id": "tick-789", "status": "success" },
  "metadata": { "triggered_by": "user@example.com", "environment": "production" }
}

Write a function \`parse_webhook(payload: dict) -> dict\` that:
1. Validates the event type is "automation.completed"
2. Returns { automation_id, automation_name, customer_id, ticket_id, status, triggered_by }
3. Raises ValueError if event type is not "automation.completed"
4. Raises KeyError with a clear message if any required field is missing`,
    type: 'code' as const,
    language: 'python',
    rubric: `Correct solution must:
- Define function with type hint (dict -> dict)
- Check event == "automation.completed", raise ValueError if not
- Extract all 6 required fields from nested structure
- Handle missing fields with descriptive KeyError messages
- Return flat dict with correct keys: automation_id, automation_name, customer_id, ticket_id, status, triggered_by
- Be syntactically valid Python 3`,
    timeLimit: 600,
  },
]

export default async function InterviewPage() {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  // Load questions from DB if table exists, else use static set
  let questions = STATIC_QUESTIONS
  try {
    const { rows } = await pool.query(
      `SELECT id, text, type, language, rubric, time_limit AS "timeLimit"
       FROM ai_interview_questions
       WHERE is_active = true
       ORDER BY sort_order, id
       LIMIT 5`
    )
    if (rows.length > 0) {
      questions = rows
    }
  } catch {
    // Table may not exist yet — use static questions
  }

  const studentName = session.user.name || session.user.email || 'Student'

  // Get the most recent submitted exam attempt for this user (for examId)
  const { rows: attempts } = await pool.query(
    `SELECT qa.id FROM quiz_attempts qa
     WHERE qa.student_id = $1 AND qa.status = 'submitted'
     ORDER BY qa.submitted_at DESC LIMIT 1`,
    [session.user.userId || session.user.email]
  )
  const examId = attempts[0]?.id ?? 'standalone'

  return (
    <div>
      <div className="bg-blue-900 text-white py-6 px-4 mb-0">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-xl font-bold mb-1">AI Interview Round</h1>
          <p className="text-blue-200 text-sm">
            {questions.length} questions · Mix of technical explanation and code challenges ·
            Evaluated by AI in real-time · Pass threshold: 70%
          </p>
        </div>
      </div>
      <InterviewClient
        examId={examId}
        questions={questions}
        studentName={studentName}
      />
    </div>
  )
}
