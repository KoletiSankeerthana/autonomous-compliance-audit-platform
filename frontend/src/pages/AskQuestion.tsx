import { useState } from 'react'
import { documentsApi } from '../api/documents'
import type { QuestionResponse } from '../types/audit'
import { extractErrorMessage } from '../utils/errors'
export default function AskQuestionPage() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QuestionResponse | null>(null)
  const [error, setError] = useState('')

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await documentsApi.ask(question.trim())
      setResult(res)
    } catch (err: unknown) {
      setError(extractErrorMessage(err) ?? 'Failed to get answer.')
    } finally {
      setLoading(false)
    }
  }

  const EXAMPLE_QUESTIONS = [
    'What are the data retention requirements in the regulation?',
    'Does our policy address incident response procedures?',
    'What are the penalties for non-compliance?',
    'Is two-factor authentication required?',
  ]

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="page-heading">Ask Questions</h1>
        <p className="page-subheading mt-1">
          Ask natural language questions about your uploaded compliance documents.
        </p>
      </div>

      {/* Question form */}
      <form onSubmit={handleAsk} className="card p-5 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
            Your Question
          </label>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={3}
            className="input resize-none"
            placeholder="e.g. What are the data retention requirements?"
          />
        </div>
        <button type="submit" disabled={!question.trim() || loading} className="btn-primary">
          {loading ? 'Searching...' : 'Get Answer'}
        </button>
      </form>

      {/* Example questions */}
      <div>
        <p className="text-xs text-gray-500 mb-2">Example questions:</p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => setQuestion(q)}
              className="px-3 py-1.5 text-xs rounded-full bg-gray-100 dark:bg-gray-800
                         text-gray-700 dark:text-gray-300 hover:bg-brand-50 dark:hover:bg-brand-950/20
                         hover:text-brand-700 dark:hover:text-brand-400 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="px-4 py-3 rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Answer */}
      {result && (
        <div className="card p-5 space-y-4">
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">Question</p>
            <p className="text-sm font-medium text-gray-900 dark:text-white">{result.question}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">Answer</p>
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">
              {result.answer}
            </p>
          </div>
          {result.sources.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Sources</p>
              <div className="flex flex-wrap gap-2">
                {result.sources.map((s: Record<string, string>, i: number) => (
                  <span key={i} className="px-2.5 py-1 rounded-md bg-gray-100 dark:bg-gray-800 text-xs text-gray-600 dark:text-gray-400">
                    {s.filename ?? s.document_type ?? 'Document'}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
