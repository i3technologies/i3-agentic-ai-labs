import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import { authOptions } from '@/lib/auth'
import LabClient from './lab-client'

// IBM watsonx Orchestrate Coding Labs
// Labs can be loaded from DB (lab_exercises table) or from this static set.

const LABS = [
  {
    id: 'lab-js-001',
    title: 'Lab 1: Fetch & Transform API Data',
    language: 'javascript' as const,
    description: `Build a function that integrates with the IBM watsonx Orchestrate Skills API.

Task:
Write an async function \`getSkillSummary(baseUrl, apiKey)\` that:

1. Fetches the list of skills from \`GET {baseUrl}/v1/skills\`
   (use the apiKey as Bearer token)
2. Returns an array of simplified objects:
   { id, name, category, isPublished }
   (map from the raw skill objects which have: id, display_name, category, published_at)
3. Filters to only include published skills (published_at is not null)
4. Sorts by name ascending
5. Handles errors: throw Error with message "Skills fetch failed: {status}" on non-OK response

Test with:
getSkillSummary('https://api.example.com', 'test-key')
  .then(skills => console.log(skills.length + ' published skills'))`,
    starterCode: `async function getSkillSummary(baseUrl, apiKey) {
  // Your implementation here
}

// Test it
getSkillSummary('https://jsonplaceholder.typicode.com', 'test')
  .then(result => console.log('Result:', JSON.stringify(result, null, 2)))
  .catch(err => console.error('Error:', err.message))`,
    expectedOutput: `Skills fetched and transformed successfully.`,
    hints: [
      'Use fetch() with an Authorization: Bearer header',
      'Check response.ok before calling response.json()',
      'Use .filter(s => s.published_at !== null) to filter published skills',
      'Use .sort((a, b) => a.name.localeCompare(b.name)) to sort alphabetically',
      'Map raw fields: display_name → name, published_at !== null → isPublished',
    ],
  },
  {
    id: 'lab-py-001',
    title: 'Lab 2: Parse Orchestrate Webhook Events',
    language: 'python' as const,
    description: `Build a webhook event processor for IBM watsonx Orchestrate.

Task:
Write a Python class \`OrchestrateEventProcessor\` with:

1. Method \`process(event: dict) -> dict\` that:
   - Validates the event has required fields: event_type, timestamp, payload
   - Routes to the correct handler based on event_type
   - Returns a result dict with: processed, event_type, summary

2. Handler methods:
   - \`_handle_skill_invoked(payload)\` → summary: "Skill {skill_name} invoked by {user}"
   - \`_handle_automation_completed(payload)\` → summary: "Automation {name} completed with status {status}"
   - \`_handle_error(payload)\` → summary: "Error in {component}: {message}"
   - Default handler → summary: "Unknown event: {event_type}"

3. Raise \`ValueError\` if required fields are missing.

Test: process a skill_invoked event and print the result.`,
    starterCode: `class OrchestrateEventProcessor:
    def process(self, event: dict) -> dict:
        # Your implementation here
        pass
    
    def _handle_skill_invoked(self, payload: dict) -> str:
        pass
    
    def _handle_automation_completed(self, payload: dict) -> str:
        pass
    
    def _handle_error(self, payload: dict) -> str:
        pass

# Test it
processor = OrchestrateEventProcessor()
test_event = {
    "event_type": "skill_invoked",
    "timestamp": "2026-09-10T14:30:00Z",
    "payload": {
        "skill_name": "Create Salesforce Lead",
        "user": "alice@example.com"
    }
}
result = processor.process(test_event)
print(result)`,
    expectedOutput: `{'processed': True, 'event_type': 'skill_invoked', 'summary': 'Skill Create Salesforce Lead invoked by alice@example.com'}`,
    hints: [
      'Use a dictionary to map event_type strings to handler methods',
      'Check for required fields with: if field not in event: raise ValueError(...)',
      'Use .get() safely for payload fields with defaults',
      'Handler methods return a string — the process() method wraps it in the result dict',
    ],
  },
  {
    id: 'lab-sql-001',
    title: 'Lab 3: Analyse EvalOS Exam Performance',
    language: 'sql' as const,
    description: `Write SQL queries to analyse exam performance data from EvalOS.

The database has these tables:
  quiz_attempts(id, student_id, exam_id, pct_score, passed, submitted_at)
  exams(id, code, title)
  questions(id, set_number, domain_name, type)

Task: Write a single SQL query that returns:
  - exam_code
  - total_attempts
  - pass_rate (% of attempts that passed, rounded to 1 decimal)
  - avg_score (average pct_score, rounded to 1 decimal)
  - top_score (max pct_score)

Filter: Only include exams with at least 3 submitted attempts.
Sort: By pass_rate DESC, then avg_score DESC.`,
    starterCode: `-- Write your query here
SELECT
  e.code AS exam_code,
  -- your columns here
FROM quiz_attempts qa
JOIN exams e ON e.id = qa.exam_id
WHERE qa.status = 'submitted'
GROUP BY e.code
-- add HAVING and ORDER BY`,
    expectedOutput: `exam_code | total_attempts | pass_rate | avg_score | top_score
C1000-207 | 17             | 76.5      | 82.3      | 98.0`,
    hints: [
      'Use COUNT(*) for total_attempts',
      'ROUND(AVG(CASE WHEN passed THEN 100.0 ELSE 0 END), 1) gives pass_rate as a percentage',
      'Use ROUND(AVG(pct_score), 1) for avg_score',
      'HAVING COUNT(*) >= 3 filters for minimum attempts',
      'Boolean passed in PostgreSQL can be used directly in CASE WHEN passed THEN ...',
    ],
  },
]

interface LabPageProps {
  searchParams: { lab?: string }
}

export default async function LabPage({ searchParams }: LabPageProps) {
  const session = await getServerSession(authOptions)
  if (!session) redirect('/api/auth/signin')

  const labId = searchParams.lab
  const selectedLab = labId ? LABS.find(l => l.id === labId) : null

  if (selectedLab) {
    return <LabClient lab={selectedLab} />
  }

  // Lab index page
  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Coding Labs</h1>
        <p className="text-sm text-slate-500 mt-1">
          Practice IBM watsonx Orchestrate integration coding with AI-assisted review
        </p>
      </div>

      <div className="grid gap-4">
        {LABS.map(lab => (
          <div key={lab.id} className="bg-white border border-slate-200 rounded-xl p-5 hover:border-slate-300 transition-colors">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    lab.language === 'javascript' ? 'bg-yellow-100 text-yellow-800' :
                    lab.language === 'python' ? 'bg-blue-100 text-blue-800' :
                    'bg-orange-100 text-orange-800'
                  }`}>
                    {lab.language.toUpperCase()}
                  </span>
                </div>
                <h2 className="text-sm font-semibold text-slate-900 mb-1">{lab.title}</h2>
                <p className="text-xs text-slate-500 line-clamp-2">
                  {lab.description.split('\n')[0]}
                </p>
              </div>
              <Link
                href={`/lab?lab=${lab.id}`}
                className="ml-4 flex-shrink-0 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-lg transition-colors"
              >
                Open Lab →
              </Link>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 text-center">
        <Link href="/dashboard" className="text-sm text-slate-500 hover:text-slate-700 transition-colors">
          ← Back to Dashboard
        </Link>
      </div>
    </div>
  )
}
