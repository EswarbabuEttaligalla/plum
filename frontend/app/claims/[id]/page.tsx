"use client"

import { useEffect, useState } from 'react'
import axios from 'axios'

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'

export default function ClaimDetails({ params }: { params: { id: string } }) {
  const id = params.id
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    axios.get(`${apiBase}/api/claims/${id}`)
      .then((response) => setData(response.data))
      .catch((err) => {
        const detail = err?.response?.data?.detail
        if (Array.isArray(detail)) {
          // convert pydantic validation errors to a readable string
          setError(detail.map((d:any) => d.msg || JSON.stringify(d)).join('; '))
        } else {
          setError(String(detail ?? err))
        }
      })
  }, [id])

  if (error) {
    return <main><p className="text-red-700">{error}</p></main>
  }

  if (!data) {
    return <main><p>Loading...</p></main>
  }

  return (
    <main>
      <h2 className="text-xl font-semibold mb-4">Claim {data.claim_code}</h2>
      <div className="bg-white p-4 rounded">
        <p><strong>Status:</strong> {data.status}</p>
        <p><strong>Confidence:</strong> {data.confidence}</p>
        <p><strong>Approved:</strong> {data.approved_amount}</p>
        <div className="mt-2">
          <strong>Reasons:</strong>
          <ul>
            {(data.decision_json?.reasons || []).map((r:any, i:number) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      </div>
    </main>
  )
}
